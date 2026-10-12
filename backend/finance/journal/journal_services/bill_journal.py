# finance/journal_entries/services/bill_journal.py

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from finance.accounting.models import ChartOfAccount
from finance.journal.models import JournalEntry, JournalEntryLine


@transaction.atomic
def create_bill_journal_entry(bill, created_by=None):
    """
    Create and post one automatic journal entry for a paid bill.

    Debit:  Purchase Expense (5100)
    Credit: Bank (1200)

    Returns the existing entry if one has already been created.
    """

    if bill.status != "paid":
        return None

    # Prevent duplicate journal entries for the same bill.
    existing_entry = JournalEntry.objects.filter(
        company=bill.company,
        source="auto",
        source_module="bill",
        source_id=str(bill.pk),
    ).first()

    if existing_entry:
        return existing_entry

    amount = Decimal(str(bill.total_amount or "0.00")).quantize(
        Decimal("0.01")
    )

    if amount <= Decimal("0.00"):
        raise ValidationError(
            "Cannot create a journal entry for a bill with a zero or negative total."
        )

    # Find active accounts belonging to this bill's company.
    expense_account = ChartOfAccount.objects.filter(
        company=bill.company,
        account_code="5100",
        account_type="expense",
        status="active",
    ).first()

    bank_account = ChartOfAccount.objects.filter(
        company=bill.company,
        account_code="1200",
        account_type="asset",
        status="active",
    ).first()

    if not expense_account:
        raise ValidationError(
            "Active Purchase Expense account (5100) was not found "
            "for this company."
        )

    if not bank_account:
        raise ValidationError(
            "Active Bank account (1200) was not found for this company."
        )

    entry = JournalEntry.objects.create(
        company=bill.company,
        entry_date=bill.bill_date or timezone.localdate(),
        reference_number=bill.bill_number,
        description=f"Purchase bill payment - {bill.bill_number}",
        source="auto",
        source_module="bill",
        source_id=str(bill.pk),
        status="posted",
        created_by=created_by,
        posted_by=created_by,
        posted_at=timezone.now(),
    )

    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=expense_account,
        description=f"Purchase expense - {bill.bill_number}",
        debit_amount=amount,
        credit_amount=Decimal("0.00"),
    )

    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=bank_account,
        description=f"Bank payment - {bill.bill_number}",
        debit_amount=Decimal("0.00"),
        credit_amount=amount,
    )

    if not entry.is_balanced:
        raise ValidationError(
            f"Journal entry {entry.entry_number} is not balanced."
        )

    return entry