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

from rest_framework import serializers

from .models import Vendor
from finance.purchaseorder.models import PurchaseOrder


class VendorOverviewSerializer(serializers.ModelSerializer):
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

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_id",
            "name",
            "vendor_type",
            "vendor_type_display",
            "client_status",
            "client_status_display",

            # Financial
            "opening_balance",
            "credit_limit",
            "currency",
            "currency_display",
            "payment_term",
            "payment_term_display",

            # Registration
            "cr_number",
            "cr_expiry_date",
            "vat_registration_number",

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

            "created_at",
            "updated_at",
        ]

from rest_framework import serializers

from finance.purchaseorder.models import PurchaseOrder


class VendorPurchaseOrderSerializer(serializers.ModelSerializer):
    po_date = serializers.DateField(
        source="order_date",
        read_only=True,
    )

    delivery_date = serializers.DateField(
        source="expected_delivery_date",
        read_only=True,
    )

    order_status = serializers.CharField(
        source="status",
        read_only=True,
    )

    delivery_status = serializers.CharField(
        source="receipt_status",
        read_only=True,
    )

    payment_status = serializers.CharField(
        source="bill_status",
        read_only=True,
    )

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "po_number",
            "po_date",
            "delivery_date",
            "total_amount",
            "order_status",
            "delivery_status",
            "bill_status",
            "payment_status",
        ]