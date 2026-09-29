# purchase_order/serializers.py

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from rest_framework import serializers

from .models import PurchaseOrder, PurchaseOrderItem

from finance.vendor.models import Vendor
from finance.warehouse.models import Warehouse
from finance.product.models import Product


MONEY = Decimal("0.01")

def get_response_results(response):
    data = response.json()

    if isinstance(data, dict) and "results" in data:
        return data["results"]

    return data
def money(value):
    return Decimal(value).quantize(
        MONEY,
        rounding=ROUND_HALF_UP,
    )


class PurchaseOrderItemCreateSerializer(serializers.ModelSerializer):

    product_name = serializers.CharField(
        source="product.product_name",
        read_only=True,
    )

    class Meta:
        model = PurchaseOrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "description",
            "quantity",
            "hs_code",
            "rate",
            "vat_percentage",
            "vat_amount",
            "amount",
        ]
        read_only_fields = [
            "id",
            "product_name",
            "vat_amount",
            "amount",
        ]

    def validate_product(self, product):
        request = self.context.get("request")

        if request and product.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Invalid product for this company."
            )

        if product.status != "active":
            raise serializers.ValidationError(
                "Inactive products cannot be added."
            )

        return product

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Quantity must be greater than zero."
            )
        return value

    def validate_rate(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Rate cannot be negative."
            )
        return value

    def validate_vat_percentage(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(
                "VAT percentage must be between 0 and 100."
            )
        return value


class PurchaseOrderCreateSerializer(serializers.ModelSerializer):

    items = PurchaseOrderItemCreateSerializer(
        many=True,
        write_only=True,
    )

    item_details = PurchaseOrderItemCreateSerializer(
        source="items",
        many=True,
        read_only=True,
    )

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "po_number",
            "vendor",
            "pr_reference",
            "order_date",
            "expected_delivery_date",
            "payment_terms",
            "status",
            "receipt_status",
            "bill_status",
            "warehouse",
            "shipping_method",
            "subtotal",
            "total_vat",
            "discount",
            "round_off",
            "total_amount",
            "notes",
            "items",
            "item_details",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "po_number",
            "receipt_status",
            "bill_status",
            "total_amount",
            "created_at",
        ]

    def validate_vendor(self, vendor):
        request = self.context.get("request")

        if request and vendor.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Invalid vendor for this company."
            )

        return vendor

    def validate_warehouse(self, warehouse):
        request = self.context.get("request")

        if request and warehouse.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Invalid warehouse for this company."
            )

        return warehouse

    def validate_discount(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Discount cannot be negative."
            )
        return value

    def validate(self, attrs):
        items = attrs.get("items", [])

        if not items:
            raise serializers.ValidationError({
                "items": "At least one item is required."
            })

        order_date = attrs.get("order_date")
        delivery_date = attrs.get("expected_delivery_date")

        if delivery_date and order_date and delivery_date < order_date:
            raise serializers.ValidationError({
                "expected_delivery_date":
                    "Delivery date cannot be before order date."
            })

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")

        request = self.context.get("request")
        company = request.user.company
        created_by = request.user

        discount = validated_data.get(
            "discount",
            Decimal("0.00"),
        )

        round_off = validated_data.get(
            "round_off",
            Decimal("0.00"),
        )

        # Generate the PO number within this company.
        last_po = (
            PurchaseOrder.objects
            .filter(company=company)
            .order_by("-id")
            .first()
        )

        next_number = (last_po.id + 1) if last_po else 1

        po_number = f"PO{next_number:05d}"

        purchase_order = PurchaseOrder.objects.create(
            company=company,
            created_by=created_by,
            po_number=po_number,
            **validated_data,
        )

        subtotal = Decimal("0.00")
        total_vat = Decimal("0.00")

        for item_data in items_data:
            product = item_data["product"]

            quantity = item_data["quantity"]
            rate = item_data["rate"]
            vat_percentage = item_data.get(
                "vat_percentage",
                Decimal("0.00"),
            )

            # Calculate line amount and VAT.
            line_subtotal = money(quantity * rate)

            vat_amount = money(
                line_subtotal * vat_percentage / Decimal("100")
            )

            line_amount = money(line_subtotal + vat_amount)

            # Default description and HS code from the product.
            description = item_data.get("description") or (
                product.description or product.product_name
            )

            hs_code = item_data.get("hs_code") or (
                product.hsn_sac_code
            )

            PurchaseOrderItem.objects.create(
                purchase_order=purchase_order,
                product=product,
                description=description,
                quantity=quantity,
                hs_code=hs_code,
                rate=rate,
                vat_percentage=vat_percentage,
                vat_amount=vat_amount,
                amount=line_amount,
            )

            subtotal += line_subtotal
            total_vat += vat_amount

        subtotal = money(subtotal)
        total_vat = money(total_vat)

        total_amount = money(
            subtotal
            + total_vat
            - discount
            + round_off
        )

        if total_amount < 0:
            raise serializers.ValidationError({
                "discount": "Discount exceeds the order value."
            })

        purchase_order.subtotal = subtotal
        purchase_order.total_vat = total_vat
        purchase_order.discount = discount
        purchase_order.round_off = round_off
        purchase_order.total_amount = total_amount

        purchase_order.save(
            update_fields=[
                "subtotal",
                "total_vat",
                "discount",
                "round_off",
                "total_amount",
            ]
        )

        return purchase_order


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(
        source="vendor.name",
        read_only=True,
    )

    warehouse_name = serializers.CharField(
        source="warehouse.warehouse_name",
        read_only=True,
    )

    created_by_name = serializers.SerializerMethodField()
    created_by_role = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "po_number",
            "vendor",
            "vendor_name",
            "pr_reference",
            "order_date",
            "expected_delivery_date",
            "total_amount",
            "status",
            "receipt_status",
            "bill_status",
            "warehouse",
            "warehouse_name",
            "created_by",
            "created_by_name",
            "created_by_role",
            "created_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None

        user = obj.created_by

        return (
            getattr(user, "get_full_name", lambda: "")()
            or getattr(user, "username", None)
            or str(user)
        )

    def get_created_by_role(self, obj):
        user = obj.created_by

        if not user:
            return None

        if getattr(user, "is_super_admin", False):
            return "Super Admin"

        if getattr(user, "is_company_admin", False):
            return "Company Admin"

        if getattr(user, "is_employee", False):
            return "Employee"

        if getattr(user, "is_staff", False):
            return "Staff"

        return "User"

class VendorDropdownSerializer(serializers.ModelSerializer):

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_id",
            "name",
        ]


class WarehouseDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = [
            "id",
            "code",
            "warehouse_name",
        ]

class ProductDropdownSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product
        fields = [
            "id",
            "code",
            "product_name",
            "sku",
            "unit",
            "hsn_sac_code",
            "cost_price",
            "tax_rate",
            "tax_type",
            "description",
        ]