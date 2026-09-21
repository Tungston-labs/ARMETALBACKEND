from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from superadmin.models import Company
from finance.customer.models import Customer
from finance.product.models import Product
from finance.quotation.models import Quotation, QuotationItem

from .models import SalesOrder, SalesOrderItem
from finance.warehouse.models import Warehouse


# =========================================================
# HELPERS
# =========================================================

def get_user_name(user):

    if not user:
        return ""

    full_name = ""

    try:
        full_name = user.get_full_name()
    except Exception:
        pass

    return (
        full_name
        or getattr(user, "username", "")
        or getattr(user, "email", "")
    )


def get_user_role(user):

    if not user:
        return ""

    if (
        getattr(user, "is_super_admin", False)
        or getattr(user, "is_superadmin", False)
    ):
        return "Super Admin"

    if getattr(user, "is_company_admin", False):
        return "Company Admin"

    if getattr(user, "is_employee", False):
        return "Employee"

    role = getattr(user, "role", "")

    if role:
        return str(role)

    return ""


# =========================================================
# SALES ORDER ITEM SERIALIZER
# =========================================================

class SalesOrderItemSerializer(serializers.ModelSerializer):

    product_name = serializers.SerializerMethodField()

    remaining_quantity = serializers.SerializerMethodField()

    class Meta:

        model = SalesOrderItem

        fields = [
            "id",

            "quotation_item",

            "product",
            "product_name",

            "service_name",
            "description",

            "quantity",
            "delivered_quantity",
            "remaining_quantity",

            "hs_code",

            "rate",

            "vat_percentage",

            "amount_before_vat",
            "vat_amount",
            "amount",
        ]

        read_only_fields = [
            "id",
            "product_name",
            "remaining_quantity",
            "amount_before_vat",
            "vat_amount",
            "amount",
        ]

    def get_product_name(self, obj):

        if obj.product:
            return obj.product.product_name

        return ""

    def get_remaining_quantity(self, obj):

        return obj.remaining_quantity


# =========================================================
# FULL SALES ORDER SERIALIZER
# =========================================================

class SalesOrderSerializer(serializers.ModelSerializer):

    quote_reference = serializers.CharField(
        source="quotation.quote_number",
        read_only=True
    )

    created_by_name = serializers.SerializerMethodField()

    created_by_role = serializers.SerializerMethodField()

    items = SalesOrderItemSerializer(
        many=True,
        required=False
    )

    class Meta:

        model = SalesOrder

        fields = [

            "id",

            "so_number",

            "quotation",
            "quote_reference",

            "company",

            "company_name",
            "company_email",
            "company_phone",
            "company_address",

            "customer",

            "customer_name",
            "customer_email",
            "customer_phone",
            "customer_address",

            "warehouse",

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

            "notes",

            "items",

            "created_by",
            "created_by_name",
            "created_by_role",

            "created_at",
            "updated_at",
        ]

        read_only_fields = [

            "id",
            "so_number",

            "quote_reference",

            "company_name",
            "company_email",
            "company_phone",
            "company_address",

            "customer_name",
            "customer_email",
            "customer_phone",
            "customer_address",

            "delivery_status",

            "subtotal",
            "total_vat",
            "order_value",

            "created_by",
            "created_by_name",
            "created_by_role",

            "created_at",
            "updated_at",
        ]

    # ---------------------------------------------------------
    # CREATED BY
    # ---------------------------------------------------------

    def get_created_by_name(self, obj):

        return get_user_name(obj.created_by)

    def get_created_by_role(self, obj):

        return get_user_role(obj.created_by)

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    def validate(self, attrs):

        request = self.context.get("request")

        quotation = attrs.get(
            "quotation",
            getattr(self.instance, "quotation", None)
        )

        company = attrs.get(
            "company",
            getattr(self.instance, "company", None)
        )

        customer = attrs.get(
            "customer",
            getattr(self.instance, "customer", None)
        )

        warehouse = attrs.get(
            "warehouse",
            getattr(self.instance, "warehouse", None)
        )

        # -----------------------------------------------------
        # CREATE: GET COMPANY/CUSTOMER FROM QUOTATION
        # -----------------------------------------------------

        if quotation:

            if not company:

                company = quotation.company
                attrs["company"] = company

            if not customer:

                customer = quotation.customer
                attrs["customer"] = customer

            # Quotation must belong to company

            if quotation.company_id != company.id:

                raise serializers.ValidationError({
                    "quotation":
                        "Quotation does not belong to the selected company."
                })

            # Customer must belong to same company

            if customer.company_id != company.id:

                raise serializers.ValidationError({
                    "customer":
                        "Customer does not belong to the selected company."
                })

            # Do not allow rejected quotation

            if quotation.status == "rejected":

                raise serializers.ValidationError({
                    "quotation":
                        "A rejected quotation cannot be converted to a Sales Order."
                })

        # -----------------------------------------------------
        # WAREHOUSE COMPANY VALIDATION
        # -----------------------------------------------------

        if warehouse and company:

            if warehouse.company_id != company.id:

                raise serializers.ValidationError({
                    "warehouse":
                        "Warehouse does not belong to the selected company."
                })

        # -----------------------------------------------------
        # DATE VALIDATION
        # -----------------------------------------------------

        order_date = attrs.get(
            "order_date",
            getattr(self.instance, "order_date", None)
        )

        delivery_date = attrs.get(
            "delivery_date",
            getattr(self.instance, "delivery_date", None)
        )

        due_date = attrs.get(
            "due_date",
            getattr(self.instance, "due_date", None)
        )

        if order_date and delivery_date:

            if delivery_date < order_date:

                raise serializers.ValidationError({
                    "delivery_date":
                        "Delivery date cannot be before order date."
                })

        if order_date and due_date:

            if due_date < order_date:

                raise serializers.ValidationError({
                    "due_date":
                        "Due date cannot be before order date."
                })

        # -----------------------------------------------------
        # COMPANY USER ISOLATION
        # -----------------------------------------------------

        if request and request.user:

            user = request.user

            is_super_admin = (
                getattr(user, "is_super_admin", False)
                or getattr(user, "is_superadmin", False)
            )

            if not is_super_admin:

                user_company = getattr(
                    user,
                    "company",
                    None
                )

                if (
                    user_company
                    and company
                    and company.id != user_company.id
                ):

                    raise serializers.ValidationError({
                        "company":
                            "You cannot create a Sales Order for another company."
                    })

        return attrs

    # ---------------------------------------------------------
    # SNAPSHOT COMPANY
    # ---------------------------------------------------------

    def set_company_snapshot(self, sales_order):

        company = sales_order.company

        sales_order.company_name = (
            getattr(company, "name", "")
            or ""
        )

        sales_order.company_email = (
            getattr(company, "email", "")
            or ""
        )

        sales_order.company_phone = (
            getattr(company, "contact_number", "")
            or ""
        )

        address_parts = []

        company_address = getattr(
            company,
            "address",
            ""
        )

        if company_address:
            address_parts.append(
                str(company_address)
            )

        location = getattr(
            company,
            "location",
            ""
        )

        if location:
            address_parts.append(
                str(location)
            )

        sales_order.company_address = ", ".join(
            address_parts
        )

    # ---------------------------------------------------------
    # SNAPSHOT CUSTOMER
    # ---------------------------------------------------------

    def set_customer_snapshot(self, sales_order):

        customer = sales_order.customer

        sales_order.customer_name = (
            getattr(customer, "customer_name", "")
            or ""
        )

        sales_order.customer_email = (
            getattr(customer, "admin_email", "")
            or getattr(customer, "financial_email", "")
            or ""
        )

        sales_order.customer_phone = (
            getattr(customer, "phone", "")
            or getattr(customer, "phno", "")
            or ""
        )

        address_parts = []

        billing_address = getattr(
            customer,
            "billing_address",
            ""
        )

        if billing_address:
            address_parts.append(
                str(billing_address)
            )

        city = getattr(customer, "city", "")

        if city:
            address_parts.append(str(city))

        state = getattr(customer, "state", "")

        if state:
            address_parts.append(str(state))

        country = getattr(customer, "country", "")

        if country:
            address_parts.append(str(country))

        postal_code = getattr(
            customer,
            "postal_code",
            ""
        )

        if postal_code:
            address_parts.append(
                str(postal_code)
            )

        sales_order.customer_address = ", ".join(
            address_parts
        )

    # ---------------------------------------------------------
    # CREATE ITEM FROM QUOTATION
    # ---------------------------------------------------------

    def create_item_from_quotation(
        self,
        sales_order,
        quotation_item
    ):

        item = SalesOrderItem.objects.create(

            sales_order=sales_order,

            quotation_item=quotation_item,

            product=quotation_item.product,

            service_name=quotation_item.service_name,

            description=quotation_item.description,

            quantity=quotation_item.quantity,

            delivered_quantity=Decimal("0.00"),

            hs_code=quotation_item.hs_code,

            rate=quotation_item.rate,

            vat_percentage=quotation_item.vat_percentage,
        )

        return item

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    @transaction.atomic
    def create(self, validated_data):

        items_data = validated_data.pop(
            "items",
            []
        )

        request = self.context.get("request")

        quotation = validated_data.get(
            "quotation"
        )

        # -----------------------------------------------------
        # GET COMPANY
        # -----------------------------------------------------

        company = validated_data.get(
            "company"
        )

        if not company and quotation:

            company = quotation.company

            validated_data["company"] = company

        # -----------------------------------------------------
        # GET CUSTOMER
        # -----------------------------------------------------

        customer = validated_data.get(
            "customer"
        )

        if not customer and quotation:

            customer = quotation.customer

            validated_data["customer"] = customer

        # -----------------------------------------------------
        # CREATED BY
        # -----------------------------------------------------

        if request and request.user:

            validated_data["created_by"] = request.user

        # -----------------------------------------------------
        # SNAPSHOT
        # -----------------------------------------------------

        sales_order = SalesOrder(
            **validated_data
        )

        self.set_company_snapshot(
            sales_order
        )

        self.set_customer_snapshot(
            sales_order
        )

        sales_order.save()

        # -----------------------------------------------------
        # ITEMS
        #
        # If frontend doesn't send items,
        # automatically copy quotation items.
        # -----------------------------------------------------

        if items_data:

            for item_data in items_data:

                quotation_item = item_data.get(
                    "quotation_item"
                )

                if quotation_item:

                    if (
                        quotation_item.quotation_id
                        != quotation.id
                    ):

                        raise serializers.ValidationError({
                            "items":
                                "Quotation item does not belong to selected quotation."
                        })

                SalesOrderItem.objects.create(
                    sales_order=sales_order,
                    **item_data
                )

        elif quotation:

            quotation_items = (
                quotation.items
                .select_related("product")
                .all()
            )

            for quotation_item in quotation_items:

                self.create_item_from_quotation(
                    sales_order,
                    quotation_item
                )

        # -----------------------------------------------------
        # CALCULATE TOTALS
        # -----------------------------------------------------

        sales_order.calculate_totals()

        sales_order.update_delivery_status()

        # -----------------------------------------------------
        # MARK QUOTATION AS CONVERTED
        # -----------------------------------------------------

        if quotation:

            if quotation.status != "converted":

                quotation.status = "converted"

                quotation.save(
                    update_fields=["status"]
                )

        return sales_order

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------

    @transaction.atomic
    def update(
        self,
        instance,
        validated_data
    ):

        items_data = validated_data.pop(
            "items",
            None
        )

        # -----------------------------------------------------
        # UPDATE NORMAL FIELDS
        # -----------------------------------------------------

        for attr, value in validated_data.items():

            setattr(
                instance,
                attr,
                value
            )

        self.set_company_snapshot(
            instance
        )

        self.set_customer_snapshot(
            instance
        )

        instance.save()

        # -----------------------------------------------------
        # REPLACE ITEMS IF PROVIDED
        # -----------------------------------------------------

        if items_data is not None:

            instance.items.all().delete()

            for item_data in items_data:

                quotation_item = item_data.get(
                    "quotation_item"
                )

                if quotation_item:

                    if (
                        quotation_item.quotation_id
                        != instance.quotation_id
                    ):

                        raise serializers.ValidationError({
                            "items":
                                "Quotation item does not belong to this quotation."
                        })

                SalesOrderItem.objects.create(
                    sales_order=instance,
                    **item_data
                )

        # -----------------------------------------------------
        # TOTALS
        # -----------------------------------------------------

        instance.calculate_totals()

        instance.update_delivery_status()

        return instance


# =========================================================
# LIST SERIALIZER
# =========================================================

class SalesOrderListSerializer(
    serializers.ModelSerializer
):

    quote_reference = serializers.CharField(
        source="quotation.quote_number",
        read_only=True
    )

    created_by_name = serializers.SerializerMethodField()

    created_by_role = serializers.SerializerMethodField()

    class Meta:

        model = SalesOrder

        fields = [

            "id",

            "so_number",

            "customer_name",

            "quote_reference",

            "order_date",

            "delivery_date",

            "due_date",

            "order_value",

            "order_status",

            "delivery_status",

            "payment_terms",

            "warehouse",

            "created_by_name",

            "created_by_role",

            "created_at",
        ]

    def get_created_by_name(self, obj):

        return get_user_name(
            obj.created_by
        )

    def get_created_by_role(self, obj):

        return get_user_role(
            obj.created_by
        )


# =========================================================
# QUOTATION PREFILL SERIALIZER
# =========================================================

class SalesOrderQuotationSerializer(
    serializers.ModelSerializer
):

    company_name = serializers.CharField(
        source="company.name",
        read_only=True
    )

    company_email = serializers.EmailField(
        source="company.email",
        read_only=True
    )

    company_phone = serializers.CharField(
        source="company.contact_number",
        read_only=True
    )

    customer_name = serializers.CharField(
        source="customer.customer_name",
        read_only=True
    )

    customer_email = serializers.SerializerMethodField()

    customer_phone = serializers.SerializerMethodField()

    customer_address = serializers.SerializerMethodField()

    items = serializers.SerializerMethodField()

    class Meta:

        model = Quotation

        fields = [

            "id",
            "quote_number",

            "company",
            "company_name",
            "company_email",
            "company_phone",

            "customer",
            "customer_name",
            "customer_email",
            "customer_phone",
            "customer_address",

            "issue_date",
            "valid_till",
            "status",

            "sub_total",
            "total_vat",
            "discount",
            "round_off",
            "quote_amount",
            "negotiation_amount",

            "notes",

            "items",
        ]

    def get_customer_email(self, obj):

        customer = obj.customer

        return (
            getattr(customer, "admin_email", "")
            or getattr(customer, "financial_email", "")
            or ""
        )

    def get_customer_phone(self, obj):

        customer = obj.customer

        return (
            getattr(customer, "phone", "")
            or getattr(customer, "phno", "")
            or ""
        )

    def get_customer_address(self, obj):

        customer = obj.customer

        parts = []

        for field in [
            "billing_address",
            "city",
            "state",
            "country",
            "postal_code",
        ]:

            value = getattr(
                customer,
                field,
                ""
            )

            if value:
                parts.append(
                    str(value)
                )

        return ", ".join(parts)

    def get_items(self, obj):

        items = obj.items.select_related(
            "product"
        ).all()

        return [

            {
                "quotation_item": item.id,

                "product": (
                    item.product_id
                    if item.product
                    else None
                ),

                "product_name": (
                    item.product.product_name
                    if item.product
                    else ""
                ),

                "service_name": item.service_name,

                "description": item.description,

                "quantity": item.quantity,

                "hs_code": item.hs_code,

                "rate": item.rate,

                "vat_percentage":
                    item.vat_percentage,

                "vat_amount":
                    item.vat_amount,

                "amount":
                    item.amount,
            }

            for item in items
        ]