from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from shared.models import TimeStampedModel


class ChartOfAccount(TimeStampedModel):

    ACCOUNT_TYPE_CHOICES = (
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("equity", "Equity"),
        ("revenue", "Revenue"),
        ("expense", "Expense"),
    )

    BALANCE_TYPE_CHOICES = (
        ("debit", "Debit"),
        ("credit", "Credit"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    CATEGORY_CHOICES = (
        ("current_asset", "Current Asset"),
        ("non_current_asset", "Non-Current Asset"),

        ("current_liability", "Current Liability"),
        ("non_current_liability", "Non-Current Liability"),

        ("equity", "Equity"),

        ("operating_revenue", "Operating Revenue"),
        ("other_revenue", "Other Revenue"),

        ("cost_of_goods_sold", "Cost of Goods Sold"),
        ("operating_expense", "Operating Expense"),
        ("other_expense", "Other Expense"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="chart_of_accounts"
    )

    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES
    )

    account_name = models.CharField(
        max_length=200
    )

    account_code = models.CharField(
        max_length=50
    )

    parent_account = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="child_accounts"
    )

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        blank=True,
        default=""
    )

    opening_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
        ]
    )

    opening_balance_type = models.CharField(
        max_length=10,
        choices=BALANCE_TYPE_CHOICES,
        default="debit"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active"
    )

    description = models.TextField(
        blank=True,
        default=""
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_chart_accounts"
    )

    class Meta:
        db_table = "accounting_chart_of_accounts"
        ordering = ["account_code"]

        constraints = [
            models.UniqueConstraint(
                fields=["company", "account_code"],
                name="unique_account_code_per_company"
            )
        ]

    def __str__(self):
        return f"{self.account_code} - {self.account_name}"
    

from django.core.exceptions import ValidationError
from shared.models import TimeStampedModel

class CompanyAccountMapping(TimeStampedModel):

    PURPOSE_CHOICES = (
        ("receivable", "Accounts Receivable"),
        ("payable", "Accounts Payable"),
        ("bank", "Bank"),
        ("cash", "Cash"),
        ("inventory", "Inventory"),
        ("vat_payable", "VAT Payable"),
        ("vat_recoverable", "VAT Recoverable"),
        ("sales_revenue", "Sales Revenue"),
        ("sales_returns", "Sales Returns"),
        ("purchase_expense", "Purchase Expense"),
        ("cogs", "Cost of Goods Sold"),
        ("round_off_gain", "Round Off Gain"),
        ("round_off_loss", "Round Off Loss"),
    )

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="account_mappings"
    )

    purpose = models.CharField(
        max_length=50,
        choices=PURPOSE_CHOICES
    )

    account = models.ForeignKey(
        "accounting.ChartOfAccount",
        on_delete=models.PROTECT,
        related_name="company_mappings"
    )

    class Meta:
        db_table = "company_account_mapping"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "purpose"],
                name="unique_company_account_purpose"
            )
        ]

    def clean(self):
        super().clean()

        if self.company_id and self.account_id:
            if self.company_id != self.account.company_id:
                raise ValidationError({
                    "account": "The selected account must belong to this company."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company_id} - {self.purpose} - {self.account.account_name}"
