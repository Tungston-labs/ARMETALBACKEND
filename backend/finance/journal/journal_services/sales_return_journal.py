
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from finance.accounting.models import ChartOfAccount
from finance.journal.models import JournalEntry, JournalEntryLine


RECEIVABLE_ACCOUNT_CODE = "1100"
VAT_PAYABLE_ACCOUNT_CODE = "2200"
SALES_RETURN_ACCOUNT_CODE = "4200"


def money(value):
    return Decimal(str(value or 0)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def get_account(company, account_code, account_type):
    account = ChartOfAccount.objects.filter(
        company=company,
        account_code=account_code,
        account_type=account_type,
        is_active=True
    ).first()

    if not account:
        raise ValidationError(
            f"Account {account_code} is not configured for this company."
        )

    return account


@transaction.atomic
def create_sales_return_journal_entry(sales_return, created_by=None):

    sales_return = (
        sales_return.__class__.objects
        .select_for_update()
        .prefetch_related("items")
        .get(pk=sales_return.pk)
    )

    if sales_return.status != "approved":
        raise ValidationError(
            "Only approved sales returns can create journal entries."
        )

    # Prevent duplicate journal entries.
    existing_entry = JournalEntry.objects.filter(
        company=sales_return.company,
        source="auto",
        source_module="sales_return",
        source_id=str(sales_return.id)
    ).first()

    if existing_entry:
        return existing_entry

    items = list(sales_return.items.all())

    if not items:
        raise ValidationError(
            "Cannot create journal entry without sales return items."
        )

    # Return item value is assumed to exclude VAT.
    sales_return_amount = money(
        sum((money(item.return_value) for item in items), Decimal("0.00"))
    )

    vat_amount = money(
        sum((money(item.vat_amount) for item in items), Decimal("0.00"))
    )

    total_amount = money(sales_return_amount + vat_amount)

    if total_amount <= 0:
        raise ValidationError(
            "Sales return amount must be greater than zero."
        )

    receivable_account = get_account(
        sales_return.company,
        RECEIVABLE_ACCOUNT_CODE,
        "asset"
    )

    sales_return_account = get_account(
        sales_return.company,
        SALES_RETURN_ACCOUNT_CODE,
        "expense"
    )

    vat_account = None

    if vat_amount > 0:
        vat_account = get_account(
            sales_return.company,
            VAT_PAYABLE_ACCOUNT_CODE,
            "liability"
        )

    entry = JournalEntry.objects.create(
        company=sales_return.company,
        entry_date=sales_return.return_date,
        reference_number=sales_return.return_number,
        description=f"Sales Return - {sales_return.return_number}",
        source="auto",
        source_module="sales_return",
        source_id=str(sales_return.id),
        status="posted",
        created_by=created_by or sales_return.created_by,
        posted_by=created_by or sales_return.created_by,
        posted_at=timezone.now()
    )

    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=sales_return_account,
        description=f"Sales return - {sales_return.return_number}",
        debit_amount=sales_return_amount,
        credit_amount=Decimal("0.00")
    )

    if vat_amount > 0:
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=vat_account,
            description="VAT reversal on sales return",
            debit_amount=vat_amount,
            credit_amount=Decimal("0.00")
        )

    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=receivable_account,
        description=f"Customer credit - {sales_return.customer_name}",
        debit_amount=Decimal("0.00"),
        credit_amount=total_amount
    )

    if not entry.is_balanced:
        raise ValidationError(
            "Sales return journal entry is not balanced."
        )

    return entry
