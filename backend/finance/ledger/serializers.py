from rest_framework import serializers

from .models import CustomerLedger


class CustomerLedgerSerializer(
    serializers.ModelSerializer
):

    transaction_type_display = serializers.CharField(
        source="get_transaction_type_display",
        read_only=True,
    )

    customer_name = serializers.CharField(
        source="customer.customer_name",
        read_only=True,
    )

    customer_id_code = serializers.CharField(
        source="customer.customer_id",
        read_only=True,
    )

    invoice_number = serializers.CharField(
        source="invoice.invoice_number",
        read_only=True,
        allow_null=True,
        default="",
    )

    payment_receipt_number = serializers.CharField(
        source="payment.receipt_number",
        read_only=True,
        allow_null=True,
        default="",
    )

    class Meta:

        model = CustomerLedger

        fields = [
            "id",
            "company",
            "customer",
            "customer_name",
            "customer_id_code",
            "transaction_date",
            "transaction_type",
            "transaction_type_display",
            "reference_number",
            "invoice",
            "invoice_number",
            "payment",
            "payment_receipt_number",
            "description",
            "debit",
            "credit",
            "balance",
            "created_by",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields


class CustomerLedgerSummarySerializer(
    serializers.Serializer
):

    customer_id = serializers.IntegerField()

    customer_code = serializers.CharField()

    customer_name = serializers.CharField()

    opening_balance = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    total_debit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    total_credit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    closing_balance = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )