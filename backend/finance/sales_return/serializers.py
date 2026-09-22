from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from .models import SalesReturn, SalesReturnItem
from finance.invoice.models import Invoice, InvoiceItem
from finance.customer.models import Customer


class SalesReturnItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = SalesReturnItem
        fields = [
            "id",
            "invoice_item",
            "product",
            "product_name",
            "invoiced_qty",
            "already_returned_qty",
            "returning_now_qty",
            "condition",
            "unit_price",
            "vat_percentage",
            "vat_amount",
            "return_value",
        ]
        read_only_fields = ["id", "vat_amount", "return_value"]


class SalesReturnSerializer(serializers.ModelSerializer):
    items = SalesReturnItemSerializer(many=True, required=False)
    items_returned = serializers.ReadOnlyField()
    customer_display_name = serializers.CharField(
        source="customer.customer_name",
        read_only=True
    )
    customer_company_name = serializers.CharField(
        source="customer.company_name",
        read_only=True
    )

    class Meta:
        model = SalesReturn
        fields = [
            "id",
            "company",
            "return_number",
            "invoice",
            "invoice_ref",
            "customer",
            "customer_display_name",
            "customer_company_name",
            "return_date",
            "reason",
            "status",
            "invoice_value",
            "already_returned",
            "eligible_to_return",
            "return_value",
            "refunded_amount",
            "applied_credits",
            "notes",
            # Company snapshot
            "from_company_name",
            "from_address",
            "from_phone_number",
            "from_email",
            # Customer snapshot
            "customer_name",
            "customer_address",
            "customer_phone",
            "finance_contact_email",
            # Items & Totals
            "items",
            "items_returned",
            # Audit
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "return_number",
            "eligible_to_return",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        items_data = attrs.get("items")
        if items_data:
            for item in items_data:
                invoiced_qty = Decimal(str(item.get("invoiced_qty", 0.00)))
                already_returned_qty = Decimal(str(item.get("already_returned_qty", 0.00)))
                returning_now_qty = Decimal(str(item.get("returning_now_qty", 0.00)))

                if returning_now_qty < Decimal("0.00"):
                    raise serializers.ValidationError({
                        "items": "Returning quantity cannot be negative."
                    })

                max_eligible = invoiced_qty - already_returned_qty
                if max_eligible > Decimal("0.00") and returning_now_qty > max_eligible:
                    raise serializers.ValidationError({
                        "items": f"Returning quantity ({returning_now_qty}) exceeds max eligible quantity ({max_eligible}) for {item.get('product_name', 'item')}."
                    })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        request = self.context.get("request")
        user = request.user if request else None

        customer = validated_data.get("customer")
        invoice = validated_data.get("invoice")
        company = validated_data.get("company")

        # Snapshot customer details if empty
        if customer:
            if not validated_data.get("customer_name"):
                validated_data["customer_name"] = customer.customer_name or customer.company_name or ""
            if not validated_data.get("customer_address"):
                validated_data["customer_address"] = getattr(customer, "billing_address", "") or getattr(customer, "address", "") or ""
            if not validated_data.get("customer_phone"):
                validated_data["customer_phone"] = getattr(customer, "phno", "") or getattr(customer, "phone", "") or ""
            if not validated_data.get("finance_contact_email"):
                validated_data["finance_contact_email"] = getattr(customer, "admin_email", "") or getattr(customer, "email", "") or ""

        # Snapshot company details if empty
        if company:
            if not validated_data.get("from_company_name"):
                validated_data["from_company_name"] = getattr(company, "name", "TUNGSTON LABS")
            if not validated_data.get("from_address"):
                validated_data["from_address"] = getattr(company, "address", "") or ""
            if not validated_data.get("from_phone_number"):
                validated_data["from_phone_number"] = getattr(company, "contact_number", "") or ""
            if not validated_data.get("from_email"):
                validated_data["from_email"] = getattr(company, "email", "") or ""

        # Invoice prefill values if invoice connected
        if invoice:
            if not validated_data.get("invoice_ref"):
                validated_data["invoice_ref"] = invoice.invoice_number
            if not validated_data.get("invoice_value") or validated_data.get("invoice_value") == Decimal("0.00"):
                validated_data["invoice_value"] = invoice.total_amount

            # Calculate already returned across existing sales returns for this invoice
            prev_returns_sum = SalesReturn.objects.filter(
                invoice=invoice
            ).exclude(status="cancelled").aggregate(
                total=serializers.models.Sum("return_value")
            )["total"] or Decimal("0.00")

            validated_data["already_returned"] = prev_returns_sum

        sales_return = SalesReturn.objects.create(**validated_data)

        # Create line items & compute return_value sum
        total_return_value = Decimal("0.00")
        for item_data in items_data:
            item_obj = SalesReturnItem.objects.create(
                sales_return=sales_return,
                **item_data
            )
            total_return_value += item_obj.return_value

        if items_data:
            sales_return.return_value = total_return_value
            sales_return.save(update_fields=["return_value", "eligible_to_return"])

        return sales_return

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            total_return_value = Decimal("0.00")
            for item_data in items_data:
                item_obj = SalesReturnItem.objects.create(
                    sales_return=instance,
                    **item_data
                )
                total_return_value += item_obj.return_value
            instance.return_value = total_return_value
            instance.save(update_fields=["return_value", "eligible_to_return"])

        return instance


class SalesReturnListSerializer(serializers.ModelSerializer):
    customer = serializers.CharField(source="customer.customer_name", read_only=True)
    items_returned = serializers.SerializerMethodField()
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = SalesReturn
        fields = [
            "id",
            "return_number",
            "customer",
            "customer_name",
            "invoice_ref",
            "return_date",
            "return_value",
            "items_returned",
            "reason",
            "reason_display",
            "status",
            "status_display",
            "created_at",
        ]

    def get_items_returned(self, obj):
        return obj.items_returned


class SalesReturnKPISerializer(serializers.Serializer):
    total_returns = serializers.IntegerField()
    total_return_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    refunded_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    applied_credits = serializers.DecimalField(max_digits=15, decimal_places=2)
    cancelled_credits = serializers.IntegerField()


class SalesReturnInvoiceDropdownSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "customer",
            "customer_name",
            "invoice_date",
            "total_amount",
            "payment_status",
        ]
