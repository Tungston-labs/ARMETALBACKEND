import csv
import io
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import openpyxl
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse

from .models import Warehouse

NEAR_FULL_CAPACITY_THRESHOLD = Decimal("80")
ZERO_DECIMAL = Decimal("0.00")


def generate_next_warehouse_code(company):
    """
    Generates the next sequential warehouse code for a given company.
    Example sequence: WH-001, WH-002, WH-003, ..., WH-010, WH-100.
    """
    if company is None:
        qs = Warehouse.objects.filter(company__isnull=True)
    else:
        qs = Warehouse.objects.filter(company=company)

    existing_codes = qs.values_list("code", flat=True)

    max_num = 0
    pattern = re.compile(r"^WH-(\d+)$", re.IGNORECASE)

    for code in existing_codes:
        if code:
            match = pattern.match(code.strip())
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass

    next_num = max_num + 1
    return f"WH-{next_num:03d}"


def resolve_request_company(request):
    """
    Resolves the target Company for the current request, supporting superadmin
    optional `?company=<id>` scoping.
    """
    if not request or not hasattr(request, "user"):
        return None
    user = request.user
    company = getattr(user, "company", None)
    if company is not None:
        return company
    if getattr(user, "is_superadmin", False):
        company_id = request.query_params.get("company") if hasattr(request, "query_params") else None
        if company_id:
            from superadmin.models import Company
            return Company.objects.filter(id=company_id).first()
    return None


def get_scoped_warehouse_queryset(request):
    """
    Returns the base Warehouse queryset scoped to the authenticated user's company
    (or all / `?company=<id>` for superadmins).
    """
    user = request.user
    if getattr(user, "is_superadmin", False):
        company_id = request.query_params.get("company")
        if company_id:
            return Warehouse.objects.filter(company_id=company_id)
        return Warehouse.objects.all()
    if hasattr(user, "company") and user.company:
        return Warehouse.objects.filter(company=user.company)
    return Warehouse.objects.none()


def annotate_warehouse_queryset(qs):
    """
    Annotates a Warehouse queryset with aggregated `total_units`, `stock_value`,
    and product stock status counts for physical products (`product_type='product'`).
    """
    return qs.select_related("created_by", "company").annotate(
        total_units=Coalesce(
            Sum(
                "products__current_stock",
                filter=Q(products__product_type="product"),
            ),
            Value(ZERO_DECIMAL),
            output_field=DecimalField(max_digits=20, decimal_places=2),
        ),
        stock_value=Coalesce(
            Sum(
                ExpressionWrapper(
                    F("products__current_stock") * F("products__cost_price"),
                    output_field=DecimalField(max_digits=24, decimal_places=4),
                ),
                filter=Q(products__product_type="product"),
            ),
            Value(ZERO_DECIMAL),
            output_field=DecimalField(max_digits=32, decimal_places=4),
        ),
        total_products=Count(
            "products",
            filter=Q(products__product_type="product"),
            distinct=True,
        ),
        low_stock_products=Count(
            "products",
            filter=(
                Q(products__product_type="product", products__current_stock__gt=0)
                & (
                    Q(products__current_stock__lt=10)
                    | Q(products__current_stock__lt=F("products__reorder_level"))
                )
            ),
            distinct=True,
        ),
        out_of_stock_products=Count(
            "products",
            filter=Q(products__product_type="product", products__current_stock__lte=0),
            distinct=True,
        ),
    )


def parse_storage_capacity(raw_value):
    """
    Extracts a positive numeric storage capacity from `storage_capacity`
    (e.g. '400', 400, '1,200', '400 units'). Returns None if unset or <= 0.
    """
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    cleaned = text.replace(",", "")
    match = re.match(r"^(\d+(?:\.\d+)?)(?:\s*[a-zA-Z]*)$", cleaned)
    if not match:
        return None
    try:
        value = Decimal(match.group(1))
    except (InvalidOperation, ValueError):
        return None
    return value if value > Decimal("0") else None


def format_compact_decimal(value):
    """
    Formats a Decimal cleanly without trailing `.00` when integral and without
    scientific notation (e.g. Decimal('400.00') -> '400', Decimal('304.50') -> '304.5').
    """
    dec = Decimal(value or 0)
    if dec == dec.to_integral_value():
        return str(int(dec))
    return format(dec, "f").rstrip("0").rstrip(".")


def compute_capacity_metrics(total_units, storage_capacity):
    """
    Computes capacity limit, percentage used, formatted display string
    (e.g. '76% (304/400)'), and near-full-capacity flag (>= 80%).
    """
    units = Decimal(total_units or 0)
    capacity = parse_storage_capacity(storage_capacity)
    if capacity is None:
        return {
            "capacity_limit": None,
            "capacity_used_percentage": 0,
            "capacity_used": "",
            "near_full_capacity": False,
        }

    pct_exact = (units / capacity) * Decimal("100")
    pct_rounded = int(pct_exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    limit_value = (
        int(capacity)
        if capacity == capacity.to_integral_value()
        else float(capacity)
    )
    return {
        "capacity_limit": limit_value,
        "capacity_used_percentage": pct_rounded,
        "capacity_used": (
            f"{pct_rounded}% ({format_compact_decimal(units)}/{format_compact_decimal(capacity)})"
        ),
        "near_full_capacity": pct_exact >= NEAR_FULL_CAPACITY_THRESHOLD,
    }


def calculate_warehouse_kpis(scoped_qs, company=None):
    """
    Calculates all Warehouse KPI summary metrics from a company-scoped
    (unannotated) Warehouse queryset in a single database query.
    """
    rows = list(
        annotate_warehouse_queryset(scoped_qs).values(
            "id",
            "status",
            "storage_capacity",
            "total_units",
            "stock_value",
            "company__currency",
        )
    )

    total_warehouses = len(rows)
    active_warehouses = 0
    inactive_warehouses = 0
    total_stock_value = ZERO_DECIMAL
    total_units_with_capacity = ZERO_DECIMAL
    total_capacity = ZERO_DECIMAL
    near_full_capacity = 0

    for row in rows:
        if row["status"] == "active":
            active_warehouses += 1
        elif row["status"] == "inactive":
            inactive_warehouses += 1

        total_stock_value += row["stock_value"] or ZERO_DECIMAL

        units = row["total_units"] or ZERO_DECIMAL
        capacity = parse_storage_capacity(row["storage_capacity"])
        if capacity is not None:
            total_units_with_capacity += units
            total_capacity += capacity
            if (units / capacity) * Decimal("100") >= NEAR_FULL_CAPACITY_THRESHOLD:
                near_full_capacity += 1

    total_stock_value = total_stock_value.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if total_capacity > Decimal("0"):
        avg_pct = (total_units_with_capacity / total_capacity) * Decimal("100")
        average_capacity_used = int(
            avg_pct.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
    else:
        average_capacity_used = 0

    currency = getattr(company, "currency", None) if company else None
    if not currency and rows:
        currency = rows[0].get("company__currency")
    currency = currency or "SAR"

    return {
        "currency": currency,
        "total_warehouses": total_warehouses,
        "active_warehouses": active_warehouses,
        "inactive_warehouses": inactive_warehouses,
        "total_stock_value": total_stock_value,
        "average_capacity_used": average_capacity_used,
        "near_full_capacity": near_full_capacity,
    }


WAREHOUSE_EXPORT_HEADERS = [
    "Code",
    "Warehouse",
    "Warehouse Type",
    "Location",
    "Manager",
    "Total Units",
    "Stock Value",
    "Storage Capacity",
    "Capacity Used",
    "Status",
    "Operating Since",
    "Country",
    "City",
    "Phone Number",
    "Email",
]


def _warehouse_export_row(warehouse):
    total_units = getattr(warehouse, "total_units", None)
    if total_units is None:
        total_units = ZERO_DECIMAL
    stock_value = getattr(warehouse, "stock_value", None)
    if stock_value is None:
        stock_value = ZERO_DECIMAL

    stock_value_rounded = Decimal(stock_value).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    capacity_metrics = compute_capacity_metrics(total_units, warehouse.storage_capacity)
    location = (warehouse.city or "").strip() or (warehouse.country or "").strip()

    return [
        warehouse.code,
        warehouse.warehouse_name,
        warehouse.get_warehouse_type_display(),
        location,
        warehouse.manager or "",
        format_compact_decimal(total_units),
        f"{stock_value_rounded:.2f}",
        warehouse.storage_capacity or "",
        capacity_metrics["capacity_used"],
        warehouse.get_status_display(),
        warehouse.operating_since.isoformat() if warehouse.operating_since else "",
        warehouse.country or "",
        warehouse.city or "",
        warehouse.phone_number or "",
        warehouse.email or "",
    ]


def build_warehouse_export_response(queryset, export_format="csv"):
    """
    Generates a CSV or XLSX HttpResponse for the filtered warehouse queryset.
    """
    fmt = (export_format or "csv").lower().strip()
    rows = [_warehouse_export_row(wh) for wh in queryset]

    if fmt == "xlsx":
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "Warehouses"
        worksheet.append(WAREHOUSE_EXPORT_HEADERS)
        for row in rows:
            worksheet.append(row)

        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="warehouses.xlsx"'
        return response

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="warehouses.csv"'
    writer = csv.writer(response)
    writer.writerow(WAREHOUSE_EXPORT_HEADERS)
    for row in rows:
        writer.writerow(row)
    return response
