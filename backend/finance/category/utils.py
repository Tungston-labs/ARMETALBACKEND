import re


def generate_next_category_code(company):
    """
    Generates the next sequential category code for a given company.
    Example sequence: CAT-001, CAT-002, CAT-003.
    """
    from .models import Category

    if company is None:
        qs = Category.objects.filter(company__isnull=True)
    else:
        qs = Category.objects.filter(company=company)

    existing_codes = qs.values_list("code", flat=True)

    max_num = 0
    pattern = re.compile(r"^CAT-(\d+)$", re.IGNORECASE)

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
    return f"CAT-{next_num:03d}"
