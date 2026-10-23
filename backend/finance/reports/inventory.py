
# reports/inventory.py

from datetime import date
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db.models import (
    Case,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import TruncMonth
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.product.models import Product
from finance.category.models import Category
from finance.warehouse.models import Warehouse

from user.permissions import IsCompanyActive, IsHRAdmin


class InventoryPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


def get_stock_adjustment_model():
    """
    Find StockAdjustment regardless of its installed app label.
    """
    for model in apps.get_models():
        if model.__name__ == "StockAdjustment":
            return model

    raise ImproperlyConfigured(
        "StockAdjustment model was not found in installed Django apps."
    )


def decimal_to_float(value):
    if value is None:
        return 0.0
    return float(value)


def get_stock_status(product):
    if product.product_type == "service":
        return "Service"

    if product.current_stock <= 0:
        return "Out of Stock"

    if product.current_stock <= product.reorder_level:
        return "Low Stock"

    return "In Stock"


class InventoryReportView(APIView):
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
        start_date_raw = request.query_params.get("start_date")
        end_date_raw = request.query_params.get("end_date")
        chart_year_raw = request.query_params.get("chart_year")

        warehouse_id = request.query_params.get("warehouse")
        category_id = request.query_params.get("category")
        product_id = request.query_params.get("product")
        product_type = request.query_params.get("product_type")
        search = request.query_params.get("search", "").strip()

        start_date = parse_date(start_date_raw) if start_date_raw else None
        end_date = parse_date(end_date_raw) if end_date_raw else None

        if start_date_raw and not start_date:
            return Response(
                {"detail": "Invalid start_date. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if end_date_raw and not end_date:
            return Response(
                {"detail": "Invalid end_date. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if start_date and end_date and start_date > end_date:
            return Response(
                {"detail": "start_date cannot be after end_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if chart_year_raw:
            try:
                chart_year = int(chart_year_raw)
                if not 1900 <= chart_year <= 9998:
                    raise ValueError
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Invalid chart_year."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            chart_year = date.today().year

        # --------------------------------------------------
        # Current inventory queryset
        # --------------------------------------------------
        products = Product.objects.filter(
            company_id=company_id
        ).select_related("category", "warehouse")

        if warehouse_id:
            products = products.filter(warehouse_id=warehouse_id)

        if category_id:
            products = products.filter(category_id=category_id)

        if product_id:
            products = products.filter(id=product_id)

        if product_type:
            if product_type not in ("product", "service"):
                return Response(
                    {
                        "detail": (
                            "Invalid product_type. "
                            "Choose 'product' or 'service'."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            products = products.filter(product_type=product_type)

        if search:
            products = products.filter(
                Q(code__icontains=search)
                | Q(product_name__icontains=search)
                | Q(sku__icontains=search)
            )

        # Inventory valuation uses cost price, not selling price.
        inventory_products = products.filter(product_type="product")

        # --------------------------------------------------
        # Summary cards
        # --------------------------------------------------
        total_products = products.count()

        inventory_summary = inventory_products.aggregate(
            total_stock_quantity=Sum("current_stock"),
            inventory_value=Sum(
                ExpressionWrapper(
                    F("current_stock") * F("cost_price"),
                    output_field=DecimalField(
                        max_digits=24,
                        decimal_places=2,
                    ),
                )
            ),
        )

        total_stock_quantity = (
            inventory_summary["total_stock_quantity"] or Decimal("0")
        )
        inventory_value = (
            inventory_summary["inventory_value"] or Decimal("0")
        )

        low_stock_items = inventory_products.filter(
            current_stock__gt=0,
            current_stock__lte=F("reorder_level"),
        ).count()

        out_of_stock_items = inventory_products.filter(
            current_stock__lte=0,
        ).count()

        # --------------------------------------------------
        # Paginated inventory table
        # --------------------------------------------------
        paginator = InventoryPagination()
        page = paginator.paginate_queryset(
            products.order_by("product_name", "id"),
            request,
            view=self,
        )

        table_rows = []

        for product in page:
            available_qty = product.current_stock - product.reserved_qty

            # Stock value is physical stock * unit cost.
            product_inventory_value = (
                product.current_stock * product.cost_price
                if product.product_type == "product"
                else Decimal("0")
            )

            table_rows.append(
                {
                    "id": product.id,
                    "code": product.code,
                    "sku": product.sku,
                    "product_name": product.product_name,
                    "product_type": product.product_type,
                    "category": (
                        {
                            "id": product.category_id,
                            "name": product.category.category_name,
                        }
                        if product.category_id
                        else None
                    ),
                    "warehouse": (
                        {
                            "id": product.warehouse_id,
                            "name": product.warehouse.warehouse_name,
                        }
                        if product.warehouse_id
                        else None
                    ),
                    "available_qty": decimal_to_float(available_qty),
                    "current_stock": decimal_to_float(product.current_stock),
                    "reserved_qty": decimal_to_float(product.reserved_qty),
                    "reorder_level": product.reorder_level,
                    "cost_price": decimal_to_float(product.cost_price),
                    "inventory_value": decimal_to_float(
                        product_inventory_value
                    ),
                    "stock_status": get_stock_status(product),
                }
            )

        # --------------------------------------------------
        # Monthly inventory movement chart
        # Uses actual stock change from each adjustment:
        # adjusted_stock - current_available_qty.
        #
        # Chart values are estimated at current product cost.
        # --------------------------------------------------
        StockAdjustment = get_stock_adjustment_model()

        movements = StockAdjustment.objects.filter(
            company_id=company_id,
            adjustment_date__year=chart_year,
        ).select_related("product")

        if start_date:
            movements = movements.filter(
                adjustment_date__gte=start_date
            )

        if end_date:
            movements = movements.filter(
                adjustment_date__lte=end_date
            )

        if warehouse_id:
            movements = movements.filter(
                warehouse_id=warehouse_id
            )

        if category_id:
            movements = movements.filter(
                product__category_id=category_id
            )

        if product_id:
            movements = movements.filter(
                product_id=product_id
            )

        if product_type:
            movements = movements.filter(
                product__product_type=product_type
            )

        if search:
            movements = movements.filter(
                Q(product__code__icontains=search)
                | Q(product__product_name__icontains=search)
                | Q(product__sku__icontains=search)
            )

        movements = movements.annotate(
            stock_delta=ExpressionWrapper(
                F("adjusted_stock") - F("current_available_qty"),
                output_field=DecimalField(
                    max_digits=20,
                    decimal_places=2,
                ),
            )
        ).annotate(
            movement_value=ExpressionWrapper(
                F("stock_delta") * F("product__cost_price"),
                output_field=DecimalField(
                    max_digits=24,
                    decimal_places=2,
                ),
            )
        )

        monthly_rows = (
            movements.annotate(month=TruncMonth("adjustment_date"))
            .values("month")
            .annotate(
                added_value=Sum(
                    Case(
                        When(
                            stock_delta__gt=0,
                            then=F("movement_value"),
                        ),
                        default=Value(Decimal("0.00")),
                        output_field=DecimalField(
                            max_digits=24,
                            decimal_places=2,
                        ),
                    )
                ),
                reduced_value=Sum(
                    Case(
                        When(
                            stock_delta__lt=0,
                            then=ExpressionWrapper(
                                F("movement_value") * Value(-1),
                                output_field=DecimalField(
                                    max_digits=24,
                                    decimal_places=2,
                                ),
                            ),
                        ),
                        default=Value(Decimal("0.00")),
                        output_field=DecimalField(
                            max_digits=24,
                            decimal_places=2,
                        ),
                    )
                ),
            )
            .order_by("month")
        )

        monthly_lookup = {
            row["month"].month: row
            for row in monthly_rows
            if row["month"] is not None
        }

        monthly_chart = []

        for month in range(1, 13):
            row = monthly_lookup.get(month, {})

            monthly_chart.append(
                {
                    "month": month,
                    "month_name": date(chart_year, month, 1).strftime("%b"),
                    "added_value": decimal_to_float(
                        row.get("added_value")
                    ),
                    "reduced_value": decimal_to_float(
                        row.get("reduced_value")
                    ),
                }
            )

        # --------------------------------------------------
        # Filter dropdown options, scoped to this company
        # --------------------------------------------------
        categories = Category.objects.filter(
            company_id=company_id,
            category_type="product",
        ).order_by("category_name").values(
            "id", "code", "category_name"
        )

        warehouses = Warehouse.objects.filter(
            company_id=company_id,
        ).order_by("warehouse_name").values(
            "id", "code", "warehouse_name"
        )

        product_options = Product.objects.filter(
            company_id=company_id,
            product_type="product",
        ).order_by("product_name").values(
            "id", "code", "product_name"
        )

        response_data = {
            "cards": {
                "total_products": total_products,
                "inventory_value": decimal_to_float(inventory_value),
                "low_stock_items": low_stock_items,
                "out_of_stock_items": out_of_stock_items,
                "total_stock_quantity": decimal_to_float(
                    total_stock_quantity
                ),
            },
            "filters": {
                "categories": list(categories),
                "warehouses": list(warehouses),
                "products": list(product_options),
                "product_types": [
                    {"value": "product", "label": "Product"},
                    {"value": "service", "label": "Service"},
                ],
            },
            "monthly_inventory_movement": {
                "year": chart_year,
                "valuation_basis": "current_product_cost_price",
                "estimated": True,
                "data": monthly_chart,
            },
            "table": {
                "count": paginator.page.paginator.count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": table_rows,
            },
        }

        return Response(response_data, status=status.HTTP_200_OK)
