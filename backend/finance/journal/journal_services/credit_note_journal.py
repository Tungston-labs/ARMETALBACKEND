
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from finance.journal.models import JournalEntry, JournalEntryLine
from finance.accounting.models import ChartOfAccount

# Confirmed from your existing Chart of Accounts
RECEIVABLE_ACCOUNT_CODE = "1300"
VAT_PAYABLE_ACCOUNT_CODE = "2200"

# Create/configure this account in the company's Chart of Accounts.
# It must be an active expense/contra-revenue account.
SALES_RETURNS_ACCOUNT_CODE = "4200"


@transaction.atomic
def create_credit_note_journal_entry(credit_note, created_by=None):
    """
    Create the journal entry when a credit note is issued (status=open).
    Do not create entries for draft, cancelled, partially applied, or closed
    credit notes.
    """

    if credit_note.status != "open":
        return None

    # Prevent duplicate entries for this credit note.
    existing_entry = JournalEntry.objects.filter(
        company=credit_note.company,
        source="auto",
        source_module="credit_note",
        source_id=str(credit_note.pk),
    ).first()

    if existing_entry:
        return existing_entry

    subtotal = Decimal(str(credit_note.sub_total or "0.00"))
    vat_amount = Decimal(str(credit_note.total_vat or "0.00"))
    discount = Decimal(str(credit_note.discount or "0.00"))
    credit_amount = Decimal(str(credit_note.credit_amount or "0.00"))

    if subtotal < 0 or vat_amount < 0 or discount < 0:
        raise ValidationError("Credit note amounts cannot be negative.")

    if credit_amount <= Decimal("0.00"):
        raise ValidationError(
            "A credit note must have a positive credit amount."
        )

    # Debit Sales Returns for the net value and VAT Payable for the VAT
    # reduction. Credit Accounts Receivable for the total credit.
    net_sales_return = subtotal - discount

    if net_sales_return < 0:
        raise ValidationError(
            "Discount cannot be greater than the subtotal."
        )

    expected_total = net_sales_return + vat_amount

    if expected_total != credit_amount:
        raise ValidationError(
            "Credit amount must equal subtotal minus discount plus VAT."
        )

    def get_account(account_code, account_type):
        account = ChartOfAccount.objects.filter(
            company=credit_note.company,
            account_code=account_code,
            account_type=account_type,
            status="active",
        ).first()

        if not account:
            raise ValidationError(
                f"Active account {account_code} ({account_type}) "
                f"is not configured for this company."
            )

        return account

    sales_returns_account = get_account(
        SALES_RETURNS_ACCOUNT_CODE, "expense"
    )
    receivable_account = get_account(
        RECEIVABLE_ACCOUNT_CODE, "asset"
    )

    vat_account = None
    if vat_amount > Decimal("0.00"):
        vat_account = get_account(
            VAT_PAYABLE_ACCOUNT_CODE, "liability"
        )

    entry = JournalEntry.objects.create(
        company=credit_note.company,
        entry_date=credit_note.issue_date or timezone.localdate(),
        reference_number=credit_note.cn_number,
        description=f"Credit Note - {credit_note.cn_number}",
        source="auto",
        source_module="credit_note",
        source_id=str(credit_note.pk),
        status="posted",
        created_by=created_by or credit_note.created_by,
        posted_by=created_by or credit_note.created_by,
        posted_at=timezone.now(),
    )

    if net_sales_return > Decimal("0.00"):
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=sales_returns_account,
            debit_amount=net_sales_return,
            credit_amount=Decimal("0.00"),
        )

    if vat_account:
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=vat_account,
            debit_amount=vat_amount,
            credit_amount=Decimal("0.00"),
        )

    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=receivable_account,
        debit_amount=Decimal("0.00"),
        credit_amount=credit_amount,
    )

    if not entry.is_balanced:
        raise ValidationError(
            "Credit note journal entry is not balanced."
        )

    return entry
