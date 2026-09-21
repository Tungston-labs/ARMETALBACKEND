from django.contrib import admin

from .models import SalesOrder, SalesOrderItem


class SalesOrderItemInline(admin.TabularInline):

    model = SalesOrderItem

    extra = 0


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):

    list_display = (
        "so_number",
        "customer_name",
        "order_date",
        "delivery_date",
        "order_value",
        "order_status",
        "delivery_status",
        "created_by",
    )

    list_filter = (
        "order_status",
        "delivery_status",
        "payment_terms",
        "order_date",
    )

    search_fields = (
        "so_number",
        "customer_name",
        "customer__customer_name",
        "quotation__quote_number",
    )

    inlines = [
        SalesOrderItemInline
    ]