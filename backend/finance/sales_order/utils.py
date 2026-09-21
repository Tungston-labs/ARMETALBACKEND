from django.db.models import Max


def generate_next_sales_order_number(company):
    """
    Generate company-wise Sales Order number.

    Example:
    SO-0001
    SO-0002
    SO-0003
    """

    last_order = (
        company.sales_orders
        .filter(so_number__startswith="SO-")
        .order_by("-id")
        .first()
    )

    if not last_order:
        next_number = 1
    else:
        try:
            last_number = int(
                last_order.so_number.replace("SO-", "")
            )
            next_number = last_number + 1
        except (ValueError, AttributeError):
            next_number = 1

    return f"SO-{next_number:04d}"