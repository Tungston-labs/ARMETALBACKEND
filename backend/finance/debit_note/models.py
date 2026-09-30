from decimal import Decimal
from django.db import models
from django.conf import settings
from shared.models import TimeStampedModel


class DebitNote(TimeStampedModel):
    STATUS_CHOICES = (
        ("open", "Open"),
        ("partially_applied", "Partially Applied"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
        ("draft", "Draft"),
    )

    REASON_CHOICES = (
        ("returned_goods", "Returned Goods"),
        ("damaged_goods", "Damaged Goods"),
        ("defective_items", "Defective Items"),
        ("overbilling", "Overbilling"),
        ("quality_issue", "Quality Issue"),
        ("wrong_item_delivered", "Wrong Item Delivered"),
        ("pricing_error", "Pricing Error"),
        ("other", "Other"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="debit_notes",
    )

    vendor = models.ForeignKey(
        "vendor.Vendor",
        on_delete=models.CASCADE,
        related_name="debit_notes",
        null=True,
        blank=True,
    )

    bill = models.ForeignKey(
        "bill.Bill",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debit_notes",
    )

    dn_number = models.CharField(
        max_length=50,
        blank=True,
    )

    bill_ref = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    issue_date = models.DateField()

    reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES,
        default="damaged_goods",
    )

    debit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    applied_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default="open",
    )

    # Header / From Company Details
    from_company_name = models.CharField(
        max_length=250,
        blank=True,
        default="Tungston Labs",
    )

    from_address = models.TextField(
        blank=True,
        default="",
    )

    from_phone_number = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    from_email = models.EmailField(
        blank=True,
        default="",
    )

    # Bill To Vendor Details
    bill_to_name = models.CharField(
        max_length=250,
        blank=True,
        default="",
    )

    bill_to_address = models.TextField(
        blank=True,
        default="",
    )

    bill_to_phone = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    finance_contact_email = models.EmailField(
        blank=True,
        default="",
    )

    # Financial Breakdown
    sub_total = models.DecimalField(
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
    )

    notes = models.TextField(
        blank=True,
        default="",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_debit_notes",
    )

    @property
    def balance(self):
        d_amt = Decimal(str(self.debit_amount or 0.00))
        a_amt = Decimal(str(self.applied_amount or 0.00))
        bal = d_amt - a_amt
        return bal if bal > Decimal("0.00") else Decimal("0.00")

    def update_status_from_applied_amount(self):
        if self.status in ["cancelled", "draft"]:
            return

        d_amt = Decimal(str(self.debit_amount or 0.00))
        a_amt = Decimal(str(self.applied_amount or 0.00))

        if a_amt <= Decimal("0.00"):
            self.status = "open"
        elif a_amt < d_amt:
            self.status = "partially_applied"
        else:
            self.status = "closed"

    def save(self, *args, **kwargs):
        if not self.dn_number or not str(self.dn_number).strip():
            last_dn = (
                DebitNote.objects.filter(company=self.company)
                .order_by("-id")
                .first()
            )
            if last_dn:
                try:
                    num_str = "".join(c for c in last_dn.dn_number if c.isdigit())
                    last_num = int(num_str) if num_str else 0
                except (ValueError, AttributeError):
                    last_num = 0
                next_num = last_num + 1
            else:
                next_num = 1
            self.dn_number = f"DN- {next_num:04d}"

        self.update_status_from_applied_amount()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dn_number} - {self.vendor or self.bill_to_name}"

    class Meta:
        db_table = "finance_debit_note"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "dn_number"],
                name="unique_debit_note_number_per_company",
            )
        ]


class DebitNoteItem(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)

    debit_note = models.ForeignKey(
        DebitNote,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debit_note_items",
    )

    bill_item = models.ForeignKey(
        "bill.BillItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debit_note_items",
    )

    item_name = models.CharField(
        max_length=250,
        blank=True,
        default="",
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    billed_qty = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    already_debited_qty = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
    )

    rate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
    )

    vat_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
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
        return f"{self.item_name or 'Debit Item'} ({self.quantity} x {self.rate})"

    class Meta:
        db_table = "finance_debit_note_item"
        ordering = ["id"]
