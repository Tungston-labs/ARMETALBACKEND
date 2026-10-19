
# reports/customer.py

import calendar
from decimal import Decimal

from django.db.models import Q, Sum, F
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.customer.models import Customer
from finance.invoice.models import Invoice
from finance.payment.models import Payment

from user.permissions import IsCompanyActive, IsHRAdmin


ZERO = Decimal("0.00")

VALID_PAYMENT_STATUSES = {
    "paid",
    "partially_paid",
    "unpaid",
    "overdue",
}


class CustomerReportPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class CustomerReportView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @staticmethod
    def money(value):
        return value if value is not None else ZERO

    @staticmethod
    def parse_date_param(value, field_name):
        if not value:
            return None

        parsed_date = parse_date(value)

        if parsed_date is None:
            raise ValueError(
                f"Invalid {field_name}. Use YYYY-MM-DD format."
            )

        return parsed_date

    @staticmethod
    def parse_integer_param(value, field_name, default):
        if value in (None, ""):
            return default

        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field_name} must be an integer.")

    def get_balance(self, invoice):
        total = self.money(invoice.total_amount)
        paid = self.money(invoice.amount_paid)

        return max(total - paid, ZERO)

    def get_invoice_status(self, invoice, today):
        """
        Determine the effective payment status.

        The Invoice model stores paid, unpaid and partially_paid.
        Overdue is calculated from due_date and outstanding balance.
        """
        balance = self.get_balance(invoice)

        if balance <= ZERO:
            return "paid"

        if invoice.due_date and invoice.due_date < today:
            return "overdue"

        if self.money(invoice.amount_paid) > ZERO:
            return "partially_paid"

        return "unpaid"

    # ---------------------------------------------------------
    # GET report
    # ---------------------------------------------------------

    def get(self, request):
        company_id = getattr(request.user, "company_id", None)

        if not company_id:
            return Response(
                {
                    "detail": (
                        "The authenticated user is not associated "
                        "with a company."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        params = request.query_params
        today = timezone.localdate()

        # -----------------------------------------------------
        # Read and validate query parameters
        # -----------------------------------------------------

        try:
            date_from = self.parse_date_param(
                params.get("date_from"),
                "date_from",
            )

            date_to = self.parse_date_param(
                params.get("date_to"),
                "date_to",
            )

            if date_from and date_to and date_from > date_to:
                raise ValueError(
                    "date_from cannot be later than date_to."
                )

            customer_id = self.parse_integer_param(
                params.get("customer_id"),
                "customer_id",
                None,
            )

            chart_year = self.parse_integer_param(
                params.get("chart_year"),
                "chart_year",
                today.year,
            )

            graph_year = self.parse_integer_param(
                params.get("graph_year"),
                "graph_year",
                today.year,
            )

            graph_month = self.parse_integer_param(
                params.get("graph_month"),
                "graph_month",
                today.month,
            )

            if not 1 <= graph_month <= 12:
                raise ValueError(
                    "graph_month must be between 1 and 12."
                )

            if not 1900 <= chart_year <= 9999:
                raise ValueError("Invalid chart_year.")

            if not 1900 <= graph_year <= 9999:
                raise ValueError("Invalid graph_year.")

        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer_type = params.get("customer_type")
        payment_status = params.get("payment_status")

        if payment_status:
            payment_status = payment_status.strip().lower()

            if payment_status not in VALID_PAYMENT_STATUSES:
                return Response(
                    {
                        "detail": (
                            "Invalid payment_status. Allowed values: "
                            "paid, partially_paid, unpaid, overdue."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # -----------------------------------------------------
        # Base invoice queryset
        # These filters apply to the table and KPI summary.
        # -----------------------------------------------------

        base_invoices = Invoice.objects.filter(
            company_id=company_id,
        ).select_related("customer")

        if customer_id is not None:
            base_invoices = base_invoices.filter(
                customer_id=customer_id,
            )

        if customer_type:
            base_invoices = base_invoices.filter(
                customer__industry=customer_type,
            )

        invoices = base_invoices

        if date_from:
            invoices = invoices.filter(
                invoice_date__gte=date_from,
            )

        if date_to:
            invoices = invoices.filter(
                invoice_date__lte=date_to,
            )

        # -----------------------------------------------------
        # Payment status filter
        # -----------------------------------------------------

        if payment_status == "paid":
            invoices = invoices.filter(
                amount_paid__gte=F("total_amount"),
            )

        elif payment_status == "partially_paid":
            invoices = invoices.filter(
                amount_paid__gt=ZERO,
                amount_paid__lt=F("total_amount"),
            ).filter(
                Q(due_date__isnull=True)
                | Q(due_date__gte=today)
            )

        elif payment_status == "unpaid":
            invoices = invoices.filter(
                amount_paid__lte=ZERO,
                total_amount__gt=ZERO,
            ).filter(
                Q(due_date__isnull=True)
                | Q(due_date__gte=today)
            )

        elif payment_status == "overdue":
            invoices = invoices.filter(
                due_date__lt=today,
                total_amount__gt=F("amount_paid"),
            )

        invoices = invoices.order_by(
            "-invoice_date",
            "-id",
        )

        invoice_list = list(invoices)

        # -----------------------------------------------------
        # KPI summary
        # -----------------------------------------------------

        customer_ids = {
            invoice.customer_id
            for invoice in invoice_list
            if invoice.customer_id
        }

        total_revenue = sum(
            (
                self.money(invoice.total_amount)
                for invoice in invoice_list
            ),
            ZERO,
        )

        total_outstanding = sum(
            (
                self.get_balance(invoice)
                for invoice in invoice_list
            ),
            ZERO,
        )

        # Actual completed receipts, filtered by payment date.
        # This uses the existing Payment model.
        payments = Payment.objects.filter(
            company_id=company_id,
            status="completed",
            customer_id__in=customer_ids,
        )

        if date_from:
            payments = payments.filter(
                payment_date__gte=date_from,
            )

        if date_to:
            payments = payments.filter(
                payment_date__lte=date_to,
            )

        payment_received = self.money(
            payments.aggregate(
                total=Sum("amount_received"),
            )["total"]
        )

        summary = {
            "total_customers": len(customer_ids),
            "total_revenue": float(total_revenue),
            "payment_received": float(payment_received),
            "outstanding_payable": float(total_outstanding),
            "total_invoices": len(invoice_list),
        }

        # -----------------------------------------------------
        # Table rows: one row per invoice
        # -----------------------------------------------------

        results = []

        for invoice in invoice_list:
            balance = self.get_balance(invoice)

            results.append({
                "customer_id": invoice.customer_id,
                "customer_name": (
                    invoice.customer.customer_name
                    if invoice.customer
                    else None
                ),
                "invoice": invoice.invoice_number,
                "invoice_date": invoice.invoice_date,
                "revenue": float(
                    self.money(invoice.total_amount)
                ),
                "payment_received": float(
                    self.money(invoice.amount_paid)
                ),
                "outstanding_value": float(balance),
                "status": self.get_invoice_status(
                    invoice,
                    today,
                ),
            })

        # -----------------------------------------------------
        # Graph 1: Monthly customer revenue by chart_year
        #
        # chart_year is independent of date_from/date_to.
        # -----------------------------------------------------

        revenue_invoices = base_invoices.filter(
            invoice_date__year=chart_year,
        )

        monthly_revenue = {
            month: ZERO
            for month in range(1, 13)
        }

        revenue_rows = (
            revenue_invoices
            .values("invoice_date__month")
            .annotate(total=Sum("total_amount"))
        )

        for row in revenue_rows:
            month_number = row["invoice_date__month"]

            if month_number:
                monthly_revenue[month_number] = self.money(
                    row["total"]
                )

        revenue_chart = {
            calendar.month_name[month]: float(
                monthly_revenue[month]
            )
            for month in range(1, 13)
        }

        # -----------------------------------------------------
        # Graph 2: Payment status by graph_month and graph_year
        #
        # This graph is independent of table date/status filters.
        # -----------------------------------------------------

        status_invoices = base_invoices.filter(
            invoice_date__year=graph_year,
            invoice_date__month=graph_month,
        )

        paid_amount = ZERO
        partially_paid_amount = ZERO
        unpaid_amount = ZERO
        overdue_amount = ZERO
        graph_outstanding = ZERO

        for invoice in status_invoices:
            invoice_status = self.get_invoice_status(
                invoice,
                today,
            )

            invoice_total = self.money(invoice.total_amount)
            balance = self.get_balance(invoice)

            graph_outstanding += balance

            if invoice_status == "paid":
                paid_amount += invoice_total

            elif invoice_status == "partially_paid":
                partially_paid_amount += invoice_total

            elif invoice_status == "overdue":
                overdue_amount += balance

            elif invoice_status == "unpaid":
                unpaid_amount += balance

        payment_status_chart = {
            "month": graph_month,
            "month_name": calendar.month_name[graph_month],
            "year": graph_year,
            "paid_amount": float(paid_amount),
            "partially_paid_amount": float(
                partially_paid_amount
            ),
            "unpaid_amount": float(unpaid_amount),
            "overdue_amount": float(overdue_amount),
            "total_outstanding_amount": float(
                graph_outstanding
            ),
        }

        # -----------------------------------------------------
        # Paginate the table while keeping summary and charts
        # -----------------------------------------------------

        paginator = CustomerReportPagination()

        page = paginator.paginate_queryset(
            results,
            request,
            view=self,
        )

        return Response({
            "count": paginator.page.paginator.count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "summary": summary,
            "charts": {
                "monthly_revenue": {
                    "year": chart_year,
                    "monthly_amounts": revenue_chart,
                },
                "payment_status": payment_status_chart,
            },
            "results": page,
        })
