
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from finance.accounting.models import ChartOfAccount
from finance.journal.models import JournalEntryLine


ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def money(value):
    return Decimal(str(value or ZERO)).quantize(
        CENT,
        rounding=ROUND_HALF_UP,
    )


def fmt(value):
    return str(money(value))


def normal_side(account):
    return (
        "debit"
        if account.account_type in ("asset", "expense")
        else "credit"
    )


def opening_amount(account):
    amount = money(account.opening_balance)
    if account.opening_balance_type != normal_side(account):
        amount = -amount
    return amount


def equity_amount(account, debit, credit):
    """
    Credit-normal equity is positive.
    Debit balances reduce equity.
    """
    return money(
        opening_amount(account)
        + money(credit)
        - money(debit)
    )


def matches(account, *keywords):
    text = (
        f"{account.account_name} {account.account_code}"
    ).lower()
    return any(word in text for word in keywords)


def classify_equity(account):
    if matches(account, "share capital", "common stock", "share issue"):
        return "share_capital"

    if matches(account, "retained earning", "retained profit"):
        return "retained_earnings"

    if matches(account, "reserve", "revaluation", "translation reserve"):
        return "reserves"

    return "other_equity"


def calculate_changes_in_equity(company_id, start_date, end_date):
    accounts = list(
        ChartOfAccount.objects.filter(
            company_id=company_id,
            account_type__in=["equity", "revenue", "expense"],
        ).order_by("account_code", "id")
    )

    equity_accounts = [
        account for account in accounts
        if account.account_type == "equity"
    ]

    base_lines = JournalEntryLine.objects.filter(
        journal_entry__company_id=company_id,
        journal_entry__status="posted",
    )

    def totals_until(cutoff_date, account_ids):
        rows = (
            base_lines.filter(
                journal_entry__entry_date__lte=cutoff_date,
                account_id__in=account_ids,
            )
            .values("account_id")
            .annotate(
                debit=Sum("debit_amount"),
                credit=Sum("credit_amount"),
            )
        )
        return {
            row["account_id"]: (
                money(row["debit"]),
                money(row["credit"]),
            )
            for row in rows
        }

    equity_ids = [a.pk for a in equity_accounts]

    # Opening balances are the balances immediately before start_date.
    opening_movements = totals_until(
        start_date - __import__("datetime").timedelta(days=1),
        equity_ids,
    )

    opening_by_account = {}
    for account in equity_accounts:
        debit, credit = opening_movements.get(
            account.pk, (ZERO, ZERO)
        )
        opening_by_account[account.pk] = money(
            opening_amount(account) + credit - debit
        )

    opening_total = money(
        sum(opening_by_account.values(), ZERO)
    )

    # Period equity movements, excluding the opening balances.
    period_rows = (
        base_lines.filter(
            journal_entry__entry_date__gte=start_date,
            journal_entry__entry_date__lte=end_date,
            account_id__in=equity_ids,
        )
        .values("account_id")
        .annotate(
            debit=Sum("debit_amount"),
            credit=Sum("credit_amount"),
        )
    )

    period_movements = {
        row["account_id"]: (
            money(row["debit"]),
            money(row["credit"]),
        )
        for row in period_rows
    }

    component_opening = defaultdict(lambda: ZERO)
    component_movement = defaultdict(lambda: ZERO)
    component_accounts = defaultdict(list)

    for account in equity_accounts:
        component = classify_equity(account)
        debit, credit = period_movements.get(
            account.pk, (ZERO, ZERO)
        )

        component_opening[component] += opening_by_account[account.pk]
        component_movement[component] += credit - debit
        component_accounts[component].append(account)

    # Profit for the selected period: revenue less expenses.
    pnl_accounts = [
        account for account in accounts
        if account.account_type in ("revenue", "expense")
    ]
    pnl_ids = [a.pk for a in pnl_accounts]

    pnl_rows = (
        base_lines.filter(
            journal_entry__entry_date__gte=start_date,
            journal_entry__entry_date__lte=end_date,
            account_id__in=pnl_ids,
        )
        .values("account__account_type")
        .annotate(
            debit=Sum("debit_amount"),
            credit=Sum("credit_amount"),
        )
    )

    revenue = ZERO
    expenses = ZERO

    for row in pnl_rows:
        debit = money(row["debit"])
        credit = money(row["credit"])

        if row["account__account_type"] == "revenue":
            revenue += credit - debit
        else:
            expenses += debit - credit

    net_profit = money(revenue - expenses)

    # Net profit increases retained earnings for the period.
    component_movement["retained_earnings"] += net_profit

    component_names = {
        "share_capital": "Share Capital",
        "retained_earnings": "Retained Earnings",
        "reserves": "Reserves",
        "other_equity": "Other Equity",
    }

    components = {}
    closing_total = ZERO

    for key, label in component_names.items():
        opening = money(component_opening[key])
        movement = money(component_movement[key])
        closing = money(opening + movement)
        closing_total += closing

        components[key] = {
            "label": label,
            "opening_balance": fmt(opening),
            "net_movement": fmt(movement),
            "closing_balance": fmt(closing),
            "accounts": [
                {
                    "id": account.pk,
                    "code": account.account_code,
                    "name": account.account_name,
                }
                for account in component_accounts[key]
            ],
        }

    # Rows are derived from identifiable equity account names.
    # Use explicit journal movement classifications for more precise
    # dividend, transfer, and adjustment rows.
    rows = [
        {
            "particulars": "Opening Balance",
            "share_capital": fmt(component_opening["share_capital"]),
            "retained_earnings": fmt(component_opening["retained_earnings"]),
            "reserves": fmt(component_opening["reserves"]),
            "other_equity": fmt(component_opening["other_equity"]),
            "total_equity": fmt(opening_total),
        },
        {
            "particulars": "Net Profit for the Period",
            "share_capital": fmt(ZERO),
            "retained_earnings": fmt(net_profit),
            "reserves": fmt(ZERO),
            "other_equity": fmt(ZERO),
            "total_equity": fmt(net_profit),
        },
        {
            "particulars": "Net Equity Movements (excluding profit)",
            "share_capital": fmt(
                component_movement["share_capital"]
            ),
            "retained_earnings": fmt(
                component_movement["retained_earnings"] - net_profit
            ),
            "reserves": fmt(component_movement["reserves"]),
            "other_equity": fmt(component_movement["other_equity"]),
            "total_equity": fmt(
                sum(
                    (
                        component_movement[key]
                        for key in component_names
                    ),
                    ZERO,
                )
            ),
        },
        {
            "particulars": "Closing Balance",
            "share_capital": fmt(
                component_opening["share_capital"]
                + component_movement["share_capital"]
            ),
            "retained_earnings": fmt(
                component_opening["retained_earnings"]
                + component_movement["retained_earnings"]
            ),
            "reserves": fmt(
                component_opening["reserves"]
                + component_movement["reserves"]
            ),
            "other_equity": fmt(
                component_opening["other_equity"]
                + component_movement["other_equity"]
            ),
            "total_equity": fmt(closing_total),
        },
    ]

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "summary": {
            "total_equity": fmt(closing_total),
            "net_profit": fmt(net_profit),
            "share_capital": fmt(
                component_opening["share_capital"]
                + component_movement["share_capital"]
            ),
            "retained_earnings": fmt(
                component_opening["retained_earnings"]
                + component_movement["retained_earnings"]
            ),
            "dividends_declared": "0.00",
        },
        "components": components,
        "rows": rows,
    }
