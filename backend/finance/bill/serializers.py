from rest_framework import serializers
from decimal import Decimal

from .models import Bill, BillItem
from finance.vendor.models import Vendor
from finance.product.models import Product


class BillItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="product.product_name")

    class Meta:
        model = BillItem
        fields = [
            "id",
            "product",
            "product_name",
            "particular",
            "quantity",
            "hs_code",
            "rate",
            "vat_percentage",
            "vat_sar",
            "amount",
        ]
        read_only_fields = ["id", "vat_sar", "amount"]


class BillListSerializer(serializers.ModelSerializer):
    vendor_name = serializers.SerializerMethodField()
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = Bill
        fields = [
            "id",
            "bill_number",
            "po_reference",
            "vendor",
            "vendor_name",
            "bill_date",
            "due_date",
            "total_amount",
            "amount_paid",
            "balance",
            "status",
            "created_at",
        ]

    def get_vendor_name(self, obj):
        if obj.vendor:
            return obj.vendor.name
        return obj.bill_to_name or ""


class BillSerializer(serializers.ModelSerializer):
    bill_number = serializers.CharField(required=False, allow_blank=True)
    vendor_name = serializers.SerializerMethodField()
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    items = BillItemSerializer(many=True, required=False)

    class Meta:
        model = Bill
        fields = [
            "id",
            "company",
            "vendor",
            "vendor_name",
            "bill_number",
            "po_reference",
            "bill_date",
            "due_date",
            "due_date_note",
            "payment_terms",
            "status",
            "note",
            # From snapshot
            "from_name",
            "from_address",
            "from_phone",
            "from_email",
            # Bill To snapshot
            "bill_to_name",
            "bill_to_address",
            "bill_to_phone",
            "bill_to_email",
            "finance_contact_email",
            # Financial totals
            "subtotal",
            "total_vat",
            "discount",
            "round_off",
            "total_amount",
            "amount_paid",
            "balance",
            # Items
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

    def get_vendor_name(self, obj):
        if obj.vendor:
            return obj.vendor.name
        return obj.bill_to_name or ""

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        
        # Populate snapshot info from vendor if vendor provided and snapshot fields empty
        vendor = validated_data.get("vendor")
        if vendor:
            if not validated_data.get("bill_to_name"):
                validated_data["bill_to_name"] = vendor.name
            if not validated_data.get("bill_to_address"):
                validated_data["bill_to_address"] = vendor.billing_address
            if not validated_data.get("bill_to_phone"):
                validated_data["bill_to_phone"] = vendor.phno
            if not validated_data.get("bill_to_email"):
                validated_data["bill_to_email"] = vendor.admin_email
            if not validated_data.get("finance_contact_email"):
                validated_data["finance_contact_email"] = vendor.financial_email

        bill = Bill.objects.create(**validated_data)

        calculated_subtotal = Decimal("0.00")
        calculated_vat = Decimal("0.00")

        for item_data in items_data:
            qty = Decimal(str(item_data.get("quantity", 1)))
            rate = Decimal(str(item_data.get("rate", 0)))
            vat_pct = Decimal(str(item_data.get("vat_percentage", 0)))

            line_amount = qty * rate
            line_vat = (line_amount * vat_pct) / Decimal("100")

            item_data["amount"] = line_amount
            item_data["vat_sar"] = line_vat

            BillItem.objects.create(bill=bill, **item_data)
            calculated_subtotal += line_amount
            calculated_vat += line_vat

        if items_data:
            bill.subtotal = calculated_subtotal
            bill.total_vat = calculated_vat
            discount = bill.discount or Decimal("0.00")
            round_off = bill.round_off or Decimal("0.00")
            bill.total_amount = calculated_subtotal + calculated_vat - discount + round_off
            bill.update_status()
            bill.save()

        return bill

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
                vat_pct = Decimal(str(item_data.get("vat_percentage", 0)))

                line_amount = qty * rate
                line_vat = (line_amount * vat_pct) / Decimal("100")

                item_data["amount"] = line_amount
                item_data["vat_sar"] = line_vat

                BillItem.objects.create(bill=instance, **item_data)
                calculated_subtotal += line_amount
                calculated_vat += line_vat

            instance.subtotal = calculated_subtotal
            instance.total_vat = calculated_vat
            discount = instance.discount or Decimal("0.00")
            round_off = instance.round_off or Decimal("0.00")
            instance.total_amount = calculated_subtotal + calculated_vat - discount + round_off

        instance.update_status()
        instance.save()
        return instance
