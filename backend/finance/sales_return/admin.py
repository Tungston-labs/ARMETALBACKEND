from django.contrib import admin
from .models import SalesReturn, SalesReturnItem


class SalesReturnItemInline(admin.TabularInline):
    model = SalesReturnItem
    extra = 1


@admin.register(SalesReturn)
class SalesReturnAdmin(admin.ModelAdmin):
    list_display = (
        "return_number",
        "company",
        "customer",
        "invoice_ref",
        "return_date",
        "return_value",
        "reason",
        "status",
        "created_at",
    )
    list_filter = ("status", "reason", "return_date", "company")
    search_fields = ("return_number", "invoice_ref", "customer_name", "notes")
    inlines = [SalesReturnItemInline]


@admin.register(SalesReturnItem)
class SalesReturnItemAdmin(admin.ModelAdmin):
    list_display = (
        "sales_return",
        "product_name",
        "invoiced_qty",
        "returning_now_qty",
        "unit_price",
        "return_value",
    )
