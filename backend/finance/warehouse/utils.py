import re
from .models import Warehouse


def generate_next_warehouse_code(company):
    """
    Generates the next sequential warehouse code for a given company.
    Example sequence: WH-001, WH-002, WH-003, ..., WH-010, WH-100.
    """
    if company is None:
        qs = Warehouse.objects.filter(company__isnull=True)
    else:
        qs = Warehouse.objects.filter(company=company)

    existing_codes = qs.values_list("code", flat=True)

    max_num = 0
    pattern = re.compile(r"^WH-(\d+)$", re.IGNORECASE)

    for code in existing_codes:
        if code:
            match = pattern.match(code.strip())
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass

    next_num = max_num + 1
    return f"WH-{next_num:03d}"
