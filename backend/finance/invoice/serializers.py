from decimal import Decimal

from django.db import transaction

from rest_framework import serializers

from .models import Invoice, InvoiceItem

from finance.product.models import Product
from finance.customer.models import Customer


class InvoiceItemSerializer(serializers.ModelSerializer):

    product_name = serializers.CharField(
        source="product.product_name",
        read_only=True
    )

    class Meta:

        model = InvoiceItem

        fields = [
            "id",
            "product",
            "product_name",
            "particular",
            "quantity",
            "hs_code",
            "rate",
            "vat_percentage",
            "vat_sar",
            "amount",
            
        ]

        read_only_fields = [
            "id",
            "product_name",
            "vat_sar",
            "amount",
        ]


class InvoiceSerializer(serializers.ModelSerializer):

    items = InvoiceItemSerializer(
        many=True
    )

    customer_display_name = serializers.CharField(
        source="customer.customer_name",
        read_only=True
    )

    class Meta:

        model = Invoice

        fields = [
            "id",
            "invoice_number",
            "company",
            "customer",
            "customer_display_name",

            "invoice_date",
            "due_date",
            "payment_status",

            "company_name",
            "company_email",
            "company_phone",
            "company_address",

            "customer_name",
            "customer_email",
            "customer_phone",
            "customer_address",

            "account_holder",
            "account_number",
            "iban",
            "qr_code",

            "items",

            "subtotal",
            "total_vat",
            "discount",
            "round_off",
            "total_amount",
            "amount_paid",

            "pdf_file",
            "created_by",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "invoice_number",
            "company",
            "company_name",
            "company_email",
            "company_phone",
            "company_address",
            "customer_name",
            "customer_email",
            "customer_phone",
            "customer_address",
            "subtotal",
            "total_vat",
            "total_amount",
            "pdf_file",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):

        invoice_date = attrs.get(
            "invoice_date",
            getattr(self.instance, "invoice_date", None)
        )

        due_date = attrs.get(
            "due_date",
            getattr(self.instance, "due_date", None)
        )

        if invoice_date and due_date and due_date < invoice_date:
            raise serializers.ValidationError({
                "due_date": "Due date cannot be before invoice date."
            })

        return attrs

    def validate_customer(self, customer):

        request = self.context.get("request")

        if request and customer.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Invalid customer for this company."
            )

        return customer

    def validate_items(self, items):

        if not items:
            raise serializers.ValidationError(
                "At least one invoice item is required."
            )

        return items

    @transaction.atomic
    def create(self, validated_data):

        items_data = validated_data.pop("items")

        request = self.context["request"]

        customer = validated_data["customer"]

        company = request.user.company

        invoice = Invoice.objects.create(
            company=company,
            created_by=request.user,

            company_name=company.name,
            company_email=company.email,
            company_phone=company.contact_number,
            company_address=company.address,

            customer_name=customer.customer_name,
            customer_email=customer.admin_email,
            customer_phone=customer.phno,
            customer_address=customer.billing_address,

            **validated_data
        )

        for item_data in items_data:

            InvoiceItem.objects.create(
                invoice=invoice,
                **item_data
            )

        self.calculate_invoice_totals(invoice)

        return invoice

    @transaction.atomic
    def update(self, instance, validated_data):

        items_data = validated_data.pop("items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if items_data is not None:

            instance.items.all().delete()

            for item_data in items_data:

                InvoiceItem.objects.create(
                    invoice=instance,
                    **item_data
                )

        self.calculate_invoice_totals(instance)

        return instance

    def calculate_invoice_totals(self, invoice):

        subtotal = Decimal("0.00")
        total_vat = Decimal("0.00")

        for item in invoice.items.all():

            item.calculate_amounts()

            item.save(
                update_fields=[
                    "amount",
                    "vat_sar",
                    "updated_at"
                ]
            )

            subtotal += item.amount
            total_vat += item.vat_sar

        total_amount = (
            subtotal
            + total_vat
            - invoice.discount
            + invoice.round_off
        )

        invoice.subtotal = subtotal
        invoice.total_vat = total_vat
        invoice.total_amount = total_amount

        invoice.save(
            update_fields=[
                "subtotal",
                "total_vat",
                "total_amount",
                "updated_at"
            ]
        )


class InvoiceListSerializer(serializers.ModelSerializer):

    amount_to_be_paid = serializers.DecimalField(
        source="total_amount",
        max_digits=15,
        decimal_places=2,
        read_only=True
    )

    paid_amount = serializers.DecimalField(
        source="amount_paid",
        max_digits=15,
        decimal_places=2,
        read_only=True
    )

    balance = serializers.SerializerMethodField()

    status = serializers.CharField(
        source="payment_status",
        read_only=True
    )

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "customer_name",
            "invoice_date",
            "due_date",
            "amount_to_be_paid",
            "paid_amount",
            "balance",
            "status",
        ]

    def get_balance(self, obj):
        return max(
            obj.total_amount - obj.amount_paid,
            Decimal("0.00")
        )