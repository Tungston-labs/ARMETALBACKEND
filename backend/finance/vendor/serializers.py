from rest_framework import serializers

from .models import (
    Vendor,
    VendorDocument,
)


class VendorDocumentSerializer(serializers.ModelSerializer):

    document_url = serializers.SerializerMethodField()

    class Meta:
        model = VendorDocument
        fields = [
            "id",
            "document_name",
            "document",
            "document_url",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "document_url",
            "created_at",
        ]

    def get_document_url(self, obj):

        if not obj.document:
            return None

        request = self.context.get("request")

        if request:
            return request.build_absolute_uri(
                obj.document.url
            )

        return obj.document.url


class VendorSerializer(serializers.ModelSerializer):

    vendor_type_display = serializers.CharField(
        source="get_vendor_type_display",
        read_only=True,
    )

    client_status_display = serializers.CharField(
        source="get_client_status_display",
        read_only=True,
    )

    payment_term_display = serializers.CharField(
        source="get_payment_term_display",
        read_only=True,
    )

    currency_display = serializers.CharField(
        source="get_currency_display",
        read_only=True,
    )

    documents = VendorDocumentSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Vendor

        fields = [
            "id",
            "vendor_id",
            "company",
            "name",
            "vendor_type",
            "vendor_type_display",
            "opening_balance",
            "credit_limit",
            "cr_number",
            "currency",
            "currency_display",
            "vat_registration_number",
            "payment_term",
            "payment_term_display",
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

            # Bank
            "bank_name",
            "account_num",
            "iban",
            "branch",

            "client_status",
            "client_status_display",

            "created_by",
            "created_at",
            "updated_at",

            "documents",
        ]

        read_only_fields = [
            "id",
            "vendor_id",
            "company",
            "created_by",
            "created_at",
            "updated_at",
            "documents",
        ]


class VendorCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Vendor

        fields = [
            "name",
            "vendor_type",
            "opening_balance",
            "credit_limit",
            "cr_number",
            "currency",
            "vat_registration_number",
            "payment_term",
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

            # Bank
            "bank_name",
            "account_num",
            "iban",
            "branch",

            "client_status",
        ]