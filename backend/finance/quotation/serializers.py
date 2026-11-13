from collections.abc import Mapping
from decimal import Decimal
from rest_framework import serializers
from .models import Quotation, QuotationItem, QuotationConversion
from finance.customer.models import Customer
from finance.product.models import Product

QUOTATION_STATUS_MAP = {
    **{k.lower(): k for k, _ in Quotation.STATUS_CHOICES},
    **{v.lower(): k for k, v in Quotation.STATUS_CHOICES},
}


def _normalize_quotation_input(data):
    if not isinstance(data, Mapping):
        return data
    data = data.copy()
    if data.get("valid_till") == "":
        data["valid_till"] = None
    if data.get("old_quote_amount") == "":
        data["old_quote_amount"] = None
    raw_status = data.get("status")
    if isinstance(raw_status, str):
        mapped = QUOTATION_STATUS_MAP.get(raw_status.strip().lower())
        if mapped:
            data["status"] = mapped
    return data


class QuotationItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
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
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Quotation
        fields = [
            "id",
            "quote_number",
            "customer",
            "customer_name",
            "currency",
            "issue_date",
            "valid_till",
            "old_quote_amount",
            "quote_amount",
            "negotiation_amount",
            "status",
            "notes",
            "created_at",
        ]

    def get_currency(self, obj):
        customer_currency = getattr(obj.customer, "currency", None) if obj.customer else None
        if customer_currency:
            return customer_currency
        if obj.company:
            return getattr(obj.company, "currency", None) or "SAR"
        return "SAR"


class QuotationSerializer(serializers.ModelSerializer):
    quote_number = serializers.CharField(required=False, allow_blank=True)
    issue_date = serializers.DateField(
        input_formats=["iso-8601", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]
    )
    valid_till = serializers.DateField(
        required=False,
        allow_null=True,
        input_formats=["iso-8601", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"],
    )
    items = QuotationItemSerializer(many=True, required=False)
    conversions = QuotationConversionSerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField(source="customer.customer_name")
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Quotation
        fields = [
            "id",
            "company",
            "currency",
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
            "old_quote_amount",
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
            "currency",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_currency(self, obj):
        customer_currency = getattr(obj.customer, "currency", None) if obj.customer else None
        if customer_currency:
            return customer_currency
        if obj.company:
            return getattr(obj.company, "currency", None) or "SAR"
        return "SAR"

    def to_internal_value(self, data):
        return super().to_internal_value(_normalize_quotation_input(data))

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        quotation = Quotation.objects.create(**validated_data)

        calculated_subtotal = Decimal("0.00")
        calculated_vat = Decimal("0.00")

        for item_data in items_data:
            item_data.pop("id", None)
            qty = Decimal(str(item_data.get("quantity", 1)))
            rate = Decimal(str(item_data.get("rate", 0)))
            vat_pct = Decimal(str(item_data.get("vat_percentage", 15)))

            line_base = qty * rate
            line_vat = line_base * (vat_pct / Decimal("100"))
            line_amount = line_base + line_vat

            item_data["vat_amount"] = line_vat
            item_data["amount"] = line_amount

            QuotationItem.objects.create(quotation=quotation, **item_data)
            calculated_subtotal += line_base
            calculated_vat += line_vat

        if not quotation.sub_total or quotation.sub_total == Decimal("0.00"):
            quotation.sub_total = calculated_subtotal

        if not quotation.total_vat or quotation.total_vat == Decimal("0.00"):
            quotation.total_vat = calculated_vat

        discount = quotation.discount or Decimal("0.00")
        round_off = quotation.round_off or Decimal("0.00")
        base_total = quotation.sub_total + quotation.total_vat - discount + round_off

        negotiation = quotation.negotiation_amount or Decimal("0.00")
        if negotiation > Decimal("0.00"):
            quotation.old_quote_amount = base_total
            quotation.quote_amount = max(Decimal("0.00"), base_total - negotiation)
        else:
            quotation.old_quote_amount = None
            quotation.quote_amount = base_total

        quotation.save()
        return quotation

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        explicit_old_quote_amount = "old_quote_amount" in validated_data

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if items_data is not None:
            existing_items = {item.id: item for item in instance.items.all()}
            kept_item_ids = set()
            calculated_subtotal = Decimal("0.00")
            calculated_vat = Decimal("0.00")

            for item_data in items_data:
                item_id = item_data.pop("id", None)
                qty = Decimal(str(item_data.get("quantity", 1)))
                rate = Decimal(str(item_data.get("rate", 0)))
                vat_pct = Decimal(str(item_data.get("vat_percentage", 15)))

                line_base = qty * rate
                line_vat = line_base * (vat_pct / Decimal("100"))
                line_amount = line_base + line_vat

                item_data["vat_amount"] = line_vat
                item_data["amount"] = line_amount

                if item_id and item_id in existing_items:
                    item_obj = existing_items[item_id]
                    for k, v in item_data.items():
                        setattr(item_obj, k, v)
                    item_obj.save()
                    kept_item_ids.add(item_id)
                else:
                    new_item = QuotationItem.objects.create(quotation=instance, **item_data)
                    kept_item_ids.add(new_item.id)

                calculated_subtotal += line_base
                calculated_vat += line_vat

            for old_id, old_obj in existing_items.items():
                if old_id not in kept_item_ids:
                    old_obj.delete()

            if "sub_total" not in validated_data:
                instance.sub_total = calculated_subtotal
            if "total_vat" not in validated_data:
                instance.total_vat = calculated_vat

        discount = instance.discount or Decimal("0.00")
        round_off = instance.round_off or Decimal("0.00")
        base_total = instance.sub_total + instance.total_vat - discount + round_off

        negotiation = instance.negotiation_amount or Decimal("0.00")
        if negotiation > Decimal("0.00"):
            instance.old_quote_amount = base_total
            instance.quote_amount = max(Decimal("0.00"), base_total - negotiation)
        else:
            if not explicit_old_quote_amount:
                instance.old_quote_amount = None
            instance.quote_amount = base_total

        instance.save()
        return instance
