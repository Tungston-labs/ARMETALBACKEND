from rest_framework import serializers
from decimal import Decimal
from .models import Quotation, QuotationItem, QuotationConversion
from finance.customer.models import Customer
from finance.product.models import Product


class QuotationItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="product.product_name")

    class Meta:
        model = QuotationItem
        fields = [
            "id",
            "product",
            "product_name",
            "service_name",
            "description",
            "quantity",
            "hs_code",
            "rate",
            "vat_percentage",
            "vat_amount",
            "amount",
        ]
        read_only_fields = ["id"]


class QuotationConversionSerializer(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField(source="customer.customer_name")
    quote_number = serializers.ReadOnlyField(source="quotation.quote_number")

    class Meta:
        model = QuotationConversion
        fields = [
            "id",
            "quotation",
            "quote_number",
            "customer",
            "customer_name",
            "company",
            "invoice_no",
            "invoice_amount",
            "outstanding_amount",
            "payment_date",
            "payment_type",
            "payment_method",
            "amount_received",
            "reference_number",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "quotation", "customer", "company", "created_at"]


class QuotationListSerializer(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField(source="customer.customer_name")

    class Meta:
        model = Quotation
        fields = [
            "id",
            "quote_number",
            "customer",
            "customer_name",
            "issue_date",
            "valid_till",
            "quote_amount",
            "negotiation_amount",
            "status",
            "notes",
            "created_at",
        ]


class QuotationSerializer(serializers.ModelSerializer):
    quote_number = serializers.CharField(required=False, allow_blank=True)
    items = QuotationItemSerializer(many=True, required=False)
    conversions = QuotationConversionSerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField(source="customer.customer_name")

    class Meta:
        model = Quotation
        fields = [
            "id",
            "company",
            "quote_number",
            "customer",
            "customer_name",
            "issue_date",
            "valid_till",
            "status",
            "from_company_name",
            "from_address",
            "from_phone_number",
            "from_email",
            "bill_to_name",
            "bill_to_address",
            "bill_to_phone",
            "finance_contact_email",
            "sub_total",
            "total_vat",
            "discount",
            "round_off",
            "quote_amount",
            "negotiation_amount",
            "notes",
            "items",
            "conversions",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        quotation = Quotation.objects.create(**validated_data)

        calculated_subtotal = Decimal("0.00")
        calculated_vat = Decimal("0.00")

        for item_data in items_data:
            qty = Decimal(str(item_data.get("quantity", 1)))
            rate = Decimal(str(item_data.get("rate", 0)))
            vat_pct = Decimal(str(item_data.get("vat_percentage", 15)))

            line_base = qty * rate
            line_vat = line_base * (vat_pct / Decimal("100"))
            line_amount = line_base + line_vat

            if "vat_amount" not in item_data or not item_data["vat_amount"]:
                item_data["vat_amount"] = line_vat
            if "amount" not in item_data or not item_data["amount"]:
                item_data["amount"] = line_amount

            QuotationItem.objects.create(quotation=quotation, **item_data)
            calculated_subtotal += line_base
            calculated_vat += line_vat

        needs_save = False
        if not quotation.sub_total or quotation.sub_total == Decimal("0.00"):
            quotation.sub_total = calculated_subtotal
            needs_save = True

        if not quotation.total_vat or quotation.total_vat == Decimal("0.00"):
            quotation.total_vat = calculated_vat
            needs_save = True

        if not quotation.quote_amount or quotation.quote_amount == Decimal("0.00"):
            discount = quotation.discount or Decimal("0.00")
            round_off = quotation.round_off or Decimal("0.00")
            quotation.quote_amount = (
                quotation.sub_total + quotation.total_vat - discount + round_off
            )
            needs_save = True

        if needs_save:
            quotation.save()

        return quotation

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if items_data is not None:
            instance.items.all().delete()
            calculated_subtotal = Decimal("0.00")
            calculated_vat = Decimal("0.00")

            for item_data in items_data:
                qty = Decimal(str(item_data.get("quantity", 1)))
                rate = Decimal(str(item_data.get("rate", 0)))
                vat_pct = Decimal(str(item_data.get("vat_percentage", 15)))

                line_base = qty * rate
                line_vat = line_base * (vat_pct / Decimal("100"))
                line_amount = line_base + line_vat

                if "vat_amount" not in item_data or not item_data["vat_amount"]:
                    item_data["vat_amount"] = line_vat
                if "amount" not in item_data or not item_data["amount"]:
                    item_data["amount"] = line_amount

                QuotationItem.objects.create(quotation=instance, **item_data)
                calculated_subtotal += line_base
                calculated_vat += line_vat

            if "sub_total" not in validated_data:
                instance.sub_total = calculated_subtotal
            if "total_vat" not in validated_data:
                instance.total_vat = calculated_vat
            if "quote_amount" not in validated_data:
                discount = instance.discount or Decimal("0.00")
                round_off = instance.round_off or Decimal("0.00")
                instance.quote_amount = (
                    instance.sub_total + instance.total_vat - discount + round_off
                )

        instance.save()
        return instance
