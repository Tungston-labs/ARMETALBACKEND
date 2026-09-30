import csv
from decimal import Decimal
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone

from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter, OpenApiTypes

from .models import DebitNote, DebitNoteItem
from .serializers import DebitNoteSerializer, DebitNoteListSerializer, DebitNoteKPISerializer
from .filters import DebitNoteFilter
from shared.pagination import CustomPagination


class DebitNoteKPICardView(APIView):
    """
    API view to retrieve KPI card metrics for Debit Notes:
    - Total Debit Notes
    - Debit Note Value
    - Open Debit Notes
    - Applied Debit Notes
    - Cancelled Debits
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Debit Note KPI Card Metrics",
        description="Returns KPI card statistics for debit notes under the authenticated user's company.",
        responses={200: OpenApiResponse(description="Debit Note KPI Statistics")}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if getattr(user, "is_superadmin", False):
            company_id = request.query_params.get("company")
            if company_id:
                base_qs = DebitNote.objects.filter(company_id=company_id)
            else:
                base_qs = DebitNote.objects.all()
        elif hasattr(user, "company") and user.company:
            base_qs = DebitNote.objects.filter(company=user.company)
        else:
            base_qs = DebitNote.objects.none()

        vendor_param = request.query_params.get("vendor")
        if vendor_param:
            base_qs = base_qs.filter(vendor_id=vendor_param)

        stats = base_qs.aggregate(
            debit_note_value=Coalesce(Sum("debit_amount"), Decimal("0.00")),
        )

        total_debit_notes = base_qs.count()
        open_debit_notes = base_qs.filter(status="open").count()
        applied_debit_notes = base_qs.filter(status__in=["closed", "partially_applied"]).count()
        cancelled_debits = base_qs.filter(status="cancelled").count()

        return Response({
            "total_debit_notes": total_debit_notes,
            "debit_note_value": stats["debit_note_value"],
            "open_debit_notes": open_debit_notes,
            "applied_debit_notes": applied_debit_notes,
            "cancelled_debits": cancelled_debits,
        })


class DebitNoteListCreateView(generics.ListCreateAPIView):
    """
    API view to list all debit notes or create a new debit note for the authenticated user's company.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DebitNoteFilter
    search_fields = [
        "dn_number",
        "bill_ref",
        "vendor__name",
        "bill_to_name",
        "reason",
        "notes",
    ]
    ordering_fields = [
        "dn_number",
        "bill_ref",
        "issue_date",
        "debit_amount",
        "applied_amount",
        "created_at",
        "status",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return DebitNoteListSerializer
        return DebitNoteSerializer

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                qs = DebitNote.objects.filter(company_id=company_id)
            else:
                qs = DebitNote.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = DebitNote.objects.filter(company=user.company)
        else:
            qs = DebitNote.objects.none()

        return qs.select_related("company", "vendor", "bill", "created_by").prefetch_related("items")

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    @extend_schema(
        summary="List Debit Notes",
        description="Retrieves a paginated list of debit notes for the authenticated company, along with KPI statistics.",
        responses={200: DebitNoteListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create New Debit Note",
        description="Creates a new debit note under the user's company.",
        request=DebitNoteSerializer,
        responses={
            201: DebitNoteSerializer,
            400: OpenApiResponse(description="Validation Error")
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        base_qs = self.get_queryset()

        vendor_param = request.query_params.get("vendor")
        if vendor_param:
            base_qs = base_qs.filter(vendor_id=vendor_param)

        stats = base_qs.aggregate(
            debit_note_value=Coalesce(Sum("debit_amount"), Decimal("0.00")),
        )
        total_debit_notes = base_qs.count()
        open_debit_notes = base_qs.filter(status="open").count()
        applied_debit_notes = base_qs.filter(status__in=["closed", "partially_applied"]).count()
        cancelled_debits = base_qs.filter(status="cancelled").count()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_debit_notes"] = total_debit_notes
            response.data["debit_note_value"] = stats["debit_note_value"]
            response.data["open_debit_notes"] = open_debit_notes
            response.data["applied_debit_notes"] = applied_debit_notes
            response.data["cancelled_debits"] = cancelled_debits
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_debit_notes": total_debit_notes,
            "debit_note_value": stats["debit_note_value"],
            "open_debit_notes": open_debit_notes,
            "applied_debit_notes": applied_debit_notes,
            "cancelled_debits": cancelled_debits,
        })


class DebitNoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a debit note by ID.
    """
    serializer_class = DebitNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            qs = DebitNote.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = DebitNote.objects.filter(company=user.company)
        else:
            qs = DebitNote.objects.none()

        return qs.select_related("company", "vendor", "bill", "created_by").prefetch_related("items")

    @extend_schema(
        summary="Get Debit Note Details",
        description="Retrieves detailed information of a specific debit note by ID.",
        responses={200: DebitNoteSerializer, 404: OpenApiResponse(description="Debit Note Not Found")}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Debit Note (Full)",
        description="Updates all fields of an existing debit note.",
        request=DebitNoteSerializer,
        responses={200: DebitNoteSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Debit Note Not Found")}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Debit Note (Partial)",
        description="Partially updates fields of an existing debit note.",
        request=DebitNoteSerializer,
        responses={200: DebitNoteSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Debit Note Not Found")}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Debit Note",
        description="Deletes a debit note by ID.",
        responses={204: OpenApiResponse(description="No Content"), 404: OpenApiResponse(description="Debit Note Not Found")}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class BillDebitNoteDetailsView(APIView):
    """
    API view to retrieve a Purchase Bill's items and already debited quantity breakdown
    for constructing a Debit Note.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Bill Debit Note Details",
        description="Retrieves bill header metadata, bill value, cumulative already debited amount, remaining balance, and item breakdown.",
        parameters=[
            OpenApiParameter("bill", int, description="Bill ID"),
            OpenApiParameter("bill_id", int, description="Alias for Bill ID"),
            OpenApiParameter("bill_number", str, description="Bill Number (e.g. BIL00001)"),
        ],
        responses={
            200: OpenApiResponse(description="Bill items and already debited details"),
            404: OpenApiResponse(description="Bill not found")
        }
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        company = getattr(user, "company", None)

        bill_id = request.query_params.get("bill") or request.query_params.get("bill_id")
        bill_number = request.query_params.get("bill_number")

        from finance.bill.models import Bill, BillItem

        bill_qs = Bill.objects.all()
        if hasattr(user, "company") and user.company:
            bill_qs = bill_qs.filter(company=company)

        bill = None
        if bill_id:
            bill = bill_qs.filter(id=bill_id).first()
        elif bill_number:
            bill = bill_qs.filter(bill_number__iexact=bill_number.strip()).first()

        if not bill:
            return Response(
                {"message": "Bill not found or does not belong to your company."},
                status=status.HTTP_404_NOT_FOUND
            )

        bill_value = bill.total_amount or Decimal("0.00")

        already_debited_amount = DebitNote.objects.filter(
            Q(bill=bill) | Q(bill_ref__iexact=bill.bill_number),
            company=company
        ).exclude(status="cancelled").aggregate(
            total=Coalesce(Sum("debit_amount"), Decimal("0.00"))
        )["total"]

        remaining_balance = bill_value - already_debited_amount
        if remaining_balance < Decimal("0.00"):
            remaining_balance = Decimal("0.00")

        items_data = []
        bill_items = BillItem.objects.filter(bill=bill).select_related("product")

        for b_item in bill_items:
            already_debited_qty = DebitNoteItem.objects.filter(
                Q(bill_item=b_item) | Q(debit_note__bill=bill, product=b_item.product),
                debit_note__company=company
            ).exclude(debit_note__status="cancelled").aggregate(
                total=Coalesce(Sum("quantity"), Decimal("0.00"))
            )["total"]

            billed_qty = b_item.quantity or Decimal("0.00")
            max_debitable_qty = billed_qty - already_debited_qty
            if max_debitable_qty < Decimal("0.00"):
                max_debitable_qty = Decimal("0.00")

            items_data.append({
                "bill_item_id": b_item.id,
                "product_id": b_item.product_id,
                "product_name": b_item.product.product_name if b_item.product else b_item.particular,
                "particular": b_item.particular,
                "billed_qty": billed_qty,
                "already_debited_qty": already_debited_qty,
                "max_debitable_qty": max_debitable_qty,
                "unit_price": b_item.rate or Decimal("0.00"),
                "vat_percentage": b_item.vat_percentage or Decimal("0.00"),
            })

        return Response({
            "message": "Bill details for debit note retrieved successfully.",
            "data": {
                "bill_id": bill.id,
                "bill_number": bill.bill_number,
                "vendor": bill.vendor_id,
                "vendor_name": bill.vendor.name if bill.vendor else bill.bill_to_name,
                "bill_date": bill.bill_date,
                "bill_value": bill_value,
                "already_debited_amount": already_debited_amount,
                "remaining_balance": remaining_balance,
                "items": items_data,
            }
        }, status=status.HTTP_200_OK)


class DebitNoteExportView(APIView):
    """
    API view to export debit notes in CSV format.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Export Debit Notes",
        description="Export debit note records in CSV format.",
        responses={200: OpenApiTypes.BINARY}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if hasattr(user, "company") and user.company:
            qs = DebitNote.objects.filter(company=user.company)
        else:
            qs = DebitNote.objects.none()

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="debit_notes_export.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Debit Note No",
            "Date",
            "Vendor",
            "Related Bill",
            "Reason",
            "Debit Note Value (SAR)",
            "Applied Amount (SAR)",
            "Balance (SAR)",
            "Status",
        ])

        for dn in qs.select_related("vendor", "bill"):
            writer.writerow([
                dn.dn_number,
                dn.issue_date,
                dn.vendor.name if dn.vendor else dn.bill_to_name,
                dn.bill.bill_number if dn.bill else dn.bill_ref,
                dn.get_reason_display(),
                dn.debit_amount,
                dn.applied_amount,
                dn.balance,
                dn.get_status_display(),
            ])

        return response
