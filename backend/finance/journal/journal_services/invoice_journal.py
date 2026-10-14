
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from finance.accounting.models import ChartOfAccount
from finance.invoice.models import Invoice
from finance.journal.models import JournalEntry, JournalEntryLine


# Replace these example codes with your actual account codes.
RECEIVABLE_ACCOUNT_CODE = "1100"
SALES_REVENUE_ACCOUNT_CODE = "4100"
VAT_PAYABLE_ACCOUNT_CODE = "2200"


def money(value):
    return Decimal(str(value or "0.00")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def get_account(company, account_code, account_type):
    account = ChartOfAccount.objects.filter(
        company=company,
        account_code=account_code,
        account_type=account_type,
        status="active",
    ).first()

    if not account:
        raise ValidationError(
            f"Active {account_type} account "
            f"{account_code} was not found for this company."
        )

    return account


@transaction.atomic
def create_invoice_journal_entry(invoice, created_by=None):
    """
    Create the sales journal for an invoice.

    Debit: Accounts Receivable
    Credit: Sales Revenue
    Credit: VAT Payable

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

    receivable_account = get_account(
        invoice.company,
        RECEIVABLE_ACCOUNT_CODE,
        "asset",
    )

    revenue_account = get_account(
        invoice.company,
        SALES_REVENUE_ACCOUNT_CODE,
        "revenue",
    )

    vat_account = None

    if vat_amount > Decimal("0.00"):
        vat_account = get_account(
            invoice.company,
            VAT_PAYABLE_ACCOUNT_CODE,
            "liability",
        )

    # The journal must balance, including discount and rounding.
    debit_total = total_amount
    credit_total = revenue_amount + vat_amount

    adjustment = debit_total - credit_total

    if adjustment != round_off:
        raise ValidationError(
            "Invoice totals do not reconcile. Check subtotal, "
            "discount, VAT, round-off, and total amount."
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

    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=receivable_account,
        description=f"Receivable - {invoice.invoice_number}",
        debit_amount=debit_total,
        credit_amount=Decimal("0.00"),
    )

    if revenue_amount > Decimal("0.00"):
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=revenue_account,
            description=f"Sales Revenue - {invoice.invoice_number}",
            debit_amount=Decimal("0.00"),
            credit_amount=revenue_amount,
        )

    if vat_account and vat_amount > Decimal("0.00"):
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=vat_account,
            description=f"VAT Payable - {invoice.invoice_number}",
            debit_amount=Decimal("0.00"),
            credit_amount=vat_amount,
        )

    # Add a rounding line when necessary.
    if adjustment > Decimal("0.00"):
        # A positive difference is a debit-side adjustment.
        # Configure the appropriate account before enabling this case.
        raise ValidationError(
            "A debit-side rounding adjustment requires a configured "
            "round-off account."
        )

    if adjustment < Decimal("0.00"):
        raise ValidationError(
            "Invoice journal totals do not balance."
        )

    if not entry.is_balanced:
        raise ValidationError(
            f"Invoice journal entry {entry.pk} is not balanced."
        )

    return entry
