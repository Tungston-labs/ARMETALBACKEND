import re
from collections.abc import Mapping
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from .models import Warehouse
from .utils import (
    ZERO_DECIMAL,
    compute_capacity_metrics,
    generate_next_warehouse_code,
    resolve_request_company,
)

STATUS_VALUE_MAP = {
    **{key.lower(): key for key, _ in Warehouse.STATUS_CHOICES},
    **{label.lower(): key for key, label in Warehouse.STATUS_CHOICES},
}

WAREHOUSE_TYPE_VALUE_MAP = {
    **{key.lower(): key for key, _ in Warehouse.WAREHOUSE_TYPE_CHOICES},
    **{label.lower(): key for key, label in Warehouse.WAREHOUSE_TYPE_CHOICES},
}

NON_NULLABLE_STRING_FIELDS = (
    "manager",
    "country",
    "city",
    "address_line_1",
    "address_line_2",
    "postal_code",
    "phone_number",
    "email",
    "storage_capacity",
    "notes",
)


class WarehouseSerializer(serializers.ModelSerializer):
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    manager = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    country = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    address_line_1 = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    address_line_2 = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True, allow_null=True)
    storage_capacity = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    operating_since = serializers.DateField(
        required=False,
        allow_null=True,
        input_formats=["iso-8601", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"],
    )

    manager_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()

    total_units = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True,
    )
    stock_value = serializers.DecimalField(
        max_digits=32,
        decimal_places=2,
        read_only=True,
    )
    total_products = serializers.IntegerField(read_only=True)
    stock_quantity = serializers.SerializerMethodField()
    low_stock_products = serializers.IntegerField(read_only=True)
    out_of_stock_products = serializers.IntegerField(read_only=True)
    capacity_limit = serializers.SerializerMethodField()
    capacity_used_percentage = serializers.SerializerMethodField()
    capacity_used = serializers.SerializerMethodField()
    near_full_capacity = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = [
            "id",
            "company",
            "company_name",
            "currency",
            "code",
            "warehouse_name",
            "warehouse_type",
            "manager",
            "manager_name",
            "status",
            "operating_since",
            "country",
            "city",
            "location",
            "address_line_1",
            "address_line_2",
            "postal_code",
            "phone_number",
            "email",
            "storage_capacity",
            "capacity_limit",
            "notes",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "total_units",
            "stock_value",
            "total_products",
            "stock_quantity",
            "low_stock_products",
            "out_of_stock_products",
            "capacity_used_percentage",
            "capacity_used",
            "near_full_capacity",
        ]
        read_only_fields = [
            "id",
            "company",
            "company_name",
            "currency",
            "manager_name",
            "location",
            "capacity_limit",
            "total_units",
            "stock_value",
            "total_products",
            "stock_quantity",
            "low_stock_products",
            "out_of_stock_products",
            "capacity_used_percentage",
            "capacity_used",
            "near_full_capacity",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def _get_product_aggregates(self, obj):
        cached = getattr(obj, "_cached_warehouse_metrics", None)
        if cached is not None:
            return cached

        if (
            hasattr(obj, "total_units")
            and hasattr(obj, "stock_value")
            and hasattr(obj, "total_products")
            and hasattr(obj, "low_stock_products")
            and hasattr(obj, "out_of_stock_products")
        ):
            total_units = obj.total_units if obj.total_units is not None else ZERO_DECIMAL
            stock_value = obj.stock_value if obj.stock_value is not None else ZERO_DECIMAL
            total_products = obj.total_products or 0
            low_stock_products = obj.low_stock_products or 0
            out_of_stock_products = obj.out_of_stock_products or 0
        elif getattr(obj, "pk", None):
            agg = obj.products.filter(product_type="product").aggregate(
                total_units=Coalesce(
                    Sum("current_stock"),
                    Value(ZERO_DECIMAL),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                ),
                stock_value=Coalesce(
                    Sum(
                        ExpressionWrapper(
                            F("current_stock") * F("cost_price"),
                            output_field=DecimalField(max_digits=24, decimal_places=4),
                        )
                    ),
                    Value(ZERO_DECIMAL),
                    output_field=DecimalField(max_digits=32, decimal_places=4),
                ),
                total_products=Count("id"),
                low_stock_products=Count(
                    "id",
                    filter=(
                        Q(current_stock__gt=0)
                        & (Q(current_stock__lt=10) | Q(current_stock__lt=F("reorder_level")))
                    ),
                ),
                out_of_stock_products=Count(
                    "id",
                    filter=Q(current_stock__lte=0),
                ),
            )
            total_units = agg["total_units"] or ZERO_DECIMAL
            stock_value = agg["stock_value"] or ZERO_DECIMAL
            total_products = agg["total_products"] or 0
            low_stock_products = agg["low_stock_products"] or 0
            out_of_stock_products = agg["out_of_stock_products"] or 0
        else:
            total_units = ZERO_DECIMAL
            stock_value = ZERO_DECIMAL
            total_products = 0
            low_stock_products = 0
            out_of_stock_products = 0

        result = {
            "total_units": total_units,
            "stock_value": stock_value,
            "total_products": total_products,
            "low_stock_products": low_stock_products,
            "out_of_stock_products": out_of_stock_products,
        }
        obj._cached_warehouse_metrics = result
        return result

    def _get_capacity_metrics(self, obj):
        cached = getattr(obj, "_cached_capacity_metrics", None)
        if cached is not None:
            return cached
        total_units = self._get_product_aggregates(obj)["total_units"]
        metrics = compute_capacity_metrics(total_units, obj.storage_capacity)
        obj._cached_capacity_metrics = metrics
        return metrics

    def to_representation(self, instance):
        metrics = self._get_product_aggregates(instance)
        for key, value in metrics.items():
            if not hasattr(instance, key):
                setattr(instance, key, value)
        return super().to_representation(instance)

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            data = data.copy()
            if data.get("operating_since") == "":
                data["operating_since"] = None

            raw_status = data.get("status")
            if isinstance(raw_status, str):
                mapped_status = STATUS_VALUE_MAP.get(raw_status.strip().lower())
                if mapped_status is not None:
                    data["status"] = mapped_status

            raw_type = data.get("warehouse_type")
            if isinstance(raw_type, str):
                mapped_type = WAREHOUSE_TYPE_VALUE_MAP.get(raw_type.strip().lower())
                if mapped_type is not None:
                    data["warehouse_type"] = mapped_type

        return super().to_internal_value(data)

    def get_manager_name(self, obj):
        return obj.manager if obj.manager else ""

    def get_created_by_name(self, obj):
        if obj.created_by:
            full_name = obj.created_by.get_full_name().strip()
            return full_name if full_name else obj.created_by.username
        return None

    def get_company_name(self, obj):
        if obj.company:
            return getattr(obj.company, "name", str(obj.company))
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_currency(self, obj):
        if obj.company:
            return getattr(obj.company, "currency", None) or "SAR"
        return "SAR"

    @extend_schema_field(OpenApiTypes.STR)
    def get_location(self, obj):
        city = (obj.city or "").strip()
        if city:
            return city
        return (obj.country or "").strip()

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_stock_quantity(self, obj):
        return self._get_product_aggregates(obj)["total_units"]

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_capacity_limit(self, obj):
        return self._get_capacity_metrics(obj)["capacity_limit"]

    @extend_schema_field(OpenApiTypes.INT)
    def get_capacity_used_percentage(self, obj):
        return self._get_capacity_metrics(obj)["capacity_used_percentage"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_capacity_used(self, obj):
        return self._get_capacity_metrics(obj)["capacity_used"]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_near_full_capacity(self, obj):
        return self._get_capacity_metrics(obj)["near_full_capacity"]

    def validate(self, attrs):
        for field_name in NON_NULLABLE_STRING_FIELDS:
            if field_name in attrs and attrs[field_name] is None:
                attrs[field_name] = ""

        if "storage_capacity" in attrs and attrs["storage_capacity"]:
            raw_capacity = str(attrs["storage_capacity"]).strip()
            if re.match(r"^-\s*\d", raw_capacity):
                raise serializers.ValidationError(
                    {"storage_capacity": "Storage capacity cannot be negative."}
                )

        request = self.context.get("request")
        company = getattr(self.instance, "company", None) or resolve_request_company(request)

        raw_code = attrs.get("code")
        code = raw_code.strip() if isinstance(raw_code, str) else raw_code

        if not self.instance:
            if not code:
                code = generate_next_warehouse_code(company)
            attrs["code"] = code
        elif "code" in attrs:
            attrs["code"] = code if code else self.instance.code

        check_code = attrs.get("code")
        if check_code and company:
            qs = Warehouse.objects.filter(company=company, code=check_code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"code": f"A warehouse with code '{check_code}' already exists for your company."}
                )

        return attrs
