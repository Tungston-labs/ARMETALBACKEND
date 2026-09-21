from django.contrib import admin

from .models import CustomerLedger


@admin.register(CustomerLedger)
class CustomerLedgerAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "company",
        "customer",
        "transaction_date",
        "transaction_type",
        "reference_number",
        "debit",
        "credit",
        "balance",
    ]

    list_filter = [
        "company",
        "transaction_type",
        "transaction_date",
    ]

    search_fields = [
        "customer__customer_name",
        "customer__customer_id",
        "reference_number",
        "description",
    ]

    readonly_fields = [
        "balance",
        "created_at",
        "updated_at",
    ]