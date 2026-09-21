import django_filters
from .models import Payment


class PaymentFilter(django_filters.FilterSet):
    customer = django_filters.NumberFilter(field_name="customer__id")
    invoice = django_filters.NumberFilter(field_name="invoice__id")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    payment_type = django_filters.CharFilter(field_name="payment_type", lookup_expr="iexact")
    payment_method = django_filters.CharFilter(field_name="payment_method", lookup_expr="iexact")
    start_date = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")

    class Meta:
        model = Payment
        fields = [
            "customer",
            "invoice",
            "status",
            "payment_type",
            "payment_method",
            "start_date",
            "end_date",
        ]
