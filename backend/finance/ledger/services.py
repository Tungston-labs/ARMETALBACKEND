from decimal import Decimal

from django.db import transaction

from finance.invoice.models import Invoice
from finance.payment.models import Payment

from .models import CustomerLedger


def recalculate_customer_ledger(
    customer_id,
    company_id,
):
    """
    Recalculates the running balance of a customer's ledger.

    Balance = Previous Balance + Debit - Credit
    """

    entries = (
        CustomerLedger.objects
        .filter(
            customer_id=customer_id,
            company_id=company_id,
        )
        .order_by(
            "transaction_date",
            "id",
        )
    )

    running_balance = Decimal("0.00")

    for entry in entries:

        running_balance += entry.debit
        running_balance -= entry.credit

        if entry.balance != running_balance:

            CustomerLedger.objects.filter(
                pk=entry.pk,
            ).update(
                balance=running_balance,
            )

    return running_balance


@transaction.atomic
def create_opening_balance_entry(
    customer,
    created_by=None,
):
    """
    Creates an opening balance ledger entry for a customer.

    Positive opening balance is recorded as debit.
    """

    opening_balance = (
        customer.opening_balance
        or Decimal("0.00")
    )

    if opening_balance <= Decimal("0.00"):

        return None

    entry, created = (
        CustomerLedger.objects.get_or_create(
            company_id=customer.company_id,
            customer_id=customer.id,
            transaction_type="opening_balance",
            reference_number=(
                f"OPENING-{customer.customer_id}"
            ),
            defaults={
                "transaction_date": (
                    customer.created_at.date()
                    if customer.created_at
                    else None
                ),
                "description": (
                    "Customer opening balance"
                ),
                "debit": opening_balance,
                "credit": Decimal("0.00"),
                "created_by": created_by,
            },
        )
    )

    recalculate_customer_ledger(
        customer_id=customer.id,
        company_id=customer.company_id,
    )

    return entry


@transaction.atomic
def sync_invoice_ledger(invoice):
    """
    Creates or updates a ledger debit entry for an invoice.
    """

    if not invoice:

        return None

    entry, created = (
        CustomerLedger.objects.update_or_create(
            company_id=invoice.company_id,
            customer_id=invoice.customer_id,
            invoice=invoice,
            transaction_type="invoice",
            defaults={
                "transaction_date": invoice.invoice_date,
                "reference_number": (
                    invoice.invoice_number
                ),
                "description": (
                    f"Invoice {invoice.invoice_number}"
                ),
                "debit": (
                    invoice.total_amount
                    or Decimal("0.00")
                ),
                "credit": Decimal("0.00"),
                "created_by": invoice.created_by,
            },
        )
    )

    recalculate_customer_ledger(
        customer_id=invoice.customer_id,
        company_id=invoice.company_id,
    )

    return entry


@transaction.atomic
def sync_payment_ledger(payment):
    """
    Creates or updates a payment credit entry.

    Only completed payments affect the ledger.
    """

    if not payment:

        return None

    existing_entry = (
        CustomerLedger.objects.filter(
            payment=payment,
        ).first()
    )

    if payment.status != "completed":

        if existing_entry:

            customer_id = existing_entry.customer_id
            company_id = existing_entry.company_id

            existing_entry.delete()

            recalculate_customer_ledger(
                customer_id=customer_id,
                company_id=company_id,
            )

        return None

    entry, created = (
        CustomerLedger.objects.update_or_create(
            company_id=payment.company_id,
            customer_id=payment.customer_id,
            payment=payment,
            transaction_type="payment",
            defaults={
                "transaction_date": payment.payment_date,
                "reference_number": (
                    payment.receipt_number
                    or payment.reference_number
                    or f"PAY-{payment.id}"
                ),
                "description": (
                    f"Payment {payment.receipt_number}"
                ),
                "debit": Decimal("0.00"),
                "credit": (
                    payment.amount_received
                    or Decimal("0.00")
                ),
                "created_by": payment.created_by,
            },
        )
    )

    recalculate_customer_ledger(
        customer_id=payment.customer_id,
        company_id=payment.company_id,
    )

    return entry


@transaction.atomic
def delete_payment_ledger(payment):
    """
    Deletes the ledger entry of a payment
    and recalculates the customer balance.
    """

    if not payment:

        return

    customer_id = payment.customer_id
    company_id = payment.company_id

    CustomerLedger.objects.filter(
        payment=payment,
    ).delete()

    recalculate_customer_ledger(
        customer_id=customer_id,
        company_id=company_id,
    )


def get_customer_ledger_balance(
    customer_id,
    company_id,
):
    """
    Returns the current customer ledger balance.
    """

    entries = CustomerLedger.objects.filter(
        customer_id=customer_id,
        company_id=company_id,
    )

    debit_total = sum(
        (
            entry.debit
            for entry in entries
        ),
        Decimal("0.00"),
    )

    credit_total = sum(
        (
            entry.credit
            for entry in entries
        ),
        Decimal("0.00"),
    )

    return debit_total - credit_total