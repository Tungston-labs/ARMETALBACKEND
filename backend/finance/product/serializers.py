from rest_framework import serializers
from .models import Product
from .utils import generate_next_product_code


class ProductSerializer(serializers.ModelSerializer):
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    company_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    warehouse_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    stock_status = serializers.ReadOnlyField()
    inventory_value = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            "id",
            "company",
            "company_name",
            "code",
            "product_name",
            "product_type",
            "sku",
            "category",
            "category_name",
            "warehouse",
            "warehouse_name",
            "brand",
            "supplier",
            "unit",
            "quantity",
            "hsn_sac_code",
            "cost_price",
            "selling_price",
            "opening_stock_qty",
            "current_stock",
            "reserved_qty",
            "reorder_level",
            "stock_status",
            "inventory_value",
            "tax_type",
            "tax_rate",
            "description",
            "status",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "company_name",
            "category_name",
            "warehouse_name",
            "stock_status",
            "inventory_value",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def get_company_name(self, obj):
        if obj.company:
            return getattr(obj.company, "name", str(obj.company))
        return None

    def get_category_name(self, obj):
        if obj.category:
            return getattr(obj.category, "category_name", str(obj.category))
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
        request = self.context.get("request")
        company = None
        if request and hasattr(request, "user"):
            company = getattr(request.user, "company", None)

        code = attrs.get("code")

        # Auto-generate code if missing/empty on create
        if not self.instance and not code:
            code = generate_next_product_code(company)
            attrs["code"] = code

        if code and company:
            qs = Product.objects.filter(company=company, code=code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"code": f"A product with code '{code}' already exists for your company."}
                )

        return attrs
