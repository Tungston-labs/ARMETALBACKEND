import django_filters
from .models import Bill


class BillFilter(django_filters.FilterSet):
    vendor = django_filters.NumberFilter(field_name="vendor_id")
    status = django_filters.CharFilter(field_name="status")

    due_date = django_filters.DateFilter(field_name="due_date")
    due_date_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_before = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")

    bill_date = django_filters.DateFilter(field_name="bill_date")
    start_date = django_filters.DateFilter(field_name="bill_date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="bill_date", lookup_expr="lte")
    bill_date_after = django_filters.DateFilter(field_name="bill_date", lookup_expr="gte")
    bill_date_before = django_filters.DateFilter(field_name="bill_date", lookup_expr="lte")

    po_reference = django_filters.CharFilter(field_name="po_reference", lookup_expr="icontains")

    class Meta:
        model = Bill
        fields = [
            "vendor",
            "status",
            "due_date",
            "due_date_after",
            "due_date_before",
            "bill_date",
            "start_date",
            "end_date",
            "bill_date_after",
            "bill_date_before",
            "po_reference",
        ]
