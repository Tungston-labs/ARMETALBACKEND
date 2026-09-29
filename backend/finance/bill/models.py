from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator

from shared.models import TimeStampedModel


class Bill(TimeStampedModel):
    """
    Purchase Bill Header model representing vendor bills/invoices received.
    """

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("unpaid", "Unpaid"),
        ("partially_paid", "Partially Paid"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    )

    PAYMENT_TERMS_CHOICES = (
        ("immediate", "Due on Receipt"),
        ("NET 10", "NET 10"),
        ("NET 15", "NET 15"),
        ("NET 30", "NET 30"),
        ("NET 45", "NET 45"),
        ("NET 60", "NET 60"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="purchase_bills",
    )

    vendor = models.ForeignKey(
        "vendor.Vendor",
        on_delete=models.PROTECT,
        related_name="purchase_bills",
        null=True,
        blank=True,
    )

    bill_number = models.CharField(
        max_length=100,
    )

    po_reference = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    bill_date = models.DateField()

    due_date = models.DateField(
        null=True,
        blank=True,
    )

    due_date_note = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    payment_terms = models.CharField(
        max_length=50,
        default="NET 10",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="unpaid",
    )

    note = models.TextField(
        blank=True,
        default="",
    )

    # From (Company Details Snapshot)
    from_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    from_address = models.TextField(
        blank=True,
        default="",
    )

    from_phone = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    from_email = models.EmailField(
        blank=True,
        default="",
    )

    # Bill To (Vendor / Client Details Snapshot)
    bill_to_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    bill_to_address = models.TextField(
        blank=True,
        default="",
    )

    bill_to_phone = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    bill_to_email = models.EmailField(
        blank=True,
        default="",
    )

    finance_contact_email = models.EmailField(
        blank=True,
        default="",
    )

    # Totals
    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_vat = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    round_off = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    amount_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchase_bills",
    )

    @property
    def balance(self):
        bal = self.total_amount - self.amount_paid
        return bal if bal > Decimal("0.00") else Decimal("0.00")

    def update_status(self):
        if self.status in ["draft", "cancelled"]:
            return

        bal = self.balance
        if bal == Decimal("0.00") and self.total_amount > Decimal("0.00"):
            self.status = "paid"
        elif self.amount_paid > Decimal("0.00") and bal > Decimal("0.00"):
            self.status = "partially_paid"
        else:
            self.status = "unpaid"

    def save(self, *args, **kwargs):
        if not self.bill_number:
            last_bill = (
                Bill.objects.filter(company=self.company)
                .order_by("-id")
                .first()
            )
            if last_bill:
                try:
                    num_part = last_bill.bill_number.replace("SR ", "").replace("BIL", "")
                    last_number = int(num_part)
                except (ValueError, AttributeError):
                    last_number = 0
                next_number = last_number + 1
            else:
                next_number = 1

            self.bill_number = f"BIL{next_number:05d}"

        self.update_status()
        super().save(*args, **kwargs)

    def calculate_totals(self):
        items = self.items.all()
        subtotal = sum((item.amount for item in items), Decimal("0.00"))
        total_vat = sum((item.vat_sar for item in items), Decimal("0.00"))

        self.subtotal = subtotal
        self.total_vat = total_vat
        self.total_amount = subtotal + total_vat - self.discount + self.round_off
        self.update_status()
        self.save(update_fields=["subtotal", "total_vat", "total_amount", "status"])

    def __str__(self):
        return f"{self.bill_number} - {self.bill_to_name or (self.vendor.name if self.vendor else '')}"

    class Meta:
        db_table = "finance_purchase_bill"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "bill_number"],
                name="unique_purchase_bill_number_per_company",
            )
        ]


class BillItem(TimeStampedModel):
    """
    Line item for a Purchase Bill.
    """

    id = models.BigAutoField(primary_key=True)

    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bill_items",
    )

    particular = models.CharField(
        max_length=500,
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    hs_code = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    rate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    vat_sar = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    def calculate_amounts(self):
        self.amount = self.quantity * self.rate
        self.vat_sar = (self.amount * self.vat_percentage) / Decimal("100")

    def save(self, *args, **kwargs):
        self.calculate_amounts()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.particular} ({self.quantity} x {self.rate})"

    class Meta:
        db_table = "finance_purchase_bill_item"
        ordering = ["id"]
