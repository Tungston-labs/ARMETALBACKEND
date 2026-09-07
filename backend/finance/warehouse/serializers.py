from rest_framework import serializers
from .models import Warehouse
from .utils import generate_next_warehouse_code


class WarehouseSerializer(serializers.ModelSerializer):
    code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    manager_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = [
            "id",
            "company",
            "company_name",
            "code",
            "warehouse_name",
            "warehouse_type",
            "manager",
            "manager_name",
            "status",
            "operating_since",
            "country",
            "city",
            "address_line_1",
            "address_line_2",
            "postal_code",
            "phone_number",
            "email",
            "storage_capacity",
            "notes",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "company_name",
            "manager_name",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def get_manager_name(self, obj):
        if obj.manager:
            full_name = obj.manager.get_full_name().strip()
            return full_name if full_name else obj.manager.username
        return None

    def get_created_by_name(self, obj):
        if obj.created_by:
            full_name = obj.created_by.get_full_name().strip()
            return full_name if full_name else obj.created_by.username
        return None

    def get_company_name(self, obj):
        if obj.company:
            return getattr(obj.company, "name", str(obj.company))
        return None

    def validate(self, attrs):
        request = self.context.get("request")
        company = None
        if request and hasattr(request, "user"):
            company = getattr(request.user, "company", None)

        code = attrs.get("code")

        # Auto-generate code if missing/empty on create
        if not self.instance and not code:
            code = generate_next_warehouse_code(company)
            attrs["code"] = code

        if code and company:
            qs = Warehouse.objects.filter(company=company, code=code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"code": f"A warehouse with code '{code}' already exists for your company."}
                )

        return attrs
