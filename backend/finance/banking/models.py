
from django.core.validators import MinValueValidator
from django.db import models

from shared.models import TimeStampedModel


class BankAccount(TimeStampedModel):
    BANK_TYPE_CHOICES = [
        ("bank", "Bank"),
        ("cash", "Cash"),
        ("loan", "Loan"),
        ("credit", "Credit"),
        ("other", "Other"),
    ]

    ACCOUNT_TYPE_CHOICES = [
        ("current", "Current Account"),
        ("savings", "Savings Account"),
        ("cash", "Cash Account"),
        ("overdraft", "Overdraft"),
        ("fixed_deposit", "Fixed Deposit"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="bank_accounts",
    )
    bank_name = models.CharField(max_length=150)
    account_holder_name = models.CharField(max_length=150)
    account_type = models.CharField(
        max_length=30, choices=ACCOUNT_TYPE_CHOICES
    )
    account_number = models.CharField(max_length=100)
    iban = models.CharField(max_length=100, blank=True)
    bank_type = models.CharField(
        max_length=20, choices=BANK_TYPE_CHOICES
    )
    branch = models.CharField(max_length=150, blank=True)
    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    note = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active"
    )

    class Meta:
        db_table = "banking_bank_account"
        ordering = ["bank_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "account_number"],
                name="unique_bank_account_number_per_company",
            )
        ]

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


class BankTransaction(TimeStampedModel):
    TRANSACTION_TYPE_CHOICES = [
        ("customer_receipt", "Customer Receipt"),
        ("vendor_payment", "Vendor Payment"),
        ("bank_transfer", "Bank Transfer"),
        ("loan_disbursement", "Loan Disbursement"),
        ("loan_repayment", "Loan Repayment"),
        ("deposit", "Deposit"),
        ("withdrawal", "Withdrawal"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("reconciled", "Reconciled"),
    ]

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="bank_transactions",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    transaction_date = models.DateField()
    reference_number = models.CharField(max_length=100)
    transaction_type = models.CharField(
        max_length=30, choices=TRANSACTION_TYPE_CHOICES
    )
    money_in = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    money_out = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    balance_after = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    description = models.TextField(blank=True)

    class Meta:
        db_table = "banking_bank_transaction"
        ordering = ["-transaction_date", "-id"]
        constraints = [
            models.CheckConstraint(
                check=~(
                    models.Q(money_in__gt=0)
                    & models.Q(money_out__gt=0)
                ),
                name="bank_txn_money_in_or_out",
            )
        ]


class LoanAccount(TimeStampedModel):
    LOAN_TYPE_CHOICES = [
        ("term_loan", "Term Loan"),
        ("business_loan", "Business Loan"),
        ("home_loan", "Home Loan"),
        ("vehicle_loan", "Vehicle Loan"),
        ("personal_loan", "Personal Loan"),
        ("overdraft", "Overdraft"),
        ("other", "Other"),
    ]

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="loans",
    )
    loan_account_number = models.CharField(max_length=100)
    loan_type = models.CharField(
        max_length=30, choices=LOAN_TYPE_CHOICES
    )
    loan_amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    interest_rate = models.DecimalField(
        max_digits=7, decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    tenure_months = models.PositiveIntegerField()
    start_date = models.DateField()
    next_due_date = models.DateField(null=True, blank=True)
    monthly_installment = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    outstanding_balance = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        db_table = "banking_loan_account"
        ordering = ["next_due_date", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["bank_account", "loan_account_number"],
                name="unique_loan_number_per_bank_account",
            )
        ]

    def __str__(self):
        return self.loan_account_number
