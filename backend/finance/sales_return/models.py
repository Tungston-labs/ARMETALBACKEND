from decimal import Decimal
from django.db import models
from django.conf import settings

from shared.models import TimeStampedModel
from .utils import generate_next_sr_number


class SalesReturn(TimeStampedModel):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("refunded", "Refunded"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    )

    REASON_CHOICES = (
        ("damaged_product", "Damaged Product"),
        ("wrong_item", "Wrong Item"),
        ("quality_issue", "Quality Issue"),
        ("other", "Other"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="sales_returns"
    )

    return_number = models.CharField(
        max_length=50,
        blank=True
    )

    invoice = models.ForeignKey(
        "invoice.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_returns"
    )

    invoice_ref = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    customer = models.ForeignKey(
        "customer.Customer",
        on_delete=models.PROTECT,
        related_name="sales_returns"
    )

    return_date = models.DateField()

    reason = models.CharField(
        max_length=100,
        choices=REASON_CHOICES,
        default="wrong_item"
    )

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default="pending"
    )

    # Monetary values
    invoice_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    already_returned = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    eligible_to_return = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    return_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    refunded_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    applied_credits = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    notes = models.TextField(
        blank=True,
        default=""
    )

    # Company Snapshot (From)
    from_company_name = models.CharField(
        max_length=255,
        blank=True,
        default="TUNGSTON LABS"
    )

    from_address = models.TextField(
        blank=True,
        default=""
    )

    from_phone_number = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    from_email = models.EmailField(
        blank=True,
        default=""
    )

    # Customer Snapshot (Bill To)
    customer_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    customer_address = models.TextField(
        blank=True,
        default=""
    )

    customer_phone = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    finance_contact_email = models.EmailField(
        blank=True,
        default=""
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sales_returns"
    )

    @property
    def items_returned(self):
        """Returns total returned items count/quantity across items."""
        total = sum(item.returning_now_qty for item in self.items.all())
        return int(total) if total == int(total) else float(total)

    def calculate_eligible_and_return_values(self):
        inv_val = Decimal(str(self.invoice_value or 0.00))
        already_ret = Decimal(str(self.already_returned or 0.00))
        self.eligible_to_return = max(inv_val - already_ret, Decimal("0.00"))

    def save(self, *args, **kwargs):
        if not self.return_number or not str(self.return_number).strip():
            self.return_number = generate_next_sr_number(self.company)

        self.calculate_eligible_and_return_values()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.return_number} - {self.customer_name or self.customer}"

    class Meta:
        db_table = "finance_sales_return"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "return_number"],
                name="unique_sales_return_number_per_company"
            )
        ]


class SalesReturnItem(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)

    sales_return = models.ForeignKey(
        SalesReturn,
        on_delete=models.CASCADE,
        related_name="items"
    )

    invoice_item = models.ForeignKey(
        "invoice.InvoiceItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_return_items"
    )

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_return_items"
    )

    product_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    invoiced_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    already_returned_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    returning_now_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    condition = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00")
    )

    vat_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    return_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    def calculate_amounts(self):
        ret_qty = Decimal(str(self.returning_now_qty or 0.00))
        u_price = Decimal(str(self.unit_price or 0.00))
        base_val = ret_qty * u_price

        if self.vat_percentage:
            self.vat_amount = base_val * (Decimal(str(self.vat_percentage)) / Decimal("100"))
        
        self.return_value = base_val

    def save(self, *args, **kwargs):
        self.calculate_amounts()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name or 'Item'} ({self.returning_now_qty} units)"

    class Meta:
        db_table = "finance_sales_return_item"
