
# finance/journal_entries/models.py

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from shared.models import TimeStampedModel


class JournalEntry(TimeStampedModel):

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("voided", "Voided"),
    )

    SOURCE_CHOICES = (
        ("manual", "Manual"),
        ("auto", "Automatic"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="journal_entries",
    )

    entry_number = models.CharField(max_length=50)

    entry_date = models.DateField(default=timezone.localdate)

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default="manual",
    )

    # Used to connect entries to their originating module.
    # Example: module="bill", source_id="125".
    source_module = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    source_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="draft",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_journal_entries",
    )

    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posted_journal_entries",
    )

    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "finance_journal_entry"
        ordering = ["-entry_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entry_number"],
                name="unique_journal_entry_number_per_company",
            ),
            models.UniqueConstraint(
                fields=["company", "source", "source_module", "source_id"],
                condition=~models.Q(source_id=""),
                name="unique_journal_source_per_company",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.entry_number:
            last_entry = (
                JournalEntry.objects
                .filter(company=self.company)
                .order_by("-id")
                .first()
            )

            next_number = 1

            if last_entry:
                try:
                    next_number = (
                        int(last_entry.entry_number.rsplit("-", 1)[-1]) + 1
                    )
                except (ValueError, AttributeError):
                    next_number = last_entry.pk + 1

            self.entry_number = f"JE-{next_number:06d}"

        super().save(*args, **kwargs)

    @property
    def total_debit(self):
        return self.lines.aggregate(
            total=models.Sum("debit_amount")
        )["total"] or Decimal("0.00")

    @property
    def total_credit(self):
        return self.lines.aggregate(
            total=models.Sum("credit_amount")
        )["total"] or Decimal("0.00")

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit

    def __str__(self):
        return self.entry_number


class JournalEntryLine(TimeStampedModel):

    id = models.BigAutoField(primary_key=True)

    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    account = models.ForeignKey(
    "accounting.ChartOfAccount",
    on_delete=models.PROTECT,
    related_name="journal_entry_lines",
)

    description = models.CharField(
        max_length=500,
        blank=True,
        default="",
    )

    debit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    credit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        db_table = "finance_journal_entry_line"
        ordering = ["id"]

    def __str__(self):
        return f"{self.journal_entry.entry_number} - {self.account_name}"