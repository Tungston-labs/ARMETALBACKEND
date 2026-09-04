from calendar import monthrange
from datetime import date
from django.db.models import Q

from employee.models import Employee_db


def get_billable_employee_count(company, month, year):
    """
    Employee must work at least 15 days in the month.
    """

    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])

    employees = Employee_db.objects.filter(
        department__company=company
    ).filter(
        Q(is_deleted=False) |
        Q(
            is_deleted=True,
            deleted_at__date__gte=first_day
        )
    )

    total = 0

    for emp in employees:

        if emp.joining_date > last_day:
            continue

        start = max(emp.joining_date, first_day)

        if emp.is_deleted and emp.deleted_at:
            end = min(emp.deleted_at.date(), last_day)
        else:
            end = last_day

        days = (end - start).days + 1

        if days >= 15:
            total += 1

    return total


def calculate_subscription_amount(company, employee_count):
    """
    Calculate monthly subscription amount.

    If company has a plan:
        base_price + extra employees * extra_employee_price

    If company has no plan:
        employee_count * company.amount_per_employee
    """

    # -----------------------------------------
    # NEW PLAN-BASED CALCULATION
    # -----------------------------------------
    if company.plan:

        plan = company.plan

        employee_limit = plan.employee_limit or 0
        base_price = plan.base_price or 0
        extra_employee_price = plan.extra_employee_price or 0

        extra_employees = max(
            0,
            employee_count - employee_limit
        )

        amount = (
            base_price +
            (extra_employees * extra_employee_price)
        )

        return amount

    # -----------------------------------------
    # OLD CALCULATION
    # -----------------------------------------
    amount_per_employee = company.amount_per_employee or 0

    return employee_count * amount_per_employee