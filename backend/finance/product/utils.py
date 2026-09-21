import re


def generate_next_product_code(company):
    """
    Generates the next sequential product code for a given company.
    Example sequence: PRD-001, PRD-002, PRD-003, ..., PRD-010, PRD-100.
    """
    from .models import Product

    if company is None:
        qs = Product.objects.filter(company__isnull=True)
    else:
        qs = Product.objects.filter(company=company)

    existing_codes = qs.values_list("code", flat=True)

    max_num = 0
    pattern = re.compile(r"^PRD-(\d+)$", re.IGNORECASE)

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
    return f"PRD-{next_num:03d}"
