from rest_framework import serializers
from .models import Category
from .utils import generate_next_category_code


class CategorySerializer(serializers.ModelSerializer):
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    company_name = serializers.SerializerMethodField()
    parent_category_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "company",
            "company_name",
            "code",
            "category_name",
            "parent_category",
            "parent_category_name",
            "category_type",
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
            "parent_category_name",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def get_company_name(self, obj):
        if obj.company:
            return getattr(obj.company, "name", str(obj.company))
        return None

    def get_parent_category_name(self, obj):
        if obj.parent_category:
            return obj.parent_category.category_name
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
        if not self.instance and not code:
            code = generate_next_category_code(company)
            attrs["code"] = code

        if code and company:
            qs = Category.objects.filter(company=company, code=code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"code": f"A category with code '{code}' already exists for your company."}
                )

        return attrs

