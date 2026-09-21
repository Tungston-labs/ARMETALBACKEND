from django.contrib import admin
from .models import DeliveryNote, DeliveryNoteItem


class DeliveryNoteItemInline(admin.TabularInline):
    model = DeliveryNoteItem
    extra = 1


@admin.register(DeliveryNote)
class DeliveryNoteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "dn_number",
        "so_ref",
        "company",
        "customer",
        "warehouse",
        "delivery_date",
        "delivery_value",
        "delivery_status",
        "invoice_status",
        "created_at",
    )
    list_filter = (
        "delivery_status",
        "invoice_status",
        "delivery_date",
        "company",
        "warehouse",
    )
    search_fields = (
        "dn_number",
        "so_ref",
        "customer__customer_name",
        "warehouse__warehouse_name",
        "notes",
    )
    inlines = [DeliveryNoteItemInline]


@admin.register(DeliveryNoteItem)
class DeliveryNoteItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "delivery_note",
        "item_name",
        "quantity",
        "rate",
        "amount",
    )
