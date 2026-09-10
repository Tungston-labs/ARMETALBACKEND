from rest_framework import serializers
from finance.product.models import Product
from finance.product.serializers import ProductSerializer
from .models import StockAdjustment


class InventoryListSerializer(ProductSerializer):
    available_qty = serializers.IntegerField(source="current_stock", read_only=True)

    class Meta(ProductSerializer.Meta):
        fields = [
            "id",
            "code",
            "product_name",
            "sku",
            "category",
            "category_name",
            "warehouse",
            "warehouse_name",
            "available_qty",
            "current_stock",
            "reserved_qty",
            "unit",
            "reorder_level",
            "stock_status",
            "inventory_value",
            "updated_at",
        ]


class StockAdjustmentSerializer(serializers.ModelSerializer):
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    adjustment_number = serializers.CharField(source="code", required=False, allow_blank=True, allow_null=True)
    product_name = serializers.SerializerMethodField()
    warehouse_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockAdjustment
        fields = [
            "id",
            "company",
            "code",
            "adjustment_number",
            "product",
            "product_name",
            "sku",
            "warehouse",
            "warehouse_name",
            "current_available_qty",
            "adjusted_stock",
            "adjustment_type",
            "adjustment_quantity",
            "reason",
            "reference_document",
            "adjustment_date",
            "note",
            "attachment",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "product_name",
            "warehouse_name",
            "current_available_qty",
            "adjusted_stock",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def get_product_name(self, obj):
        if obj.product:
            return obj.product.product_name
        return None

    def get_warehouse_name(self, obj):
        if obj.warehouse:
            return getattr(obj.warehouse, "warehouse_name", str(obj.warehouse))
        return None

    def get_created_by_name(self, obj):
        if obj.created_by:
            full_name = obj.created_by.get_full_name().strip()
            return full_name if full_name else obj.created_by.username
        return None

    def validate(self, attrs):
        adj_type = str(attrs.get("adjustment_type", "add_stock")).lower().strip()
        qty = attrs.get("adjustment_quantity", 0)
        product = attrs.get("product")

        if adj_type in ["set_exact_quantity", "set_exact", "set exact quantity"]:
            if qty < 0:
                raise serializers.ValidationError({"adjustment_quantity": "Exact stock quantity cannot be negative."})
        else:
            if qty <= 0:
                raise serializers.ValidationError({"adjustment_quantity": "Adjustment quantity must be greater than 0."})

        if adj_type in ["subtraction", "decrease", "reduce_stock", "remove_stock", "reduce stock", "remove stock"] and product:
            if product.current_stock < qty:
                raise serializers.ValidationError({
                    "adjustment_quantity": f"Cannot reduce quantity by {qty}. Current available stock is only {product.current_stock}."
                })

        return attrs
