import csv
from decimal import Decimal
from django.db import models
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from finance.invoice.models import Invoice
from user.permissions import IsCompanyActive, IsHRAdmin

from .filters import PaymentFilter
from .models import Payment
from .serializers import (
    PaymentKPISerializer,
    PaymentListSerializer,
    PaymentSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List Payments",
        description="Retrieve a paginated list of payments for the authenticated user's company with search and filter support.",
        responses={200: PaymentListSerializer(many=True)},
    ),
    create=extend_schema(
        summary="Record Payment",
        description="Record a new payment transaction. Links to customer and optional invoice, updating invoice paid status automatically.",
        request=PaymentSerializer,
        responses={201: PaymentSerializer},
    ),
    retrieve=extend_schema(
        summary="Retrieve Payment",
        description="Retrieve details of a specific payment by ID.",
        responses={200: PaymentSerializer},
    ),
    update=extend_schema(
        summary="Update Payment",
        description="Update payment record details.",
        request=PaymentSerializer,
        responses={200: PaymentSerializer},
    ),
    partial_update=extend_schema(
        summary="Partial Update Payment",
        description="Partially update payment record details.",
        request=PaymentSerializer,
        responses={200: PaymentSerializer},
    ),
    destroy=extend_schema(
        summary="Delete Payment",
        description="Delete a payment record and update linked invoice payment status.",
        responses={200: OpenApiTypes.OBJECT},
    ),
)
class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
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
    filterset_class = PaymentFilter
    search_fields = [
        "receipt_number",
        "customer__customer_name",
        "invoice__invoice_number",
        "reference_number",
    ]
    ordering_fields = [
        "created_at",
        "payment_date",
        "amount_received",
        "receipt_number",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not getattr(user, "company", None):
            return Payment.objects.none()

        return (
            Payment.objects.filter(company=user.company)
            .select_related("company", "customer", "invoice", "created_by")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        response_serializer = self.get_serializer(payment)
        return Response(
            {
                "message": "Payment recorded successfully.",
                "data": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = PaymentListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = PaymentListSerializer(queryset, many=True)
        return Response(
            {
                "message": "Payments retrieved successfully.",
                "data": serializer.data,
            }
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(
            {
                "message": "Payment retrieved successfully.",
                "data": serializer.data,
            }
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        response_serializer = self.get_serializer(payment)
        return Response(
            {
                "message": "Payment updated successfully.",
                "data": response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {
                "message": "Payment deleted successfully.",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Payment KPI Metrics",
        description="Retrieve financial summary KPIs including Total Collections, This Month Collections, Outstanding Receivables, Overdue Receivables, and Collection Rate.",
        responses={200: PaymentKPISerializer},
    )
    @action(detail=False, methods=["get"], url_path="kpi")
    def kpi(self, request):
        user = request.user
        company = user.company

        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        # 1. Total collections
        total_collections = (
            Payment.objects.filter(
                company=company,
                status="completed",
            ).aggregate(
                total=models.Sum("amount_received")
            )["total"]
            or Decimal("0.00")
        )

        # 2. This month collections
        this_month_collections = (
            Payment.objects.filter(
                company=company,
                status="completed",
                payment_date__gte=start_of_month,
            ).aggregate(
                total=models.Sum("amount_received")
            )["total"]
            or Decimal("0.00")
        )

        # 3. Outstanding receivables (total unpaid on non-paid invoices)
        invoices = Invoice.objects.filter(company=company)
        outstanding_receivables = Decimal("0.00")
        overdue_receivables = Decimal("0.00")

        for inv in invoices.exclude(payment_status="paid"):
            rem = inv.total_amount - inv.amount_paid
            if rem > Decimal("0.00"):
                outstanding_receivables += rem
                if inv.due_date and inv.due_date < today:
                    overdue_receivables += rem

        # 4. Collection rate percentage
        total_invoiced = total_collections + outstanding_receivables
        if total_invoiced > Decimal("0.00"):
            collection_rate = round(
                float((total_collections / total_invoiced) * Decimal("100")),
                2,
            )
        else:
            collection_rate = 0.0

        data = {
            "total_collections": total_collections,
            "this_month_collections": this_month_collections,
            "outstanding_receivables": outstanding_receivables,
            "overdue_receivables": overdue_receivables,
            "collection_rate": collection_rate,
        }

        serializer = PaymentKPISerializer(data)
        return Response(
            {
                "message": "Payment KPI metrics retrieved successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Export Payments",
        description="Export payment records in CSV format.",
        responses={200: OpenApiTypes.BINARY},
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="payments_export.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Receipt No",
            "Customer",
            "Invoice No",
            "Payment Date",
            "Payment Type",
            "Payment Method",
            "Amount Received (SAR)",
            "Reference Number",
            "Status",
            "Notes",
        ])

        for payment in queryset:
            writer.writerow([
                payment.receipt_number,
                payment.customer.customer_name if payment.customer else "",
                payment.invoice.invoice_number if payment.invoice else "",
                payment.payment_date,
                payment.get_payment_type_display(),
                payment.get_payment_method_display(),
                payment.amount_received,
                payment.reference_number,
                payment.get_status_display(),
                payment.notes,
            ])

        return response
