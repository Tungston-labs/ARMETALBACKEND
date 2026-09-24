from calendar import monthrange
from datetime import timedelta

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import (
    generics,
    status,
    viewsets,
)

from rest_framework.decorators import action

from rest_framework.filters import (
    SearchFilter,
    OrderingFilter,
)

from rest_framework.permissions import IsAuthenticated

from rest_framework.response import Response

from user.permissions import (
    IsCompanyActive,
    IsHRAdmin,
)

from .models import (
    RecurringService,
    RecurringPricingPlan,
    RecurringBilling,
    RecurringBillingOccurrence,
)

from .serializers import (
    RecurringServiceSerializer,
    RecurringBillingSerializer,
    RecurringBillingOccurrenceSerializer,
    RecurringPricingPlanSerializer,
    RecurringCreateSerializer,
)


# ==========================================================
# HELPER FUNCTION
# ==========================================================

def calculate_next_invoice_date(
    start_date,
    frequency,
):
    """
    Calculate the next invoice date
    based on recurrence frequency.
    """

    if not start_date:
        return None

    # ------------------------------------------------------
    # DAILY
    # ------------------------------------------------------

    if frequency == "daily":
        return start_date + timedelta(days=1)

    # ------------------------------------------------------
    # WEEKLY
    # ------------------------------------------------------

    if frequency == "weekly":
        return start_date + timedelta(weeks=1)

    # ------------------------------------------------------
    # MONTHLY / QUARTERLY
    # ------------------------------------------------------

    if frequency in [
        "monthly",
        "quarterly",
    ]:

        months_to_add = (
            1
            if frequency == "monthly"
            else 3
        )

        total_months = (
            start_date.year * 12
            + (start_date.month - 1)
            + months_to_add
        )

        year, month_index = divmod(
            total_months,
            12,
        )

        month = month_index + 1

        day = min(
            start_date.day,
            monthrange(
                year,
                month,
            )[1],
        )

        return start_date.replace(
            year=year,
            month=month,
            day=day,
        )

    # ------------------------------------------------------
    # YEARLY
    # ------------------------------------------------------

    if frequency == "yearly":

        try:
            return start_date.replace(
                year=start_date.year + 1
            )

        except ValueError:
            # February 29
            return start_date.replace(
                year=start_date.year + 1,
                month=2,
                day=28,
            )

    return None


# ==========================================================
# RECURRING SERVICE VIEWSET
# ==========================================================

class RecurringServiceViewSet(
    viewsets.ModelViewSet
):

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    serializer_class = (
        RecurringServiceSerializer
    )

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "status",
        "billing_type",
        "product",
        "category",
    ]

    search_fields = [
        "product_code",
        "product_service_name",
        "product__product_name",
        "product__code",
    ]

    ordering_fields = [
        "created_at",
        "product_service_name",
        "unit_price",
        "final_price",
    ]

    ordering = [
        "-created_at",
    ]

    # ======================================================
    # QUERYSET
    # ======================================================

    def get_queryset(self):

        user = self.request.user

        if (
            not user.is_authenticated
            or not getattr(
                user,
                "company",
                None,
            )
        ):
            return (
                RecurringService
                .objects
                .none()
            )

        return (
            RecurringService
            .objects
            .filter(
                company=user.company
            )
            .select_related(
                "product",
                "category",
                "created_by",
            )
            .prefetch_related(
                "pricing_plans"
            )
        )


# ==========================================================
# RECURRING BILLING VIEWSET
# ==========================================================

class RecurringBillingViewSet(
    viewsets.ModelViewSet
):

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    serializer_class = (
        RecurringBillingSerializer
    )

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "customer",
        "billing_cycle",
        "recurrence_status",
        "frequency",
        "recurring_service",
        "auto_renew",
    ]

    search_fields = [
        "contract_number",
        "customer__customer_name",
        "customer__customer_id",
        "recurring_service__product_service_name",
        "recurring_service__product_code",
    ]

    ordering_fields = [
        "contract_number",
        "start_date",
        "invoice_date",
        "next_invoice_date",
        "monthly_amount",
        "created_at",
    ]

    ordering = [
        "-created_at",
    ]

    # ======================================================
    # QUERYSET
    # ======================================================

    def get_queryset(self):

        user = self.request.user

        if (
            not user.is_authenticated
            or not getattr(
                user,
                "company",
                None,
            )
        ):
            return (
                RecurringBilling
                .objects
                .none()
            )

        queryset = (
            RecurringBilling
            .objects
            .filter(
                company=user.company
            )
            .select_related(
                "customer",
                "recurring_service",
                "created_by",
            )
        )

        # ==================================================
        # EXACT RENEWAL DATE
        # ==================================================

        renewal_date = (
            self.request.query_params.get(
                "renewal_date"
            )
        )

        if renewal_date:
            queryset = queryset.filter(
                next_invoice_date=renewal_date
            )

        # ==================================================
        # RENEWAL FROM
        # ==================================================

        renewal_from = (
            self.request.query_params.get(
                "renewal_from"
            )
        )

        if renewal_from:
            queryset = queryset.filter(
                next_invoice_date__gte=renewal_from
            )

        # ==================================================
        # RENEWAL TO
        # ==================================================

        renewal_to = (
            self.request.query_params.get(
                "renewal_to"
            )
        )

        if renewal_to:
            queryset = queryset.filter(
                next_invoice_date__lte=renewal_to
            )

        return queryset

    # ======================================================
    # CREATE
    # ======================================================

    @transaction.atomic
    def perform_create(
        self,
        serializer,
    ):

        user = self.request.user

        last_contract = (
            RecurringBilling
            .objects
            .filter(
                company=user.company,
                contract_number__startswith="REC",
            )
            .order_by("-id")
            .first()
        )

        last_number = 0

        if last_contract:

            try:
                last_number = int(
                    last_contract
                    .contract_number
                    .replace(
                        "REC",
                        "",
                    )
                )

            except (
                ValueError,
                AttributeError,
            ):
                last_number = 0

        contract_number = (
            f"REC{last_number + 1:05d}"
        )

        billing = serializer.save(
            company=user.company,
            created_by=user,
            contract_number=contract_number,
        )

        billing.invoice_date = (
            billing.start_date
        )

        billing.next_invoice_date = (
            calculate_next_invoice_date(
                billing.start_date,
                billing.frequency,
            )
        )

        service = (
            billing.recurring_service
        )

        billing.monthly_amount = (
            service.final_price
        )

        billing.save(
            update_fields=[
                "invoice_date",
                "next_invoice_date",
                "monthly_amount",
                "updated_at",
            ]
        )

    # ======================================================
    # CREATE RESPONSE
    # ======================================================

    def create(
        self,
        request,
        *args,
        **kwargs,
    ):

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        self.perform_create(
            serializer
        )

        return Response(
            {
                "message": (
                    "Recurring billing created "
                    "successfully."
                ),
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    # ======================================================
    # DASHBOARD
    # ======================================================

    @action(
        detail=False,
        methods=["get"],
        url_path="dashboard",
    )
    def dashboard(
        self,
        request,
    ):

        user = request.user

        queryset = self.get_queryset()

        today = timezone.localdate()

        # ==================================================
        # CURRENT MONTH
        # ==================================================

        month_start = today.replace(
            day=1
        )

        # ==================================================
        # ACTIVE SUBSCRIPTIONS
        # ==================================================

        active_subscriptions = (
            queryset
            .filter(
                recurrence_status="active"
            )
            .filter(
                Q(end_date__isnull=True)
                | Q(end_date__gte=today)
            )
        )

        total_active_subscription = (
            active_subscriptions.count()
        )

        # ==================================================
        # MONTHLY RENEWAL AMOUNT
        # ==================================================

        monthly_renewal_amount = (
            active_subscriptions
            .aggregate(
                total=Sum(
                    "monthly_amount"
                )
            )["total"]
            or 0
        )

        # ==================================================
        # UPCOMING RENEWALS
        # NEXT 30 DAYS
        # ==================================================

        upcoming_end = (
            today + timedelta(days=30)
        )

        upcoming_renewal = (
            active_subscriptions
            .filter(
                next_invoice_date__gte=today,
                next_invoice_date__lte=upcoming_end,
            )
            .count()
        )

        # ==================================================
        # AUTO-GENERATED INVOICE
        # THIS MONTH
        # ==================================================

        auto_generated_invoice = (
            RecurringBillingOccurrence
            .objects
            .filter(
                recurring_billing__company=user.company,
                generated_at__date__gte=month_start,
                generated_at__date__lte=today,
                status__in=[
                    "generated",
                    "sent",
                    "paid",
                ],
            )
            .count()
        )

        # ==================================================
        # EXPIRED CONTRACTS
        # ==================================================

        expired_contract = (
            queryset
            .filter(
                Q(
                    recurrence_status="expired"
                )
                |
                Q(
                    end_date__lt=today
                )
            )
            .distinct()
            .count()
        )

        # ==================================================
        # RESPONSE
        # ==================================================

        return Response(
            {
                "message": (
                    "Recurring billing dashboard "
                    "retrieved successfully."
                ),
                "data": {
                    "total_active_subscription": (
                        total_active_subscription
                    ),
                    "monthly_renewal_amount": (
                        monthly_renewal_amount
                    ),
                    "upcoming_renewal": (
                        upcoming_renewal
                    ),
                    "auto_generated_invoice": (
                        auto_generated_invoice
                    ),
                    "expired_contract": (
                        expired_contract
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )


# ==========================================================
# COMBINED RECURRING CREATE API
# ==========================================================

class RecurringCreateView(
    generics.CreateAPIView
):

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    serializer_class = (
        RecurringCreateSerializer
    )

    # ======================================================
    # CREATE EVERYTHING IN ONE TRANSACTION
    # ======================================================

    @transaction.atomic
    def create(
        self,
        request,
        *args,
        **kwargs,
    ):

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        validated_data = (
            serializer.validated_data
        )

        user = request.user
        company = user.company

        # ==================================================
        # SERVICE DATA
        # ==================================================

        service_data = (
            validated_data["service"]
        )

        pricing_plans = (
            validated_data.get(
                "pricing_plans",
                [],
            )
        )

        billing_data = (
            validated_data["billing"]
        )

        # ==================================================
        # CREATE RECURRING SERVICE
        # ==================================================

        service = (
            RecurringService
            .objects
            .create(
                company=company,
                created_by=user,
                **service_data,
            )
        )

        # ==================================================
        # CREATE PRICING PLANS
        # ==================================================

        created_plans = []

        for plan_data in pricing_plans:

            plan = (
                RecurringPricingPlan
                .objects
                .create(
                    recurring_service=service,
                    **plan_data,
                )
            )

            created_plans.append(plan)

        # ==================================================
        # GENERATE CONTRACT NUMBER
        # ==================================================

        last_contract = (
            RecurringBilling
            .objects
            .filter(
                company=company,
                contract_number__startswith="REC",
            )
            .order_by("-id")
            .first()
        )

        last_number = 0

        if last_contract:

            try:
                last_number = int(
                    last_contract
                    .contract_number
                    .replace(
                        "REC",
                        "",
                    )
                )

            except (
                ValueError,
                AttributeError,
            ):
                last_number = 0

        contract_number = (
            f"REC{last_number + 1:05d}"
        )

        # ==================================================
        # CREATE BILLING
        # ==================================================

        billing = (
            RecurringBilling
            .objects
            .create(
                company=company,
                created_by=user,
                recurring_service=service,
                contract_number=contract_number,
                **billing_data,
            )
        )

        # ==================================================
        # INVOICE DATE
        # ==================================================

        billing.invoice_date = (
            billing.start_date
        )

        # ==================================================
        # NEXT INVOICE DATE
        # ==================================================

        billing.next_invoice_date = (
            calculate_next_invoice_date(
                billing.start_date,
                billing.frequency,
            )
        )

        # ==================================================
        # MONTHLY AMOUNT
        # ==================================================

        billing.monthly_amount = (
            service.final_price
        )

        # ==================================================
        # SAVE BILLING
        # ==================================================

        billing.save(
            update_fields=[
                "invoice_date",
                "next_invoice_date",
                "monthly_amount",
                "updated_at",
            ]
        )

        # ==================================================
        # RESPONSE DATA
        # ==================================================

        service_response = (
            RecurringServiceSerializer(
                service,
                context={
                    "request": request,
                },
            ).data
        )

        pricing_response = (
            RecurringPricingPlanSerializer(
                created_plans,
                many=True,
            ).data
        )

        billing_response = (
            RecurringBillingSerializer(
                billing,
                context={
                    "request": request,
                },
            ).data
        )

        # ==================================================
        # FINAL RESPONSE
        # ==================================================

        return Response(
            {
                "message": (
                    "Recurring service, pricing "
                    "plans and billing created "
                    "successfully."
                ),
                "data": {
                    "service": service_response,
                    "pricing_plans": pricing_response,
                    "billing": billing_response,
                },
            },
            status=status.HTTP_201_CREATED,
        )
    

from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from user.permissions import IsCompanyActive, IsHRAdmin

from .models import (
    RecurringBilling,
    RecurringBillingOccurrence,
)

class RecurringSummaryView(generics.GenericAPIView):

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    def get(self, request, *args, **kwargs):

        user = request.user
        company = getattr(user, "company", None)

        if not company:
            return Response(
                {
                    "message": "User is not associated with a company.",
                    "data": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.localdate()

        # ==================================================
        # COMPANY-SCOPED BILLING
        # ==================================================

        billing_queryset = RecurringBilling.objects.filter(
            company=company
        )

        # ==================================================
        # ACTIVE SUBSCRIPTIONS
        # ==================================================

        active_subscriptions = billing_queryset.filter(
            recurrence_status="active"
        ).filter(
            Q(end_date__isnull=True) |
            Q(end_date__gte=today)
        )

        active_subscription_count = (
            active_subscriptions.count()
        )

        # ==================================================
        # TOTAL MONTHLY REVENUE AMOUNT
        # ==================================================

        total_monthly_revenue = (
            active_subscriptions.aggregate(
                total=Sum("monthly_amount")
            )["total"]
            or 0
        )

        # ==================================================
        # UPCOMING RENEWALS
        # NEXT 30 DAYS
        # ==================================================

        upcoming_renewal_end = (
            today + timedelta(days=30)
        )

        upcoming_renewal_count = (
            active_subscriptions.filter(
                next_invoice_date__gte=today,
                next_invoice_date__lte=upcoming_renewal_end,
            ).count()
        )

        # ==================================================
        # AUTO GENERATED INVOICES
        # CURRENT MONTH
        # ==================================================

        month_start = today.replace(day=1)

        auto_generated_invoice_count = (
            RecurringBillingOccurrence.objects.filter(
                recurring_billing__company=company,
                generated_at__date__gte=month_start,
                generated_at__date__lte=today,
                status__in=[
                    "generated",
                    "sent",
                    "paid",
                ],
            ).count()
        )

        # ==================================================
        # EXPIRED CONTRACTS
        # ==================================================

        expired_contract_count = (
            billing_queryset.filter(
                Q(recurrence_status="expired") |
                Q(end_date__lt=today)
            )
            .distinct()
            .count()
        )

        # ==================================================
        # RESPONSE
        # ==================================================

        return Response(
            {
                "message": (
                    "Recurring summary retrieved "
                    "successfully."
                ),
                "data": {
                    "active_subscription": (
                        active_subscription_count
                    ),
                    "total_monthly_revenue_amount": (
                        total_monthly_revenue
                    ),
                    "upcoming_renewal": (
                        upcoming_renewal_count
                    ),
                    "auto_generated_invoice_month": (
                        auto_generated_invoice_count
                    ),
                    "expired_contract_count": (
                        expired_contract_count
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )