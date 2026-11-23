from rest_framework import serializers
from decimal import Decimal

from .models import (
    Vendor,
    VendorDocument,
    VendorPayment,
)
from finance.bill.models import Bill


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

    def validate(self, attrs):
        vendor = attrs.get("vendor") or getattr(self.instance, "vendor", None)
        bill = attrs.get("bill") or getattr(self.instance, "bill", None)

        if bill and vendor and bill.vendor and bill.vendor != vendor:
            raise serializers.ValidationError({
                "bill": "Selected bill does not belong to the selected vendor."
            })

        return attrs



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

class VendorPaymentListSerializer(serializers.ModelSerializer):
    vendor_name = serializers.ReadOnlyField(source="vendor.name")
    bill_number = serializers.ReadOnlyField(source="bill.bill_number")
    payment_no = serializers.CharField(source="receipt_number", read_only=True)
    receipt_no = serializers.CharField(source="receipt_number", read_only=True)
    payment_number = serializers.CharField(source="receipt_number", read_only=True)
    payment_type_name = serializers.CharField(source="get_payment_type_display", read_only=True)
    payment_method_name = serializers.CharField(source="get_payment_method_display", read_only=True)
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    amount = serializers.DecimalField(source="amount_paid", max_digits=15, decimal_places=2, read_only=True)
    amount_received = serializers.DecimalField(source="amount_paid", max_digits=15, decimal_places=2, read_only=True)
    bill_total = serializers.DecimalField(source="bill.total_amount", max_digits=15, decimal_places=2, read_only=True, default=Decimal("0.00"))
    bill_amount = serializers.DecimalField(source="bill.total_amount", max_digits=15, decimal_places=2, read_only=True, default=Decimal("0.00"))
    already_paid = serializers.DecimalField(source="bill.amount_paid", max_digits=15, decimal_places=2, read_only=True, default=Decimal("0.00"))
    balance_due = serializers.DecimalField(source="bill.balance", max_digits=15, decimal_places=2, read_only=True, default=Decimal("0.00"))
    outstanding_amount = serializers.DecimalField(source="bill.balance", max_digits=15, decimal_places=2, read_only=True, default=Decimal("0.00"))

    class Meta:
        model = VendorPayment
        fields = [
            "id",
            "receipt_number",
            "receipt_no",
            "payment_no",
            "payment_number",
            "vendor",
            "vendor_name",
            "bill",
            "bill_number",
            "bill_total",
            "bill_amount",
            "already_paid",
            "balance_due",
            "outstanding_amount",
            "payment_date",
            "payment_type",
            "payment_type_name",
            "payment_method",
            "payment_method_name",
            "amount_paid",
            "amount",
            "amount_received",
            "reference_number",
            "bank_name",
            "account_holder",
            "iban",
            "notes",
            "status",
            "status_name",
            "created_at",
            "updated_at",
        ]


class VendorPaymentSerializer(serializers.ModelSerializer):
    receipt_number = serializers.CharField(required=False, allow_blank=True)
    payment_no = serializers.CharField(source="receipt_number", read_only=True)
    receipt_no = serializers.CharField(source="receipt_number", read_only=True)
    payment_number = serializers.CharField(source="receipt_number", read_only=True)
    vendor_name = serializers.ReadOnlyField(source="vendor.name")
    bill_number = serializers.ReadOnlyField(source="bill.bill_number")
    payment_type_name = serializers.CharField(source="get_payment_type_display", read_only=True)
    payment_method_name = serializers.CharField(source="get_payment_method_display", read_only=True)
    status_name = serializers.CharField(source="get_status_display", read_only=True)
    bill_total = serializers.DecimalField(source="bill.total_amount", max_digits=15, decimal_places=2, read_only=True, default=Decimal("0.00"))
    bill_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    already_paid = serializers.DecimalField(source="bill.amount_paid", max_digits=15, decimal_places=2, read_only=True, default=Decimal("0.00"))
    balance_due = serializers.DecimalField(source="bill.balance", max_digits=15, decimal_places=2, read_only=True, default=Decimal("0.00"))
    outstanding_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    amount = serializers.DecimalField(source="amount_paid", max_digits=15, decimal_places=2, required=False)
    amount_received = serializers.DecimalField(source="amount_paid", max_digits=15, decimal_places=2, required=False)
    amount_paid = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)

    class Meta:
        model = VendorPayment
        fields = [
            "id",
            "company",
            "receipt_number",
            "receipt_no",
            "payment_no",
            "payment_number",
            "vendor",
            "vendor_name",
            "bill",
            "bill_number",
            "bill_total",
            "bill_amount",
            "already_paid",
            "balance_due",
            "outstanding_amount",
            "payment_date",
            "payment_type",
            "payment_type_name",
            "payment_method",
            "payment_method_name",
            "amount_paid",
            "amount",
            "amount_received",
            "reference_number",
            "bank_name",
            "account_holder",
            "iban",
            "notes",
            "status",
            "status_name",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "bill_total",
            "bill_amount",
            "already_paid",
            "balance_due",
            "outstanding_amount",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        # Support aliases for amount
        if "amount_paid" not in attrs:
            if "amount" in self.initial_data:
                attrs["amount_paid"] = self.initial_data["amount"]
            elif "amount_received" in self.initial_data:
                attrs["amount_paid"] = self.initial_data["amount_received"]

        if "amount_paid" not in attrs and not self.instance:
            raise serializers.ValidationError({"amount_paid": "This field is required."})

        # Support aliases for vendor and bill
        if "vendor" not in attrs and "vendor_id" in self.initial_data:
            from finance.vendor.models import Vendor
            try:
                attrs["vendor"] = Vendor.objects.get(id=self.initial_data["vendor_id"])
            except Vendor.DoesNotExist:
                raise serializers.ValidationError({"vendor": "Vendor does not exist."})

        if "bill" not in attrs and "bill_id" in self.initial_data and self.initial_data["bill_id"]:
            from finance.bill.models import Bill
            try:
                attrs["bill"] = Bill.objects.get(id=self.initial_data["bill_id"])
            except Bill.DoesNotExist:
                raise serializers.ValidationError({"bill": "Bill does not exist."})

        vendor = attrs.get("vendor") or getattr(self.instance, "vendor", None)
        bill = attrs.get("bill") or getattr(self.instance, "bill", None)

        if bill and vendor and bill.vendor and bill.vendor != vendor:
            raise serializers.ValidationError({
                "bill": "Selected bill does not belong to the selected vendor."
            })

        return attrs


class VendorPaymentKPISerializer(serializers.Serializer):
    total_payments = serializers.DecimalField(max_digits=15, decimal_places=2)
    payments_this_month = serializers.DecimalField(max_digits=15, decimal_places=2)
    outstanding = serializers.DecimalField(max_digits=15, decimal_places=2)
    advance_payments = serializers.DecimalField(max_digits=15, decimal_places=2)





from rest_framework import serializers
from decimal import Decimal

from .models import (
    Vendor,
    VendorDocument,
    VendorPayment,
)
from finance.bill.models import Bill


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

    def validate(self, attrs):
        vendor = attrs.get("vendor") or getattr(self.instance, "vendor", None)
        bill = attrs.get("bill") or getattr(self.instance, "bill", None)

        if bill and vendor and bill.vendor and bill.vendor != vendor:
            raise serializers.ValidationError({
                "bill": "Selected bill does not belong to the selected vendor."
            })

        return attrs



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


from rest_framework import serializers

from .models import VendorDocument


class VendorDocumentUploadSerializer(serializers.ModelSerializer):

    class Meta:
        model = VendorDocument
        fields = [
            "id",
            "vendor",
            "document",
            "document_name",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_vendor(self, value):
        request = self.context["request"]

        if value.company_id != request.user.company.id:
            raise serializers.ValidationError(
                "Vendor does not belong to your company."
            )

        return value



from rest_framework import serializers

from finance.bill.models import Bill


class VendorBillListSerializer(serializers.ModelSerializer):

    balance_amount = serializers.DecimalField(
        source="balance",
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )

    balance_due = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Bill
        fields = [
            "id",
            "bill_number",
            "po_reference",
            "bill_date",
            "due_date",
            "total_amount",
            "balance_amount",
            "balance_due",
            "status",
        ]



from .models import VendorPayment


class VendorDetailPaymentListSerializer(serializers.ModelSerializer):

    payment_number = serializers.CharField(
        source="receipt_number",
        read_only=True,
    )

    bill_number = serializers.CharField(
        source="bill.bill_number",
        read_only=True,
    )

    payment_method_name = serializers.CharField(
        source="get_payment_method_display",
        read_only=True,
    )

    status_name = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = VendorPayment

        fields = [
            "id",
            "payment_number",
            "bill",
            "bill_number",
            "payment_date",
            "payment_method",
            "payment_method_name",
            "reference_number",
            "amount_paid",
            "status",
            "status_name",
        ]

from rest_framework import serializers

from finance.debit_note.models import DebitNote


class VendorDebitNoteListSerializer(serializers.ModelSerializer):
    debit_note_number = serializers.CharField(
        source="dn_number",
        read_only=True
    )

    bill_number = serializers.CharField(
        source="bill.bill_number",
        read_only=True
    )

    bill_amount = serializers.DecimalField(
        source="bill.total_amount",
        max_digits=15,
        decimal_places=2,
        read_only=True
    )

    reason_name = serializers.CharField(
        source="get_reason_display",
        read_only=True
    )

    status_name = serializers.CharField(
        source="get_status_display",
        read_only=True
    )

    after_applied_amount = serializers.DecimalField(
        source="applied_amount",
        max_digits=15,
        decimal_places=2,
        read_only=True
    )

    pending_amount = serializers.DecimalField(
        source="balance",
        max_digits=15,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = DebitNote
        fields = [
            "id",
            "debit_note_number",
            "bill",
            "bill_number",
            "issue_date",
            "reason",
            "reason_name",
            "bill_amount",
            "debit_amount",
            "after_applied_amount",
            "pending_amount",
            "status",
            "status_name",       # <-- ADD THIS
        ]