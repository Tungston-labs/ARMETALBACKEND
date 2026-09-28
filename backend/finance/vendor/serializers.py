from rest_framework import serializers

from .models import (
    Vendor,
    VendorDocument,
)


class VendorDocumentSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = VendorDocument

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


class VendorSerializer(
    serializers.ModelSerializer
):

    documents = VendorDocumentSerializer(
        many=True,
        read_only=True,
    )

    vendor_type_name = serializers.CharField(
        source="get_vendor_type_display",
        read_only=True,
    )

    payment_term_name = serializers.CharField(
        source="get_payment_term_display",
        read_only=True,
    )

    currency_name = serializers.CharField(
        source="get_currency_display",
        read_only=True,
    )

    client_status_name = serializers.CharField(
        source="get_client_status_display",
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
            "vendor_type_name",
            "opening_balance",
            "credit_limit",
            "cr_number",
            "currency",
            "currency_name",
            "vat_registration_number",
            "payment_term",
            "payment_term_name",
            "cr_expiry_date",

            # Address
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
            "client_status_name",

            "documents",
            "created_by",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "vendor_id",
            "company",
            "created_by",
            "documents",
            "vendor_type_name",
            "payment_term_name",
            "currency_name",
            "client_status_name",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Vendor name cannot be empty."
            )

        return value

    def validate_opening_balance(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Opening balance cannot be negative."
            )

        return value

    def validate_credit_limit(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Credit limit cannot be negative."
            )

        return value


class VendorCreateSerializer(VendorSerializer):
    """
    Multipart form-data create serializer.
    Documents are uploaded using the 'documents' key.
    """

    documents = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        write_only=True,
    )

    class Meta(VendorSerializer.Meta):
        fields = VendorSerializer.Meta.fields

    def create(self, validated_data):
        documents = validated_data.pop(
            "documents",
            [],
        )

        vendor = Vendor.objects.create(
            **validated_data
        )

        VendorDocument.objects.bulk_create([
            VendorDocument(
                vendor=vendor,
                document=document,
                document_name=document.name,
            )
            for document in documents
        ])

        return vendor