from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from shared.models import TimeStampedModel


class CustomerLedger(TimeStampedModel):

    TRANSACTION_TYPE_CHOICES = (
        ("opening_balance", "Opening Balance"),
        ("invoice", "Invoice"),
        ("payment", "Payment"),
        ("credit_note", "Credit Note"),
        ("debit_note", "Debit Note"),
        ("adjustment", "Adjustment"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="customer_ledger_entries",
    )

    customer = models.ForeignKey(
        "customer.Customer",
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )

    transaction_date = models.DateField()

    transaction_type = models.CharField(
        max_length=30,
        choices=TRANSACTION_TYPE_CHOICES,
    )

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    invoice = models.ForeignKey(
        "invoice.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_ledger_entries",
    )

    payment = models.ForeignKey(
        "payment.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_ledger_entries",
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    debit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
        ],
    )

    credit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
        ],
    )

    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_customer_ledger_entries",
    )

    class Meta:

        db_table = "finance_customer_ledger"

        ordering = [
            "transaction_date",
            "id",
        ]

        indexes = [
            models.Index(
                fields=["company", "customer", "transaction_date"],
                name="ledger_cust_date_idx",
            ),
            models.Index(
                fields=[
                    "company",
                    "transaction_type",
                ],
                name="ledger_company_type_idx",
            ),
        ]

    def __str__(self):

        return (
            f"{self.customer.customer_name} - "
            f"{self.transaction_type} - "
            f"{self.reference_number}"
        )