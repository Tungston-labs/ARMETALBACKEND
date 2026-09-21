import re


def generate_next_dn_number(company):
    """
    Generates auto-incremented Delivery Note number per company, e.g. DN 0123 or DN-001.
    """
    from .models import DeliveryNote

    if not company:
        return "DN 0123"

    last_dn = (
        DeliveryNote.objects.filter(company=company)
        .order_by("-id")
        .first()
    )

    if last_dn and last_dn.dn_number:
        numbers = re.findall(r"\d+", last_dn.dn_number)
        if numbers:
            last_num = int(numbers[-1])
        else:
            last_num = 0
        next_num = last_num + 1
    else:
        next_num = 123

    return f"DN {next_num:04d}"
