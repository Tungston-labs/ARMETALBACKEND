from decimal import Decimal

from django.db import transaction

from rest_framework import serializers

from .models import Invoice, InvoiceItem

from finance.product.models import Product
from finance.customer.models import Customer

from finance.sales_order.models import (
    SalesOrder,
    SalesOrderItem,
)


# =========================================================
# INVOICE ITEM SERIALIZER
# =========================================================

class InvoiceItemSerializer(serializers.ModelSerializer):

    product_name = serializers.CharField(
        source="product.product_name",
        read_only=True
    )

    sales_order_item_id = serializers.IntegerField(
        source="sales_order_item.id",
        read_only=True
    )

    class Meta:

        model = InvoiceItem

        fields = [

            "id",

            "sales_order_item",
            "sales_order_item_id",

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

            "sales_order_item_id",

            "product_name",

            "vat_sar",

            "amount",

        ]


# =========================================================
# INVOICE SERIALIZER
# =========================================================

class InvoiceSerializer(serializers.ModelSerializer):

    qr_code = serializers.ImageField(
        required=False,
        allow_null=True
    )

    items = InvoiceItemSerializer(
        many=True,
        required=False
    )

    # -----------------------------------------------------
    # SALES ORDER DISPLAY
    # -----------------------------------------------------

    sales_order_number = serializers.CharField(
        source="sales_order.so_number",
        read_only=True
    )

    # -----------------------------------------------------
    # CUSTOMER DISPLAY
    # -----------------------------------------------------

    customer_display_name = serializers.CharField(
        source="customer.customer_name",
        read_only=True
    )

    class Meta:

        model = Invoice

        fields = [

            "id",

            "invoice_number",

            # Sales Order
            "sales_order",
            "sales_order_number",

            # Company
            "company",

            # Customer
            "customer",
            "customer_display_name",

            # Dates
            "invoice_date",
            "due_date",

            # Payment
            "payment_status",

            # Company snapshot
            "company_name",
            "company_email",
            "company_phone",
            "company_address",

            # Customer snapshot
            "customer_name",
            "customer_email",
            "customer_phone",
            "customer_address",

            # Bank details
            "account_holder",
            "account_number",
            "iban",
            "qr_code",

            # Items
            "items",

            # Totals
            "subtotal",
            "total_vat",
            "discount",
            "round_off",
            "total_amount",
            "amount_paid",

            # PDF
            "pdf_file",

            # Audit
            "created_by",
            "created_at",
            "updated_at",

        ]

        read_only_fields = [

            "id",

            "invoice_number",

            "sales_order_number",

            "company",

            "customer",

            "customer_display_name",

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

    # =====================================================
    # VALIDATE SALES ORDER
    # =====================================================

    def validate_sales_order(self, sales_order):

        request = self.context.get("request")

        if request:

            company = getattr(
                request.user,
                "company",
                None
            )

            if not company:

                raise serializers.ValidationError(
                    "User is not associated with a company."
                )

            if sales_order.company_id != company.id:

                raise serializers.ValidationError(
                    "Invalid sales order for this company."
                )

        # -------------------------------------------------
        # Rejected SO
        # -------------------------------------------------

        if sales_order.order_status == "rejected":

            raise serializers.ValidationError(
                "Cannot create invoice from a rejected sales order."
            )

        # -------------------------------------------------
        # SO must have items
        # -------------------------------------------------

        if not sales_order.items.exists():

            raise serializers.ValidationError(
                "Selected sales order does not contain any items."
            )

        return sales_order

    # =====================================================
    # VALIDATE CUSTOMER
    # =====================================================

    def validate_customer(self, customer):

        request = self.context.get("request")

        if request:

            company = getattr(
                request.user,
                "company",
                None
            )

            if company and customer.company_id != company.id:

                raise serializers.ValidationError(
                    "Invalid customer for this company."
                )

        return customer

    # =====================================================
    # VALIDATE DATES
    # =====================================================

    def validate(self, attrs):

        invoice_date = attrs.get(
            "invoice_date",
            getattr(
                self.instance,
                "invoice_date",
                None
            )
        )

        due_date = attrs.get(
            "due_date",
            getattr(
                self.instance,
                "due_date",
                None
            )
        )

        if (
            invoice_date
            and due_date
            and due_date < invoice_date
        ):

            raise serializers.ValidationError({

                "due_date":
                    "Due date cannot be before invoice date."

            })

        return attrs

    # =====================================================
    # CREATE
    # =====================================================

    @transaction.atomic
    def create(self, validated_data):

        request = self.context["request"]

        # Pop items so it is not passed to Invoice.objects.create()
        items_data = validated_data.pop("items", None)

        # -------------------------------------------------
        # Get Sales Order
        # -------------------------------------------------

        sales_order = validated_data.pop(
            "sales_order",
            None
        )

        # -------------------------------------------------
        # Company
        # -------------------------------------------------

        company = request.user.company

        if sales_order:
            if sales_order.company_id != company.id:
                raise serializers.ValidationError({
                    "sales_order":
                        "Sales order does not belong to your company."
                })
            customer = sales_order.customer
        else:
            customer = validated_data.get("customer")
            if not customer:
                raise serializers.ValidationError({
                    "customer":
                        "Customer is required when sales_order is not provided."
                })

        # -------------------------------------------------
        # Remove customer/company from request data
        # -------------------------------------------------

        validated_data.pop(
            "company",
            None
        )

        validated_data.pop(
            "customer",
            None
        )

        # -------------------------------------------------
        # Create Invoice
        # -------------------------------------------------

        invoice = Invoice.objects.create(

            company=company,

            customer=customer,

            sales_order=sales_order,

            created_by=request.user,

            # Company snapshot
            company_name=getattr(company, "name", "") or "",

            company_email=getattr(company, "email", "") or "",

            company_phone=getattr(company, "contact_number", "") or "",

            company_address=getattr(company, "address", "") or "",

            # Customer snapshot
            customer_name=getattr(customer, "customer_name", "") or "",

            customer_email=getattr(customer, "admin_email", "") or "",

            customer_phone=getattr(customer, "phno", "") or getattr(customer, "phone", "") or "",

            customer_address=getattr(customer, "billing_address", "") or "",

            **validated_data

        )

        # -------------------------------------------------
        # Items handling
        # -------------------------------------------------

        if items_data:
            for item_data in items_data:
                so_item = item_data.get("sales_order_item")
                product = item_data.get("product")
                
                particular = item_data.get("particular") or (
                    product.product_name if product else "Item"
                )
                quantity = item_data.get("quantity", Decimal("1.00"))
                hs_code = item_data.get("hs_code", "")
                rate = item_data.get("rate", Decimal("0.00"))
                vat_percentage = item_data.get("vat_percentage", Decimal("0.00"))

                InvoiceItem.objects.create(
                    invoice=invoice,
                    sales_order_item=so_item,
                    product=product,
                    particular=particular,
                    quantity=quantity,
                    hs_code=hs_code,
                    rate=rate,
                    vat_percentage=vat_percentage,
                )
        elif sales_order:
            sales_order_items = (
                sales_order.items
                .select_related("product")
                .all()
            )

            for so_item in sales_order_items:
                if not so_item.product:
                    raise serializers.ValidationError({
                        "sales_order":
                            f"Sales order item {so_item.id} "
                            "does not have a product."
                    })

                InvoiceItem.objects.create(
                    invoice=invoice,
                    sales_order_item=so_item,
                    product=so_item.product,
                    particular=(
                        so_item.service_name
                        or (
                            so_item.product.product_name
                            if so_item.product
                            else so_item.description
                        )
                    ),
                    quantity=so_item.quantity,
                    hs_code=so_item.hs_code,
                    rate=so_item.rate,
                    vat_percentage=so_item.vat_percentage,
                )

        # -------------------------------------------------
        # Calculate totals
        # -------------------------------------------------

        self.calculate_invoice_totals(
            invoice
        )

        # -------------------------------------------------
        # Update payment status
        # -------------------------------------------------

        self.update_payment_status(
            invoice
        )

        return invoice

    # =====================================================
    # UPDATE
    # =====================================================

    @transaction.atomic
    def update(
        self,
        instance,
        validated_data
    ):

        # -------------------------------------------------
        # Sales Order should not be changed
        # -------------------------------------------------

        validated_data.pop(
            "sales_order",
            None
        )

        # -------------------------------------------------
        # Company / Customer should not be changed
        # -------------------------------------------------

        validated_data.pop(
            "company",
            None
        )

        validated_data.pop(
            "customer",
            None
        )

        # -------------------------------------------------
        # Items
        # -------------------------------------------------

        items_data = validated_data.pop(
            "items",
            None
        )

        # -------------------------------------------------
        # Update normal fields
        # -------------------------------------------------

        for attr, value in validated_data.items():

            setattr(
                instance,
                attr,
                value
            )

        instance.save()

        # -------------------------------------------------
        # If items explicitly supplied
        # -------------------------------------------------

        if items_data is not None:

            instance.items.all().delete()

            for item_data in items_data:

                InvoiceItem.objects.create(

                    invoice=instance,

                    **item_data

                )

        # -------------------------------------------------
        # Recalculate
        # -------------------------------------------------

        self.calculate_invoice_totals(
            instance
        )

        self.update_payment_status(
            instance
        )

        return instance

    # =====================================================
    # CALCULATE TOTALS
    # =====================================================

    def calculate_invoice_totals(
        self,
        invoice
    ):

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

            # IMPORTANT:
            # Invoice subtotal is pre-VAT amount
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

    # =====================================================
    # PAYMENT STATUS
    # =====================================================

    def update_payment_status(
        self,
        invoice
    ):

        amount_paid = (
            invoice.amount_paid
            or Decimal("0.00")
        )

        total_amount = (
            invoice.total_amount
            or Decimal("0.00")
        )

        if amount_paid <= Decimal("0.00"):

            status = "unpaid"

        elif amount_paid >= total_amount:

            status = "paid"

        else:

            status = "partially_paid"

        if invoice.payment_status != status:

            invoice.payment_status = status

            invoice.save(
                update_fields=[
                    "payment_status",
                    "updated_at"
                ]
            )


# =========================================================
# INVOICE LIST SERIALIZER
# =========================================================

class InvoiceListSerializer(
    serializers.ModelSerializer
):

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

    sales_order_number = serializers.CharField(
        source="sales_order.so_number",
        read_only=True
    )

    class Meta:

        model = Invoice

        fields = [

            "id",

            "invoice_number",

            "sales_order_number",

            "customer_name",

            "invoice_date",

            "due_date",

            "amount_to_be_paid",

            "paid_amount",

            "balance",

            "status",

        ]

    def get_balance(
        self,
        obj
    ):

        return max(

            (
                obj.total_amount
                - obj.amount_paid
            ),

            Decimal("0.00")

        )


# =========================================================
# SALES ORDER DROPDOWN SERIALIZER
# =========================================================

class InvoiceSalesOrderSerializer(
    serializers.ModelSerializer
):

    customer_name = serializers.CharField(
        source="customer.customer_name",
        read_only=True
    )

    class Meta:

        model = SalesOrder

        fields = [

            "id",

            "so_number",

            "customer",

            "customer_name",

            "order_date",

            "delivery_date",

            "due_date",

            "payment_terms",

            "order_status",

            "delivery_status",

            "subtotal",

            "total_vat",

            "discount",

            "round_off",

            "order_value",

        ]