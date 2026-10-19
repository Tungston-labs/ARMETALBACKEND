
# reports/vendor.py

import calendar
from collections import defaultdict
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Sum
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.vendor.models import Vendor, VendorPayment
from finance.bill.models import Bill
from finance.purchaseorder.models import PurchaseOrder
from user.permissions import IsCompanyActive, IsHRAdmin


ZERO = Decimal("0.00")


def get_field_name(model, *candidates):
    """
    Return the first field that actually exists on a model.
    This accommodates small differences in Vendor model field names.
    """
    available = {field.name for field in model._meta.get_fields()}

    for candidate in candidates:
        if candidate in available:
            return candidate

    return None


def decimal_value(value):
    return value if value is not None else ZERO


def get_bill_balance(bill):
    """
    Calculate outstanding balance without allowing negative values.
    """
    total = decimal_value(bill.total_amount)
    paid = decimal_value(bill.amount_paid)
    return max(total - paid, ZERO)


def get_bill_payment_status(bill, today=None):
    """
    Derive payment status consistently from bill amounts and due date.
    """
    today = today or timezone.localdate()
    balance = get_bill_balance(bill)

    if balance <= ZERO:
        return "paid"

    if bill.due_date and bill.due_date < today:
        return "overdue"

    if decimal_value(bill.amount_paid) > ZERO:
        return "partially_paid"

    return "unpaid"


class VendorReportPagination:
    """Simple pagination settings for the vendor report."""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class VendorReportView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    def get(self, request):
        company_id = getattr(request.user, "company_id", None)

        if not company_id:
            return Response(
                {"detail": "Your account is not associated with a company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.localdate()

        # ---------------------------------------------------------
        # 1. Detect optional Vendor model field names
        # ---------------------------------------------------------
        vendor_name_field = get_field_name(
            Vendor, "name", "vendor_name"
        )
        vendor_code_field = get_field_name(
            Vendor, "vendor_id", "code"
        )
        payment_term_field = get_field_name(
            Vendor, "payment_term", "payment_terms"
        )
        active_field = get_field_name(
            Vendor, "is_active", "active", "status"
        )

        if not vendor_name_field:
            return Response(
                {
                    "detail": (
                        "Could not identify the vendor name field. "
                        "Check your Vendor model."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ---------------------------------------------------------
        # 2. Read filters
        # ---------------------------------------------------------
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        vendor_filter = request.query_params.get("vendor")
        payment_term_filter = request.query_params.get("payment_term")
        payment_status_filter = request.query_params.get(
            "payment_status"
        )

        current_year = today.year
        chart_year_value = request.query_params.get(
            "chart_year", str(current_year)
        )
        graph_year_value = request.query_params.get(
            "graph_year", str(current_year)
        )
        graph_month_value = request.query_params.get("graph_month")

        try:
            chart_year = int(chart_year_value)
            graph_year = int(graph_year_value)

            if graph_month_value:
                graph_month = int(graph_month_value)
                if graph_month < 1 or graph_month > 12:
                    raise ValueError("Month must be between 1 and 12.")
            else:
                graph_month = None

        except (TypeError, ValueError):
            return Response(
                {
                    "detail": (
                        "chart_year and graph_year must be valid years; "
                        "graph_month must be between 1 and 12."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_payment_statuses = {
            "paid",
            "partially_paid",
            "unpaid",
            "overdue",
        }

        if (
            payment_status_filter
            and payment_status_filter not in valid_payment_statuses
        ):
            return Response(
                {
                    "detail": (
                        "Invalid payment_status. Use paid, "
                        "partially_paid, unpaid, or overdue."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 3. Base company-scoped querysets
        # ---------------------------------------------------------
        vendors = Vendor.objects.filter(company_id=company_id)

        bills = Bill.objects.filter(company_id=company_id).exclude(
            status__in=["draft", "cancelled"]
        )

        payments = VendorPayment.objects.filter(
            company_id=company_id
        ).exclude(status="cancelled")

        purchase_orders = PurchaseOrder.objects.filter(
            company_id=company_id
        ).exclude(status="cancelled")

        # ---------------------------------------------------------
        # 4. Apply vendor and payment-term filters
        # ---------------------------------------------------------
        if vendor_filter:
            try:
                vendor_id = int(vendor_filter)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "vendor must be a valid vendor ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            vendors = vendors.filter(pk=vendor_id)
            bills = bills.filter(vendor_id=vendor_id)
            payments = payments.filter(vendor_id=vendor_id)
            purchase_orders = purchase_orders.filter(
                vendor_id=vendor_id
            )

        if payment_term_filter:
            if not payment_term_field:
                return Response(
                    {
                        "detail": (
                            "Your Vendor model does not have a "
                            "recognized payment term field."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            vendors = vendors.filter(
                **{payment_term_field: payment_term_filter}
            )
            bills = bills.filter(
                vendor_id__in=vendors.values_list("pk", flat=True)
            )
            payments = payments.filter(
                vendor_id__in=vendors.values_list("pk", flat=True)
            )
            purchase_orders = purchase_orders.filter(
                vendor_id__in=vendors.values_list("pk", flat=True)
            )

        vendor_ids = list(vendors.values_list("pk", flat=True))

        bills = bills.filter(vendor_id__in=vendor_ids)
        payments = payments.filter(vendor_id__in=vendor_ids)
        purchase_orders = purchase_orders.filter(
            vendor_id__in=vendor_ids
        )

        # ---------------------------------------------------------
        # 5. Apply report date range
        #    Bill/purchase values use bill_date.
        #    Payments received use payment_date.
        # ---------------------------------------------------------
        if date_from:
            bills = bills.filter(bill_date__gte=date_from)
            payments = payments.filter(payment_date__gte=date_from)

        if date_to:
            bills = bills.filter(bill_date__lte=date_to)
            payments = payments.filter(payment_date__lte=date_to)

        # Payment status filtering is based on bill payment status.
        filtered_bill_list = list(
            bills.select_related("vendor").order_by("-bill_date", "-id")
        )

        if payment_status_filter:
            filtered_bill_list = [
                bill
                for bill in filtered_bill_list
                if get_bill_payment_status(bill, today)
                == payment_status_filter
            ]

        filtered_bill_ids = [bill.id for bill in filtered_bill_list]

        # When filtering by payment status, show only payments linked
        # to matching bills. Payments without a bill are excluded from
        # the filtered table/KPI total in this case.
        if payment_status_filter:
            payments = payments.filter(bill_id__in=filtered_bill_ids)

        payment_total = decimal_value(
            payments.filter(status="completed").aggregate(
                total=Sum("amount_paid")
            )["total"]
        )

        # ---------------------------------------------------------
        # 6. KPI cards
        # ---------------------------------------------------------
        total_vendors = vendors.count()
        total_bills = len(filtered_bill_list)

        outstanding_payables = sum(
            (get_bill_balance(bill) for bill in filtered_bill_list),
            ZERO,
        )

        kpis = {
            "total_vendors": total_vendors,
            "total_bills": total_bills,
            "total_payments": float(payment_total),
            "outstanding_payables": float(outstanding_payables),
        }

        # ---------------------------------------------------------
        # 7. Build vendor table rows
        # ---------------------------------------------------------
        vendor_map = {
            vendor.pk: vendor
            for vendor in vendors.order_by(vendor_name_field)
        }

        bills_by_vendor = defaultdict(list)
        for bill in filtered_bill_list:
            if bill.vendor_id:
                bills_by_vendor[bill.vendor_id].append(bill)

        payments_by_vendor = defaultdict(Decimal)
        completed_payments = payments.filter(
            status="completed"
        ).values("vendor_id").annotate(
            total=Sum("amount_paid")
        )

        for payment in completed_payments:
            payments_by_vendor[payment["vendor_id"]] = decimal_value(
                payment["total"]
            )

        pos_by_vendor = defaultdict(list)
        for po in purchase_orders.order_by("-order_date"):
            if po.vendor_id:
                po_number = getattr(po, "po_number", None)
                if po_number and po_number not in pos_by_vendor[po.vendor_id]:
                    pos_by_vendor[po.vendor_id].append(po_number)

        table_rows = []

        for vendor_id, vendor in vendor_map.items():
            vendor_bills = bills_by_vendor.get(vendor_id, [])

            purchase_value = sum(
                (
                    decimal_value(bill.total_amount)
                    for bill in vendor_bills
                ),
                ZERO,
            )

            outstanding_value = sum(
                (get_bill_balance(bill) for bill in vendor_bills),
                ZERO,
            )

            bill_numbers = [
                bill.bill_number
                for bill in vendor_bills
                if bill.bill_number
            ]

            if active_field:
                raw_active_status = getattr(vendor, active_field, None)

                if active_field == "status":
                    vendor_status = (
                        "active"
                        if str(raw_active_status).lower() == "active"
                        else "inactive"
                    )
                else:
                    vendor_status = (
                        "active" if raw_active_status else "inactive"
                    )
            else:
                vendor_status = "unknown"

            vendor_row = {
                "vendor_id": vendor.pk,
                "vendor_name": getattr(vendor, vendor_name_field),
                "purchase_orders": pos_by_vendor.get(vendor_id, []),
                "bills": bill_numbers,
                "bill_count": len(vendor_bills),
                "purchase_value": float(purchase_value),
                "payments_received": float(
                    payments_by_vendor.get(vendor_id, ZERO)
                ),
                "outstanding_value": float(outstanding_value),
                "status": vendor_status,
            }

            if vendor_code_field:
                vendor_row["vendor_code"] = getattr(
                    vendor, vendor_code_field, None
                )

            if payment_term_field:
                vendor_row["payment_term"] = getattr(
                    vendor, payment_term_field, None
                )

            table_rows.append(vendor_row)

        # Keep vendors with no bills in the table as well.
        table_rows.sort(key=lambda row: row["vendor_name"].lower())

        # ---------------------------------------------------------
        # 8. Pagination
        # ---------------------------------------------------------
        paginator_config = VendorReportPagination()

        try:
            page_number = int(request.query_params.get("page", 1))
            page_size = int(
                request.query_params.get(
                    paginator_config.page_size_query_param,
                    paginator_config.page_size,
                )
            )
            if page_number < 1 or page_size < 1:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"detail": "page and page_size must be positive integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        page_size = min(page_size, paginator_config.max_page_size)
        paginator = Paginator(table_rows, page_size)
        page_obj = paginator.get_page(page_number)

        paginated_results = list(page_obj.object_list)

        # ---------------------------------------------------------
        # 9. Graph 1 - monthly purchase trend by chart_year
        #    This graph is independent of date_from/date_to.
        # ---------------------------------------------------------
        chart_bills = Bill.objects.filter(
            company_id=company_id,
            bill_date__year=chart_year,
        ).exclude(status__in=["draft", "cancelled"])

        chart_bills = chart_bills.filter(vendor_id__in=vendor_ids)

        monthly_totals = {
            month: ZERO for month in range(1, 13)
        }

        for item in chart_bills.values("bill_date__month").annotate(
            total=Sum("total_amount")
        ):
            month = item["bill_date__month"]
            monthly_totals[month] = decimal_value(item["total"])

        purchase_trend = {
            calendar.month_name[month]: float(monthly_totals[month])
            for month in range(1, 13)
        }

        # ---------------------------------------------------------
        # 10. Graph 2 - payment status for selected month/year
        # ---------------------------------------------------------
        graph_bills = Bill.objects.filter(
            company_id=company_id,
            bill_date__year=graph_year,
        ).exclude(status__in=["draft", "cancelled"])

        graph_bills = graph_bills.filter(vendor_id__in=vendor_ids)

        if graph_month:
            graph_bills = graph_bills.filter(
                bill_date__month=graph_month
            )

        payment_status_totals = {
            "paid_amount": ZERO,
            "partially_paid_amount": ZERO,
            "unpaid_amount": ZERO,
            "overdue_amount": ZERO,
            "total_outstanding_amount": ZERO,
        }

        for bill in graph_bills:
            bill_status = get_bill_payment_status(bill, today)
            balance = get_bill_balance(bill)
            amount_paid = decimal_value(bill.amount_paid)

            if bill_status == "paid":
                payment_status_totals["paid_amount"] += amount_paid

            elif bill_status == "partially_paid":
                payment_status_totals[
                    "partially_paid_amount"
                ] += amount_paid

            elif bill_status == "overdue":
                payment_status_totals["overdue_amount"] += balance

            else:
                payment_status_totals["unpaid_amount"] += balance

            payment_status_totals[
                "total_outstanding_amount"
            ] += balance

        payment_status_graph = {
            key: float(value)
            for key, value in payment_status_totals.items()
        }

        # ---------------------------------------------------------
        # 11. Response
        # ---------------------------------------------------------
        return Response(
            {
                "filters": {
                    "date_from": date_from,
                    "date_to": date_to,
                    "vendor": vendor_filter,
                    "payment_term": payment_term_filter,
                    "payment_status": payment_status_filter,
                    "chart_year": chart_year,
                    "graph_year": graph_year,
                    "graph_month": graph_month,
                },
                "kpis": kpis,
                "graphs": {
                    "monthly_purchase_trend": {
                        "year": chart_year,
                        "data": purchase_trend,
                    },
                    "vendor_payment_status": {
                        "year": graph_year,
                        "month": graph_month,
                        "data": payment_status_graph,
                    },
                },
                "pagination": {
                    "count": paginator.count,
                    "total_pages": paginator.num_pages,
                    "current_page": page_obj.number,
                    "page_size": page_size,
                    "next_page": (
                        page_obj.next_page_number()
                        if page_obj.has_next()
                        else None
                    ),
                    "previous_page": (
                        page_obj.previous_page_number()
                        if page_obj.has_previous()
                        else None
                    ),
                },
                "results": paginated_results,
            }
        )
