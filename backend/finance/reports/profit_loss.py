from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.accounting.models import ChartOfAccount
from finance.journal.models import JournalEntryLine
from user.permissions import IsCompanyActive, IsHRAdmin


ZERO = Decimal("0.00")
MONEY_FIELD = DecimalField(max_digits=18, decimal_places=2)


def _period(request):
    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.query_params.get("date_from", f"{today.year}-01-01"))
        end = date.fromisoformat(request.query_params.get("date_to", today.isoformat()))
    except ValueError:
        raise ValidationError({"date": "Use valid dates in YYYY-MM-DD format."})
    if start > end:
        raise ValidationError({"date_to": "End date must be on or after the start date."})
    try:
        previous_start = start.replace(year=start.year - 1)
        previous_end = end.replace(year=end.year - 1)
    except ValueError:  # February 29
        previous_start = start.replace(year=start.year - 1, day=28)
        previous_end = end.replace(year=end.year - 1, day=28)
    return start, end, previous_start, previous_end


def _amounts(company_id, start, end):
    period = Q(
        journal_entry_lines__journal_entry__company_id=company_id,
        journal_entry_lines__journal_entry__status="posted",
        journal_entry_lines__journal_entry__entry_date__gte=start,
        journal_entry_lines__journal_entry__entry_date__lte=end,
    )
    accounts = ChartOfAccount.objects.filter(company_id=company_id, status="active").annotate(
        debit=Coalesce(Sum("journal_entry_lines__debit_amount", filter=period), Value(ZERO), output_field=MONEY_FIELD),
        credit=Coalesce(Sum("journal_entry_lines__credit_amount", filter=period), Value(ZERO), output_field=MONEY_FIELD),
    ).filter(account_type__in=("revenue", "expense"))
    amounts = {}
    for account in accounts:
        value = account.credit - account.debit if account.account_type == "revenue" else account.debit - account.credit
        amounts[account.id] = (account, value)
    return amounts


def _money(value):
    return str(Decimal(value or ZERO).quantize(Decimal("0.01")))


def _rows(current, previous, category_values):
    ids = {account_id for amount_set in (current, previous) for account_id in amount_set}
    result = []
    for account_id in ids:
        account, current_value = current.get(account_id, (previous[account_id][0], ZERO))
        previous_value = previous.get(account_id, (account, ZERO))[1]
        if account.category not in category_values:
            continue
        result.append({
            "account_id": account.id,
            "particular": account.account_name,
            "current_year": _money(current_value),
            "last_year": _money(previous_value),
            "variance": _money(current_value - previous_value),
        })
    return sorted(result, key=lambda row: row["particular"].lower())


class ProfitLossReportView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyActive, IsHRAdmin]

    def get(self, request):
        company_id = getattr(request.user, "company_id", None)
        if not company_id:
            raise ValidationError({"company": "Your user account is not linked to a company."})

        start, end, previous_start, previous_end = _period(request)
        current = _amounts(company_id, start, end)
        previous = _amounts(company_id, previous_start, previous_end)
        revenues = _rows(current, previous, {"operating_revenue", "other_revenue"})
        cogs = _rows(current, previous, {"cost_of_goods_sold"})
        operating_expenses = _rows(current, previous, {"operating_expense"})
        other_expenses = _rows(current, previous, {"other_expense"})

        def total(rows, key):
            return sum((Decimal(row[key]) for row in rows), ZERO)

        revenue = total(revenues, "current_year")
        revenue_last = total(revenues, "last_year")
        cogs_total = total(cogs, "current_year")
        cogs_last = total(cogs, "last_year")
        op_exp_total = total(operating_expenses, "current_year")
        other_exp_total = total(other_expenses, "current_year")
        op_exp_last = total(operating_expenses, "last_year")
        other_exp_last = total(other_expenses, "last_year")
        gross = revenue - cogs_total
        gross_last = revenue_last - cogs_last
        expenses = cogs_total + op_exp_total + other_exp_total
        expenses_last = cogs_last + op_exp_last + other_exp_last
        net = revenue - expenses
        net_last = revenue_last - expenses_last

        return Response({
            "date_from": start.isoformat(), "date_to": end.isoformat(),
            "comparison_date_from": previous_start.isoformat(), "comparison_date_to": previous_end.isoformat(),
            "currency": "SAR",
            "kpis": {
                "total_revenue": _money(revenue), "cost_of_goods_sold": _money(cogs_total),
                "gross_profit": _money(gross), "operating_expenses": _money(op_exp_total + other_exp_total),
                "total_expenses": _money(expenses), "net_profit": _money(net),
            },
            "sections": {
                "revenue": {"rows": revenues, "total": _money(revenue), "last_year_total": _money(revenue_last), "variance": _money(revenue - revenue_last)},
                "cost_of_goods_sold": {"rows": cogs, "total": _money(cogs_total), "last_year_total": _money(cogs_last), "variance": _money(cogs_total - cogs_last)},
                "gross_profit": {"current_year": _money(gross), "last_year": _money(gross_last), "variance": _money(gross - gross_last)},
                "operating_expenses": {"rows": operating_expenses, "total": _money(op_exp_total), "last_year_total": _money(op_exp_last), "variance": _money(op_exp_total - op_exp_last)},
                "other_expenses": {"rows": other_expenses, "total": _money(other_exp_total), "last_year_total": _money(other_exp_last), "variance": _money(other_exp_total - other_exp_last)},
                "net_profit": {"current_year": _money(net), "last_year": _money(net_last), "variance": _money(net - net_last)},
            },
        })
