import csv
import io
import re
from decimal import Decimal

import openpyxl
from django.http import HttpResponse


def generate_next_quote_number(company):
    """
    Generates auto-incremented quote number per company, e.g. QUT-001, QUT-002.
    """
    from .models import Quotation

    if not company:
        return "QUT-001"

    last_quote = (
        Quotation.objects.filter(company=company)
        .order_by("-id")
        .first()
    )

    if last_quote and last_quote.quote_number:
        numbers = re.findall(r"\d+", last_quote.quote_number)
        if numbers:
            last_num = int(numbers[-1])
        else:
            last_num = 0
        next_num = last_num + 1
    else:
        next_num = 1

    return f"QUT-{next_num:03d}"


QUOTATION_EXPORT_HEADERS = [
    "Quote No.",
    "Customer",
    "Issue Date",
    "Valid Till",
    "Old Quote Amt",
    "Negotiation Amount",
    "Quote Value",
    "Status",
]


def _quotation_export_row(quotation):
    customer_name = (
        getattr(quotation.customer, "customer_name", None)
        or quotation.bill_to_name
        or ""
    )
    old_amt = (
        f"{Decimal(quotation.old_quote_amount):.2f}"
        if quotation.old_quote_amount is not None
        else ""
    )
    neg_amt = (
        f"{Decimal(quotation.negotiation_amount):.2f}"
        if quotation.negotiation_amount is not None
        else "0.00"
    )
    quote_amt = (
        f"{Decimal(quotation.quote_amount):.2f}"
        if quotation.quote_amount is not None
        else "0.00"
    )
    return [
        quotation.quote_number or "",
        customer_name,
        quotation.issue_date.isoformat() if quotation.issue_date else "",
        quotation.valid_till.isoformat() if quotation.valid_till else "",
        old_amt,
        neg_amt,
        quote_amt,
        quotation.get_status_display(),
    ]


def build_quotation_export_response(queryset, export_format="csv"):
    """
    Generates a CSV or XLSX HttpResponse for the filtered quotation queryset.
    """
    fmt = (export_format or "csv").lower().strip()
    rows = [_quotation_export_row(q) for q in queryset]

    if fmt == "xlsx":
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "Quotations"
        worksheet.append(QUOTATION_EXPORT_HEADERS)
        for row in rows:
            worksheet.append(row)

        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="quotations.xlsx"'
        return response

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="quotations.csv"'
    writer = csv.writer(response)
    writer.writerow(QUOTATION_EXPORT_HEADERS)
    for row in rows:
        writer.writerow(row)
    return response
