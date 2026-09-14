from django.db import models
from django.conf import settings
from shared.models import TimeStampedModel


class Quotation(TimeStampedModel):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("converted", "Converted"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="quotations"
    )

    quote_number = models.CharField(
        max_length=50,
        blank=True
    )

    customer = models.ForeignKey(
        "customer.Customer",
        on_delete=models.CASCADE,
        related_name="quotations"
    )

    issue_date = models.DateField()

    valid_till = models.DateField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    # From details
    from_company_name = models.CharField(
        max_length=200,
        blank=True,
        default="Tungston Labs"
    )

    from_address = models.TextField(
        blank=True,
        default=""
    )

    from_phone_number = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    from_email = models.EmailField(
        blank=True,
        default=""
    )

    # Bill To details
    bill_to_name = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )

    bill_to_address = models.TextField(
        blank=True,
        default=""
    )

    bill_to_phone = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    finance_contact_email = models.EmailField(
        blank=True,
        default=""
    )

    # Financial breakdown
    sub_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    total_vat = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    round_off = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    quote_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    negotiation_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    notes = models.TextField(
        blank=True,
        default=""
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_quotations"
    )

    def save(self, *args, **kwargs):
        if not self.quote_number or not str(self.quote_number).strip():
            from .utils import generate_next_quote_number
            self.quote_number = generate_next_quote_number(self.company)

        if self.customer and not self.bill_to_name:
            self.bill_to_name = getattr(self.customer, "customer_name", "")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quote_number} - {self.bill_to_name or self.customer}"

    class Meta:
        db_table = "finance_quotation"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "quote_number"],
                name="unique_quote_number_per_company"
            )
        ]


class QuotationItem(TimeStampedModel):

    id = models.BigAutoField(primary_key=True)

    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotation_items"
    )

    service_name = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )

    description = models.TextField(
        blank=True,
        default=""
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1.00
    )

    hs_code = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )

    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15.00
    )

    vat_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    def save(self, *args, **kwargs):
        # Auto calculate vat_amount and line amount if zero
        if self.rate and self.quantity:
            base_val = self.rate * self.quantity
            if not self.vat_amount:
                self.vat_amount = base_val * (self.vat_percentage / 100)
            if not self.amount:
                self.amount = base_val + self.vat_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service_name or 'Item'} ({self.quantity} x {self.rate})"

    class Meta:
        db_table = "finance_quotation_item"


class QuotationConversion(TimeStampedModel):

    PAYMENT_TYPE_CHOICES = (
        ("full_payment", "Full Payment"),
        ("partial_payment", "Partial Payment"),
    )

    PAYMENT_METHOD_CHOICES = (
        ("bank_transfer", "Bank Transfer"),
        ("cash", "Cash"),
        ("credit_card", "Credit Card"),
        ("check", "Check"),
        ("other", "Other"),
    )

    id = models.BigAutoField(primary_key=True)

    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name="conversions"
    )

    customer = models.ForeignKey(
        "customer.Customer",
        on_delete=models.CASCADE,
        related_name="quotation_conversions"
    )

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="quotation_conversions"
    )

    invoice_no = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    invoice_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    outstanding_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    payment_date = models.DateField(
        null=True,
        blank=True
    )

    payment_type = models.CharField(
        max_length=50,
        choices=PAYMENT_TYPE_CHOICES,
        default="full_payment"
    )

    payment_method = models.CharField(
        max_length=50,
        choices=PAYMENT_METHOD_CHOICES,
        default="bank_transfer"
    )

    amount_received = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    notes = models.TextField(
        blank=True,
        default=""
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"SO Conversion - {self.invoice_no or self.quotation.quote_number}"

    class Meta:
        db_table = "finance_quotation_conversion"
        ordering = ["-created_at"]
