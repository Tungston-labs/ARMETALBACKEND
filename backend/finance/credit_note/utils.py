import re


def generate_next_cn_number(company):
    """
    Generates auto-incremented Credit Note number per company, e.g. CN- 0123 or CN-0001.
    """
    from .models import CreditNote

    if not company:
        return "CN- 0123"

    last_cn = (
        CreditNote.objects.filter(company=company)
        .order_by("-id")
        .first()
    )

    if last_cn and last_cn.cn_number:
        numbers = re.findall(r"\d+", last_cn.cn_number)
        if numbers:
            last_num = int(numbers[-1])
        else:
            last_num = 0
        next_num = last_num + 1
    else:
        next_num = 123

    return f"CN- {next_num:04d}"
