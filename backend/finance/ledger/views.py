from decimal import Decimal

from django.db.models import Sum

from django_filters.rest_framework import (
    DjangoFilterBackend,
)

from rest_framework import (
    status,
    viewsets,
)
from rest_framework.decorators import action
from rest_framework.filters import (
    OrderingFilter,
    SearchFilter,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from finance.customer.models import Customer

from user.permissions import (
    IsCompanyActive,
    IsHRAdmin,
)

from .models import CustomerLedger
from .serializers import (
    CustomerLedgerSerializer,
    CustomerLedgerSummarySerializer,
)


class CustomerLedgerViewSet(
    viewsets.ReadOnlyModelViewSet
):

    serializer_class = CustomerLedgerSerializer

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "customer",
        "transaction_type",
        "transaction_date",
    ]

    search_fields = [
        "reference_number",
        "description",
        "customer__customer_name",
        "customer__customer_id",
        "invoice__invoice_number",
        "payment__receipt_number",
    ]

    ordering_fields = [
        "transaction_date",
        "created_at",
        "debit",
        "credit",
        "balance",
    ]

    ordering = [
        "transaction_date",
        "id",
    ]

    def get_queryset(self):

        user = self.request.user

        if (
            not user.is_authenticated
            or not getattr(user, "company", None)
        ):
            return CustomerLedger.objects.none()

        queryset = (
            CustomerLedger.objects
            .filter(
                company=user.company,
            )
            .select_related(
                "company",
                "customer",
                "invoice",
                "payment",
                "created_by",
            )
        )

        customer_id = (
            self.request.query_params.get(
                "customer_id"
            )
        )

        from_date = (
            self.request.query_params.get(
                "from_date"
            )
        )

        to_date = (
            self.request.query_params.get(
                "to_date"
            )
        )

        transaction_type = (
            self.request.query_params.get(
                "transaction_type"
            )
        )

        if customer_id:

            queryset = queryset.filter(
                customer_id=customer_id,
            )

        if from_date:

            queryset = queryset.filter(
                transaction_date__gte=from_date,
            )

        if to_date:

            queryset = queryset.filter(
                transaction_date__lte=to_date,
            )

        if transaction_type:

            queryset = queryset.filter(
                transaction_type=transaction_type,
            )

        return queryset

    @action(
        detail=False,
        methods=["get"],
        url_path="customer/(?P<customer_id>[^/.]+)",
    )
    def customer_ledger(
        self,
        request,
        customer_id,
    ):

        user = request.user

        customer = (
            Customer.objects.filter(
                id=customer_id,
                company=user.company,
            )
            .first()
        )

        if not customer:

            return Response(
                {
                    "message": "Customer not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        queryset = self.filter_queryset(
            self.get_queryset().filter(
                customer=customer,
            )
        )

        page = self.paginate_queryset(queryset)

        if page is not None:

            serializer = self.get_serializer(
                page,
                many=True,
            )

            return self.get_paginated_response(
                serializer.data,
            )

        serializer = self.get_serializer(
            queryset,
            many=True,
        )

        return Response(
            {
                "message": (
                    "Customer ledger retrieved successfully."
                ),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="summary",
    )
    def summary(
        self,
        request,
    ):

        user = request.user

        customer_id = (
            request.query_params.get(
                "customer_id"
            )
        )

        if not customer_id:

            return Response(
                {
                    "message": (
                        "customer_id is required."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer = (
            Customer.objects.filter(
                id=customer_id,
                company=user.company,
            )
            .first()
        )

        if not customer:

            return Response(
                {
                    "message": "Customer not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        queryset = CustomerLedger.objects.filter(
            company=user.company,
            customer=customer,
        )

        total_debit = (
            queryset.aggregate(
                total=Sum("debit"),
            )["total"]
            or Decimal("0.00")
        )

        total_credit = (
            queryset.aggregate(
                total=Sum("credit"),
            )["total"]
            or Decimal("0.00")
        )

        closing_balance = (
            total_debit - total_credit
        )

        data = {
            "customer_id": customer.id,
            "customer_code": customer.customer_id,
            "customer_name": customer.customer_name,
            "opening_balance": (
                customer.opening_balance
                or Decimal("0.00")
            ),
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": closing_balance,
        }

        serializer = CustomerLedgerSummarySerializer(
            data
        )

        return Response(
            {
                "message": (
                    "Customer ledger summary retrieved successfully."
                ),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )