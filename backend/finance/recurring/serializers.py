from rest_framework import serializers

from .models import (
    RecurringService,
    RecurringPricingPlan,
    RecurringBilling,
    RecurringBillingOccurrence,
)


# ==========================================================
# RECURRING PRICING PLAN SERIALIZER
# ==========================================================

class RecurringPricingPlanSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = RecurringPricingPlan

        fields = [
            "id",
            "plan_type",
            "service_id",
            "users",
            "billing_cycle",
            "discount_percent",
            "price",
        ]

        read_only_fields = [
            "id",
        ]


# ==========================================================
# RECURRING SERVICE SERIALIZER
# ==========================================================

class RecurringServiceSerializer(
    serializers.ModelSerializer
):
    product_name = serializers.CharField(
        source="product.product_name",
        read_only=True,
    )

    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )

    class Meta:
        model = RecurringService

        fields = [
            "id",
            "product",
            "product_name",
            "product_code",
            "product_service_name",
            "category",
            "category_name",
            "hs_code",
            "vat_rate",
            "base_price",
            "unit_price",
            "unit",
            "billing_type",
            "discount",
            "final_price",
            "technology",
            "database",
            "product_icon",
            "screenshot",
            "status",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


# ==========================================================
# RECURRING BILLING SERIALIZER
# ==========================================================
class RecurringBillingSerializer(serializers.ModelSerializer):

    customer_name = serializers.CharField(
        source="customer.customer_name",
        read_only=True,
    )

    customer_code = serializers.CharField(
        source="customer.customer_id",
        read_only=True,
    )

    service_name = serializers.CharField(
        source="recurring_service.product_service_name",
        read_only=True,
    )

    service_type = serializers.CharField(
        source="recurring_service.billing_type",
        read_only=True,
    )

    auto_renew_display = serializers.SerializerMethodField()

    class Meta:
        model = RecurringBilling

        fields = [
            "id",
            "contract_number",
            "recurring_service",
            "service_name",
            "service_type",
            "customer",
            "customer_code",
            "customer_name",
            "recurring_type",
            "start_date",
            "end_date",
            "frequency",
            "total_recurrence",
            "unlimited_recurrence",
            "payment_term",
            "reminder_before_due_days",
            "reminder_before_renewal_days",
            "billing_cycle",
            "auto_email_to",
            "whatsapp_number",
            "auto_generate_invoice",
            "auto_send",
            "include_tax",
            "auto_renew",
            "recurrence_status",
            "additional_notes",
            "invoice_date",
            "next_invoice_date",
            "monthly_amount",
            "auto_renew_display",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "contract_number",
            "invoice_date",
            "next_invoice_date",
            "monthly_amount",
            "created_at",
            "updated_at",
        ]

    def get_auto_renew_display(self, obj):
        return "Yes" if obj.auto_renew else "No"

    def validate_customer(self, customer):
        request = self.context.get("request")

        if (
            request
            and customer.company_id != request.user.company_id
        ):
            raise serializers.ValidationError(
                "Customer does not belong to your company."
            )

        return customer

    def validate_recurring_service(self, recurring_service):
        request = self.context.get("request")

        if (
            request
            and recurring_service.company_id
            != request.user.company_id
        ):
            raise serializers.ValidationError(
                "Recurring service does not belong to your company."
            )

        return recurring_service

class RecurringBillingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringBilling
        fields = [
            "customer",
            "recurring_type",
            "start_date",
            "end_date",
            "frequency",
            "total_recurrence",
            "unlimited_recurrence",
            "payment_term",
            "reminder_before_due_days",
            "reminder_before_renewal_days",
            "billing_cycle",
            "auto_email_to",
            "whatsapp_number",
            "auto_generate_invoice",
            "auto_send",
            "include_tax",
            "auto_renew",
            "recurrence_status",
            "additional_notes",
        ]

    def validate_customer(self, customer):
        request = self.context.get("request")

        if (
            request
            and customer.company_id != request.user.company_id
        ):
            raise serializers.ValidationError(
                "Customer does not belong to your company."
            )

        return customer
# ==========================================================
# RECURRING BILLING OCCURRENCE SERIALIZER
# ==========================================================

class RecurringBillingOccurrenceSerializer(
    serializers.ModelSerializer
):
    contract_number = serializers.CharField(
        source="recurring_billing.contract_number",
        read_only=True,
    )

    class Meta:
        model = RecurringBillingOccurrence

        fields = [
            "id",
            "recurring_billing",
            "contract_number",
            "occurrence_number",
            "scheduled_date",
            "generated_at",
            "invoice_number",
            "status",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "generated_at",
            "created_at",
        ]


# ==========================================================
# COMBINED CREATE SERIALIZER
# ==========================================================

class RecurringCreateSerializer(
    serializers.Serializer
):
    service = RecurringServiceSerializer()

    pricing_plans = RecurringPricingPlanSerializer(
        many=True,
        required=False,
    )

    billing = RecurringBillingCreateSerializer()

    def validate(self, attrs):
        request = self.context.get("request")

        if not request:
            return attrs

        company = getattr(
            request.user,
            "company",
            None,
        )

        if not company:
            raise serializers.ValidationError(
                "User is not associated with a company."
            )

        # ==================================================
        # SERVICE VALIDATION
        # ==================================================

        service_data = attrs.get(
            "service",
            {},
        )

        product = service_data.get("product")

        if product:
            if product.company_id != company.id:
                raise serializers.ValidationError({
                    "service": {
                        "product": (
                            "Product does not belong "
                            "to your company."
                        )
                    }
                })

        category = service_data.get("category")

        if category:
            if category.company_id != company.id:
                raise serializers.ValidationError({
                    "service": {
                        "category": (
                            "Category does not belong "
                            "to your company."
                        )
                    }
                })

        # ==================================================
        # BILLING VALIDATION
        # ==================================================

        billing_data = attrs.get(
            "billing",
            {},
        )

        customer = billing_data.get("customer")

        if customer:
            if customer.company_id != company.id:
                raise serializers.ValidationError({
                    "billing": {
                        "customer": (
                            "Customer does not belong "
                            "to your company."
                        )
                    }
                })

        return attrs