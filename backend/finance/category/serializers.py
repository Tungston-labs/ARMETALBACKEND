from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):

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
            "created_by",
            "created_by_name",
            "parent_category_name",
            "created_at",
            "updated_at",
        ]

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

        # Parent must belong to same company
        if value.company_id != company.id:
            raise serializers.ValidationError(
                "Parent category must belong to the same company."
            )

        # A category cannot be its own parent
        if self.instance and value.id == self.instance.id:
            raise serializers.ValidationError(
                "A category cannot be its own parent."
            )

        # Parent must itself be a parent category
        if value.parent_category_id is not None:
            raise serializers.ValidationError(
                "A sub-category cannot be used as a parent category."
            )

        return value