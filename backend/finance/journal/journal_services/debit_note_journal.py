
# finance/journal/journal_services/debit_note_journal.py

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from finance.accounting.models import ChartOfAccount
from finance.journal.models import JournalEntry, JournalEntryLine


PAYABLE_ACCOUNT_CODE = "2100"
PURCHASE_ACCOUNT_CODE = "5100"
VAT_RECOVERABLE_ACCOUNT_CODE = "1400"


def money(value):
    """Convert a value to a two-decimal-place Decimal."""
    return Decimal(str(value or "0.00")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def get_account(company, code, expected_type):
    """Return an active account configured for the company."""
    account = ChartOfAccount.objects.filter(
        company=company,
        account_code=code,
        account_type=expected_type,
        status="active",
    ).first()

    if not account:
        raise ValidationError(
            f"Active account {code} with type "
            f"'{expected_type}' is not configured for this company."
        )

    return account


@transaction.atomic
def create_debit_note_journal_entry(debit_note, created_by=None):
    """
    Create a journal entry when a debit note is issued.

    Accounting treatment:
    - Debit Accounts Payable.
    - Credit Purchase Expense, net of discount.
    - Credit Recoverable VAT.

    Draft and cancelled debit notes are not posted.
    Duplicate journal entries are prevented.
    """

    # Do not create entries for draft or cancelled debit notes.
    if debit_note.status in ("draft", "cancelled"):
        return None

    # Prevent duplicate journal entries.
    existing_entry = JournalEntry.objects.filter(
        company=debit_note.company,
        source="auto",
        source_module="debit_note",
        source_id=str(debit_note.pk),
    ).first()

    if existing_entry:
        return existing_entry

    # Normalize monetary values.
    subtotal = money(debit_note.sub_total)
    vat_amount = money(debit_note.total_vat)
    discount = money(debit_note.discount)
    debit_amount = money(debit_note.debit_amount)

    # Validate amounts.
    if subtotal < 0 or vat_amount < 0 or discount < 0:
        raise ValidationError(
            "Debit note amounts cannot be negative."
        )

    if discount > subtotal:
        raise ValidationError(
            "Discount cannot exceed the subtotal."
        )

    if debit_amount <= Decimal("0.00"):
        raise ValidationError(
            "Debit note amount must be greater than zero."
        )

    # Validate the debit note total.
    net_purchase = money(subtotal - discount)
    expected_total = money(net_purchase + vat_amount)

    if expected_total != debit_amount:
        raise ValidationError(
            f"Debit note total ({debit_amount}) does not match "
            f"subtotal - discount + VAT ({expected_total})."
        )

    # Retrieve the required ledger accounts.
    payable_account = get_account(
        debit_note.company,
        PAYABLE_ACCOUNT_CODE,
        "liability",
    )

    purchase_account = get_account(
        debit_note.company,
        PURCHASE_ACCOUNT_CODE,
        "expense",
    )

    vat_account = None

    if vat_amount > 0:
        vat_account = get_account(
            debit_note.company,
            VAT_RECOVERABLE_ACCOUNT_CODE,
            "asset",
        )

    user = created_by or debit_note.created_by

    # Create the journal entry.
    entry = JournalEntry.objects.create(
        company=debit_note.company,
        entry_date=(
            debit_note.issue_date or timezone.localdate()
        ),
        reference_number=debit_note.dn_number,
        description=f"Debit Note - {debit_note.dn_number}",
        source="auto",
        source_module="debit_note",
        source_id=str(debit_note.pk),
        status="posted",
        created_by=user,
        posted_by=user,
        posted_at=timezone.now(),
    )

    # 1. Debit Accounts Payable.
    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=payable_account,
        debit_amount=debit_amount,
        credit_amount=Decimal("0.00"),
        description=(
            f"Vendor payable reduction - {debit_note.dn_number}"
        ),
    )

    # 2. Credit Purchase Expense, net of discount.
    if net_purchase > 0:
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=purchase_account,
            debit_amount=Decimal("0.00"),
            credit_amount=net_purchase,
            description=(
                f"Purchase adjustment - {debit_note.dn_number}"
            ),
        )

    # 3. Credit Recoverable VAT.
    if vat_amount > 0:
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=vat_account,
            debit_amount=Decimal("0.00"),
            credit_amount=vat_amount,
            description=(
                f"VAT adjustment - {debit_note.dn_number}"
            ),
        )

    # Validate that the journal entry balances.
    if not entry.is_balanced:
        raise ValidationError(
            "Debit note journal entry is not balanced."
        )

    return entry
