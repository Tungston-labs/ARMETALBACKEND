
# finance/journal_entries/services/payment_journal.py

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from finance.accounting.models import ChartOfAccount
from finance.journal.models import JournalEntry, JournalEntryLine


BANK_ACCOUNT_CODE = "1200"
RECEIVABLE_ACCOUNT_CODE = "1300"


@transaction.atomic
def create_payment_journal_entry(payment, created_by=None):
    """
    Create a journal entry for a completed customer payment.

    Debit:  Bank (1200)
    Credit: Accounts Receivable (1300)

    Pending payments do not create journal entries.
    Existing entries are returned to prevent duplicate posting.
    """

    if payment.status != "completed":
        return None

    if payment.payment_method == "cash":
        raise ValidationError(
            "Cash payments cannot be posted because a Cash account "
            "has not been configured in the Chart of Accounts."
        )

    if payment.payment_method not in {
        "bank_transfer",
        "online_payment",
        "cheque",
    }:
        raise ValidationError(
            f"Unsupported payment method: {payment.payment_method}"
        )

    existing_entry = JournalEntry.objects.filter(
        company=payment.company,
        source="auto",
        source_module="payment",
        source_id=str(payment.pk),
    ).first()

    if existing_entry:
        return existing_entry

    amount = Decimal(
        str(payment.amount_received or "0.00")
    ).quantize(Decimal("0.01"))

    if amount <= Decimal("0.00"):
        raise ValidationError(
            "Cannot create a journal entry for a zero or negative payment."
        )

    bank_account = ChartOfAccount.objects.filter(
        company=payment.company,
        account_code=BANK_ACCOUNT_CODE,
        account_type="asset",
        status="active",
    ).first()

    receivable_account = ChartOfAccount.objects.filter(
        company=payment.company,
        account_code=RECEIVABLE_ACCOUNT_CODE,
        account_type="asset",
        status="active",
    ).first()

    if not bank_account:
        raise ValidationError(
            "Active Bank account (1200) was not found for this company."
        )

    if not receivable_account:
        raise ValidationError(
            "Active Accounts Receivable account (1300) was not found "
            "for this company."
        )

    entry = JournalEntry.objects.create(
        company=payment.company,
        entry_date=payment.payment_date or timezone.localdate(),
        reference_number=payment.receipt_number,
        description=f"Customer payment - {payment.receipt_number}",
        source="auto",
        source_module="payment",
        source_id=str(payment.pk),
        status="posted",
        created_by=created_by or payment.created_by,
        posted_by=created_by or payment.created_by,
        posted_at=timezone.now(),
    )

    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=bank_account,
        description=f"Payment received - {payment.receipt_number}",
        debit_amount=amount,
        credit_amount=Decimal("0.00"),
    )

    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=receivable_account,
        description=f"Accounts receivable - {payment.receipt_number}",
        debit_amount=Decimal("0.00"),
        credit_amount=amount,
    )

    if not entry.is_balanced:
        raise ValidationError(
            f"Journal entry {entry.entry_number} is not balanced."
        )

    return entry
