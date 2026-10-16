import csv
import calendar
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.credit_note.models import CreditNote
from finance.invoice.models import Invoice
from finance.ledger.models import CustomerLedger
from finance.payment.models import Payment
from finance.sales_return.models import SalesReturnItem
from user.permissions import IsCompanyActive, IsHRAdmin


ZERO = Decimal("0.00")


class SalesReportPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = None


class SalesReportView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyActive, IsHRAdmin]
    pagination_class = SalesReportPagination

    def get(self, request):
        company = getattr(request.user, "company", None)
        if company is None:
            return Response({"detail": "User is not associated with a company."}, status=status.HTTP_400_BAD_REQUEST)

        params = request.query_params
        invoices = Invoice.objects.filter(company=company).select_related("customer").prefetch_related("items__product__category")
        if params.get("date_from"):
            invoices = invoices.filter(invoice_date__gte=params["date_from"])
        if params.get("date_to"):
            invoices = invoices.filter(invoice_date__lte=params["date_to"])
        if params.get("customer"):
            invoices = invoices.filter(customer_id=params["customer"])
        if params.get("category"):
            invoices = invoices.filter(items__product__category_id=params["category"])
        invoices = invoices.distinct()

        credits = CreditNote.objects.filter(company=company).exclude(status__in=["draft", "cancelled"])
        if params.get("date_from"):
            credits = credits.filter(issue_date__gte=params["date_from"])
        if params.get("date_to"):
            credits = credits.filter(issue_date__lte=params["date_to"])
        if params.get("customer"):
            credits = credits.filter(customer_id=params["customer"])
        if params.get("category"):
            credits = credits.filter(items__product__category_id=params["category"])
        credits = credits.distinct()

        paid_by_invoice = dict(
            Payment.objects.filter(company=company, status="completed", invoice__in=invoices)
            .values("invoice_id").annotate(total=Sum("amount_received"))
            .values_list("invoice_id", "total")
        )
        credited_by_invoice = dict(
            credits.exclude(invoice__isnull=True).values("invoice_id")
            .annotate(total=Sum("applied_amount")).values_list("invoice_id", "total")
        )
        rows = []
        for invoice in invoices.order_by("-invoice_date", "-id"):
            amount = invoice.subtotal or ZERO
            tax = invoice.total_vat or ZERO
            discount = invoice.discount or ZERO
            net = amount + tax - discount
            paid = paid_by_invoice.get(invoice.id) or ZERO
            credited = credited_by_invoice.get(invoice.id) or ZERO
            if credited >= net or paid + credited >= net:
                report_status = "Paid"
            elif paid + credited > ZERO:
                report_status = "Partial"
            else:
                report_status = "Unpaid"
            rows.append({
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "date": invoice.invoice_date.isoformat(),
                "customer_id": invoice.customer_id,
                "customer": invoice.customer_name or invoice.customer.customer_name,
                "amount": amount,
                "tax_amount": tax,
                "discount": discount,
                "net_amount": net,
                "status": report_status,
                "paid": paid,
                "credited": credited,
                "products_sold": sum((item.quantity for item in invoice.items.all()), ZERO),
            })

        status_filter = params.get("status", "").lower()
        if status_filter in ("paid", "partial", "unpaid"):
            rows = [row for row in rows if row["status"].lower() == status_filter]

        invoice_ids = [row["invoice_id"] for row in rows]
        revenue = sum((row["net_amount"] for row in rows), ZERO)
        selected_credits = sum((cn.credit_amount for cn in credits), ZERO)
        payment_total = Payment.objects.filter(company=company, status="completed", invoice_id__in=invoice_ids).aggregate(total=Sum("amount_received"))["total"] or ZERO
        returned_units = SalesReturnItem.objects.filter(
            sales_return__company=company,
            sales_return__status__in=["approved", "refunded"],
            invoice_item__invoice_id__in=invoice_ids,
        ).aggregate(total=Sum("returning_now_qty"))["total"] or ZERO
        invoiced_units = sum((row["products_sold"] for row in rows), ZERO)

        # Current outstanding is intentionally independent of report filters.
        outstanding = CustomerLedger.objects.filter(company=company).aggregate(
            debit=Sum("debit"), credit=Sum("credit")
        )
        current_owed = max((outstanding["debit"] or ZERO) - (outstanding["credit"] or ZERO), ZERO)

        try:
            year = int(params.get("year", timezone.localdate().year))
        except ValueError:
            return Response({"detail": "year must be a four digit year."}, status=status.HTTP_400_BAD_REQUEST)
        chart_invoices = Invoice.objects.filter(company=company)
        if year:
            chart_invoices = chart_invoices.filter(invoice_date__year=year)
        if params.get("customer"):
            chart_invoices = chart_invoices.filter(customer_id=params["customer"])
        if params.get("category"):
            chart_invoices = chart_invoices.filter(items__product__category_id=params["category"]).distinct()
        chart_credits = CreditNote.objects.filter(company=company).exclude(status__in=["draft", "cancelled"])
        if year:
            chart_credits = chart_credits.filter(issue_date__year=year)
        if params.get("customer"):
            chart_credits = chart_credits.filter(customer_id=params["customer"])
        if params.get("category"):
            chart_credits = chart_credits.filter(items__product__category_id=params["category"]).distinct()
        chart = []
        for month in range(1, 13):
            month_invoices = chart_invoices.filter(invoice_date__month=month)
            # Net is computed per invoice to match the report definition.
            total = sum((inv.subtotal + inv.total_vat - inv.discount for inv in month_invoices), ZERO)
            total -= chart_credits.filter(issue_date__month=month).aggregate(total=Sum("credit_amount"))["total"] or ZERO
            chart.append({
                "month": month,
                "label": calendar.month_abbr[month],
                "revenue": total,
            })

        if params.get("export", "").lower() in ("1", "true", "csv", "excel"):
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="sales-report.csv"'
            writer = csv.writer(response)
            writer.writerow(["Inv No", "Date", "Customer", "Amount", "Tax Amount", "Discount", "Net Amount", "Status"])
            for row in rows:
                writer.writerow([row["invoice_number"], row["date"], row["customer"], row["amount"], row["tax_amount"], row["discount"], row["net_amount"], row["status"]])
            return response

        page = self.pagination_class()
        page_rows = page.paginate_queryset(rows, request, view=self)
        response = page.get_paginated_response(page_rows)
        response.data["summary"] = {
            "total_sales_revenue": revenue - selected_credits,
            "total_invoices": len(rows),
            "products_sold": max(invoiced_units - returned_units, ZERO),
            "payments_received": payment_total,
            "outstanding_receivables": current_owed,
        }
        response.data["chart"] = {"year": year, "months": chart}
        return response
