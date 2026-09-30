import django_filters
from .models import VendorPayment


class VendorPaymentFilter(django_filters.FilterSet):
    vendor = django_filters.NumberFilter(field_name="vendor_id")
    bill = django_filters.NumberFilter(field_name="bill_id")
    status = django_filters.CharFilter(field_name="status")
    payment_type = django_filters.CharFilter(field_name="payment_type")
    payment_method = django_filters.CharFilter(field_name="payment_method")

    payment_date = django_filters.DateFilter(field_name="payment_date")
    start_date = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")
    payment_date_after = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    payment_date_before = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")

    class Meta:
        model = VendorPayment
        fields = [
            "vendor",
            "bill",
            "status",
            "payment_type",
            "payment_method",
            "payment_date",
            "start_date",
            "end_date",
            "payment_date_after",
            "payment_date_before",
        ]
