import re


def generate_next_quote_number(company):
    """
    Generates auto-incremented quote number per company, e.g. QUT-001, QUT-002.
    """
    from .models import Quotation

    if not company:
        return "QUT-001"

    last_quote = (
        Quotation.objects.filter(company=company)
        .order_by("-id")
        .first()
    )

    if last_quote and last_quote.quote_number:
        numbers = re.findall(r"\d+", last_quote.quote_number)
        if numbers:
            last_num = int(numbers[-1])
        else:
            last_num = 0
        next_num = last_num + 1
    else:
        next_num = 1

    return f"QUT-{next_num:03d}"
