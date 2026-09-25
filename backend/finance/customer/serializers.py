from rest_framework import serializers

from .models import Customer, CustomerDocument


from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from finance.invoice.models import Invoice
from finance.payment.models import Payment

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

    # ---------------------------------------------------------
    # CUSTOMER FINANCIAL SUMMARY
    # ---------------------------------------------------------

    total_invoice = serializers.SerializerMethodField()

    total_payments_received = serializers.SerializerMethodField()

    balance_amount = serializers.SerializerMethodField()

    outstanding_days = serializers.SerializerMethodField()

    last_payment = serializers.SerializerMethodField()

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
            "vat_number",
            "trade_license_number",
            "currency",
            "currency_name",
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

            # Customer financial summary
            "total_invoice",
            "total_payments_received",
            "balance_amount",
            "outstanding_days",
            "last_payment",

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

            # Customer financial summary
            "total_invoice",
            "total_payments_received",
            "balance_amount",
            "outstanding_days",
            "last_payment",

            "created_at",
            "updated_at",
        ]

    # ---------------------------------------------------------
    # TOTAL INVOICE
    # ---------------------------------------------------------

    def get_total_invoice(self, obj):
        total = (
            Invoice.objects
            .filter(
                customer=obj,
                company=obj.company,
            )
            .aggregate(
                total=Sum("total_amount")
            )["total"]
        )

        return total or Decimal("0.00")

    # ---------------------------------------------------------
    # TOTAL PAYMENTS RECEIVED
    # ---------------------------------------------------------

    def get_total_payments_received(self, obj):
        total = (
            Payment.objects
            .filter(
                customer=obj,
                company=obj.company,
                status="completed",
            )
            .aggregate(
                total=Sum("amount_received")
            )["total"]
        )

        return total or Decimal("0.00")

    # ---------------------------------------------------------
    # BALANCE AMOUNT
    # ---------------------------------------------------------

    def get_balance_amount(self, obj):
        invoice_total = (
            Invoice.objects
            .filter(
                customer=obj,
                company=obj.company,
            )
            .aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        payment_total = (
            Payment.objects
            .filter(
                customer=obj,
                company=obj.company,
                status="completed",
            )
            .aggregate(
                total=Sum("amount_received")
            )["total"]
            or Decimal("0.00")
        )

        balance = invoice_total - payment_total

        return max(
            balance,
            Decimal("0.00")
        )

    # ---------------------------------------------------------
    # OUTSTANDING DAYS
    # ---------------------------------------------------------

    def get_outstanding_days(self, obj):
        today = timezone.localdate()

        overdue_invoice = (
            Invoice.objects
            .filter(
                customer=obj,
                company=obj.company,
            )
            .exclude(
                payment_status="paid"
            )
            .filter(
                due_date__lt=today
            )
            .order_by("due_date")
            .first()
        )

        if not overdue_invoice:
            return 0

        return (
            today - overdue_invoice.due_date
        ).days

    # ---------------------------------------------------------
    # LAST PAYMENT
    # ---------------------------------------------------------

    def get_last_payment(self, obj):
        payment = (
            Payment.objects
            .filter(
                customer=obj,
                company=obj.company,
                status="completed",
            )
            .order_by(
                "-payment_date",
                "-id"
            )
            .first()
        )

        if not payment:
            return None

        return payment.payment_date

    # ---------------------------------------------------------
    # VALIDATIONS
    # ---------------------------------------------------------

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


class CustomerHeaderSerializer(serializers.ModelSerializer):
    client_status_name = serializers.CharField(
        source="get_client_status_display",
        read_only=True
    )

    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_id",
            "customer_name",
            "created_at",
            "client_status",
            "client_status_name",
        ]


class CustomerOverviewSerializer(serializers.Serializer):
    header = CustomerHeaderSerializer(source="*", read_only=True)
    company_info = serializers.SerializerMethodField()
    contact_info = serializers.SerializerMethodField()
    financial_info = serializers.SerializerMethodField()
    documents = CustomerDocumentSerializer(many=True, read_only=True)

    def get_company_info(self, obj):
        address_parts = [
            obj.billing_address,
            obj.city,
            obj.state,
            obj.country,
            obj.postal
        ]
        full_address = ", ".join([p for p in address_parts if p and p.strip()])

        return {
            "customer_name": obj.customer_name,
            "company_name": obj.company_name,
            "billing_address": obj.billing_address,
            "city": obj.city,
            "state": obj.state,
            "country": obj.country,
            "postal": obj.postal,
            "full_address": full_address,
            "website": obj.website,
        }

    def get_contact_info(self, obj):
        return {
            "phno": obj.phno,
            "admin_email": obj.admin_email,
            "financial_email": obj.financial_email,
            "technical_email": obj.technical_email,
        }

    def get_financial_info(self, obj):
        return {
            "cr_number": obj.cr_number,
            "vat_number": obj.vat_number,
            "trade_license_number": obj.trade_license_number,
            "currency": obj.currency,
            "currency_name": obj.get_currency_display(),
            "credit_limit": obj.credit_limit,
            "payment_term": obj.payment_term,
            "payment_term_name": obj.get_payment_term_display(),
            "opening_balance": obj.opening_balance,
        }


class CustomerQuotationsKPISerializer(serializers.Serializer):
    total_quotations = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    negotiation_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    rejected_quotations = serializers.IntegerField()
    approved_quotations = serializers.IntegerField()
    pending_quotations = serializers.IntegerField()


class CustomerPaymentsKPISerializer(serializers.Serializer):
    total_payments_received = serializers.DecimalField(max_digits=15, decimal_places=2)
    this_month_collections = serializers.DecimalField(max_digits=15, decimal_places=2)
    pending_payments = serializers.DecimalField(max_digits=15, decimal_places=2)
    overdue_amount = serializers.DecimalField(max_digits=15, decimal_places=2)


class CustomerCreditNotesKPISerializer(serializers.Serializer):
    total_credit_notes = serializers.IntegerField()
    total_credit_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    this_month = serializers.DecimalField(max_digits=15, decimal_places=2)
    open_credit_notes = serializers.IntegerField()