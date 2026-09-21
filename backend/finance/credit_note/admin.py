from django.contrib import admin
from .models import CreditNote, CreditNoteItem


class CreditNoteItemInline(admin.TabularInline):
    model = CreditNoteItem
    extra = 1


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = (
        "cn_number",
        "customer",
        "invoice_ref",
        "issue_date",
        "reason",
        "credit_amount",
        "applied_amount",
        "balance",
        "status",
        "company",
    )
    list_filter = ("status", "reason", "issue_date", "company")
    search_fields = ("cn_number", "invoice_ref", "customer__customer_name", "customer__company_name")
    ordering = ("-created_at",)
    inlines = [CreditNoteItemInline]


@admin.register(CreditNoteItem)
class CreditNoteItemAdmin(admin.ModelAdmin):
    list_display = ("credit_note", "item_name", "service_name", "quantity", "rate", "vat_amount", "amount")
    search_fields = ("item_name", "service_name", "credit_note__cn_number")
