from rest_framework import serializers
from .models import Category
from .utils import generate_next_category_code


class CategorySerializer(serializers.ModelSerializer):

    company_name = serializers.CharField(
        source="company.name",
        read_only=True
    )

    parent_category_name = serializers.CharField(
        source="parent_category.category_name",
        read_only=True
    )

    created_by_name = serializers.CharField(
        source="created_by.username",
        read_only=True
    )

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
            "parent_category_name",
            "created_at",
            "updated_at",
        ]

    def validate_code(self, value):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return value

        company = request.user.company

        if not company:
            raise serializers.ValidationError(
                "User is not associated with a company."
            )

        queryset = Category.objects.filter(
            company=company,
            code=value,
        )

        if self.instance:
            queryset = queryset.exclude(
                id=self.instance.id
            )

        if queryset.exists():
            raise serializers.ValidationError(
                "A category with this code already exists."
            )

        return value

    def validate_parent_category(self, value):
        if value is None:
            return value

        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return value

        company = request.user.company

        if not company:
            raise serializers.ValidationError(
                "User is not associated with a company."
            )

        if value.company_id != company.id:
            raise serializers.ValidationError(
                "Parent category must belong to the same company."
            )

        if self.instance and value.id == self.instance.id:
            raise serializers.ValidationError(
                "A category cannot be its own parent."
            )

        if value.parent_category_id is not None:
            raise serializers.ValidationError(
                "A sub-category cannot be used as a parent category."
            )

        return value
