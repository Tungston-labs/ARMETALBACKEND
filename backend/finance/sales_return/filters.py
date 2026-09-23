import django_filters
from .models import SalesReturn


class SalesReturnFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    reason = django_filters.CharFilter(field_name="reason", lookup_expr="exact")
    customer = django_filters.NumberFilter(field_name="customer_id")
    start_date = django_filters.DateFilter(field_name="return_date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="return_date", lookup_expr="lte")

    class Meta:
        model = SalesReturn
        fields = ["status", "reason", "customer", "start_date", "end_date"]
