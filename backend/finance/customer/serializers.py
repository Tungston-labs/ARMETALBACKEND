from rest_framework import serializers

from .models import Customer, CustomerDocument


class CustomerDocumentSerializer(
    serializers.ModelSerializer
):

    class Meta:
        model = CustomerDocument

        fields = [
            "id",
            "document",
            "document_name",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]


class CustomerSerializer(
    serializers.ModelSerializer
):

    created_by_name = serializers.CharField(
        source="created_by.username",
        read_only=True
    )

    documents = CustomerDocumentSerializer(
        many=True,
        read_only=True
    )

    industry_name = serializers.CharField(
        source="get_industry_display",
        read_only=True
    )

    currency_name = serializers.CharField(
        source="get_currency_display",
        read_only=True
    )

    payment_term_name = serializers.CharField(
        source="get_payment_term_display",
        read_only=True
    )

    client_status_name = serializers.CharField(
        source="get_client_status_display",
        read_only=True
    )

    class Meta:
        model = Customer

        fields = [
            "id",
            "customer_id",
            "company",
            "customer_name",
            "company_name",
            "industry",
            "industry_name",
            "website",
            "cr_number",
            "currency",
            "currency_name",
            "vat_number",
            "payment_term",
            "payment_term_name",
            "cr_expiry_date",

            # Billing address
            "billing_address",
            "city",
            "state",
            "country",
            "postal",

            # Contact
            "phno",
            "admin_email",
            "financial_email",
            "technical_email",

            "client_status",
            "client_status_name",

            # Financial
            "credit_limit",
            "opening_balance",
            "notes",

            # Documents
            "documents",

            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "customer_id",
            "company",
            "created_by",
            "created_by_name",
            "industry_name",
            "currency_name",
            "payment_term_name",
            "client_status_name",
            "documents",
            "created_at",
            "updated_at",
        ]

    def validate_customer_name(self, value):

        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Customer name cannot be empty."
            )

        return value

    def validate_credit_limit(self, value):

        if value < 0:
            raise serializers.ValidationError(
                "Credit limit cannot be negative."
            )

        return value

    def validate_opening_balance(self, value):

        if value < 0:
            raise serializers.ValidationError(
                "Opening balance cannot be negative."
            )

        return value