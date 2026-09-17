
import django_filters

from .models import Invoice


class InvoiceFilter(django_filters.FilterSet):

    due_date = django_filters.DateFilter(
        field_name="due_date"
    )

    due_date_after = django_filters.DateFilter(
        field_name="due_date",
        lookup_expr="gte"
    )

    due_date_before = django_filters.DateFilter(
        field_name="due_date",
        lookup_expr="lte"
    )

    customer = django_filters.NumberFilter(
        field_name="customer_id"
    )

    payment_status = django_filters.CharFilter(
        field_name="payment_status"
    )

    class Meta:
        model = Invoice

        fields = [
            "due_date",
            "due_date_after",
            "due_date_before",
            "customer",
            "payment_status",
        ]
