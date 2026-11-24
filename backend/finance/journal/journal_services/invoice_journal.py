
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from finance.accounting.account_mapping import get_company_account
from finance.invoice.models import Invoice
from finance.journal.models import JournalEntry, JournalEntryLine


def money(value):
    return Decimal(str(value or "0.00")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def get_mapped_account(company, purpose, expected_type):
    """
    Retrieve a company's mapped account and validate its account type.
    """

    account = get_company_account(company, purpose)

    if account.account_type != expected_type:
        raise ValidationError(
            f"Mapped account for '{purpose}' must be of type "
            f"'{expected_type}', but '{account.account_name}' "
            f"is configured as '{account.account_type}'."
        )

    return account


@transaction.atomic
def create_invoice_journal_entry(invoice, created_by=None):
    """
    Create the sales journal for an invoice.

    Debit: Accounts Receivable
    Credit: Sales Revenue
    Credit: VAT Payable

    Round-off:
    Positive adjustment -> Credit Round Off Gain
    Negative adjustment -> Debit Round Off Loss

    This service does not record customer payments.
    """

    # Prevent duplicate journal entries.
    existing_entry = JournalEntry.objects.filter(
        company=invoice.company,
        source="auto",
        source_module="invoice",
        source_id=str(invoice.pk),
    ).first()

    if existing_entry:
        return existing_entry

    invoice.refresh_from_db()

    subtotal = money(invoice.subtotal)
    vat_amount = money(invoice.total_vat)
    discount = money(invoice.discount)
    round_off = money(invoice.round_off)
    total_amount = money(invoice.total_amount)

    if total_amount <= Decimal("0.00"):
        raise ValidationError(
            "Cannot create a journal entry for an invoice "
            "with a zero or negative total."
        )

    if not invoice.items.exists():
        raise ValidationError(
            "Cannot create a journal entry without invoice items."
        )

    # Revenue after discount.
    revenue_amount = subtotal - discount

    if revenue_amount < Decimal("0.00"):
        raise ValidationError(
            "Invoice discount cannot exceed the subtotal."
        )

    if vat_amount < Decimal("0.00"):
        raise ValidationError(
            "VAT amount cannot be negative."
        )

    # Get company-specific mapped accounts.
    receivable_account = get_mapped_account(
        invoice.company,
        "receivable",
        "asset",
    )

    revenue_account = get_mapped_account(
        invoice.company,
        "sales_revenue",
        "revenue",
    )

    vat_account = None

    if vat_amount > Decimal("0.00"):
        vat_account = get_mapped_account(
            invoice.company,
            "vat_payable",
            "liability",
        )

    # The journal must balance, including discount and rounding.
    debit_total = total_amount
    credit_total = revenue_amount + vat_amount

    adjustment = money(debit_total - credit_total)

    if adjustment != round_off:
        raise ValidationError(
            "Invoice totals do not reconcile. Check subtotal, "
            "discount, VAT, round-off, and total amount."
        )

    # Get round-off account only when an adjustment is required.
    round_off_account = None
    round_off_purpose = None

    if adjustment > Decimal("0.00"):
        round_off_purpose = "round_off_gain"

        round_off_account = get_mapped_account(
            invoice.company,
            round_off_purpose,
            "revenue",
        )

    elif adjustment < Decimal("0.00"):
        round_off_purpose = "round_off_loss"

        round_off_account = get_mapped_account(
            invoice.company,
            round_off_purpose,
            "expense",
        )

    user = created_by or invoice.created_by

    entry = JournalEntry.objects.create(
        company=invoice.company,
        entry_date=invoice.invoice_date or timezone.localdate(),
        reference_number=invoice.invoice_number,
        description=f"Sales Invoice - {invoice.invoice_number}",
        source="auto",
        source_module="invoice",
        source_id=str(invoice.pk),
        status="posted",
        created_by=user,
        posted_by=user,
        posted_at=timezone.now(),
    )

    # Debit Accounts Receivable.
    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=receivable_account,
        description=f"Receivable - {invoice.invoice_number}",
        debit_amount=debit_total,
        credit_amount=Decimal("0.00"),
    )

    # Credit Sales Revenue.
    if revenue_amount > Decimal("0.00"):
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=revenue_account,
            description=f"Sales Revenue - {invoice.invoice_number}",
            debit_amount=Decimal("0.00"),
            credit_amount=revenue_amount,
        )

    # Credit VAT Payable.
    if vat_account and vat_amount > Decimal("0.00"):
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=vat_account,
            description=f"VAT Payable - {invoice.invoice_number}",
            debit_amount=Decimal("0.00"),
            credit_amount=vat_amount,
        )

    # Add round-off adjustment when necessary.
    if adjustment > Decimal("0.00"):
        # Credit Round Off Gain.
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=round_off_account,
            description=f"Round Off Gain - {invoice.invoice_number}",
            debit_amount=Decimal("0.00"),
            credit_amount=adjustment,
        )

    elif adjustment < Decimal("0.00"):
        # Debit Round Off Loss.
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=round_off_account,
            description=f"Round Off Loss - {invoice.invoice_number}",
            debit_amount=abs(adjustment),
            credit_amount=Decimal("0.00"),
        )

    if not entry.is_balanced:
        raise ValidationError(
            f"Invoice journal entry {entry.pk} is not balanced."
        )

    return entry
