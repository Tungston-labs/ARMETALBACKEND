from django.core.management.base import BaseCommand

from finance.customer.models import Customer

from finance.ledger.services import (
    create_opening_balance_entry,
)


class Command(BaseCommand):

    help = (
        "Create opening balance ledger entries "
        "for existing customers."
    )

    def handle(
        self,
        *args,
        **options,
    ):

        customers = Customer.objects.all()

        processed_count = 0

        for customer in customers:

            entry = create_opening_balance_entry(
                customer=customer,
            )

            if entry:

                processed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Processed {processed_count} "
                    "opening balance entries."
                )
            )
        )