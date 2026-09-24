from calendar import monthrange
from datetime import timedelta


def calculate_next_invoice_date(start_date, frequency):
    if frequency == "daily":
        return start_date + timedelta(days=1)

    if frequency == "weekly":
        return start_date + timedelta(weeks=1)

    if frequency == "monthly":
        year = start_date.year + (start_date.month // 12)
        month = (start_date.month % 12) + 1
        day = min(
            start_date.day,
            monthrange(year, month)[1],
        )
        return start_date.replace(
            year=year,
            month=month,
            day=day,
        )

    if frequency == "quarterly":
        total_months = start_date.year * 12 + start_date.month - 1 + 3
        year = total_months // 12
        month = total_months % 12 + 1
        day = min(
            start_date.day,
            monthrange(year, month)[1],
        )
        return start_date.replace(
            year=year,
            month=month,
            day=day,
        )

    if frequency == "yearly":
        try:
            return start_date.replace(
                year=start_date.year + 1
            )
        except ValueError:
            return start_date.replace(
                year=start_date.year + 1,
                month=2,
                day=28,
            )

    return None