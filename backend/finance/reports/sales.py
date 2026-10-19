
# reports/sales.py

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

from finance.invoice.models import Invoice
from finance.payment.models import Payment
from finance.credit_note.models import CreditNote
from finance.sales_return.models import SalesReturnItem

from user.permissions import IsCompanyActive, IsHRAdmin


ZERO = Decimal("0.00")

VALID_STATUSES = {
    "paid": "paid",
    "partial": "partially_paid",
    "partially_paid": "partially_paid",
    "unpaid": "unpaid",
}


class SalesReportPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class SalesReportView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    pagination_class = SalesReportPagination

    # ------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------

    @staticmethod
    def get_invoice_total(invoice):
        """
        Return the stored invoice total.
        Fall back to calculating the total for older or
        incomplete invoice records.
        """
        total = invoice.total_amount

        if total is None or (
            total == ZERO
            and (
                (invoice.subtotal or ZERO)
                or (invoice.total_vat or ZERO)
                or (invoice.discount or ZERO)
            )
        ):
            total = (
                (invoice.subtotal or ZERO)
                + (invoice.total_vat or ZERO)
                - (invoice.discount or ZERO)
                + (invoice.round_off or ZERO)
            )

        return total or ZERO

    @staticmethod
    def parse_optional_id(params, param_name):
        raw_value = params.get(param_name)

        if not raw_value:
            return None

        try:
            value = int(raw_value)
            if value <= 0:
                raise ValueError

            return value

        except (ValueError, TypeError):
            raise ValueError(
                f"{param_name} must be a positive integer."
            )

    # ------------------------------------------------------
    # GET SALES REPORT
    # ------------------------------------------------------

    def get(self, request):
        company = getattr(request.user, "company", None)

        if company is None:
            return Response(
                {
                    "detail": (
                        "User is not associated with a company."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        params = request.query_params

        # --------------------------------------------------
        # 1. VALIDATE DATE FILTERS
        # --------------------------------------------------

        raw_date_from = params.get("date_from")
        raw_date_to = params.get("date_to")

        date_from = None
        date_to = None

        if raw_date_from:
            date_from = parse_date(raw_date_from)

            if date_from is None:
                return Response(
                    {
                        "detail": (
                            "date_from must use YYYY-MM-DD format."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if raw_date_to:
            date_to = parse_date(raw_date_to)

            if date_to is None:
                return Response(
                    {
                        "detail": (
                            "date_to must use YYYY-MM-DD format."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if date_from and date_to and date_from > date_to:
            return Response(
                {
                    "detail": (
                        "date_from cannot be after date_to."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------
        # 2. VALIDATE CUSTOMER AND CATEGORY
        # --------------------------------------------------

        try:
            customer_id = self.parse_optional_id(
                params, "customer"
            )
            category_id = self.parse_optional_id(
                params, "category"
            )

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------
        # 3. FILTER INVOICES
        # --------------------------------------------------

        invoices = (
            Invoice.objects.filter(company=company)
            .select_related("customer")
            .prefetch_related("items__product")
        )

        if date_from:
            invoices = invoices.filter(
                invoice_date__gte=date_from
            )

        if date_to:
            invoices = invoices.filter(
                invoice_date__lte=date_to
            )

        if customer_id:
            invoices = invoices.filter(
                customer_id=customer_id
            )

        if category_id:
            invoices = invoices.filter(
                items__product__category_id=category_id
            )

        invoices = invoices.distinct().order_by(
            "-invoice_date", "-id"
        )

        invoice_list = list(invoices)
        invoice_ids = [
            invoice.id for invoice in invoice_list
        ]

        # --------------------------------------------------
        # 4. COMPLETED PAYMENTS PER INVOICE
        # --------------------------------------------------

        payment_totals = {}

        if invoice_ids:
            payment_totals = dict(
                Payment.objects.filter(
                    company=company,
                    invoice_id__in=invoice_ids,
                    status="completed",
                )
                .values("invoice_id")
                .annotate(total=Sum("amount_received"))
                .values_list("invoice_id", "total")
            )

        # --------------------------------------------------
        # 5. FILTER CREDIT NOTES
        # --------------------------------------------------

        credits = CreditNote.objects.filter(
            company=company,
        ).exclude(
            status__in=["draft", "cancelled"]
        )

        if date_from:
            credits = credits.filter(
                issue_date__gte=date_from
            )

        if date_to:
            credits = credits.filter(
                issue_date__lte=date_to
            )

        if customer_id:
            credits = credits.filter(
                customer_id=customer_id
            )

        if category_id:
            credits = credits.filter(
                items__product__category_id=category_id
            )

        credits = credits.distinct()

        # Get distinct credit-note IDs after applying filters.
        credit_ids = list(
            credits.values_list("id", flat=True).distinct()
        )

        # Aggregate from CreditNote without joining its items.
        selected_credit_total = ZERO

        if credit_ids:
            selected_credit_total = (
                CreditNote.objects.filter(
                    id__in=credit_ids,
                    company=company,
                ).aggregate(
                    total=Sum("credit_amount")
                )["total"]
                or ZERO
            )

        # Applied credits grouped by invoice.
        applied_credits_by_invoice = {}

        if credit_ids and invoice_ids:
            applied_credits_by_invoice = dict(
                CreditNote.objects.filter(
                    company=company,
                    id__in=credit_ids,
                    invoice_id__in=invoice_ids,
                )
                .values("invoice_id")
                .annotate(total=Sum("applied_amount"))
                .values_list("invoice_id", "total")
            )

        # --------------------------------------------------
        # 6. RETURNED QUANTITIES PER INVOICE
        # --------------------------------------------------

        returned_by_invoice = defaultdict(
            lambda: ZERO
        )

        if invoice_ids:
            returned_items = SalesReturnItem.objects.filter(
                sales_return__company=company,
                sales_return__status__in=[
                    "approved",
                    "refunded",
                ],
                invoice_item__invoice_id__in=invoice_ids,
            )

            if category_id:
                returned_items = returned_items.filter(
                    product__category_id=category_id
                )

            returned_rows = (
                returned_items
                .values("invoice_item__invoice_id")
                .annotate(
                    total=Sum("returning_now_qty")
                )
            )

            for row in returned_rows:
                returned_by_invoice[
                    row["invoice_item__invoice_id"]
                ] = row["total"] or ZERO

        # --------------------------------------------------
        # 7. BUILD INVOICE TABLE ROWS
        # --------------------------------------------------

        rows = []

        for invoice in invoice_list:
            subtotal = invoice.subtotal or ZERO
            tax_amount = invoice.total_vat or ZERO
            discount = invoice.discount or ZERO
            net_amount = self.get_invoice_total(invoice)

            paid = payment_totals.get(invoice.id) or ZERO

            # Report status based on completed payments.
            if net_amount > ZERO and paid >= net_amount:
                report_status = "paid"

            elif paid > ZERO:
                report_status = "partially_paid"

            else:
                report_status = "unpaid"

            customer_name = (
                invoice.customer_name
                or (
                    invoice.customer.customer_name
                    if invoice.customer_id
                    else ""
                )
            )

            # Invoice item quantity for the selected category.
            matching_items = invoice.items.all()

            if category_id:
                matching_items = matching_items.filter(
                    product__category_id=category_id
                )

            invoiced_quantity = sum(
                (
                    item.quantity or ZERO
                    for item in matching_items
                ),
                ZERO,
            )

            returned_quantity = (
                returned_by_invoice[invoice.id]
            )

            products_sold = max(
                invoiced_quantity - returned_quantity,
                ZERO,
            )

            rows.append({
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "date": invoice.invoice_date.isoformat(),
                "customer_id": invoice.customer_id,
                "customer": customer_name,
                "amount": subtotal,
                "tax_amount": tax_amount,
                "discount": discount,
                "net_amount": net_amount,
                "status": report_status,
                "paid": paid,
                "products_sold": products_sold,
                "returned_quantity": returned_quantity,
            })

        # --------------------------------------------------
        # 8. PAYMENT STATUS FILTER
        # --------------------------------------------------

        requested_status = (
            params.get("status") or ""
        ).lower().strip()

        if requested_status:
            if requested_status not in VALID_STATUSES:
                return Response(
                    {
                        "detail": (
                            "Invalid status. Use paid, partial, "
                            "partially_paid, or unpaid."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            expected_status = VALID_STATUSES[
                requested_status
            ]

            rows = [
                row
                for row in rows
                if row["status"] == expected_status
            ]

        # --------------------------------------------------
        # 9. KPI SUMMARY
        # --------------------------------------------------

        total_invoice_revenue = sum(
            (
                row["net_amount"]
                for row in rows
            ),
            ZERO,
        )

        products_sold = sum(
            (
                row["products_sold"]
                for row in rows
            ),
            ZERO,
        )

        payments_received = sum(
            (
                row["paid"]
                for row in rows
            ),
            ZERO,
        )

        summary = {
            "total_sales_revenue": (
                total_invoice_revenue
                - selected_credit_total
            ),
            "total_invoices": len(rows),
            "products_sold": products_sold,
            "payments_received": payments_received,
        }

        # --------------------------------------------------
        # 10. CURRENT OUTSTANDING RECEIVABLES
        # Independent of report filters.
        # --------------------------------------------------

        all_invoices = Invoice.objects.filter(
            company=company
        )

        all_invoice_ids = list(
            all_invoices.values_list("id", flat=True)
        )

        all_payments = {}

        if all_invoice_ids:
            all_payments = dict(
                Payment.objects.filter(
                    company=company,
                    invoice_id__in=all_invoice_ids,
                    status="completed",
                )
                .values("invoice_id")
                .annotate(total=Sum("amount_received"))
                .values_list("invoice_id", "total")
            )

        all_applied_credits = {}

        if all_invoice_ids:
            all_applied_credits = dict(
                CreditNote.objects.filter(
                    company=company,
                    invoice_id__in=all_invoice_ids,
                )
                .exclude(
                    status__in=["draft", "cancelled"]
                )
                .values("invoice_id")
                .annotate(total=Sum("applied_amount"))
                .values_list("invoice_id", "total")
            )

        outstanding_receivables = ZERO

        for invoice in all_invoices.only(
            "id",
            "total_amount",
            "subtotal",
            "total_vat",
            "discount",
            "round_off",
        ).iterator():

            invoice_total = self.get_invoice_total(
                invoice
            )

            paid = all_payments.get(
                invoice.id
            ) or ZERO

            applied_credit = all_applied_credits.get(
                invoice.id
            ) or ZERO

            outstanding_receivables += max(
                invoice_total - paid - applied_credit,
                ZERO,
            )

        summary["outstanding_receivables"] = (
            outstanding_receivables
        )

        # --------------------------------------------------
        # 11. VALIDATE CHART YEAR
        # --------------------------------------------------

        try:
            year = int(
                params.get(
                    "year",
                    timezone.localdate().year,
                )
            )

            if year < 1 or year > 9999:
                raise ValueError

        except (ValueError, TypeError):
            return Response(
                {
                    "detail": (
                        "year must be a valid four-digit year."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------
        # 12. MONTHLY REVENUE CHART
        # --------------------------------------------------

        chart_invoices = Invoice.objects.filter(
            company=company,
            invoice_date__year=year,
        )

        if customer_id:
            chart_invoices = chart_invoices.filter(
                customer_id=customer_id
            )

        if category_id:
            chart_invoices = chart_invoices.filter(
                items__product__category_id=category_id
            ).distinct()

        chart_invoice_rows = chart_invoices.values(
            "id",
            "invoice_date",
            "total_amount",
            "subtotal",
            "total_vat",
            "discount",
            "round_off",
        )

        monthly_revenue = defaultdict(
            lambda: ZERO
        )

        for invoice in chart_invoice_rows:
            month = invoice["invoice_date"].month
            amount = invoice["total_amount"]

            if amount is None or (
                amount == ZERO
                and (
                    (invoice["subtotal"] or ZERO)
                    or (invoice["total_vat"] or ZERO)
                    or (invoice["discount"] or ZERO)
                )
            ):
                amount = (
                    (invoice["subtotal"] or ZERO)
                    + (invoice["total_vat"] or ZERO)
                    - (invoice["discount"] or ZERO)
                    + (invoice["round_off"] or ZERO)
                )

            monthly_revenue[month] += amount or ZERO

        chart_credits = CreditNote.objects.filter(
            company=company,
            issue_date__year=year,
        ).exclude(
            status__in=["draft", "cancelled"]
        )

        if customer_id:
            chart_credits = chart_credits.filter(
                customer_id=customer_id
            )

        if category_id:
            chart_credits = chart_credits.filter(
                items__product__category_id=category_id
            )

        chart_credit_ids = list(
            chart_credits.values_list(
                "id", flat=True
            ).distinct()
        )

        monthly_credits = defaultdict(
            lambda: ZERO
        )

        if chart_credit_ids:
            credit_rows = CreditNote.objects.filter(
                company=company,
                id__in=chart_credit_ids,
            ).values(
                "issue_date",
                "credit_amount",
            )

            for credit in credit_rows:
                month = credit["issue_date"].month

                monthly_credits[month] += (
                    credit["credit_amount"] or ZERO
                )

        chart = []

        for month in range(1, 13):
            chart.append({
                "month": month,
                "label": calendar.month_abbr[month],
                "revenue": (
                    monthly_revenue[month]
                    - monthly_credits[month]
                ),
            })

        # --------------------------------------------------
        # 13. CSV EXPORT
        # --------------------------------------------------

        export_format = (
            params.get("export") or ""
        ).lower().strip()

        if export_format in (
            "1",
            "true",
            "csv",
            "excel",
        ):
            response = HttpResponse(
                content_type="text/csv; charset=utf-8"
            )

            response["Content-Disposition"] = (
                'attachment; filename="sales-report.csv"'
            )

            writer = csv.writer(response)

            writer.writerow([
                "Invoice Number",
                "Date",
                "Customer",
                "Amount",
                "Tax Amount",
                "Discount",
                "Net Amount",
                "Status",
            ])

            for row in rows:
                writer.writerow([
                    row["invoice_number"],
                    row["date"],
                    row["customer"],
                    row["amount"],
                    row["tax_amount"],
                    row["discount"],
                    row["net_amount"],
                    row["status"],
                ])

            return response

        # --------------------------------------------------
        # 14. PAGINATION
        # --------------------------------------------------

        paginator = self.pagination_class()

        page_rows = paginator.paginate_queryset(
            rows,
            request,
            view=self,
        )

        response = paginator.get_paginated_response(
            page_rows
        )

        response.data["summary"] = summary

        response.data["chart"] = {
            "year": year,
            "months": chart,
        }

        return response
