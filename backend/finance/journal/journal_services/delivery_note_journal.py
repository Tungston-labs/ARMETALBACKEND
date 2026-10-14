
# finance/journal/journal_services/delivery_note_journal.py

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from finance.accounting.models import ChartOfAccount
from finance.journal.models import JournalEntry, JournalEntryLine


# Replace these with the account codes configured in your company.
INVENTORY_ACCOUNT_CODE = "1200"
COGS_ACCOUNT_CODE = "5200"


def money(value):
    return Decimal(str(value or "0.00")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def get_account(company, code, expected_type):
    account = ChartOfAccount.objects.filter(
        company=company,
        account_code=code,
        account_type=expected_type,
        status="active",
    ).first()

    if not account:
        raise ValidationError(
            f"Active account {code} with type '{expected_type}' "
            "is not configured for this company."
        )

    return account


@transaction.atomic
def create_delivery_note_journal_entry(
    delivery_note,
    created_by=None,
):
    """
    Record inventory cost at delivery:
        Debit: Cost of Goods Sold
        Credit: Inventory

    This function must only be called when the delivery note
    transitions to delivered.

    IMPORTANT:
    Implement get_item_cost() using your actual product-cost
    or inventory-valuation model before enabling posting.
    """

    if delivery_note.delivery_status != "delivered":
        return None

    existing_entry = JournalEntry.objects.filter(
        company=delivery_note.company,
        source="auto",
        source_module="delivery_note",
        source_id=str(delivery_note.pk),
    ).first()

    if existing_entry:
        return existing_entry

    items = list(
        delivery_note.items.select_related("product").all()
    )

    if not items:
        raise ValidationError(
            "Cannot post a delivery note without items."
        )

    total_cost = Decimal("0.00")

    # Do not use the selling rate as the inventory cost.
    # Replace this section with your actual inventory-cost lookup.
    for item in items:
        if not item.product:
            raise ValidationError(
                f"Item '{item.item_name or item.service_name}' "
                "has no linked product. Its inventory cost "
                "cannot be determined."
            )

        raise ValidationError(
            "Delivery Note journal posting is not configured yet: "
            "connect the product's actual inventory cost or "
            "inventory valuation service before posting."
        )

    total_cost = money(total_cost)

    if total_cost <= Decimal("0.00"):
        raise ValidationError(
            "Delivery cost must be greater than zero."
        )

    inventory_account = get_account(
        delivery_note.company,
        INVENTORY_ACCOUNT_CODE,
        "asset",
    )

    cogs_account = get_account(
        delivery_note.company,
        COGS_ACCOUNT_CODE,
        "expense",
    )

    user = created_by or delivery_note.created_by

    entry = JournalEntry.objects.create(
        company=delivery_note.company,
        entry_date=(
            delivery_note.delivery_date or timezone.localdate()
        ),
        reference_number=delivery_note.dn_number,
        description=f"Delivery Note - {delivery_note.dn_number}",
        source="auto",
        source_module="delivery_note",
        source_id=str(delivery_note.pk),
        status="posted",
        created_by=user,
        posted_by=user,
        posted_at=timezone.now(),
    )

    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=cogs_account,
        debit_amount=total_cost,
        credit_amount=Decimal("0.00"),
        description=f"Cost of goods sold - {delivery_note.dn_number}",
    )

    JournalEntryLine.objects.create(
        journal_entry=entry,
        account=inventory_account,
        debit_amount=Decimal("0.00"),
        credit_amount=total_cost,
        description=f"Inventory reduction - {delivery_note.dn_number}",
    )

    if not entry.is_balanced:
        raise ValidationError(
            "Delivery Note journal entry is not balanced."
        )

    return entry
