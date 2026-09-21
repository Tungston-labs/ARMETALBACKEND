from django.db import models
from django.conf import settings
from decimal import Decimal
from shared.models import TimeStampedModel


class CreditNote(TimeStampedModel):

    STATUS_CHOICES = (
        ("open", "Open"),
        ("partially_applied", "Partially Applied"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
        ("draft", "Draft"),
    )

    REASON_CHOICES = (
        ("sales_return", "Sales Return"),
        ("price_adjustment", "Price Adjustment"),
        ("damaged_goods", "Damaged Goods"),
        ("discount_adjustment", "Discount Adjustment"),
        ("pricing_error", "Pricing Error"),
        ("other", "Other"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="credit_notes"
    )

    cn_number = models.CharField(
        max_length=50,
        blank=True
    )

    customer = models.ForeignKey(
        "customer.Customer",
        on_delete=models.CASCADE,
        related_name="credit_notes"
    )

    invoice_ref = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    issue_date = models.DateField()

    reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES,
        default="sales_return"
    )

    credit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    applied_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default="open"
    )

    # Header / From Company Details
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

    # Financial Breakdown
    sub_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total_vat = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
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
        related_name="created_credit_notes"
    )

    @property
    def balance(self):
        c_amt = Decimal(str(self.credit_amount or 0.00))
        a_amt = Decimal(str(self.applied_amount or 0.00))
        bal = c_amt - a_amt
        return bal if bal > Decimal("0.00") else Decimal("0.00")

    def update_status_from_applied_amount(self):
        if self.status in ["cancelled", "draft"]:
            return

        c_amt = Decimal(str(self.credit_amount or 0.00))
        a_amt = Decimal(str(self.applied_amount or 0.00))

        if a_amt <= Decimal("0.00"):
            self.status = "open"
        elif a_amt < c_amt:
            self.status = "partially_applied"
        else:
            self.status = "closed"

    def save(self, *args, **kwargs):
        if not self.cn_number or not str(self.cn_number).strip():
            from .utils import generate_next_cn_number
            self.cn_number = generate_next_cn_number(self.company)

        self.update_status_from_applied_amount()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cn_number} - {self.customer}"

    class Meta:
        db_table = "finance_credit_note"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "cn_number"],
                name="unique_cn_number_per_company"
            )
        ]


class CreditNoteItem(TimeStampedModel):

    id = models.BigAutoField(primary_key=True)

    credit_note = models.ForeignKey(
        CreditNote,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_note_items"
    )

    item_name = models.CharField(
        max_length=200,
        blank=True,
        default=""
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
        default=Decimal("1.00")
    )

    rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00")
    )

    vat_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    def save(self, *args, **kwargs):
        if self.rate and self.quantity:
            base_val = Decimal(str(self.rate)) * Decimal(str(self.quantity))
            if not self.vat_amount:
                self.vat_amount = base_val * (Decimal(str(self.vat_percentage)) / Decimal("100"))
            if not self.amount:
                self.amount = base_val + self.vat_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_name or self.service_name or 'Item'} ({self.quantity} x {self.rate})"

    class Meta:
        db_table = "finance_credit_note_item"
