from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "company",
        "customer",
        "invoice",
        "payment_date",
        "payment_type",
        "payment_method",
        "amount_received",
        "status",
    )
    list_filter = (
        "company",
        "payment_type",
        "payment_method",
        "status",
        "payment_date",
    )
    search_fields = (
        "receipt_number",
        "customer__customer_name",
        "invoice__invoice_number",
        "reference_number",
    )
    ordering = ("-created_at",)
