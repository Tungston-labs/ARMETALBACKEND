from decimal import Decimal

from rest_framework import serializers

from .models import VendorLedger
from finance.vendor.models import Vendor
from django.db.models import Q

class VendorLedgerCreateSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = VendorLedger

        fields = [
            "id",
            "vendor",
            "entry_date",
            "reference_number",
            "transaction_type",
            "description",
            "debit_amount",
            "credit_amount",
            "attachment",
        ]

        read_only_fields = [
            "id",
        ]

    def validate_vendor(self, vendor):
        request = self.context.get("request")

        if (
            request
            and vendor.company_id != request.user.company_id
        ):
            raise serializers.ValidationError(
                "Invalid vendor for this company."
            )

        return vendor

    def validate(self, attrs):
        debit = attrs.get(
            "debit_amount",
            Decimal("0.00"),
        )

        credit = attrs.get(
            "credit_amount",
            Decimal("0.00"),
        )

        if debit > 0 and credit > 0:
            raise serializers.ValidationError({
                "amount": (
                    "Enter either debit amount or "
                    "credit amount, not both."
                )
            })

        if debit == 0 and credit == 0:
            raise serializers.ValidationError({
                "amount": (
                    "Either debit amount or "
                    "credit amount is required."
                )
            })

        return attrs

    def create(self, validated_data):
        request = self.context["request"]

        return VendorLedger.objects.create(
            company=request.user.company,
            created_by=request.user,
            **validated_data,
        )
    
from rest_framework import serializers

from .models import VendorLedger


class VendorLedgerListSerializer(
    serializers.ModelSerializer
):
    vendor_code = serializers.CharField(
        source="vendor.vendor_id",
        read_only=True,
    )

    vendor_name = serializers.CharField(
        source="vendor.name",
        read_only=True,
    )

    credit_limit = serializers.DecimalField(
        source="vendor.credit_limit",
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )

    opening_balance = serializers.DecimalField(
        source="vendor.opening_balance",
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )

    transaction_type_display = serializers.CharField(
        source="get_transaction_type_display",
        read_only=True,
    )

    balance = serializers.SerializerMethodField()

    due_date = serializers.SerializerMethodField()

    last_payment = serializers.SerializerMethodField()

    vendor_status = serializers.CharField(
        source="vendor.client_status",
        read_only=True,
    )

    class Meta:
        model = VendorLedger

        fields = [
            "id",

            "vendor",
            "vendor_code",
            "vendor_name",
            "vendor_status",

            "credit_limit",
            "opening_balance",

            "entry_date",
            "reference_number",

            "transaction_type",
            "transaction_type_display",

            "description",

            "debit_amount",
            "credit_amount",
            "balance",

            "due_date",
            "last_payment",

            "attachment",
            "created_at",
        ]

    def get_balance(self, obj):

        entries = (
            VendorLedger.objects
            .filter(
                company=obj.company,
                vendor_id=obj.vendor_id,
            )
            .filter(
                Q(entry_date__lt=obj.entry_date)
                |
                Q(
                    entry_date=obj.entry_date,
                    id__lte=obj.id,
                )
            )
            .values(
                "debit_amount",
                "credit_amount",
            )
        )

        debit = sum(
            (
                entry["debit_amount"]
                for entry in entries
            ),
            Decimal("0.00"),
        )

        credit = sum(
            (
                entry["credit_amount"]
                for entry in entries
            ),
            Decimal("0.00"),
        )

        return debit - credit

    def get_due_date(self, obj):
        if obj.bill:
            return obj.bill.due_date

        return None

    def get_last_payment(self, obj):
        payment = (
            obj.vendor.payments
            .filter(
                company=obj.company,
                status="completed",
            )
            .order_by("-payment_date", "-id")
            .first()
        )

        if not payment:
            return None

        return {
            "receipt_number": payment.receipt_number,
            "payment_date": payment.payment_date,
            "amount": payment.amount_paid,
        }