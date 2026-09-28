from decimal import Decimal

from django.db.models import Sum, Q
from django.utils import timezone

from rest_framework import (
    viewsets,
    generics,
    filters,
    status,
)
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import (
    MultiPartParser,
    FormParser,
    JSONParser,
)
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from django_filters.rest_framework import (
    DjangoFilterBackend,
)

from user.permissions import IsHRAdmin,IsCompanyActive
from shared.pagination import CustomPagination
from .models import (
    Vendor,
    VendorBill,
    VendorPayment,
    VendorDocument,
)

from .serializers import (
    VendorSerializer,
    VendorCreateSerializer,
)

class VendorViewSet(viewsets.ModelViewSet):

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    pagination_class = CustomPagination

    parser_classes = [
        MultiPartParser,
        FormParser,
        JSONParser,
    ]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = [
        "client_status",
        "vendor_type",
        "payment_term",
        "currency",
    ]

    search_fields = [
        "vendor_id",
        "name",
        "cr_number",
        "vat_registration_number",
        "admin_email",
        "financial_email",
        "technical_email",
        "city",
        "country",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
        "vendor_id",
        "opening_balance",
        "credit_limit",
    ]

    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user

        if not getattr(user, "company", None):
            return Vendor.objects.none()

        return (
            Vendor.objects
            .filter(company=user.company)
            .select_related(
                "company",
                "created_by",
            )
            .prefetch_related("documents")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return VendorCreateSerializer

        return VendorSerializer

    def perform_create(self, serializer):
        user = self.request.user

        if not getattr(user, "company", None):
            from rest_framework.exceptions import (
                ValidationError,
            )

            raise ValidationError({
                "detail": (
                    "User is not associated "
                    "with a company."
                )
            })

        serializer.save(
            company=user.company,
            created_by=user,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)

        vendor = serializer.instance

        response_serializer = VendorSerializer(
            vendor,
            context=self.get_serializer_context(),
        )

        return Response(
            {
                "message": "Vendor created successfully.",
                "data": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset()
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True,
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = self.get_serializer(
            queryset,
            many=True,
        )

        return Response({
            "message": "Vendors fetched successfully.",
            "data": serializer.data,
        })

    @action(
        detail=True,
        methods=["post"],
        url_path="upload-documents",
        parser_classes=[
            MultiPartParser,
            FormParser,
        ],
    )
    def upload_documents(self, request, pk=None):
        vendor = self.get_object()

        documents = request.FILES.getlist(
            "documents"
        )

        if not documents:
            return Response(
                {
                    "message": (
                        "Please upload at least "
                        "one document."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        VendorDocument.objects.bulk_create([
            VendorDocument(
                vendor=vendor,
                document=document,
                document_name=document.name,
            )
            for document in documents
        ])

        return Response({
            "message": (
                "Vendor documents uploaded successfully."
            ),
            "data": VendorSerializer(
                vendor,
                context=self.get_serializer_context(),
            ).data,
        }, status=status.HTTP_201_CREATED)
    


class VendorDashboardView(generics.GenericAPIView):

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    def get(self, request, *args, **kwargs):
        company = getattr(
            request.user,
            "company",
            None,
        )

        if not company:
            return Response(
                {
                    "message": (
                        "User is not associated "
                        "with a company."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.localdate()

        month_start = today.replace(day=1)

        vendors = Vendor.objects.filter(
            company=company
        )

        bills = VendorBill.objects.filter(
            company=company,
            vendor__company=company,
        )

        payments = VendorPayment.objects.filter(
            company=company,
            vendor__company=company,
        )

        # Vendor counts
        total_vendor = vendors.count()

        active_vendor = vendors.filter(
            client_status="active"
        ).count()

        inactive_vendor = vendors.filter(
            client_status="inactive"
        ).count()

        # Payments completed this month
        total_payment_this_month = (
            payments.filter(
                status="completed",
                payment_date__gte=month_start,
                payment_date__lte=today,
            )
            .aggregate(
                total=Sum("amount_paid")
            )["total"]
            or Decimal("0.00")
        )

        # Outstanding bills
        total_bills = (
            bills.aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        # Opening balances
        total_opening_balance = (
            vendors.aggregate(
                total=Sum("opening_balance")
            )["total"]
            or Decimal("0.00")
        )

        # Completed payments, all time
        total_payments = (
            payments.filter(
                status="completed"
            )
            .aggregate(
                total=Sum("amount_paid")
            )["total"]
            or Decimal("0.00")
        )

        total_payable_outstanding = (
            total_opening_balance
            + total_bills
            - total_payments
        )

        total_payable_outstanding = max(
            total_payable_outstanding,
            Decimal("0.00"),
        )

        return Response({
            "message": (
                "Vendor dashboard fetched successfully."
            ),
            "data": {
                "total_vendor": total_vendor,
                "active_vendor": active_vendor,
                "inactive_vendor": inactive_vendor,
                "total_payment_this_month": (
                    total_payment_this_month
                ),
                "total_payable_outstanding": (
                    total_payable_outstanding
                ),
            },
        })