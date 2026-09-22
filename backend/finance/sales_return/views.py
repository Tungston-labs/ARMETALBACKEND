import csv
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Q, Count
from django.db.models.functions import Coalesce
from django.http import HttpResponse
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

from user.permissions import IsCompanyActive
from shared.pagination import CustomPagination

from finance.invoice.models import Invoice, InvoiceItem
from .filters import SalesReturnFilter
from .models import SalesReturn, SalesReturnItem
from .serializers import (
    SalesReturnSerializer,
    SalesReturnListSerializer,
    SalesReturnKPISerializer,
    SalesReturnInvoiceDropdownSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List Sales Returns",
        description="Retrieve a paginated list of sales returns for the user's company with search, date range, and filter support.",
        responses={200: SalesReturnListSerializer(many=True)},
    ),
    create=extend_schema(
        summary="Create Sales Return",
        description="Create a new sales return record with nested line items and automated prefill validation.",
        request=SalesReturnSerializer,
        responses={201: SalesReturnSerializer},
    ),
    retrieve=extend_schema(
        summary="Retrieve Sales Return",
        description="Retrieve details of a specific sales return by ID.",
        responses={200: SalesReturnSerializer},
    ),
    update=extend_schema(
        summary="Update Sales Return (Full)",
        description="Update all fields of a sales return record.",
        request=SalesReturnSerializer,
        responses={200: SalesReturnSerializer},
    ),
    partial_update=extend_schema(
        summary="Partial Update Sales Return",
        description="Partially update fields of a sales return record.",
        request=SalesReturnSerializer,
        responses={200: SalesReturnSerializer},
    ),
    destroy=extend_schema(
        summary="Delete Sales Return",
        description="Delete a sales return record.",
        responses={200: OpenApiTypes.OBJECT},
    ),
)
class SalesReturnViewSet(viewsets.ModelViewSet):
    serializer_class = SalesReturnSerializer
    permission_classes = [IsAuthenticated, IsCompanyActive]
    pagination_class = CustomPagination

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]
    filterset_class = SalesReturnFilter
    search_fields = [
        "return_number",
        "invoice_ref",
        "customer__customer_name",
        "customer_name",
        "reason",
        "notes",
    ]
    ordering_fields = [
        "created_at",
        "return_date",
        "return_number",
        "return_value",
        "status",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                qs = SalesReturn.objects.filter(company_id=company_id)
            else:
                qs = SalesReturn.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = SalesReturn.objects.filter(company=user.company)
        else:
            qs = SalesReturn.objects.none()

        return (
            qs.select_related("company", "customer", "invoice", "created_by")
            .prefetch_related("items")
        )

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        base_qs = self.get_queryset()

        stats = base_qs.aggregate(
            total_returns_count=Count("id"),
            total_return_val=Coalesce(Sum("return_value"), Decimal("0.00")),
            total_refunded=Coalesce(Sum("refunded_amount"), Decimal("0.00")),
            total_applied_credits=Coalesce(Sum("applied_credits"), Decimal("0.00")),
            total_cancelled=Count("id", filter=Q(status="cancelled")),
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SalesReturnListSerializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_returns"] = stats["total_returns_count"]
            response.data["total_return_value"] = stats["total_return_val"]
            response.data["refunded_amount"] = stats["total_refunded"]
            response.data["applied_credits"] = stats["total_applied_credits"]
            response.data["cancelled_credits"] = stats["total_cancelled"]
            return response

        serializer = SalesReturnListSerializer(queryset, many=True)
        return Response(
            {
                "results": serializer.data,
                "total_returns": stats["total_returns_count"],
                "total_return_value": stats["total_return_val"],
                "refunded_amount": stats["total_refunded"],
                "applied_credits": stats["total_applied_credits"],
                "cancelled_credits": stats["total_cancelled"],
            }
        )

    @extend_schema(
        summary="Sales Return KPI Card Metrics",
        description="Retrieve KPI metrics (Total Returns, Return Value, Refunded Amount, Applied Credits, Cancelled Credits).",
        responses={200: SalesReturnKPISerializer},
    )
    @action(detail=False, methods=["get"], url_path="kpi")
    def kpi(self, request):
        base_qs = self.get_queryset()
        stats = base_qs.aggregate(
            total_returns_count=Count("id"),
            total_return_val=Coalesce(Sum("return_value"), Decimal("0.00")),
            total_refunded=Coalesce(Sum("refunded_amount"), Decimal("0.00")),
            total_applied_credits=Coalesce(Sum("applied_credits"), Decimal("0.00")),
            total_cancelled=Count("id", filter=Q(status="cancelled")),
        )

        data = {
            "total_returns": stats["total_returns_count"],
            "total_return_value": stats["total_return_val"],
            "refunded_amount": stats["total_refunded"],
            "applied_credits": stats["total_applied_credits"],
            "cancelled_credits": stats["total_cancelled"],
        }
        return Response({"message": "KPI metrics retrieved successfully.", "data": data})

    @extend_schema(
        summary="Export Sales Returns",
        description="Export sales return records in CSV format.",
        responses={200: OpenApiTypes.BINARY},
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="sales_returns_export.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Return No",
            "Customer",
            "Invoice Ref",
            "Return Date",
            "Return Value (SAR)",
            "Items Returned",
            "Reason",
            "Status",
            "Refunded Amount (SAR)",
            "Applied Credits (SAR)",
            "Notes",
        ])

        for sr in queryset:
            writer.writerow([
                sr.return_number,
                sr.customer_name or (sr.customer.customer_name if sr.customer else ""),
                sr.invoice_ref,
                sr.return_date,
                sr.return_value,
                sr.items_returned,
                sr.get_reason_display(),
                sr.get_status_display(),
                sr.refunded_amount,
                sr.applied_credits,
                sr.notes,
            ])

        return response

    @extend_schema(
        summary="List Eligible Invoices for Return",
        description="Retrieve invoices available for creating sales returns.",
        responses={200: SalesReturnInvoiceDropdownSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="invoices")
    def invoices(self, request):
        user = request.user
        company = getattr(user, "company", None)
        if not company and not getattr(user, "is_superadmin", False):
            return Response([])

        if getattr(user, "is_superadmin", False):
            invoices_qs = Invoice.objects.all()
        else:
            invoices_qs = Invoice.objects.filter(company=company)

        serializer = SalesReturnInvoiceDropdownSerializer(invoices_qs, many=True)
        return Response({"message": "Invoices retrieved successfully.", "data": serializer.data})

    @extend_schema(
        summary="Get Invoice Detail for Return Prefill",
        description="Retrieve invoice detail with calculated eligible item quantities for creating a sales return.",
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(detail=False, methods=["get"], url_path=r"invoices/(?P<invoice_id>\d+)")
    def invoice_detail_for_return(self, request, invoice_id=None):
        user = request.user
        company = getattr(user, "company", None)

        try:
            if getattr(user, "is_superadmin", False):
                invoice = Invoice.objects.get(id=invoice_id)
            else:
                invoice = Invoice.objects.get(id=invoice_id, company=company)
        except Invoice.DoesNotExist:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)

        # Sum previous returns
        prev_returns_sum = SalesReturn.objects.filter(
            invoice=invoice
        ).exclude(status="cancelled").aggregate(
            total=Sum("return_value")
        )["total"] or Decimal("0.00")

        items_data = []
        for inv_item in invoice.items.select_related("product").all():
            # calculate already returned qty for this specific line item
            prev_item_returned_qty = SalesReturnItem.objects.filter(
                sales_return__invoice=invoice,
                invoice_item=inv_item
            ).exclude(sales_return__status="cancelled").aggregate(
                total=Sum("returning_now_qty")
            )["total"] or Decimal("0.00")

            items_data.append({
                "invoice_item": inv_item.id,
                "product": inv_item.product.id if inv_item.product else None,
                "product_name": inv_item.product.product_name if inv_item.product else inv_item.particular,
                "invoiced_qty": inv_item.quantity,
                "already_returned_qty": prev_item_returned_qty,
                "returning_now_qty": max(inv_item.quantity - prev_item_returned_qty, Decimal("0.00")),
                "condition": "Wrong Item",
                "unit_price": inv_item.rate,
                "vat_percentage": inv_item.vat_percentage,
                "return_value": (max(inv_item.quantity - prev_item_returned_qty, Decimal("0.00"))) * inv_item.rate,
            })

        data = {
            "invoice": invoice.id,
            "invoice_ref": invoice.invoice_number,
            "customer": invoice.customer.id,
            "customer_name": invoice.customer_name or invoice.customer.customer_name,
            "customer_address": invoice.customer_address,
            "customer_phone": invoice.customer_phone,
            "finance_contact_email": invoice.customer_email,
            "invoice_value": invoice.total_amount,
            "already_returned": prev_returns_sum,
            "eligible_to_return": max(invoice.total_amount - prev_returns_sum, Decimal("0.00")),
            "items": items_data,
        }

        return Response({"message": "Invoice details for return retrieved successfully.", "data": data})
