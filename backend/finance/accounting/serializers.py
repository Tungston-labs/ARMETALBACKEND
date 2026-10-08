from rest_framework import serializers

from .models import ChartOfAccount


class ChartOfAccountSerializer(serializers.ModelSerializer):

    account_type_display = serializers.CharField(
        source="get_account_type_display",
        read_only=True
    )

    category_display = serializers.CharField(
        source="get_category_display",
        read_only=True
    )

    opening_balance_type_display = serializers.CharField(
        source="get_opening_balance_type_display",
        read_only=True
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True
    )

    parent_account_name = serializers.CharField(
        source="parent_account.account_name",
        read_only=True
    )

    balance = serializers.SerializerMethodField()

    class Meta:
        model = ChartOfAccount

        fields = [
            "id",
            "account_type",
            "account_type_display",
            "account_name",
            "account_code",
            "parent_account",
            "parent_account_name",
            "category",
            "category_display",
            "opening_balance",
            "opening_balance_type",
            "opening_balance_type_display",
            "balance",
            "status",
            "status_display",
            "description",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "balance",
            "created_at",
            "updated_at",
        ]

    def get_balance(self, obj):
        """
        For now, balance is based only on opening balance.

        Once Journal Entry is implemented, this will be changed
        to calculate the current balance from posted journal entries.
        """

        if obj.opening_balance_type == "credit":
            return -obj.opening_balance

        return obj.opening_balance

    def validate_account_code(self, value):
        company = self.context["request"].user.company

        queryset = ChartOfAccount.objects.filter(
            company=company,
            account_code=value
        )

        if self.instance:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise serializers.ValidationError(
                "Account code already exists for this company."
            )

        return value

    def validate_parent_account(self, value):

        if not value:
            return value

        company = self.context["request"].user.company

        if value.company_id != company.id:
            raise serializers.ValidationError(
                "Parent account must belong to the same company."
            )

        return value