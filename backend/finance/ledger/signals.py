from django.db.models.signals import (
    post_delete,
    post_save,
)
from django.dispatch import receiver
from finance.invoice.models import Invoice
from finance.payment.models import Payment
from .services import (
    delete_payment_ledger,
    sync_invoice_ledger,
    sync_payment_ledger,
)


@receiver(
    post_save,
    sender=Invoice,
)
def invoice_saved(
    sender,
    instance,
    created,
    **kwargs,
):
    """
    Sync invoice debit entry.
    """

    sync_invoice_ledger(instance)


@receiver(
    post_save,
    sender=Payment,
)
def payment_saved(
    sender,
    instance,
    created,
    **kwargs,
):
    """
    Sync payment credit entry.
    """

    sync_payment_ledger(instance)


@receiver(
    post_delete,
    sender=Payment,
)
def payment_deleted(
    sender,
    instance,
    **kwargs,
):
    """
    Remove payment credit entry.
    """

    delete_payment_ledger(instance)