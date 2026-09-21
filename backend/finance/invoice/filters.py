import django_filters

from .models import Invoice


class InvoiceFilter(
    django_filters.FilterSet
):

    # -----------------------------------------------------
    # SALES ORDER
    # -----------------------------------------------------

    sales_order = django_filters.NumberFilter(
        field_name="sales_order_id"
    )

    # -----------------------------------------------------
    # CUSTOMER
    # -----------------------------------------------------

    customer = django_filters.NumberFilter(
        field_name="customer_id"
    )

    # -----------------------------------------------------
    # PAYMENT STATUS
    # -----------------------------------------------------

    payment_status = django_filters.CharFilter(
        field_name="payment_status"
    )

    # -----------------------------------------------------
    # DUE DATE
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # INVOICE DATE
    # -----------------------------------------------------

    invoice_date = django_filters.DateFilter(
        field_name="invoice_date"
    )

    invoice_date_after = django_filters.DateFilter(
        field_name="invoice_date",
        lookup_expr="gte"
    )

    invoice_date_before = django_filters.DateFilter(
        field_name="invoice_date",
        lookup_expr="lte"
    )

    class Meta:

        model = Invoice

        fields = [

            "sales_order",

            "customer",

            "payment_status",

            "due_date",

            "due_date_after",

            "due_date_before",

            "invoice_date",

            "invoice_date_after",

            "invoice_date_before",

        ]