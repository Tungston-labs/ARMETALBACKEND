from django.db import transaction
from django.utils import timezone


def generate_next_adjustment_code(company=None):
    """
    Generates the next sequential stock adjustment number per company.
    Format: SA20260001, SA20260002, etc.
    """
    from .models import StockAdjustment

    with transaction.atomic():
        year = timezone.now().year
        prefix = f"SA{year}"

        if company:
            qs = StockAdjustment.objects.filter(company=company)
        else:
            qs = StockAdjustment.objects.filter(company__isnull=True)

        existing_codes = list(qs.values_list("code", flat=True))
        max_num = 0

        for code_str in existing_codes:
            if code_str:
                if code_str.startswith(prefix):
                    try:
                        num = int(code_str.replace(prefix, ""))
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        continue
                elif code_str.startswith("ADJ-"):
                    try:
                        num = int(code_str.replace("ADJ-", ""))
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        continue

        next_num = max_num + 1
        return f"{prefix}{next_num:04d}"
