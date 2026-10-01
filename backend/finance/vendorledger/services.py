from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import VendorLedger



ZERO = Decimal("0.00")

@transaction.atomic
def create_vendor_ledger_entry(
    *,
    vendor,
    transaction_type,
    amount=Decimal("0.00"),
    debit_amount=Decimal("0.00"),
    credit_amount=Decimal("0.00"),
    entry_date=None,
    reference_number="",
    description="",
    created_by=None,
    attachment=None,
    purchase_order=None,
    bill=None,
    payment=None,
):
    if entry_date is None:
        entry_date = timezone.localdate()

    if amount:
        if transaction_type in [
            "purchase_order",
            "bill",
            "debit_note",
        ]:
            debit_amount = amount
            credit_amount = Decimal("0.00")

        elif transaction_type in [
            "payment",
            "credit_note",
        ]:
            credit_amount = amount
            debit_amount = Decimal("0.00")

    return VendorLedger.objects.create(
        company=vendor.company,
        vendor=vendor,
        entry_date=entry_date,
        reference_number=reference_number,
        transaction_type=transaction_type,
        description=description,
        debit_amount=debit_amount,
        credit_amount=credit_amount,
        attachment=attachment,
        created_by=created_by,
        purchase_order=purchase_order,
        bill=bill,
        payment=payment,
    )



@transaction.atomic
def sync_vendor_opening_balance(vendor, created_by=None):

    opening_balance = vendor.opening_balance or ZERO

    ledger = VendorLedger.objects.filter(
        company=vendor.company,
        vendor=vendor,
        transaction_type="opening_balance",
        bill__isnull=True,
        payment__isnull=True,
        purchase_order__isnull=True,
    ).first()

    if opening_balance <= ZERO:
        if ledger:
            ledger.delete()
        return None

    data = {
        "company": vendor.company,
        "vendor": vendor,
        "entry_date": vendor.created_at.date(),
        "reference_number": f"OB-{vendor.vendor_id}",
        "transaction_type": "opening_balance",
        "description": f"Opening balance for {vendor.vendor_id}",
        "debit_amount": opening_balance,
        "credit_amount": ZERO,
        "created_by": created_by,
    }

    if ledger:
        for field, value in data.items():
            setattr(ledger, field, value)

        ledger.save()
        return ledger

    return VendorLedger.objects.create(**data)


@transaction.atomic
def sync_bill_ledger(bill, created_by=None):

    # No vendor = no vendor ledger
    if not bill.vendor:
        VendorLedger.objects.filter(
            bill=bill
        ).delete()
        return None

    # Draft bills should not affect ledger
    if bill.status == "draft":
        VendorLedger.objects.filter(
            bill=bill
        ).delete()
        return None

    # Cancelled bill should not affect balance
    if bill.status == "cancelled":
        VendorLedger.objects.filter(
            bill=bill
        ).delete()
        return None

    ledger, _ = VendorLedger.objects.update_or_create(
        bill=bill,
        defaults={
            "company": bill.company,
            "vendor": bill.vendor,
            "entry_date": bill.bill_date,
            "reference_number": bill.bill_number,
            "transaction_type": "bill",
            "description": f"Vendor bill {bill.bill_number}",
            "debit_amount": bill.total_amount or ZERO,
            "credit_amount": ZERO,
            "created_by": (
                created_by
                or getattr(bill, "created_by", None)
            ),
        },
    )

    return ledger


@transaction.atomic
def sync_vendor_payment_ledger(payment, created_by=None):

    if not payment.vendor:
        VendorLedger.objects.filter(
            payment=payment
        ).delete()
        return None

    credit_amount = (
        payment.amount_paid
        if payment.status == "completed"
        else ZERO
    )

    ledger, _ = VendorLedger.objects.update_or_create(
        payment=payment,
        defaults={
            "company": payment.company,
            "vendor": payment.vendor,
            "entry_date": payment.payment_date,
            "reference_number": (
                payment.receipt_number
                or payment.reference_number
                or f"PAY-{payment.id}"
            ),
            "transaction_type": "payment",
            "description": (
                payment.notes
                or f"Payment for {payment.vendor.vendor_id}"
            ),
            "debit_amount": ZERO,
            "credit_amount": credit_amount,
            "created_by": (
                created_by
                or getattr(payment, "created_by", None)
            ),
        },
    )

    return ledger


def delete_bill_ledger(bill):
    VendorLedger.objects.filter(
        bill=bill
    ).delete()


def delete_payment_ledger(payment):
    VendorLedger.objects.filter(
        payment=payment
    ).delete()