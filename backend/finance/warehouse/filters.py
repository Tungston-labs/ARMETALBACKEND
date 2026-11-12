import django_filters

from .models import Warehouse
from .utils import compute_capacity_metrics

WAREHOUSE_TYPE_LABEL_MAP = {
    label.lower(): key for key, label in Warehouse.WAREHOUSE_TYPE_CHOICES
}
WAREHOUSE_TYPE_KEY_MAP = {
    key.lower(): key for key, _ in Warehouse.WAREHOUSE_TYPE_CHOICES
}


class WarehouseFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(method="filter_status")
    warehouse_type = django_filters.CharFilter(method="filter_warehouse_type")
    city = django_filters.CharFilter(field_name="city", lookup_expr="iexact")
    country = django_filters.CharFilter(field_name="country", lookup_expr="iexact")
    near_full = django_filters.BooleanFilter(method="filter_near_full")

    class Meta:
        model = Warehouse
        fields = ["status", "warehouse_type", "city", "country"]

    def filter_status(self, queryset, name, value):
        val = (value or "").strip().lower()
        if not val or val == "all":
            return queryset
        return queryset.filter(status__iexact=val)

    def filter_warehouse_type(self, queryset, name, value):
        val = (value or "").strip().lower()
        if not val or val == "all":
            return queryset
        normalized = WAREHOUSE_TYPE_KEY_MAP.get(val) or WAREHOUSE_TYPE_LABEL_MAP.get(val) or val
        return queryset.filter(warehouse_type__iexact=normalized)

    def filter_near_full(self, queryset, name, value):
        if value is None:
            return queryset
        matching_ids = [
            row["id"]
            for row in queryset.values("id", "storage_capacity", "total_units")
            if compute_capacity_metrics(row["total_units"], row["storage_capacity"])["near_full_capacity"] is bool(value)
        ]
        return queryset.filter(id__in=matching_ids)
