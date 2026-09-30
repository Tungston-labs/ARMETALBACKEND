from rest_framework import serializers
from decimal import Decimal

from .models import DebitNote, DebitNoteItem
from finance.vendor.models import Vendor
from finance.product.models import Product


class DebitNoteItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="product.product_name")

    class Meta:
        model = DebitNoteItem
        fields = [
            "id",
            "bill_item",
            "product",
            "product_name",
            "item_name",
            "description",
            "billed_qty",
            "already_debited_qty",
            "quantity",
            "rate",
            "vat_percentage",
            "vat_amount",
            "amount",
        ]
        read_only_fields = ["id"]


class DebitNoteListSerializer(serializers.ModelSerializer):
    vendor_name = serializers.ReadOnlyField(source="vendor.name")
    bill_number = serializers.ReadOnlyField(source="bill.bill_number")
    reason_name = serializers.CharField(source="get_reason_display", read_only=True)
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = DebitNote
        fields = [
            "id",
            "dn_number",
            "vendor",
            "vendor_name",
            "bill",
            "bill_number",
            "bill_ref",
            "issue_date",
            "reason",
            "reason_name",
            "debit_amount",
            "applied_amount",
            "balance",
            "status",
            "status_name",
            "created_at",
        ]


class DebitNoteSerializer(serializers.ModelSerializer):
    dn_number = serializers.CharField(required=False, allow_blank=True)
    vendor_name = serializers.ReadOnlyField(source="vendor.name")
    bill_number = serializers.ReadOnlyField(source="bill.bill_number")
    reason_name = serializers.CharField(source="get_reason_display", read_only=True)
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    items = DebitNoteItemSerializer(many=True, required=False)

    class Meta:
        model = DebitNote
        fields = [
            "id",
            "company",
            "dn_number",
            "vendor",
            "vendor_name",
            "bill",
            "bill_number",
            "bill_ref",
            "issue_date",
            "reason",
            "reason_name",
            "debit_amount",
            "applied_amount",
            "balance",
            "status",
            "status_name",
            # Snapshots
            "from_company_name",
            "from_address",
            "from_phone_number",
            "from_email",
            "bill_to_name",
            "bill_to_address",
            "bill_to_phone",
            "finance_contact_email",
            # Totals
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

        if validated_data.get("bill") and not validated_data.get("bill_ref"):
            validated_data["bill_ref"] = validated_data["bill"].bill_number

        vendor = validated_data.get("vendor")
        if vendor:
            if not validated_data.get("bill_to_name"):
                validated_data["bill_to_name"] = vendor.name
            if not validated_data.get("bill_to_address"):
                validated_data["bill_to_address"] = vendor.billing_address
            if not validated_data.get("bill_to_phone"):
                validated_data["bill_to_phone"] = vendor.phno
            if not validated_data.get("finance_contact_email"):
                validated_data["finance_contact_email"] = vendor.financial_email or vendor.admin_email

        debit_note = DebitNote.objects.create(**validated_data)

        calculated_subtotal = Decimal("0.00")
        calculated_vat = Decimal("0.00")

        for item_data in items_data:
            bill_item = item_data.get("bill_item")
            if bill_item:
                if not item_data.get("item_name"):
                    item_data["item_name"] = bill_item.particular
                if not item_data.get("product") and bill_item.product:
                    item_data["product"] = bill_item.product
                if "rate" not in item_data or item_data["rate"] == Decimal("0.00"):
                    item_data["rate"] = bill_item.rate
                if "vat_percentage" not in item_data or item_data["vat_percentage"] == Decimal("0.00"):
                    item_data["vat_percentage"] = bill_item.vat_percentage

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

            DebitNoteItem.objects.create(debit_note=debit_note, **item_data)
            calculated_subtotal += line_base
            calculated_vat += line_vat

        needs_save = False
        if items_data:
            if not debit_note.sub_total or debit_note.sub_total == Decimal("0.00"):
                debit_note.sub_total = calculated_subtotal
                needs_save = True

            if not debit_note.total_vat or debit_note.total_vat == Decimal("0.00"):
                debit_note.total_vat = calculated_vat
                needs_save = True

            if not debit_note.debit_amount or debit_note.debit_amount == Decimal("0.00"):
                discount = debit_note.discount or Decimal("0.00")
                debit_note.debit_amount = (
                    debit_note.sub_total + debit_note.total_vat - discount
                )
                needs_save = True

        debit_note.update_status_from_applied_amount()
        if needs_save:
            debit_note.save()

        return debit_note

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

                DebitNoteItem.objects.create(debit_note=instance, **item_data)
                calculated_subtotal += line_base
                calculated_vat += line_vat

            instance.sub_total = calculated_subtotal
            instance.total_vat = calculated_vat
            discount = instance.discount or Decimal("0.00")
            instance.debit_amount = (
                instance.sub_total + instance.total_vat - discount
            )

        instance.update_status_from_applied_amount()
        instance.save()
        return instance


class DebitNoteKPISerializer(serializers.Serializer):
    total_debit_notes = serializers.IntegerField()
    debit_note_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    open_debit_notes = serializers.IntegerField()
    applied_debit_notes = serializers.IntegerField()
    cancelled_debits = serializers.IntegerField()
