from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from shared.models import TimeStampedModel
from django.db.models import Q

class VendorLedger(TimeStampedModel):

    TRANSACTION_TYPE_CHOICES = (
        ("opening_balance", "Opening Balance"),
        ("purchase_order", "Purchase Order"),
        ("bill", "Bill"),
        ("payment", "Payment"),
        ("debit_note", "Debit Note"),
        ("credit_note", "Credit Note"),
        ("manual", "Manual Entry"),
    )

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="vendor_ledger_entries",
    )

    vendor = models.ForeignKey(
        "vendor.Vendor",
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )

    entry_date = models.DateField()

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    transaction_type = models.CharField(
        max_length=30,
        choices=TRANSACTION_TYPE_CHOICES,
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    debit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
        ],
    )

    credit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
        ],
    )

    attachment = models.FileField(
        upload_to="vendor/ledger/",
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_vendor_ledger_entries",
    )

    # Source document references
    purchase_order = models.ForeignKey(
        "purchaseorder.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )

    bill = models.ForeignKey(
        "bill.Bill",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )

    payment = models.ForeignKey(
        "vendor.VendorPayment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )

    class Meta:
        db_table = "finance_vendor_ledger"
        ordering = ["-entry_date", "-id"]

        constraints = [
            models.UniqueConstraint(
                fields=["bill"],
                condition=Q(bill__isnull=False),
                name="unique_vendor_ledger_bill",
            ),
            models.UniqueConstraint(
                fields=["payment"],
                condition=Q(payment__isnull=False),
                name="unique_vendor_ledger_payment",
            ),
            models.UniqueConstraint(
                fields=["purchase_order"],
                condition=Q(purchase_order__isnull=False),
                name="unique_vendor_ledger_purchase_order",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if (
            self.debit_amount > Decimal("0.00")
            and self.credit_amount > Decimal("0.00")
        ):
            raise ValidationError(
                "A ledger entry cannot have both debit and credit amounts."
            )

        if (
            self.debit_amount == Decimal("0.00")
            and self.credit_amount == Decimal("0.00")
        ):
            raise ValidationError(
                "Either debit or credit amount is required."
            )

    def __str__(self):
        return (
            f"{self.vendor.vendor_id} - "
            f"{self.transaction_type} - "
            f"{self.reference_number}"
        )