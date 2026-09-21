from django.contrib import admin
from .models import Quotation, QuotationItem, QuotationConversion


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ("quote_number", "company", "customer", "issue_date", "valid_till", "quote_amount", "status", "created_at")
    list_filter = ("status", "company", "issue_date")
    search_fields = ("quote_number", "customer__customer_name", "bill_to_name")
    inlines = [QuotationItemInline]


@admin.register(QuotationConversion)
class QuotationConversionAdmin(admin.ModelAdmin):
    list_display = ("invoice_no", "quotation", "customer", "payment_date", "amount_received", "payment_type", "payment_method")
    list_filter = ("payment_type", "payment_method", "company")
    search_fields = ("invoice_no", "reference_number", "notes")
