from rest_framework import serializers
from decimal import Decimal
from django.db import models, transaction

from .models import DeliveryNote, DeliveryNoteItem
from finance.customer.models import Customer
from finance.warehouse.models import Warehouse
from finance.product.models import Product
from finance.sales_order.models import SalesOrder, SalesOrderItem


def update_product_inventory_on_delivery(product, delta_qty):
    """
    Deducts delta_qty from product's current_stock and reserved_qty.
    delta_qty is positive for new delivery (deduct stock and reserved),
    negative for rollback/deletion (restore stock and reserved).
    """
    if not product:
        return
    
    qty_int = int(delta_qty)
    if delta_qty > 0:
        product.current_stock = max(0, product.current_stock - qty_int)
        product.reserved_qty = max(0, product.reserved_qty - qty_int)
    else:
        restore_qty = abs(qty_int)
        product.current_stock = product.current_stock + restore_qty
        product.reserved_qty = product.reserved_qty + restore_qty

    product.save(update_fields=["current_stock", "reserved_qty", "updated_at"])


def update_so_item_delivered_qty(sales_order_item):
    """
    Recalculates delivered_quantity on SalesOrderItem based on linked DeliveryNoteItems
    and updates SalesOrder delivery status.
    """
    if not sales_order_item:
        return

    delivered = DeliveryNoteItem.objects.filter(
        sales_order_item=sales_order_item
    ).exclude(
        delivery_note__delivery_status="cancelled"
    ).aggregate(
        total=models.Sum("quantity")
    )["total"] or Decimal("0.00")

    sales_order_item.delivered_quantity = delivered
    sales_order_item.save(update_fields=["delivered_quantity", "updated_at"])
    
    if sales_order_item.sales_order:
        sales_order_item.sales_order.update_delivery_status()


class DeliveryNoteItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    ordered_qty = serializers.SerializerMethodField()
    already_delivered = serializers.SerializerMethodField()
    delivering_now = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryNoteItem
        fields = [
            "id",
            "product",
            "sales_order_item",
            "product_name",
            "item_name",
            "service_name",
            "description",
            "ordered_qty",
            "already_delivered",
            "delivering_now",
            "quantity",
            "balance",
            "hs_code",
            "rate",
            "vat_percentage",
            "vat_amount",
            "amount",
            "status",
        ]
        read_only_fields = ["id", "product_name", "ordered_qty", "already_delivered", "delivering_now", "balance", "status"]

    def get_product_name(self, obj):
        if obj.product:
            return obj.product.product_name
        return obj.item_name or obj.service_name or "Item"

    def get_ordered_qty(self, obj):
        if obj.sales_order_item:
            return obj.sales_order_item.quantity
        return obj.quantity

    def get_already_delivered(self, obj):
        if obj.sales_order_item:
            # Sum previous delivery note items for this sales_order_item excluding this line item
            qs = DeliveryNoteItem.objects.filter(
                sales_order_item=obj.sales_order_item
            ).exclude(
                delivery_note__delivery_status="cancelled"
            )
            if obj.pk:
                qs = qs.exclude(pk=obj.pk)
            total = qs.aggregate(total=models.Sum("quantity"))["total"] or Decimal("0.00")
            return total
        return Decimal("0.00")

    def get_delivering_now(self, obj):
        return obj.quantity

    def get_balance(self, obj):
        ordered = self.get_ordered_qty(obj)
        already = self.get_already_delivered(obj)
        now = self.get_delivering_now(obj)
        rem = ordered - already - now
        return max(Decimal("0.00"), rem)

    def get_status(self, obj):
        ordered = self.get_ordered_qty(obj)
        already = self.get_already_delivered(obj)
        now = self.get_delivering_now(obj)
        delivered_total = already + now

        if delivered_total >= ordered and ordered > 0:
            return "Fully Delivered"
        elif delivered_total > 0:
            return "Partial"
        return "Pending"


class DeliveryNoteSerializer(serializers.ModelSerializer):
    dn_number = serializers.CharField(required=False, allow_blank=True)
    customer_name = serializers.ReadOnlyField(source="customer.customer_name")
    warehouse_name = serializers.ReadOnlyField(source="warehouse.warehouse_name")
    items = DeliveryNoteItemSerializer(many=True, required=False)

    # Header SO metrics
    so_order_value = serializers.SerializerMethodField()
    so_already_delivered_value = serializers.SerializerMethodField()
    so_balance_to_deliver_value = serializers.SerializerMethodField()

    # Footer metrics
    total_quantity = serializers.SerializerMethodField()
    pending_quantity = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryNote
        fields = [
            "id",
            "company",
            "dn_number",
            "sales_order",
            "so_ref",
            "customer",
            "customer_name",
            "delivery_date",
            "warehouse",
            "warehouse_name",
            "delivery_value",
            "delivery_status",
            "invoice_status",
            "so_order_value",
            "so_already_delivered_value",
            "so_balance_to_deliver_value",
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
            "total_quantity",
            "pending_quantity",
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
            "so_order_value",
            "so_already_delivered_value",
            "so_balance_to_deliver_value",
            "total_quantity",
            "pending_quantity",
        ]

    def get_so_order_value(self, obj):
        if obj.sales_order:
            return obj.sales_order.order_value
        return obj.delivery_value or Decimal("0.00")

    def get_so_already_delivered_value(self, obj):
        if obj.sales_order:
            qs = DeliveryNote.objects.filter(
                sales_order=obj.sales_order
            ).exclude(
                delivery_status="cancelled"
            )
            if obj.pk:
                qs = qs.exclude(pk=obj.pk)
            total = qs.aggregate(total=models.Sum("delivery_value"))["total"] or Decimal("0.00")
            return total
        return Decimal("0.00")

    def get_so_balance_to_deliver_value(self, obj):
        order_val = self.get_so_order_value(obj)
        already_val = self.get_so_already_delivered_value(obj)
        current_val = obj.delivery_value or Decimal("0.00")
        bal = order_val - already_val - current_val
        return max(Decimal("0.00"), bal)

    def get_total_quantity(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_pending_quantity(self, obj):
        pending_sum = Decimal("0.00")
        for item in obj.items.all():
            if item.sales_order_item:
                ordered = item.sales_order_item.quantity
                prev_deliv = DeliveryNoteItem.objects.filter(
                    sales_order_item=item.sales_order_item
                ).exclude(
                    delivery_note__delivery_status="cancelled"
                ).aggregate(total=models.Sum("quantity"))["total"] or Decimal("0.00")
                rem = ordered - prev_deliv
                if rem > Decimal("0.00"):
                    pending_sum += rem
            else:
                pass
        return pending_sum

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        delivery_note = DeliveryNote.objects.create(**validated_data)

        calculated_subtotal = Decimal("0.00")
        calculated_vat = Decimal("0.00")

        created_items = []
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

            item_obj = DeliveryNoteItem.objects.create(delivery_note=delivery_note, **item_data)
            created_items.append(item_obj)
            calculated_subtotal += line_base
            calculated_vat += line_vat

            # Apply inventory reduction & reserved qty removal
            update_product_inventory_on_delivery(item_obj.product, item_obj.quantity)
            if item_obj.sales_order_item:
                update_so_item_delivered_qty(item_obj.sales_order_item)

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

        # Update SalesOrder delivery_status if linked
        if delivery_note.sales_order:
            delivery_note.sales_order.update_delivery_status()

        return delivery_note

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if items_data is not None:
            # Revert inventory & delivered qty for previous items
            existing_items = list(instance.items.all())
            for old_item in existing_items:
                update_product_inventory_on_delivery(old_item.product, -old_item.quantity)
                so_item = old_item.sales_order_item
                old_item.delete()
                if so_item:
                    update_so_item_delivered_qty(so_item)

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

                item_obj = DeliveryNoteItem.objects.create(delivery_note=instance, **item_data)
                calculated_subtotal += line_base
                calculated_vat += line_vat

                # Apply new inventory reduction
                update_product_inventory_on_delivery(item_obj.product, item_obj.quantity)
                if item_obj.sales_order_item:
                    update_so_item_delivered_qty(item_obj.sales_order_item)

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
        if instance.sales_order:
            instance.sales_order.update_delivery_status()

        return instance
