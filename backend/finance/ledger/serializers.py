from decimal import Decimal

from rest_framework import serializers

from finance.customer.models import Customer

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


class CustomerLedgerListSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(
        source="get_transaction_type_display",
        read_only=True,
    )

    class Meta:
        model = CustomerLedger
        fields = [
            "id",
            "transaction_date",
            "reference_number",
            "description",
            "transaction_type",
            "transaction_type_display",
            "debit",
            "credit",
            "balance",
            "created_at",
        ]
        read_only_fields = fields


class CustomerLedgerCreateSerializer(
    serializers.ModelSerializer
):

    mode = serializers.ChoiceField(
        choices=[
            ("debit", "Debit"),
            ("credit", "Credit"),
        ]
    )

    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    class Meta:
        model = CustomerLedger

        fields = [
            "customer",
            "transaction_date",
            "reference_number",
            "description",
            "mode",
            "amount",
        ]

    def validate_customer(self, customer):

        request = self.context.get("request")

        if request and request.user.company != customer.company:
            raise serializers.ValidationError(
                "Customer does not belong to your company."
            )

        return customer

    def create(self, validated_data):

        mode = validated_data.pop("mode")
        amount = validated_data.pop("amount")

        request = self.context["request"]
        user = request.user

        customer = validated_data["customer"]

        # ------------------------------------------------
        # Determine debit / credit
        # ------------------------------------------------

        if mode == "debit":

            debit = amount
            credit = Decimal("0.00")

        else:

            debit = Decimal("0.00")
            credit = amount

        # ------------------------------------------------
        # Get previous ledger entry
        # ------------------------------------------------

        previous_entry = (
            CustomerLedger.objects
            .filter(
                company=user.company,
                customer=customer,
            )
            .order_by(
                "-transaction_date",
                "-id",
            )
            .first()
        )

        # ------------------------------------------------
        # Determine previous balance
        # ------------------------------------------------

        if previous_entry:

            previous_balance = previous_entry.balance

        else:

            previous_balance = (
                customer.opening_balance
                or Decimal("0.00")
            )

        # ------------------------------------------------
        # Calculate new balance
        # ------------------------------------------------

        balance = (
            previous_balance
            + debit
            - credit
        )

        # ------------------------------------------------
        # Create ledger
        # ------------------------------------------------

        ledger = CustomerLedger.objects.create(
            company=user.company,
            customer=customer,
            transaction_date=validated_data[
                "transaction_date"
            ],
            transaction_type="adjustment",
            reference_number=validated_data.get(
                "reference_number",
                "",
            ),
            description=validated_data.get(
                "description",
                "",
            ),
            debit=debit,
            credit=credit,
            balance=balance,
            created_by=user,
        )

        return ledger


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


class CustomerLedgerCustomerSummarySerializer(
    serializers.Serializer
):
    customer_code = serializers.CharField()
    customer_name = serializers.CharField()

    total_invoice = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    total_payment = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    credit_note = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    overdue = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    outstanding = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

from rest_framework import serializers


class CustomerFinancialSummarySerializer(serializers.Serializer):
    total_receivable = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    total_invoice = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    total_collection = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    total_credit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    overdue_amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )



