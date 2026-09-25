from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from shared.models import TimeStampedModel


class RecurringService(TimeStampedModel):

    BILLING_TYPE_CHOICES = (
        ("one_time", "One Time"),
        ("recurring", "Recurring"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    UNIT_CHOICES = (
        ("PCS", "Piece (PCS)"),
        ("Box", "Box"),
        ("Pack", "Pack"),
        ("Month", "Month"),
        ("Project", "Project"),
        ("Set", "Set"),
        ("Kg", "Kilogram (Kg)"),
        ("Meter", "Meter"),
        ("Other", "Other"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="recurring_services",
    )

    # Existing Product / Service
    product = models.ForeignKey(
        "product.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_services",
    )

    # --------------------------------------------------
    # SERVICE INFORMATION
    # --------------------------------------------------

    product_code = models.CharField(
        max_length=50,
    )

    product_service_name = models.CharField(
        max_length=200,
    )

    category = models.ForeignKey(
        "category.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_services",
    )

    hs_code = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    unit = models.CharField(
        max_length=50,
        choices=UNIT_CHOICES,
        default="Month",
    )

    billing_type = models.CharField(
        max_length=20,
        choices=BILLING_TYPE_CHOICES,
        default="recurring",
    )

    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
        ],
    )

    final_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # --------------------------------------------------
    # SERVICE DETAILS
    # --------------------------------------------------

    technology = models.CharField(
        max_length=200,
        blank=True,
        default="",
    )

    database = models.CharField(
        max_length=200,
        blank=True,
        default="",
    )

    # --------------------------------------------------
    # FILES
    # --------------------------------------------------

    product_icon = models.ImageField(
        upload_to="recurring/product_icons/",
        null=True,
        blank=True,
    )

    screenshot = models.ImageField(
        upload_to="recurring/screenshots/",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_recurring_services",
    )

    def __str__(self):
        return (
            f"{self.product_code} - "
            f"{self.product_service_name}"
        )

    class Meta:
        db_table = "finance_recurring_service"
        ordering = ["-created_at"]



class RecurringPricingPlan(TimeStampedModel):

    PLAN_CHOICES = (
        ("starter", "Starter"),
        ("professional", "Professional"),
        ("enterprise", "Enterprise"),
    )

    BILLING_CYCLE_CHOICES = (
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    )

    id = models.BigAutoField(primary_key=True)

    recurring_service = models.ForeignKey(
        RecurringService,
        on_delete=models.CASCADE,
        related_name="pricing_plans",
    )

    plan_type = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
    )

    service_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    users = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
    )

    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    class Meta:
        db_table = "finance_recurring_pricing_plan"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "recurring_service",
                    "plan_type",
                ],
                name="unique_recurring_plan_type",
            )
        ]

    def __str__(self):
        return (
            f"{self.recurring_service.product_service_name} - "
            f"{self.plan_type}"
        )
    

class RecurringBilling(TimeStampedModel):

    RECURRING_TYPE_CHOICES = (
        ("invoice", "Invoice"),
        ("bill", "Bill"),
    )

    FREQUENCY_CHOICES = (
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("half_yearly", "Half Yearly"),
        ("yearly", "Yearly"),
    )

    PAYMENT_TERM_CHOICES = (
        ("immediate", "Due on Receipt"),
        ("7_days", "7 Days"),
        ("15_days", "15 Days"),
        ("30_days", "30 Days"),
        ("45_days", "45 Days"),
        ("60_days", "60 Days"),
        ("90_days", "90 Days"),
    )

    BILLING_CYCLE_CHOICES = (
        ("advance", "Advance"),
        ("arrears", "Arrears"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="recurring_billings",
    )

    contract_number = models.CharField(
        max_length=50,
        unique=False,
    )

    recurring_service = models.ForeignKey(
        RecurringService,
        on_delete=models.PROTECT,
        related_name="billing_contracts",
    )

    customer = models.ForeignKey(
        "customer.Customer",
        on_delete=models.PROTECT,
        related_name="recurring_billings",
    )

    # --------------------------------------------------
    # BILLING
    # --------------------------------------------------

    recurring_type = models.CharField(
        max_length=20,
        choices=RECURRING_TYPE_CHOICES,
        default="invoice",
    )

    start_date = models.DateField()

    end_date = models.DateField(
        null=True,
        blank=True,
    )

    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default="monthly",
    )

    total_recurrence = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    unlimited_recurrence = models.BooleanField(
        default=False,
    )

    # --------------------------------------------------
    # PAYMENT
    # --------------------------------------------------

    payment_term = models.CharField(
        max_length=20,
        choices=PAYMENT_TERM_CHOICES,
        default="30_days",
    )

    reminder_before_due_days = models.PositiveIntegerField(
        default=0,
    )

    reminder_before_renewal_days = models.PositiveIntegerField(
        default=0,
    )

    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default="advance",
    )

    # --------------------------------------------------
    # EMAIL / WHATSAPP
    # --------------------------------------------------

    auto_email_to = models.EmailField(
        blank=True,
        default="",
    )

    whatsapp_number = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    # --------------------------------------------------
    # AUTOMATION
    # --------------------------------------------------

    auto_generate_invoice = models.BooleanField(
        default=False,
    )

    auto_send = models.BooleanField(
        default=False,
    )

    include_tax = models.BooleanField(
        default=True,
    )

    auto_renew = models.BooleanField(
        default=True,
    )

    # --------------------------------------------------
    # STATUS
    # --------------------------------------------------

    recurrence_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    additional_notes = models.TextField(
        blank=True,
        default="",
    )

    # --------------------------------------------------
    # CALCULATED / TRACKING
    # --------------------------------------------------

    invoice_date = models.DateField(
        null=True,
        blank=True,
    )

    next_invoice_date = models.DateField(
        null=True,
        blank=True,
    )

    monthly_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_recurring_billings",
    )

    def clean(self):

        if (
            self.customer_id
            and self.company_id
        ):
            if self.customer.company_id != self.company_id:
                raise ValidationError(
                    "Customer does not belong to the selected company."
                )

        if (
            self.end_date
            and self.end_date < self.start_date
        ):
            raise ValidationError(
                "End date cannot be before start date."
            )

        if (
            not self.unlimited_recurrence
            and not self.total_recurrence
        ):
            raise ValidationError(
                "Total recurrence is required unless recurrence is unlimited."
            )

    def __str__(self):
        return self.contract_number

    class Meta:
        db_table = "finance_recurring_billing"
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "contract_number",
                ],
                name="unique_contract_number_per_company",
            )
        ]



class RecurringBillingOccurrence(TimeStampedModel):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("generated", "Generated"),
        ("sent", "Sent"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
    )

    id = models.BigAutoField(primary_key=True)

    recurring_billing = models.ForeignKey(
        RecurringBilling,
        on_delete=models.CASCADE,
        related_name="occurrences",
    )

    occurrence_number = models.PositiveIntegerField()

    scheduled_date = models.DateField()

    generated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    invoice_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    class Meta:
        db_table = "finance_recurring_billing_occurrence"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "recurring_billing",
                    "occurrence_number",
                ],
                name="unique_recurring_occurrence",
            )
        ]

        ordering = [
            "scheduled_date",
            "occurrence_number",
        ]

    def __str__(self):
        return (
            f"{self.recurring_billing.contract_number} - "
            f"{self.occurrence_number}"
        )