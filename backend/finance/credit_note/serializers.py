from rest_framework import serializers
from decimal import Decimal

from .models import CreditNote, CreditNoteItem
from finance.customer.models import Customer
from finance.product.models import Product


class CreditNoteItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="product.product_name")

    class Meta:
        model = CreditNoteItem
        fields = [
            "id",
            "invoice_item",
            "product",
            "product_name",
            "item_name",
            "service_name",
            "description",
            "quantity",
            "rate",
            "vat_percentage",
            "vat_amount",
            "amount",
        ]
        read_only_fields = ["id"]


class CreditNoteSerializer(serializers.ModelSerializer):
    cn_number = serializers.CharField(required=False, allow_blank=True)
    customer_name = serializers.ReadOnlyField(source="customer.customer_name")
    customer_company = serializers.ReadOnlyField(source="customer.company_name")
    invoice_number = serializers.ReadOnlyField(source="invoice.invoice_number")
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    items = CreditNoteItemSerializer(many=True, required=False)

    class Meta:
        model = CreditNote
        fields = [
            "id",
            "company",
            "cn_number",
            "customer",
            "customer_name",
            "customer_company",
            "invoice",
            "invoice_number",
            "invoice_ref",
            "issue_date",
            "reason",
            "credit_amount",
            "applied_amount",
            "balance",
            "status",
            "from_company_name",
            "from_address",
            "from_phone_number",
            "from_email",
            "sub_total",
            "total_vat",
            "discount",
            "notes",
            "items",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "balance",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])

        if validated_data.get("invoice") and not validated_data.get("invoice_ref"):
            validated_data["invoice_ref"] = validated_data["invoice"].invoice_number

        credit_note = CreditNote.objects.create(**validated_data)

        calculated_subtotal = Decimal("0.00")
        calculated_vat = Decimal("0.00")

        for item_data in items_data:
            inv_item = item_data.get("invoice_item")
            if inv_item:
                if not item_data.get("item_name"):
                    item_data["item_name"] = inv_item.particular
                if not item_data.get("product") and inv_item.product:
                    item_data["product"] = inv_item.product
                if "rate" not in item_data or item_data["rate"] == Decimal("0.00"):
                    item_data["rate"] = inv_item.rate
                if "vat_percentage" not in item_data or item_data["vat_percentage"] == Decimal("0.00"):
                    item_data["vat_percentage"] = inv_item.vat_percentage

            qty = Decimal(str(item_data.get("quantity", 1)))
            rate = Decimal(str(item_data.get("rate", 0)))
            vat_pct = Decimal(str(item_data.get("vat_percentage", 15)))

            line_base = qty * rate
            line_vat = line_base * (vat_pct / Decimal("100"))
            line_amount = line_base + line_vat

            if "vat_amount" not in item_data or not item_data["vat_amount"]:
                item_data["vat_amount"] = line_vat
            if "amount" not in item_data or not item_data["amount"]:
                item_data["amount"] = line_amount

            CreditNoteItem.objects.create(credit_note=credit_note, **item_data)
            calculated_subtotal += line_base
            calculated_vat += line_vat

        needs_save = False
        if items_data:
            if not credit_note.sub_total or credit_note.sub_total == Decimal("0.00"):
                credit_note.sub_total = calculated_subtotal
                needs_save = True

            if not credit_note.total_vat or credit_note.total_vat == Decimal("0.00"):
                credit_note.total_vat = calculated_vat
                needs_save = True

            if not credit_note.credit_amount or credit_note.credit_amount == Decimal("0.00"):
                discount = credit_note.discount or Decimal("0.00")
                credit_note.credit_amount = (
                    credit_note.sub_total + credit_note.total_vat - discount
                )
                needs_save = True

        credit_note.update_status_from_applied_amount()
        if needs_save:
            credit_note.save()

        return credit_note

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if items_data is not None:
            instance.items.all().delete()
            calculated_subtotal = Decimal("0.00")
            calculated_vat = Decimal("0.00")

            for item_data in items_data:
                qty = Decimal(str(item_data.get("quantity", 1)))
                rate = Decimal(str(item_data.get("rate", 0)))
                vat_pct = Decimal(str(item_data.get("vat_percentage", 15)))

                line_base = qty * rate
                line_vat = line_base * (vat_pct / Decimal("100"))
                line_amount = line_base + line_vat

                if "vat_amount" not in item_data or not item_data["vat_amount"]:
                    item_data["vat_amount"] = line_vat
                if "amount" not in item_data or not item_data["amount"]:
                    item_data["amount"] = line_amount

                CreditNoteItem.objects.create(credit_note=instance, **item_data)
                calculated_subtotal += line_base
                calculated_vat += line_vat

            if "sub_total" not in validated_data:
                instance.sub_total = calculated_subtotal
            if "total_vat" not in validated_data:
                instance.total_vat = calculated_vat
            if "credit_amount" not in validated_data:
                discount = instance.discount or Decimal("0.00")
                instance.credit_amount = (
                    instance.sub_total + instance.total_vat - discount
                )

        instance.update_status_from_applied_amount()
        instance.save()
        return instance
