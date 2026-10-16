
from django.db import models
from django.core.validators import MinValueValidator
from shared.models import TimeStampedModel


class Expense(TimeStampedModel):
    CATEGORY_CHOICES = [
        ("rent", "Rent"),
        ("utilities", "Utilities"),
        ("salary_wages", "Salary and Wages"),
        ("marketing", "Marketing"),
        ("others", "Others"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
        ("card", "Card"),
        ("cheque", "Cheque"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("paid", "Paid"),
        ("unpaid", "Unpaid"),
    ]

    expense_id = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="expenses",
    )

    expense_date = models.DateField()
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
    )
    paid_to = models.CharField(max_length=200)
    paid_method = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
    )

    paid_from_account = models.ForeignKey(
        "banking.BankAccount",
        on_delete=models.PROTECT,
        related_name="expenses",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )

    document = models.FileField(
        upload_to="expenses/documents/",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="paid",
    )

    description = models.TextField(blank=True)

    class Meta:
        db_table = "finance_expense"
        ordering = ["-expense_date", "-id"]

    def save(self, *args, **kwargs):
        if not self.expense_id:
            # Save first to obtain a database-generated primary key.
            super().save(*args, **kwargs)

            self.expense_id = f"EXP-{self.pk:06d}"

            type(self).objects.filter(pk=self.pk).update(
                expense_id=self.expense_id
            )
            return

        super().save(*args, **kwargs)

    def __str__(self):
        return self.expense_id or f"Expense {self.pk}"
