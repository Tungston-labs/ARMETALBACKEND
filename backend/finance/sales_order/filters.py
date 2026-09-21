import django_filters

from .models import SalesOrder


class SalesOrderFilter(django_filters.FilterSet):

    customer = django_filters.NumberFilter(
        field_name="customer_id"
    )

    quotation = django_filters.NumberFilter(
        field_name="quotation_id"
    )

    warehouse = django_filters.NumberFilter(
        field_name="warehouse_id"
    )

    order_status = django_filters.CharFilter(
        field_name="order_status"
    )

    delivery_status = django_filters.CharFilter(
        field_name="delivery_status"
    )

    payment_terms = django_filters.CharFilter(
        field_name="payment_terms"
    )

    order_date = django_filters.DateFilter(
        field_name="order_date"
    )

    order_date_after = django_filters.DateFilter(
        field_name="order_date",
        lookup_expr="gte"
    )

    order_date_before = django_filters.DateFilter(
        field_name="order_date",
        lookup_expr="lte"
    )

    delivery_date = django_filters.DateFilter(
        field_name="delivery_date"
    )

    delivery_date_after = django_filters.DateFilter(
        field_name="delivery_date",
        lookup_expr="gte"
    )

    delivery_date_before = django_filters.DateFilter(
        field_name="delivery_date",
        lookup_expr="lte"
    )

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

    class Meta:

        model = SalesOrder

        fields = [
            "customer",
            "quotation",
            "warehouse",
            "order_status",
            "delivery_status",
            "payment_terms",
            "order_date",
            "order_date_after",
            "order_date_before",
            "delivery_date",
            "delivery_date_after",
            "delivery_date_before",
            "due_date",
            "due_date_after",
            "due_date_before",
        ]