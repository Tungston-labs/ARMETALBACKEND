import re


def generate_next_sr_number(company):
    """
    Generates auto-incremented Sales Return number per company, e.g. SR - 0123.
    """
    from .models import SalesReturn

    if not company:
        return "SR - 0123"

    last_sr = (
        SalesReturn.objects.filter(company=company)
        .order_by("-id")
        .first()
    )

    if last_sr and last_sr.return_number:
        numbers = re.findall(r"\d+", last_sr.return_number)
        if numbers:
            last_num = int(numbers[-1])
        else:
            last_num = 0
        next_num = last_num + 1
    else:
        next_num = 123

    return f"SR - {next_num:04d}"
