from rest_framework import serializers
from .models import FinanceRecord,FinanceCategory

class FinanceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceCategory
        fields = ["id", "name", "payment_type", "company", "created_at"]
        read_only_fields = ["company", "created_at"]

class FinanceRecordSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name",
        read_only=True
    )

    class Meta:
        model = FinanceRecord
        fields = "__all__"