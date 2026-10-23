
# reports/tax.py

from datetime import date
from decimal import Decimal

from django.apps import apps
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from user.permissions import IsCompanyActive, IsHRAdmin


ZERO = Decimal("0.00")

SALES_STATUSES = {"paid", "unpaid", "partially_paid"}
PURCHASE_STATUSES = {
    "draft", "unpaid", "partially_paid", "paid", "overdue", "cancelled"
}


def get_model_by_name(model_name):
    """Resolve an installed Django model by its class name."""
    for model in apps.get_models():
        if model.__name__ == model_name:
            return model
    return None


def to_decimal(value):
    return value if value is not None else ZERO


def to_float(value):
    return float(to_decimal(value))


def get_party_name(document, document_type):
    """Use the stored snapshot name first, then the related object."""
    if document_type == "sales":
        snapshot = getattr(document, "customer_name", "")
        related = getattr(document, "customer", None)
        candidates = ("customer_name", "name", "company_name")
    else:
        snapshot = getattr(document, "bill_to_name", "")
        related = getattr(document, "vendor", None)
        candidates = ("name", "vendor_name", "company_name")

    if snapshot:
        return snapshot

    if related:
        for field in candidates:
            value = getattr(related, field, None)
            if value:
                return str(value)

    return ""


def fetch_documents(
    model,
    document_type,
    company_id,
    start_date=None,
    end_date=None,
    customer_id=None,
    vendor_id=None,
    document_status=None,
):
    """Fetch company-scoped sales invoices or purchase bills."""
    if model is None:
        return []

    qs = model.objects.filter(company_id=company_id)

    if document_type == "sales":
        date_field = "invoice_date"
        number_field = "invoice_number"
        status_field = "payment_status"
        relation_field = "customer"
        allowed_statuses = SALES_STATUSES

        if customer_id:
            qs = qs.filter(customer_id=customer_id)

        # A vendor filter excludes sales invoices.
        if vendor_id:
            return []

    else:
        date_field = "bill_date"
        number_field = "bill_number"
        status_field = "status"
        relation_field = "vendor"
        allowed_statuses = PURCHASE_STATUSES

        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)

        # A customer filter excludes purchase bills.
        if customer_id:
            return []

    if start_date:
        qs = qs.filter(**{f"{date_field}__gte": start_date})

    if end_date:
        qs = qs.filter(**{f"{date_field}__lte": end_date})

    if document_status:
        if document_status not in allowed_statuses:
            return []
        qs = qs.filter(**{status_field: document_status})

    qs = qs.select_related(relation_field).order_by(
        f"-{date_field}", "-id"
    )

    rows = []

    for document in qs.iterator():
        doc_date = getattr(document, date_field)
        taxable_amount = to_decimal(
            getattr(document, "subtotal", ZERO)
        )
        tax_amount = to_decimal(
            getattr(document, "total_vat", ZERO)
        )

        rows.append({
            "document_id": document.pk,
            "document_number": getattr(document, number_field),
            "date": doc_date.isoformat() if doc_date else None,
            "type": document_type,
            "customer_vendor": get_party_name(document, document_type),
            "taxable_amount": to_float(taxable_amount),
            "tax_amount": to_float(tax_amount),
            "tax_type": "VAT",
            "status": getattr(document, status_field, ""),
            "_date": doc_date,
            "_taxable": taxable_amount,
            "_tax": tax_amount,
        })

    return rows


def build_monthly_chart(
    Invoice,
    Bill,
    company_id,
    chart_year,
    invoice_type=None,
    customer_id=None,
    vendor_id=None,
    document_status=None,
):
    """Aggregate recorded output and input VAT by document month."""
    sales = fetch_documents(
        model=Invoice,
        document_type="sales",
        company_id=company_id,
        customer_id=customer_id,
        document_status=document_status,
    )

    purchases = fetch_documents(
        model=Bill,
        document_type="purchase",
        company_id=company_id,
        vendor_id=vendor_id,
        document_status=document_status,
    )

    if invoice_type == "sales":
        rows = sales
    elif invoice_type == "purchase":
        rows = purchases
    else:
        rows = sales + purchases

    monthly = {
        month: {
            "output_tax": ZERO,
            "input_tax": ZERO,
        }
        for month in range(1, 13)
    }

    for row in rows:
        doc_date = row["_date"]

        if not doc_date or doc_date.year != chart_year:
            continue

        if row["type"] == "sales":
            monthly[doc_date.month]["output_tax"] += row["_tax"]
        else:
            monthly[doc_date.month]["input_tax"] += row["_tax"]

    return [
        {
            "month": month,
            "month_name": date(chart_year, month, 1).strftime("%b"),
            "output_tax": to_float(monthly[month]["output_tax"]),
            "input_tax": to_float(monthly[month]["input_tax"]),
        }
        for month in range(1, 13)
    ]


class TaxReportView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    def get(self, request):
        company_id = getattr(request.user, "company_id", None)

        if not company_id:
            return Response(
                {"detail": "No company is associated with this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------
        # Query parameters
        # --------------------------------------------------
        start_raw = request.query_params.get("start_date")
        end_raw = request.query_params.get("end_date")
        chart_year_raw = request.query_params.get("chart_year")

        customer_id = request.query_params.get("customer")
        vendor_id = request.query_params.get("vendor")
        invoice_type = request.query_params.get("invoice_type", "").lower()
        tax_type = request.query_params.get("tax_type", "").lower()
        tax_status = request.query_params.get("tax_status", "").lower()

        start_date = parse_date(start_raw) if start_raw else None
        end_date = parse_date(end_raw) if end_raw else None

        if start_raw and not start_date:
            return Response(
                {"detail": "Invalid start_date. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if end_raw and not end_date:
            return Response(
                {"detail": "Invalid end_date. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if start_date and end_date and start_date > end_date:
            return Response(
                {"detail": "start_date cannot be after end_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            chart_year = (
                int(chart_year_raw)
                if chart_year_raw
                else date.today().year
            )
            if not 1900 <= chart_year <= 9998:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"detail": "Invalid chart_year."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if tax_type and tax_type not in {"vat", "gst"}:
            return Response(
                {"detail": "tax_type must be 'vat' or 'gst'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if tax_type == "gst":
            return Response(
                {
                    "detail": (
                        "GST filtering is unavailable because the current "
                        "models only store VAT amounts and have no tax_type "
                        "field. Add tax_type to the models to distinguish VAT "
                        "from GST."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if invoice_type not in {"", "sales", "purchase"}:
            return Response(
                {
                    "detail": (
                        "invoice_type must be 'sales' or 'purchase'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if tax_status and tax_status not in (
            SALES_STATUSES | PURCHASE_STATUSES
        ):
            return Response(
                {
                    "detail": (
                        "Invalid tax_status. Use a document status such as "
                        "paid, unpaid, partially_paid, draft, overdue, "
                        "or cancelled."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        Invoice = get_model_by_name("Invoice")
        Bill = get_model_by_name("Bill")
        Customer = get_model_by_name("Customer")
        Vendor = get_model_by_name("Vendor")

        if Invoice is None or Bill is None:
            return Response(
                {
                    "detail": (
                        "Invoice or Bill model was not found. "
                        "Check that both apps are installed."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # --------------------------------------------------
        # Main table dataset
        # --------------------------------------------------
        sales_rows = fetch_documents(
            model=Invoice,
            document_type="sales",
            company_id=company_id,
            start_date=start_date,
            end_date=end_date,
            customer_id=customer_id,
            vendor_id=vendor_id,
            document_status=tax_status,
        )

        purchase_rows = fetch_documents(
            model=Bill,
            document_type="purchase",
            company_id=company_id,
            start_date=start_date,
            end_date=end_date,
            customer_id=customer_id,
            vendor_id=vendor_id,
            document_status=tax_status,
        )

        if invoice_type == "sales":
            rows = sales_rows
        elif invoice_type == "purchase":
            rows = purchase_rows
        else:
            rows = sales_rows + purchase_rows

        rows.sort(
            key=lambda row: (
                row["_date"] or date.min,
                row["document_id"],
            ),
            reverse=True,
        )

        # --------------------------------------------------
        # Summary cards: use the same date/party/status filters
        # --------------------------------------------------
        output_tax = sum(
            (row["_tax"] for row in rows if row["type"] == "sales"),
            ZERO,
        )
        input_tax_credit = sum(
            (row["_tax"] for row in rows if row["type"] == "purchase"),
            ZERO,
        )
        taxable_sales = sum(
            (row["_taxable"] for row in rows if row["type"] == "sales"),
            ZERO,
        )

        # --------------------------------------------------
        # Monthly chart: chart_year is independent of table dates
        # --------------------------------------------------
        monthly_data = build_monthly_chart(
            Invoice=Invoice,
            Bill=Bill,
            company_id=company_id,
            chart_year=chart_year,
            invoice_type=invoice_type or None,
            customer_id=customer_id,
            vendor_id=vendor_id,
            document_status=tax_status,
        )

        # --------------------------------------------------
        # Pagination
        # --------------------------------------------------
        try:
            page_size = int(request.query_params.get("page_size", 10))
            if page_size < 1:
                raise ValueError
            page_size = min(page_size, 100)
        except (TypeError, ValueError):
            return Response(
                {"detail": "page_size must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paginator = Paginator(rows, page_size)

        try:
            page_obj = paginator.page(request.query_params.get("page", 1))
        except (EmptyPage, PageNotAnInteger):
            return Response(
                {"detail": "Invalid page number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        public_rows = [
            {
                key: value
                for key, value in row.items()
                if not key.startswith("_")
            }
            for row in page_obj.object_list
        ]

        # --------------------------------------------------
        # Dropdown options, scoped to current company
        # --------------------------------------------------
        customer_options = []
        if Customer is not None:
            customer_options = list(
                Customer.objects.filter(company_id=company_id)
                .order_by("customer_name")
                .values("id", "customer_id", "customer_name")
            )

        vendor_options = []
        if Vendor is not None:
            vendor_options = list(
                Vendor.objects.filter(company_id=company_id)
                .order_by("name")
                .values("id", "vendor_id", "name")
            )

        return Response(
            {
                "cards": {
                    "total_tax_collected": to_float(output_tax),
                    "input_tax_credit": to_float(input_tax_credit),
                    "net_tax_payable": to_float(
                        output_tax - input_tax_credit
                    ),
                    "taxable_sales": to_float(taxable_sales),
                },
                "filters": {
                    "tax_types": [
                        {"value": "vat", "label": "VAT"},
                    ],
                    "invoice_types": [
                        {"value": "sales", "label": "Sales Invoice"},
                        {"value": "purchase", "label": "Purchase Bill"},
                    ],
                    "customers": customer_options,
                    "vendors": vendor_options,
                    "tax_statuses": [
                        {"value": "paid", "label": "Paid"},
                        {"value": "unpaid", "label": "Unpaid"},
                        {
                            "value": "partially_paid",
                            "label": "Partially Paid",
                        },
                        {"value": "draft", "label": "Draft"},
                        {"value": "overdue", "label": "Overdue"},
                        {"value": "cancelled", "label": "Cancelled"},
                    ],
                    "note": (
                        "Status filter uses existing document payment/status "
                        "fields; it is not a separate tax-status field."
                    ),
                },
                "monthly_tax": {
                    "year": chart_year,
                    "data": monthly_data,
                },
                "table": {
                    "count": paginator.count,
                    "page": page_obj.number,
                    "page_size": page_size,
                    "total_pages": paginator.num_pages,
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
                    "results": public_rows,
                },
            },
            status=status.HTTP_200_OK,
        )
