from rest_framework import serializers
from django.db.models import Q

from .models import Category


class CategorySerializer(serializers.ModelSerializer):

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
            "created_at",
            "updated_at",
        ]