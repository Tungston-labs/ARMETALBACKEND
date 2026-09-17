from rest_framework import serializers
from decimal import Decimal

from .models import DeliveryNote, DeliveryNoteItem
from finance.customer.models import Customer
from finance.warehouse.models import Warehouse
from finance.product.models import Product


class DeliveryNoteItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="product.product_name")

    class Meta:
        model = DeliveryNoteItem
        fields = [
            "id",
            "product",
            "product_name",
            "item_name",
            "service_name",
            "description",
            "quantity",
            "hs_code",
            "rate",
            "vat_percentage",
            "vat_amount",
            "amount",
        ]
        read_only_fields = ["id"]


class DeliveryNoteSerializer(serializers.ModelSerializer):
    dn_number = serializers.CharField(required=False, allow_blank=True)
    customer_name = serializers.ReadOnlyField(source="customer.customer_name")
    warehouse_name = serializers.ReadOnlyField(source="warehouse.warehouse_name")
    items = DeliveryNoteItemSerializer(many=True, required=False)

    class Meta:
        model = DeliveryNote
        fields = [
            "id",
            "company",
            "dn_number",
            "so_ref",
            "customer",
            "customer_name",
            "delivery_date",
            "warehouse",
            "warehouse_name",
            "delivery_value",
            "delivery_status",
            "invoice_status",
            "from_company_name",
            "from_address",
            "from_phone_number",
            "from_email",
            "shipping_address",
            "contact_person",
            "contact_phone",
            "contact_email",
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
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        delivery_note = DeliveryNote.objects.create(**validated_data)

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

            DeliveryNoteItem.objects.create(delivery_note=delivery_note, **item_data)
            calculated_subtotal += line_base
            calculated_vat += line_vat

        needs_save = False
        if not delivery_note.sub_total or delivery_note.sub_total == Decimal("0.00"):
            delivery_note.sub_total = calculated_subtotal
            needs_save = True

        if not delivery_note.total_vat or delivery_note.total_vat == Decimal("0.00"):
            delivery_note.total_vat = calculated_vat
            needs_save = True

        if not delivery_note.delivery_value or delivery_note.delivery_value == Decimal("0.00"):
            discount = delivery_note.discount or Decimal("0.00")
            delivery_note.delivery_value = (
                delivery_note.sub_total + delivery_note.total_vat - discount
            )
            needs_save = True

        if needs_save:
            delivery_note.save()

        return delivery_note

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

                DeliveryNoteItem.objects.create(delivery_note=instance, **item_data)
                calculated_subtotal += line_base
                calculated_vat += line_vat

            if "sub_total" not in validated_data:
                instance.sub_total = calculated_subtotal
            if "total_vat" not in validated_data:
                instance.total_vat = calculated_vat
            if "delivery_value" not in validated_data:
                discount = instance.discount or Decimal("0.00")
                instance.delivery_value = (
                    instance.sub_total + instance.total_vat - discount
                )

        instance.save()
        return instance
