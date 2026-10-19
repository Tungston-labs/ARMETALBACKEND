
# reports/payment.py

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.payment.models import Payment
from finance.vendor.models import VendorPayment
from finance.banking.models import BankTransaction
from user.permissions import IsCompanyActive, IsHRAdmin


ZERO = Decimal("0.00")


def as_decimal(value):
    return value if value is not None else ZERO


def related_name(obj):
    """Return a readable customer/vendor name when available."""
    if obj is None:
        return "Unknown"

    for field in ("name", "customer_name", "vendor_name", "company_name"):
        value = getattr(obj, field, None)
        if value:
            return str(value)

    return str(obj)


def account_display(bank_transaction):
    """Return the bank account display name."""
    if not bank_transaction or not bank_transaction.bank_account:
        return None

    account = bank_transaction.bank_account

    return (
        getattr(account, "bank_name", None)
        or getattr(account, "account_number", None)
        or str(account.pk)
    )


def parse_filter_date(value, field_name):
    if not value:
        return None

    parsed = parse_date(value)
    if parsed is None:
        raise ValueError(
            f"{field_name} must be in YYYY-MM-DD format."
        )

    return parsed


class PaymentReportView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    DEFAULT_PAGE_SIZE = 10
    MAX_PAGE_SIZE = 100

    def get(self, request):
        company_id = getattr(request.user, "company_id", None)

        if not company_id:
            return Response(
                {"detail": "Your account is not associated with a company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 1. Read and validate filters
        # ---------------------------------------------------------
        try:
            date_from = parse_filter_date(
                request.query_params.get("date_from"), "date_from"
            )
            date_to = parse_filter_date(
                request.query_params.get("date_to"), "date_to"
            )

            chart_year = int(
                request.query_params.get(
                    "chart_year", timezone.localdate().year
                )
            )
            graph_year = int(
                request.query_params.get(
                    "graph_year", timezone.localdate().year
                )
            )

            graph_month_value = request.query_params.get("graph_month")
            graph_month = (
                int(graph_month_value) if graph_month_value else None
            )

            page = int(request.query_params.get("page", 1))
            page_size = int(
                request.query_params.get(
                    "page_size", self.DEFAULT_PAGE_SIZE
                )
            )

        except (TypeError, ValueError):
            return Response(
                {
                    "detail": (
                        "Invalid filters. Use dates in YYYY-MM-DD format, "
                        "valid years, a month from 1 to 12, and positive "
                        "page/page_size values."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if date_from and date_to and date_from > date_to:
            return Response(
                {"detail": "date_from cannot be later than date_to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if graph_month is not None and not 1 <= graph_month <= 12:
            return Response(
                {"detail": "graph_month must be between 1 and 12."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if page < 1 or page_size < 1:
            return Response(
                {"detail": "page and page_size must be positive integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        page_size = min(page_size, self.MAX_PAGE_SIZE)

        payment_type_filter = request.query_params.get("payment_type")
        payment_method_filter = request.query_params.get("payment_method")
        payment_status_filter = request.query_params.get("status")
        bank_account_filter = request.query_params.get("bank_account")

        valid_types = {"customer_receipt", "vendor_payment"}

        if payment_type_filter and payment_type_filter not in valid_types:
            return Response(
                {
                    "detail": (
                        "payment_type must be customer_receipt "
                        "or vendor_payment."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if bank_account_filter:
            try:
                bank_account_filter = int(bank_account_filter)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "bank_account must be a valid account ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ---------------------------------------------------------
        # 2. Fetch company-scoped customer and vendor payments
        # ---------------------------------------------------------
        customer_payments = Payment.objects.filter(
            company_id=company_id
        ).select_related("customer")

        vendor_payments = VendorPayment.objects.filter(
            company_id=company_id
        ).select_related("vendor")

        # BankTransaction has no guaranteed direct FK to the payment
        # records, so associate using matching reference_number values.
        bank_transactions = BankTransaction.objects.filter(
            company_id=company_id
        ).select_related("bank_account")

        customer_records = list(customer_payments)
        vendor_records = list(vendor_payments)

        reference_numbers = set()

        for payment in customer_records:
            reference = getattr(payment, "reference_number", None)
            if reference:
                reference_numbers.add(str(reference))

        for payment in vendor_records:
            reference = getattr(payment, "reference_number", None)
            if reference:
                reference_numbers.add(str(reference))

        transaction_map = defaultdict(list)

        if reference_numbers:
            for transaction in bank_transactions.filter(
                reference_number__in=reference_numbers
            ):
                transaction_map[str(transaction.reference_number)].append(
                    transaction
                )

        # ---------------------------------------------------------
        # 3. Normalize both payment models into one table structure
        # ---------------------------------------------------------
        rows = []

        def matching_bank_transaction(reference, expected_type):
            if not reference:
                return None

            candidates = transaction_map.get(str(reference), [])

            for transaction in candidates:
                if transaction.transaction_type == expected_type:
                    return transaction

            return None

        for payment in customer_records:
            reference = (
                getattr(payment, "reference_number", None)
                or getattr(payment, "receipt_number", None)
            )

            bank_transaction = matching_bank_transaction(
                reference, "customer_receipt"
            )

            rows.append({
                "id": payment.pk,
                "date": payment.payment_date,
                "type": "customer_receipt",
                "name": related_name(getattr(payment, "customer", None)),
                "reference": reference,
                "method": getattr(payment, "payment_method", None),
                "amount": as_decimal(
                    getattr(payment, "amount_received", ZERO)
                ),
                "status": getattr(payment, "status", None),
                "bank_account_id": (
                    bank_transaction.bank_account_id
                    if bank_transaction else None
                ),
                "bank_account": account_display(bank_transaction),
                "_source": "customer",
            })

        for payment in vendor_records:
            reference = (
                getattr(payment, "reference_number", None)
                or getattr(payment, "receipt_number", None)
            )

            bank_transaction = matching_bank_transaction(
                reference, "vendor_payment"
            )

            rows.append({
                "id": payment.pk,
                "date": payment.payment_date,
                "type": "vendor_payment",
                "name": related_name(getattr(payment, "vendor", None)),
                "reference": reference,
                "method": getattr(payment, "payment_method", None),
                "amount": as_decimal(
                    getattr(payment, "amount_paid", ZERO)
                ),
                "status": getattr(payment, "status", None),
                "bank_account_id": (
                    bank_transaction.bank_account_id
                    if bank_transaction else None
                ),
                "bank_account": account_display(bank_transaction),
                "_source": "vendor",
            })

        # ---------------------------------------------------------
        # 4. Apply filters to the table and KPI dataset
        # ---------------------------------------------------------
        filtered_rows = list(rows)

        if date_from:
            filtered_rows = [
                row for row in filtered_rows
                if row["date"] and row["date"] >= date_from
            ]

        if date_to:
            filtered_rows = [
                row for row in filtered_rows
                if row["date"] and row["date"] <= date_to
            ]

        if payment_type_filter:
            filtered_rows = [
                row for row in filtered_rows
                if row["type"] == payment_type_filter
            ]

        if payment_method_filter:
            filtered_rows = [
                row for row in filtered_rows
                if str(row["method"]) == payment_method_filter
            ]

        if payment_status_filter:
            filtered_rows = [
                row for row in filtered_rows
                if str(row["status"]) == payment_status_filter
            ]

        if bank_account_filter:
            filtered_rows = [
                row for row in filtered_rows
                if row["bank_account_id"] == bank_account_filter
            ]

        filtered_rows.sort(
            key=lambda row: (row["date"] or date.min, row["id"]),
            reverse=True,
        )

        # ---------------------------------------------------------
        # 5. KPI cards
        # ---------------------------------------------------------
        non_cancelled_rows = [
            row for row in filtered_rows
            if str(row["status"]).lower() != "cancelled"
        ]

        total_payment_amount = sum(
            (row["amount"] for row in non_cancelled_rows), ZERO
        )

        amount_received = sum(
            (
                row["amount"]
                for row in non_cancelled_rows
                if row["type"] == "customer_receipt"
                and str(row["status"]).lower() == "completed"
            ),
            ZERO,
        )

        amount_paid = sum(
            (
                row["amount"]
                for row in non_cancelled_rows
                if row["type"] == "vendor_payment"
                and str(row["status"]).lower() == "completed"
            ),
            ZERO,
        )

        pending_payments = sum(
            1 for row in filtered_rows
            if str(row["status"]).lower() == "pending"
        )

        kpis = {
            "total_payment": len(non_cancelled_rows),
            "total_payment_amount": float(total_payment_amount),
            "amount_received": float(amount_received),
            "amount_paid": float(amount_paid),
            "pending_payments": pending_payments,
        }

        # ---------------------------------------------------------
        # 6. Graph 1 - monthly payment trend by chart_year
        #    Independent of the table's date range.
        # ---------------------------------------------------------
        chart_rows = [
            row for row in rows
            if row["date"]
            and row["date"].year == chart_year
            and str(row["status"]).lower() != "cancelled"
        ]

        if payment_type_filter:
            chart_rows = [
                row for row in chart_rows
                if row["type"] == payment_type_filter
            ]

        if payment_method_filter:
            chart_rows = [
                row for row in chart_rows
                if str(row["method"]) == payment_method_filter
            ]

        if payment_status_filter:
            chart_rows = [
                row for row in chart_rows
                if str(row["status"]) == payment_status_filter
            ]

        if bank_account_filter:
            chart_rows = [
                row for row in chart_rows
                if row["bank_account_id"] == bank_account_filter
            ]

        monthly_payment_totals = {
            month: ZERO for month in range(1, 13)
        }

        for row in chart_rows:
            monthly_payment_totals[row["date"].month] += row["amount"]

        monthly_payment_graph = {
            calendar.month_name[month]: float(
                monthly_payment_totals[month]
            )
            for month in range(1, 13)
        }

        # ---------------------------------------------------------
        # 7. Graph 2 - customer receipts vs vendor payments
        #    by month for graph_year and optional graph_month.
        # ---------------------------------------------------------
        graph_rows = [
            row for row in rows
            if row["date"]
            and row["date"].year == graph_year
            and str(row["status"]).lower() != "cancelled"
        ]

        if graph_month:
            graph_rows = [
                row for row in graph_rows
                if row["date"].month == graph_month
            ]

        if payment_type_filter:
            graph_rows = [
                row for row in graph_rows
                if row["type"] == payment_type_filter
            ]

        if payment_method_filter:
            graph_rows = [
                row for row in graph_rows
                if str(row["method"]) == payment_method_filter
            ]

        if payment_status_filter:
            graph_rows = [
                row for row in graph_rows
                if str(row["status"]) == payment_status_filter
            ]

        if bank_account_filter:
            graph_rows = [
                row for row in graph_rows
                if row["bank_account_id"] == bank_account_filter
            ]

        monthly_comparison = {
            month: {
                "customer_receipts": ZERO,
                "vendor_payments": ZERO,
            }
            for month in range(1, 13)
        }

        for row in graph_rows:
            month = row["date"].month

            if row["type"] == "customer_receipt":
                monthly_comparison[month]["customer_receipts"] += (
                    row["amount"]
                )
            elif row["type"] == "vendor_payment":
                monthly_comparison[month]["vendor_payments"] += (
                    row["amount"]
                )

        payment_comparison_graph = {
            calendar.month_name[month]: {
                "customer_receipts": float(
                    monthly_comparison[month]["customer_receipts"]
                ),
                "vendor_payments": float(
                    monthly_comparison[month]["vendor_payments"]
                ),
            }
            for month in range(1, 13)
        }

        # ---------------------------------------------------------
        # 8. Pagination
        # ---------------------------------------------------------
        paginator = Paginator(filtered_rows, page_size)
        page_obj = paginator.get_page(page)

        results = []

        for row in page_obj.object_list:
            results.append({
                key: (
                    float(value)
                    if isinstance(value, Decimal)
                    else value
                )
                for key, value in row.items()
                if not key.startswith("_")
            })

        # ---------------------------------------------------------
        # 9. Response
        # ---------------------------------------------------------
        return Response({
            "filters": {
                "date_from": date_from,
                "date_to": date_to,
                "payment_type": payment_type_filter,
                "payment_method": payment_method_filter,
                "status": payment_status_filter,
                "bank_account": bank_account_filter,
                "chart_year": chart_year,
                "graph_year": graph_year,
                "graph_month": graph_month,
            },
            "kpis": kpis,
            "graphs": {
                "monthly_payment_trend": {
                    "year": chart_year,
                    "data": monthly_payment_graph,
                },
                "customer_receipts_vs_vendor_payments": {
                    "year": graph_year,
                    "month_filter": graph_month,
                    "data": payment_comparison_graph,
                },
            },
            "pagination": {
                "count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page_obj.number,
                "page_size": page_size,
                "next_page": (
                    page_obj.next_page_number()
                    if page_obj.has_next() else None
                ),
                "previous_page": (
                    page_obj.previous_page_number()
                    if page_obj.has_previous() else None
                ),
            },
            "results": results,
        })
