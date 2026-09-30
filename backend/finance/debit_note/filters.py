import django_filters
from .models import DebitNote


class DebitNoteFilter(django_filters.FilterSet):
    vendor = django_filters.NumberFilter(field_name="vendor_id")
    bill = django_filters.NumberFilter(field_name="bill_id")
    status = django_filters.CharFilter(field_name="status")
    reason = django_filters.CharFilter(field_name="reason")

    issue_date = django_filters.DateFilter(field_name="issue_date")
    start_date = django_filters.DateFilter(field_name="issue_date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="issue_date", lookup_expr="lte")
    issue_date_after = django_filters.DateFilter(field_name="issue_date", lookup_expr="gte")
    issue_date_before = django_filters.DateFilter(field_name="issue_date", lookup_expr="lte")

    bill_ref = django_filters.CharFilter(field_name="bill_ref", lookup_expr="icontains")

    class Meta:
        model = DebitNote
        fields = [
            "vendor",
            "bill",
            "status",
            "reason",
            "issue_date",
            "start_date",
            "end_date",
            "issue_date_after",
            "issue_date_before",
            "bill_ref",
        ]
