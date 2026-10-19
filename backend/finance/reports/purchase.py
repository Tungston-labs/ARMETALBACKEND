
import calendar
import csv
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.bill.models import Bill, BillItem
from finance.vendor.models import VendorPayment
from finance.purchaseorder.models import PurchaseOrder

from user.permissions import IsCompanyActive, IsHRAdmin


ZERO = Decimal("0.00")

VALID_BILL_STATUSES = {
    "draft",
    "unpaid",
    "partially_paid",
    "paid",
    "overdue",
    "cancelled",
}

VALID_PO_STATUSES = {
    "draft",
    "pending",
    "approved",
    "ordered",
    "partially_received",
    "received",
    "cancelled",
}

VALID_PO_BILL_STATUSES = {
    "pending",
    "partially_billed",
    "billed",
}


class PurchaseReportPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class PurchaseReportView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    pagination_class = PurchaseReportPagination

    @staticmethod
    def money(value):
        """Convert a value to a safe Decimal."""
        if value is None:
            return ZERO
        return Decimal(str(value))

    @staticmethod
    def format_money(value):
        """Return monetary values as strings for consistent JSON output."""
        return str(Decimal(str(value or ZERO)).quantize(Decimal("0.01")))

    @staticmethod
    def parse_optional_id(value, field_name):
        if value in (None, ""):
            return None

        try:
            parsed = int(value)
            if parsed <= 0:
                raise ValueError
            return parsed
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name} must be a positive integer."
            )

    @staticmethod
    def parse_date_filter(value, field_name):
        if not value:
            return None

        parsed = parse_date(value)

        if parsed is None:
            raise ValueError(
                f"{field_name} must be a valid date in YYYY-MM-DD format."
            )

        return parsed

    @staticmethod
    def get_company_id(request):
        return getattr(request.user, "company_id", None)

    def get(self, request):
        company_id = self.get_company_id(request)

        if not company_id:
            return Response(
                {"detail": "The logged-in user is not associated with a company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date_from = self.parse_date_filter(
                request.query_params.get("date_from"),
                "date_from",
            )
            date_to = self.parse_date_filter(
                request.query_params.get("date_to"),
                "date_to",
            )

            vendor_id = self.parse_optional_id(
                request.query_params.get("vendor"),
                "vendor",
            )
            category_id = self.parse_optional_id(
                request.query_params.get("category"),
                "category",
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if date_from and date_to and date_from > date_to:
            return Response(
                {"detail": "date_from cannot be later than date_to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        po_status = request.query_params.get("po_status", "").strip()
        bill_status = request.query_params.get("bill_status", "").strip()
        payment_status = request.query_params.get(
            "payment_status", ""
        ).strip()

        if po_status and po_status not in VALID_PO_STATUSES:
            return Response(
                {
                    "detail": (
                        "Invalid po_status.",
                        {"allowed_values": sorted(VALID_PO_STATUSES)},
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if bill_status and bill_status not in VALID_PO_BILL_STATUSES:
            return Response(
                {
                    "detail": (
                        "Invalid bill_status.",
                        {"allowed_values": sorted(VALID_PO_BILL_STATUSES)},
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment_status and payment_status not in VALID_BILL_STATUSES:
            return Response(
                {
                    "detail": (
                        "Invalid payment_status.",
                        {"allowed_values": sorted(VALID_BILL_STATUSES)},
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------
        # 1. Purchase orders
        # --------------------------------------------------
        po_queryset = PurchaseOrder.objects.filter(
            company_id=company_id,
        ).select_related("vendor").prefetch_related(
            "items__product"
        )

        if date_from:
            po_queryset = po_queryset.filter(order_date__gte=date_from)

        if date_to:
            po_queryset = po_queryset.filter(order_date__lte=date_to)

        if vendor_id:
            po_queryset = po_queryset.filter(vendor_id=vendor_id)

        if category_id:
            po_queryset = po_queryset.filter(
                items__product__category_id=category_id
            ).distinct()

        if po_status:
            po_queryset = po_queryset.filter(status=po_status)

        if bill_status:
            po_queryset = po_queryset.filter(bill_status=bill_status)

        purchase_orders = list(
            po_queryset.order_by("-order_date", "-id")
        )

        # Map PO numbers to their matching purchase orders.
        # Bill.po_reference is a text field, not a ForeignKey.
        po_by_number = {
            po.po_number: po
            for po in purchase_orders
            if po.po_number
        }

        # --------------------------------------------------
        # 2. Vendor bills
        # --------------------------------------------------
        bill_queryset = Bill.objects.filter(
            company_id=company_id,
        ).select_related(
            "vendor"
        ).prefetch_related(
            "items__product"
        )

        # This is a financial report, so the date range applies
        # to bill_date for billed purchases and payables.
        if date_from:
            bill_queryset = bill_queryset.filter(
                bill_date__gte=date_from
            )

        if date_to:
            bill_queryset = bill_queryset.filter(
                bill_date__lte=date_to
            )

        if vendor_id:
            bill_queryset = bill_queryset.filter(
                vendor_id=vendor_id
            )

        if category_id:
            bill_queryset = bill_queryset.filter(
                items__product__category_id=category_id
            ).distinct()

        if payment_status:
            bill_queryset = bill_queryset.filter(
                status=payment_status
            )
        else:
            # Exclude draft/cancelled bills from the normal
            # purchase amount and payable calculations.
            bill_queryset = bill_queryset.exclude(
                status__in=["draft", "cancelled"]
            )

        # When filtering by PO status or PO bill status, only include
        # bills whose PO reference matches the selected PO records.
        if po_status or bill_status:
            allowed_po_numbers = list(
                po_queryset.exclude(po_number="").values_list(
                    "po_number", flat=True
                )
            )

            bill_queryset = bill_queryset.filter(
                po_reference__in=allowed_po_numbers
            )

        bills = list(
            bill_queryset.order_by("-bill_date", "-id")
        )

        bill_ids = [bill.id for bill in bills]

        # --------------------------------------------------
        # 3. Completed vendor payments
        # --------------------------------------------------
        payments_queryset = VendorPayment.objects.filter(
            company_id=company_id,
            status="completed",
            bill_id__in=bill_ids,
        )

        # Payment made is based on the payment date.
        if date_from:
            payments_queryset = payments_queryset.filter(
                payment_date__gte=date_from
            )

        if date_to:
            payments_queryset = payments_queryset.filter(
                payment_date__lte=date_to
            )

        if vendor_id:
            payments_queryset = payments_queryset.filter(
                vendor_id=vendor_id
            )

        payments_made = (
            payments_queryset.aggregate(
                total=Sum("amount_paid")
            )["total"]
            or ZERO
        )

        # --------------------------------------------------
        # 4. Build the report rows
        # --------------------------------------------------
        rows = []
        outstanding_payable = ZERO
        total_purchase_amount = ZERO
        matched_po_ids = set()

        for bill in bills:
            po = po_by_number.get(bill.po_reference)

            # A PO filter requires a matching PO.
            if (po_status or bill_status) and po is None:
                continue

            if po:
                matched_po_ids.add(po.id)

            # Include only the matching category's item descriptions
            # when a category filter is selected.
            bill_items = list(bill.items.all())

            if category_id:
                bill_items = [
                    item
                    for item in bill_items
                    if item.product_id
                    and item.product
                    and item.product.category_id == category_id
                ]

            item_names = [
                (
                    item.particular
                    or (
                        item.product.product_name
                        if item.product
                        else ""
                    )
                )
                for item in bill_items
            ]

            item_names = [name for name in item_names if name]

            purchase_value = self.money(bill.total_amount)
            amount_paid = self.money(bill.amount_paid)

            # Use the model's balance property.
            outstanding = self.money(bill.balance)

            total_purchase_amount += purchase_value
            outstanding_payable += outstanding

            rows.append({
                "bill_id": bill.id,
                "po_id": po.id if po else None,
                "po_number": (
                    po.po_number
                    if po
                    else (bill.po_reference or "—")
                ),
                "po_date": (
                    po.order_date.isoformat()
                    if po
                    else bill.bill_date.isoformat()
                ),
                "bill_number": bill.bill_number,
                "bill_date": bill.bill_date.isoformat(),
                "vendor_id": bill.vendor_id,
                "vendor_name": (
                    bill.vendor.name
                    if bill.vendor
                    else bill.bill_to_name or "—"
                ),
                "items": item_names,
                "purchase_value": self.format_money(
                    purchase_value
                ),
                "amount_paid": self.format_money(amount_paid),
                "outstanding_value": self.format_money(
                    outstanding
                ),
                "po_status": po.status if po else None,
                "bill_status": (
                    po.bill_status if po else None
                ),
                "payment_status": bill.status,
            })

        # --------------------------------------------------
        # 5. Summary
        # --------------------------------------------------
        total_purchase_count = len(matched_po_ids)

        summary = {
            "total_purchase_amount": self.format_money(
                total_purchase_amount
            ),
            "total_purchase_count": total_purchase_count,
            "payments_made": self.format_money(payments_made),
            "purchase_returns": self.format_money(ZERO),
            "purchase_returns_tracked": False,
            "outstanding_payable": self.format_money(
                outstanding_payable
            ),
        }

        # --------------------------------------------------
        # 6. Monthly chart
        # --------------------------------------------------
        current_year = timezone.localdate().year
        year_value = request.query_params.get(
            "chart_year",
            str(current_year),
        )
        try:
            chart_year = int(year_value)
            if chart_year < 1900 or chart_year > 9999:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"detail": "year must be a valid four-digit year."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chart_queryset = Bill.objects.filter(
            company_id=company_id,
            bill_date__year=chart_year,
        ).exclude(
            status__in=["draft", "cancelled"]
        )

        if vendor_id:
            chart_queryset = chart_queryset.filter(
                vendor_id=vendor_id
            )

        if category_id:
            chart_queryset = chart_queryset.filter(
                items__product__category_id=category_id
            ).distinct()

        if payment_status:
            chart_queryset = chart_queryset.filter(
                status=payment_status
            )

        monthly_totals = defaultdict(lambda: ZERO)

        for bill in chart_queryset.only(
            "id", "bill_date", "total_amount"
        ):
            monthly_totals[bill.bill_date.month] += self.money(
                bill.total_amount
            )

        chart = {
                calendar.month_name[month]: float(monthly_totals[month])
                for month in range(1, 13)
            }

        # --------------------------------------------------
        # 7. CSV export
        # --------------------------------------------------
        export_value = request.query_params.get(
            "export", ""
        ).lower()

        if export_value in {"1", "true", "csv", "excel"}:
            response = HttpResponse(
                content_type="text/csv; charset=utf-8"
            )
            response["Content-Disposition"] = (
                'attachment; filename="purchase_report.csv"'
            )

            writer = csv.writer(response)

            writer.writerow([
                "PO Number",
                "PO Date",
                "Bill Number",
                "Bill Date",
                "Vendor Name",
                "Items",
                "Purchase Value",
                "Amount Paid",
                "Outstanding Value",
                "PO Status",
                "Bill Status",
                "Payment Status",
            ])

            for row in rows:
                writer.writerow([
                    row["po_number"],
                    row["po_date"],
                    row["bill_number"],
                    row["bill_date"],
                    row["vendor_name"],
                    ", ".join(row["items"]),
                    row["purchase_value"],
                    row["amount_paid"],
                    row["outstanding_value"],
                    row["po_status"] or "",
                    row["bill_status"] or "",
                    row["payment_status"],
                ])

            return response

        # --------------------------------------------------
        # 8. Pagination
        # --------------------------------------------------
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(rows, request, view=self)

        return paginator.get_paginated_response({
            "summary": summary,
            "chart": chart,
            "results": page,
        })