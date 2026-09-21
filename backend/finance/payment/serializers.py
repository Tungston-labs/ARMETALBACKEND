from decimal import Decimal
from rest_framework import serializers

from finance.customer.models import Customer
from finance.invoice.models import Invoice
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        required=False,
        allow_null=True
    )
    invoice = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(),
        required=False,
        allow_null=True
    )
    customer_name = serializers.CharField(
        source="customer.customer_name",
        read_only=True
    )
    customer_id_code = serializers.CharField(
        source="customer.customer_id",
        read_only=True
    )
    invoice_number = serializers.CharField(
        source="invoice.invoice_number",
        read_only=True,
        default=""
    )
    invoice_amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    outstanding_amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "receipt_number",
            "company",
            "customer",
            "customer_name",
            "customer_id_code",
            "invoice",
            "invoice_number",
            "invoice_amount",
            "outstanding_amount",
            "payment_date",
            "payment_type",
            "payment_method",
            "amount_received",
            "reference_number",
            "notes",
            "status",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "receipt_number",
            "company",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj):
        if obj and obj.created_by:
            full_name = obj.created_by.get_full_name()
            return full_name if full_name else obj.created_by.username
        return ""

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated or not getattr(user, "company", None):
            raise serializers.ValidationError("Authentication and valid company context are required.")

        company = user.company

        customer = attrs.get("customer")
        if not customer and self.instance:
            customer = self.instance.customer

        invoice = attrs.get("invoice")
        if "invoice" not in attrs and self.instance:
            invoice = self.instance.invoice

        # Auto-assign customer from invoice if invoice is provided and customer is missing
        if invoice and not customer:
            customer = invoice.customer
            attrs["customer"] = customer

        if not customer:
            raise serializers.ValidationError({"customer": "Customer is required."})

        if customer.company != company:
            raise serializers.ValidationError({"customer": "Selected customer does not belong to your company."})

        if invoice:
            if invoice.company != company:
                raise serializers.ValidationError({"invoice": "Selected invoice does not belong to your company."})

            if invoice.customer != customer:
                raise serializers.ValidationError({
                    "invoice": f"Invoice '{invoice.invoice_number}' belongs to customer '{invoice.customer.customer_name}', not selected customer."
                })

        amount_received = attrs.get("amount_received")
        if amount_received is None and self.instance:
            amount_received = self.instance.amount_received

        if amount_received is not None and amount_received < Decimal("0.00"):
            raise serializers.ValidationError({"amount_received": "Amount received cannot be negative."})

        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["company"] = user.company
        validated_data["created_by"] = user
        return super().create(validated_data)


class PaymentListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source="customer.customer_name",
        read_only=True
    )
    invoice_number = serializers.CharField(
        source="invoice.invoice_number",
        read_only=True,
        default=""
    )
    payment_type_display = serializers.CharField(
        source="get_payment_type_display",
        read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display",
        read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "receipt_number",
            "customer",
            "customer_name",
            "invoice",
            "invoice_number",
            "payment_date",
            "payment_type",
            "payment_type_display",
            "payment_method",
            "payment_method_display",
            "amount_received",
            "reference_number",
            "status",
            "status_display",
            "created_at",
        ]


class PaymentKPISerializer(serializers.Serializer):
    total_collections = serializers.DecimalField(max_digits=15, decimal_places=2)
    this_month_collections = serializers.DecimalField(max_digits=15, decimal_places=2)
    outstanding_receivables = serializers.DecimalField(max_digits=15, decimal_places=2)
    overdue_receivables = serializers.DecimalField(max_digits=15, decimal_places=2)
    collection_rate = serializers.FloatField()
