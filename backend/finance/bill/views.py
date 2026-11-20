from decimal import Decimal
from django.db.models import Sum, Q, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone

from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from .models import Bill
from .serializers import BillSerializer, BillListSerializer
from .filters import BillFilter
from shared.pagination import CustomPagination
from finance.vendorledger.services import sync_bill_ledger
from finance.vendorledger.services import (
    sync_bill_ledger,
    delete_bill_ledger,
)
from django.db import transaction
from finance.journal.models import JournalEntry
from finance.journal.journal_services.bill_journal import (
    create_bill_journal_entry,
)

from django.db import transaction
from rest_framework.exceptions import ValidationError



def get_user_company(user):
    return getattr(user, "company", None)


class BillKPICardView(APIView):
    """
    API view to retrieve KPI card metrics for Purchase Bills:
    - Total Bill Value (Sum of total_amount)
    - Total Payables (Sum of outstanding balance)
    - Total Debit Notes (Total debit notes value)
    - Overdue Payables (Sum of balance for overdue bills)
    - Total Bills (Count of total bills)
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Purchase Bill KPI Card Metrics",
        description="Returns KPI card statistics for purchase bills under the authenticated user's company.",
        responses={200: OpenApiResponse(description="Purchase Bill KPI Statistics")}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if getattr(user, "is_superadmin", False):
            company_id = request.query_params.get("company")
            if company_id:
                base_qs = Bill.objects.filter(company_id=company_id)
            else:
                base_qs = Bill.objects.all()
        elif hasattr(user, "company") and user.company:
            base_qs = Bill.objects.filter(company=user.company)
        else:
            base_qs = Bill.objects.none()

        vendor_param = request.query_params.get("vendor")
        if vendor_param:
            base_qs = base_qs.filter(vendor_id=vendor_param)

        today = timezone.now().date()

        # Expression for balance per bill
        balance_expr = ExpressionWrapper(
            F("total_amount") - F("amount_paid"),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        total_bill_value = base_qs.aggregate(
            total=Coalesce(Sum("total_amount"), Decimal("0.00"))
        )["total"]

        total_payables = base_qs.exclude(status="paid").annotate(
            rem_balance=balance_expr
        ).aggregate(
            total=Coalesce(Sum("rem_balance"), Decimal("0.00"))
        )["total"]

        overdue_payables = base_qs.filter(
            due_date__lt=today
        ).exclude(status="paid").annotate(
            rem_balance=balance_expr
        ).aggregate(
            total=Coalesce(Sum("rem_balance"), Decimal("0.00"))
        )["total"]

        total_bills = base_qs.count()

        # For total_debit_notes, check if debit notes exist in system, else default to 0.00
        total_debit_notes = Decimal("0.00")

        return Response({
            "total_bill_value": total_bill_value,
            "total_payables": total_payables,
            "total_debit_notes": total_debit_notes,
            "overdue_payables": overdue_payables,
            "total_bills": total_bills,
        }, status=status.HTTP_200_OK)


class BillListCreateView(generics.ListCreateAPIView):
    """
    API view to list purchase bills or create a new purchase bill for the authenticated user's company.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = BillFilter
    search_fields = [
        "bill_number",
        "po_reference",
        "vendor__name",
        "bill_to_name",
        "note",
        "due_date_note",
    ]
    ordering_fields = [
        "bill_number",
        "bill_date",
        "due_date",
        "total_amount",
        "amount_paid",
        "status",
        "created_at",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return BillListSerializer
        return BillSerializer

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                qs = Bill.objects.filter(company_id=company_id)
            else:
                qs = Bill.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = Bill.objects.filter(company=user.company)
        else:
            qs = Bill.objects.none()

        return qs.select_related("company", "vendor", "created_by").prefetch_related("items")

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)

        with transaction.atomic():
            bill = serializer.save(
                company=company,
                created_by=user,
            )

            # Preserve existing vendor ledger functionality.
            sync_bill_ledger(bill, created_by=user)

            # Handle a bill created directly with paid status as well.
            if bill.status == "paid":
                create_bill_journal_entry(
                    bill=bill,
                    created_by=user,
                )


    def perform_update(self, serializer):
        user = self.request.user

        # Capture the old status before saving.
        previous_status = serializer.instance.status

        with transaction.atomic():
            bill = serializer.save()

            # Preserve existing vendor ledger functionality.
            sync_bill_ledger(bill, created_by=user)

            # Create the journal only on a transition to paid.
            if previous_status != "paid" and bill.status == "paid":
                create_bill_journal_entry(
                    bill=bill,
                    created_by=user,
                )
    


    def perform_destroy(self, instance):
        with transaction.atomic():
            # Prevent deletion if the bill has a posted journal entry.
            has_posted_journal = JournalEntry.objects.filter(
                company=instance.company,
                source="auto",
                source_module="bill",
                source_id=str(instance.pk),
                status="posted",
            ).exists()

            if has_posted_journal:
                raise ValidationError({
                    "detail": (
                        "This bill has a posted journal entry and cannot be "
                        "deleted. Please reverse the journal entry first."
                    )
                })

            # Preserve existing vendor ledger functionality.
            delete_bill_ledger(instance)

            instance.delete()


    @extend_schema(
        summary="List Purchase Bills",
        description="Retrieves a paginated list of purchase bills for the authenticated company, along with KPI statistics.",
        responses={200: BillListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create New Purchase Bill",
        description="Creates a new purchase bill with line items under the user's company.",
        request=BillSerializer,
        responses={
            201: BillSerializer,
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

        today = timezone.now().date()
        balance_expr = ExpressionWrapper(
            F("total_amount") - F("amount_paid"),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        total_bill_value = base_qs.aggregate(
            total=Coalesce(Sum("total_amount"), Decimal("0.00"))
        )["total"]

        total_payables = base_qs.exclude(status="paid").annotate(
            rem_balance=balance_expr
        ).aggregate(
            total=Coalesce(Sum("rem_balance"), Decimal("0.00"))
        )["total"]

        overdue_payables = base_qs.filter(
            due_date__lt=today
        ).exclude(status="paid").annotate(
            rem_balance=balance_expr
        ).aggregate(
            total=Coalesce(Sum("rem_balance"), Decimal("0.00"))
        )["total"]

        total_bills = base_qs.count()
        total_debit_notes = Decimal("0.00")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_bill_value"] = total_bill_value
            response.data["total_payables"] = total_payables
            response.data["total_debit_notes"] = total_debit_notes
            response.data["overdue_payables"] = overdue_payables
            response.data["total_bills"] = total_bills
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_bill_value": total_bill_value,
            "total_payables": total_payables,
            "total_debit_notes": total_debit_notes,
            "overdue_payables": overdue_payables,
            "total_bills": total_bills,
        })


class BillDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a purchase bill by ID.
    """
    serializer_class = BillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            qs = Bill.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = Bill.objects.filter(company=user.company)
        else:
            qs = Bill.objects.none()

        return qs.select_related("company", "vendor", "created_by").prefetch_related("items")

    @extend_schema(
        summary="Get Purchase Bill Details",
        description="Retrieves detailed information of a specific purchase bill by ID.",
        responses={200: BillSerializer, 404: OpenApiResponse(description="Bill Not Found")}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Purchase Bill (Full)",
        description="Updates all fields of an existing purchase bill.",
        request=BillSerializer,
        responses={200: BillSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Bill Not Found")}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Purchase Bill (Partial)",
        description="Partially updates fields of an existing purchase bill.",
        request=BillSerializer,
        responses={200: BillSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Bill Not Found")}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Purchase Bill",
        description="Deletes a purchase bill by ID.",
        responses={204: OpenApiResponse(description="No Content"), 404: OpenApiResponse(description="Bill Not Found")}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    
    def perform_update(self, serializer):
        user = self.request.user

        with transaction.atomic():
            bill = serializer.save()

            # Sync vendor ledger
            sync_bill_ledger(bill, created_by=user)

            # Create journal entry when the bill is fully paid
            if bill.status == "paid":
                create_bill_journal_entry(
                    bill=bill,
                    created_by=user,
                )


class ApprovedPurchaseOrderReferenceListView(APIView):
    """
    API view to list Approved Purchase Orders for selection as Bill reference,
    or retrieve complete prefilled Bill data when po_id or po_number is provided.
    Only approved purchase orders are returned.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List Approved Purchase Orders for Bill Reference",
        description="Returns approved purchase orders for the user's company to use as reference in creating a Bill.",
        parameters=[
            OpenApiParameter("search", str, description="Search by PO number, vendor name, or PR reference"),
            OpenApiParameter("vendor", int, description="Filter by vendor ID"),
            OpenApiParameter("po_id", int, description="Retrieve full prefill data for this PO ID"),
            OpenApiParameter("po_number", str, description="Retrieve full prefill data for this PO Number"),
        ],
        responses={200: OpenApiResponse(description="Approved purchase orders or prefill details")}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        company = getattr(user, "company", None)

        from finance.purchaseorder.models import PurchaseOrder

        base_qs = PurchaseOrder.objects.filter(
            company=company,
            status__iexact="approved",
        ).select_related("vendor", "warehouse").prefetch_related("items__product")

        # If po_id or po_number is requested, return the detailed prefilled bill payload
        po_id = request.query_params.get("po_id")
        po_number = request.query_params.get("po_number")

        if po_id or po_number:
            po = None
            if po_id and str(po_id).isdigit():
                po = base_qs.filter(id=int(po_id)).first()
            if not po and po_number:
                po = base_qs.filter(po_number__iexact=str(po_number).strip()).first()

            if not po:
                return Response(
                    {"detail": "Approved purchase order not found for this company."},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(self._build_po_prefill_data(po, company), status=status.HTTP_200_OK)

        # Otherwise return list of approved purchase orders
        search = request.query_params.get("search")
        if search:
            base_qs = base_qs.filter(
                Q(po_number__icontains=search)
                | Q(vendor__name__icontains=search)
                | Q(pr_reference__icontains=search)
            )

        vendor_id = request.query_params.get("vendor")
        if vendor_id and str(vendor_id).isdigit():
            base_qs = base_qs.filter(vendor_id=int(vendor_id))

        results = []
        for po in base_qs.order_by("-order_date", "-id"):
            results.append({
                "id": po.id,
                "po_number": po.po_number,
                "vendor": po.vendor_id,
                "vendor_name": po.vendor.name if po.vendor else "",
                "order_date": po.order_date,
                "expected_delivery_date": po.expected_delivery_date,
                "payment_terms": po.payment_terms or "NET 10",
                "status": po.status,
                "subtotal": str(po.subtotal),
                "total_vat": str(po.total_vat),
                "discount": str(po.discount),
                "round_off": str(po.round_off),
                "total_amount": str(po.total_amount),
                "warehouse_name": po.warehouse.warehouse_name if po.warehouse else "",
                "items_count": po.items.count(),
            })

        return Response({
            "count": len(results),
            "results": results,
        }, status=status.HTTP_200_OK)

    @classmethod
    def _build_po_prefill_data(cls, po, company):
        vendor = po.vendor
        address_parts = [
            getattr(vendor, "billing_address", ""),
            getattr(vendor, "city", ""),
            getattr(vendor, "state", ""),
            getattr(vendor, "country", ""),
            getattr(vendor, "postal", ""),
        ] if vendor else []
        vendor_address = ", ".join([str(p).strip() for p in address_parts if p and str(p).strip()])

        items_data = []
        for idx, it in enumerate(po.items.all().select_related("product"), start=1):
            prod = it.product
            items_data.append({
                "id": it.id,
                "product": it.product_id,
                "product_name": prod.product_name if prod else (it.description or f"Item {idx}"),
                "particular": it.description or (prod.product_name if prod else f"Item {idx}"),
                "quantity": str(it.quantity),
                "qty": str(it.quantity),
                "hs_code": it.hs_code or (getattr(prod, "hsn_sac_code", "") if prod else ""),
                "rate": str(it.rate),
                "vat_percentage": str(it.vat_percentage),
                "vat": str(it.vat_percentage),
                "vat_sar": str(it.vat_amount),
                "amount": str(it.amount),
            })

        company_address = getattr(company, "address", "") or getattr(company, "registered_address", "")
        company_phone = getattr(company, "phone", "") or getattr(company, "contact_number", "") or getattr(company, "phno", "")

        return {
            "purchase_order_id": po.id,
            "po_reference": po.po_number,
            "po_number": po.po_number,
            "vendor": po.vendor_id,
            "vendor_name": vendor.name if vendor else "",
            # Bill To (Vendor Details)
            "bill_to_name": vendor.name if vendor else "",
            "bill_to_address": vendor_address,
            "bill_to_phone": getattr(vendor, "phno", "") or getattr(vendor, "mobile", ""),
            "bill_to_email": getattr(vendor, "admin_email", "") or getattr(vendor, "email", ""),
            "finance_contact_email": getattr(vendor, "financial_email", "") or getattr(vendor, "admin_email", ""),
            # From (Company Details)
            "from_name": getattr(company, "name", "Tungston Labs"),
            "from_address": company_address,
            "from_phone": company_phone,
            "from_email": getattr(company, "email", ""),
            # Terms & Dates
            "payment_terms": po.payment_terms or "NET 10",
            "bill_date": timezone.now().date().isoformat(),
            "due_date": po.expected_delivery_date.isoformat() if po.expected_delivery_date else None,
            "due_date_note": "",
            "note": f"Bill against Purchase Order {po.po_number}",
            # Totals
            "subtotal": str(po.subtotal),
            "total_vat": str(po.total_vat),
            "discount": str(po.discount),
            "round_off": str(po.round_off),
            "total_amount": str(po.total_amount),
            # Line Items
            "items": items_data,
        }


class ApprovedPurchaseOrderDetailView(APIView):
    """
    API view to retrieve the full prefill Bill data for a specific approved Purchase Order by ID.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Approved Purchase Order Prefill Data for Bill",
        description="Returns full prefilled bill metadata and items for a specific approved Purchase Order by ID.",
        responses={200: OpenApiResponse(description="Prefill Bill data from Approved PO")}
    )
    def get(self, request, po_id, *args, **kwargs):
        user = request.user
        company = getattr(user, "company", None)

        from finance.purchaseorder.models import PurchaseOrder

        po = PurchaseOrder.objects.filter(
            id=po_id,
            company=company,
            status__iexact="approved",
        ).select_related("vendor", "warehouse").prefetch_related("items__product").first()

        if not po:
            return Response(
                {"detail": "Approved purchase order not found for this company."},
                status=status.HTTP_404_NOT_FOUND
            )

        data = ApprovedPurchaseOrderReferenceListView._build_po_prefill_data(po, company)
        return Response(data, status=status.HTTP_200_OK)

