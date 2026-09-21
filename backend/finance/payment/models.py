from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from shared.models import TimeStampedModel


def sync_invoice_payment_status(invoice):
    """
    Recalculates the total amount_paid and payment_status on an Invoice
    based on all completed payments linked to it.
    """
    if not invoice:
        return

    completed_total = (
        Payment.objects.filter(
            invoice=invoice,
            status="completed"
        ).aggregate(
            total=models.Sum("amount_received")
        )["total"]
        or Decimal("0.00")
    )

    invoice.amount_paid = completed_total

    if (
        invoice.amount_paid >= invoice.total_amount
        and invoice.total_amount > Decimal("0.00")
    ):
        invoice.payment_status = "paid"
    elif invoice.amount_paid > Decimal("0.00"):
        invoice.payment_status = "partially_paid"
    else:
        invoice.payment_status = "unpaid"

    invoice.save(update_fields=["amount_paid", "payment_status"])


class Payment(TimeStampedModel):

    PAYMENT_TYPE_CHOICES = (
        ("full_payment", "Full Payment"),
        ("partial_payment", "Partial Payment"),
        ("advance_payment", "Advance Payment"),
    )

    PAYMENT_METHOD_CHOICES = (
        ("bank_transfer", "Bank Transfer"),
        ("cheque", "Cheque"),
        ("online_payment", "Online Payment"),
        ("cash", "Cash"),
    )

    STATUS_CHOICES = (
        ("completed", "Completed"),
        ("pending", "Pending"),
        ("cancelled", "Cancelled"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="payments"
    )

    receipt_number = models.CharField(
        max_length=50,
        blank=True
    )

    customer = models.ForeignKey(
        "customer.Customer",
        on_delete=models.CASCADE,
        related_name="payments"
    )

    invoice = models.ForeignKey(
        "invoice.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments"
    )

    payment_date = models.DateField()

    payment_type = models.CharField(
        max_length=30,
        choices=PAYMENT_TYPE_CHOICES,
        default="full_payment"
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
        default="bank_transfer"
    )

    amount_received = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
        ]
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

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="completed"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payments"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_invoice_id = getattr(self, "invoice_id", None)
        self._original_status = getattr(self, "status", None)

    @property
    def invoice_amount(self):
        if self.invoice:
            return self.invoice.total_amount
        return Decimal("0.00")

    @property
    def outstanding_amount(self):
        if self.invoice:
            rem = self.invoice.total_amount - self.invoice.amount_paid
            return rem if rem > Decimal("0.00") else Decimal("0.00")
        return Decimal("0.00")

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            last_payment = (
                Payment.objects.filter(company=self.company)
                .order_by("-id")
                .first()
            )
            if last_payment:
                try:
                    last_num_str = "".join(
                        c for c in last_payment.receipt_number if c.isdigit()
                    )
                    last_number = int(last_num_str) if last_num_str else 0
                except (ValueError, AttributeError):
                    last_number = 0
                next_number = last_number + 1
            else:
                next_number = 1

            self.receipt_number = f"REC{next_number:03d}"

        super().save(*args, **kwargs)

        # Sync invoice status
        if self.invoice:
            sync_invoice_payment_status(self.invoice)

        if (
            self._original_invoice_id
            and self._original_invoice_id != self.invoice_id
        ):
            from finance.invoice.models import Invoice
            old_invoice = Invoice.objects.filter(
                id=self._original_invoice_id
            ).first()
            if old_invoice:
                sync_invoice_payment_status(old_invoice)

        self._original_invoice_id = self.invoice_id
        self._original_status = self.status

    def delete(self, *args, **kwargs):
        inv = self.invoice
        super().delete(*args, **kwargs)
        if inv:
            sync_invoice_payment_status(inv)

    def __str__(self):
        return f"{self.receipt_number} - {self.customer}"

    class Meta:
        db_table = "finance_payment"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "receipt_number"],
                name="unique_receipt_number_per_company"
            )
        ]
