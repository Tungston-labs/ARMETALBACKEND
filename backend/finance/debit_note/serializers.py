from rest_framework import serializers
from decimal import Decimal

from .models import DebitNote, DebitNoteItem
from finance.vendor.models import Vendor
from finance.product.models import Product


class DebitNoteItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="product.product_name")
    reason_detail = serializers.CharField(source="description", required=False, allow_blank=True)
    qty = serializers.DecimalField(source="quantity", max_digits=10, decimal_places=2, required=False)
    unit_price = serializers.DecimalField(source="rate", max_digits=15, decimal_places=2, required=False)
    vat = serializers.DecimalField(source="vat_percentage", max_digits=5, decimal_places=2, required=False)

    class Meta:
        model = DebitNoteItem
        fields = [
            "id",
            "bill_item",
            "product",
            "product_name",
            "item_name",
            "description",
            "reason_detail",
            "billed_qty",
            "already_debited_qty",
            "quantity",
            "qty",
            "rate",
            "unit_price",
            "vat_percentage",
            "vat",
            "vat_amount",
            "amount",
        ]
        read_only_fields = ["id"]


class DebitNoteListSerializer(serializers.ModelSerializer):
    vendor_name = serializers.SerializerMethodField()
    bill_number = serializers.ReadOnlyField(source="bill.bill_number")
    against_bill = serializers.SerializerMethodField()
    debit_note_number = serializers.CharField(source="dn_number", read_only=True)
    debitNoteNo = serializers.CharField(source="dn_number", read_only=True)
    reason_name = serializers.CharField(source="get_reason_display", read_only=True)
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    bill_amount = serializers.DecimalField(source="bill.total_amount", max_digits=15, decimal_places=2, read_only=True, default=Decimal("0.00"))
    bill_value = serializers.DecimalField(source="bill.total_amount", max_digits=15, decimal_places=2, read_only=True, default=Decimal("0.00"))
    after_applied = serializers.DecimalField(source="balance", max_digits=15, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(source="balance", max_digits=15, decimal_places=2, read_only=True)
    date_issued = serializers.DateField(source="issue_date", read_only=True)

    class Meta:
        model = DebitNote
        fields = [
            "id",
            "dn_number",
            "debit_note_number",
            "debitNoteNo",
            "vendor",
            "vendor_name",
            "bill",
            "bill_number",
            "bill_ref",
            "against_bill",
            "issue_date",
            "date_issued",
            "reason",
            "reason_name",
            "bill_amount",
            "bill_value",
            "debit_amount",
            "applied_amount",
            "after_applied",
            "remaining_amount",
            "balance",
            "status",
            "status_name",
            "created_at",
        ]

    def get_vendor_name(self, obj):
        if obj.vendor:
            return obj.vendor.name
        return obj.bill_to_name or "-"

    def get_against_bill(self, obj):
        if obj.bill and obj.bill.bill_number:
            return obj.bill.bill_number
        return obj.bill_ref or "-"


class DebitNoteSerializer(serializers.ModelSerializer):
    dn_number = serializers.CharField(required=False, allow_blank=True)
    debit_note_number = serializers.CharField(source="dn_number", required=False, allow_blank=True)
    vendor_name = serializers.ReadOnlyField(source="vendor.name")
    bill_number = serializers.ReadOnlyField(source="bill.bill_number")
    against_bill = serializers.SerializerMethodField()
    reason_name = serializers.CharField(source="get_reason_display", read_only=True)
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    bill_amount = serializers.DecimalField(source="bill.total_amount", max_digits=15, decimal_places=2, read_only=True, default=Decimal("0.00"))
    after_applied = serializers.DecimalField(source="balance", max_digits=15, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(source="balance", max_digits=15, decimal_places=2, read_only=True)

    company_name = serializers.CharField(source="from_company_name", required=False, allow_blank=True)
    company_address = serializers.CharField(source="from_address", required=False, allow_blank=True)
    company_phone = serializers.CharField(source="from_phone_number", required=False, allow_blank=True)
    company_email = serializers.CharField(source="from_email", required=False, allow_blank=True)

    vendor_address = serializers.CharField(source="bill_to_address", required=False, allow_blank=True)
    vendor_phone = serializers.CharField(source="bill_to_phone", required=False, allow_blank=True)
    vendor_email = serializers.CharField(source="finance_contact_email", required=False, allow_blank=True)

    bill_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    vendor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    bill_value = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    already_debited = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    remaining_balance = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)

    items = DebitNoteItemSerializer(many=True, required=False)

    class Meta:
        model = DebitNote
        fields = [
            "id",
            "company",
            "dn_number",
            "debit_note_number",
            "vendor",
            "vendor_id",
            "vendor_name",
            "bill",
            "bill_id",
            "bill_number",
            "bill_ref",
            "against_bill",
            "bill_amount",
            "bill_value",
            "already_debited",
            "remaining_balance",
            "issue_date",
            "reason",
            "reason_name",
            "debit_amount",
            "applied_amount",
            "after_applied",
            "remaining_amount",
            "balance",
            "status",
            "status_name",
            # Snapshots
            "from_company_name",
            "company_name",
            "from_address",
            "company_address",
            "from_phone_number",
            "company_phone",
            "from_email",
            "company_email",
            "bill_to_name",
            "bill_to_address",
            "vendor_address",
            "bill_to_phone",
            "vendor_phone",
            "finance_contact_email",
            "vendor_email",
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

    def get_against_bill(self, obj):
        if obj.bill and obj.bill.bill_number:
            return obj.bill.bill_number
        return obj.bill_ref or "-"

    def validate(self, attrs):
        if "bill" not in attrs and "bill_id" in self.initial_data and self.initial_data["bill_id"]:
            from finance.bill.models import Bill
            try:
                attrs["bill"] = Bill.objects.get(id=self.initial_data["bill_id"])
            except Bill.DoesNotExist:
                raise serializers.ValidationError({"bill": "Bill does not exist."})

        if "vendor" not in attrs and "vendor_id" in self.initial_data and self.initial_data["vendor_id"]:
            from finance.vendor.models import Vendor
            try:
                attrs["vendor"] = Vendor.objects.get(id=self.initial_data["vendor_id"])
            except Vendor.DoesNotExist:
                raise serializers.ValidationError({"vendor": "Vendor does not exist."})

        bill = attrs.get("bill") or getattr(self.instance, "bill", None)
        if bill and "vendor" not in attrs and not getattr(self.instance, "vendor", None):
            if bill.vendor:
                attrs["vendor"] = bill.vendor

        if not attrs.get("dn_number") and self.initial_data.get("debit_note_number"):
            attrs["dn_number"] = self.initial_data["debit_note_number"]

        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        validated_data.pop("bill_id", None)
        validated_data.pop("vendor_id", None)

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
        else:
            if not debit_note.sub_total or debit_note.sub_total == Decimal("0.00"):
                debit_note.sub_total = (
                    (debit_note.debit_amount or Decimal("0.00"))
                    - (debit_note.total_vat or Decimal("0.00"))
                    + (debit_note.discount or Decimal("0.00"))
                )
                needs_save = True

        debit_note.update_status_from_applied_amount()
        if needs_save:
            debit_note.save()

        return debit_note

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        validated_data.pop("bill_id", None)
        validated_data.pop("vendor_id", None)

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
        else:
            if not instance.sub_total or instance.sub_total == Decimal("0.00"):
                instance.sub_total = (
                    (instance.debit_amount or Decimal("0.00"))
                    - (instance.total_vat or Decimal("0.00"))
                    + (instance.discount or Decimal("0.00"))
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
