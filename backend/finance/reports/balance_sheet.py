
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from finance.accounting.models import ChartOfAccount
from finance.journal.models import JournalEntry, JournalEntryLine


ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def money(value):
    """Return a consistently rounded Decimal amount."""
    return Decimal(str(value or ZERO)).quantize(
        CENT,
        rounding=ROUND_HALF_UP,
    )


def amount_string(value):
    """Serialize money as a JSON-friendly decimal string."""
    return str(money(value))


def fiscal_year_start(as_of_date):
    """
    Defaults to a calendar year.

    Configure in settings.py if required:
        BALANCE_SHEET_FISCAL_YEAR_START_MONTH = 4
        BALANCE_SHEET_FISCAL_YEAR_START_DAY = 1

    For example, April 1 is a common financial-year start in India.
    """
    month = getattr(
        settings,
        "BALANCE_SHEET_FISCAL_YEAR_START_MONTH",
        1,
    )
    day = getattr(
        settings,
        "BALANCE_SHEET_FISCAL_YEAR_START_DAY",
        1,
    )

    start = as_of_date.replace(month=month, day=day)

    if as_of_date < start:
        start = start.replace(year=start.year - 1)

    return start



def normal_balance(account, debit_total, credit_total):
    opening = money(account.opening_balance)

    normal_side = (
        "debit"
        if account.account_type in ("asset", "expense")
        else "credit"
    )

    if account.opening_balance_type != normal_side:
        opening = -opening

    debit_total = money(debit_total)
    credit_total = money(credit_total)

    if normal_side == "debit":
        return money(opening + debit_total - credit_total)

    return money(opening + credit_total - debit_total)



def account_label(account):
    return account.account_name.strip().lower()


def matches(account, keywords):
    name = account_label(account)
    code = (account.account_code or "").strip().lower()

    return any(
        keyword in name or keyword in code
        for keyword in keywords
    )


def account_row(account, balance):
    return {
        "account_id": account.pk,
        "account_code": account.account_code,
        "account_name": account.account_name,
        "category": account.category,
        "balance": amount_string(balance),
    }


def sum_balances(account_balances, accounts):
    return money(
        sum(
            (
                account_balances.get(account.pk, ZERO)
                for account in accounts
            ),
            ZERO,
        )
    )


def calculate_balance_sheet(company_id, as_of_date):
    """
    Build a company-specific balance sheet as of a given date.

    Only posted journal entries dated on or before as_of_date are included.
    Opening balances are added once per ChartOfAccount.
    """
    accounts = list(
        ChartOfAccount.objects.filter(
            company_id=company_id,
        ).order_by("account_code", "id")
    )

    # Movements up to the selected reporting date.
    posted_lines = JournalEntryLine.objects.filter(
        journal_entry__company_id=company_id,
        journal_entry__status="posted",
        journal_entry__entry_date__lte=as_of_date,
    )

    movement_rows = (
        posted_lines
        .values("account_id")
        .annotate(
            debit_total=Sum("debit_amount"),
            credit_total=Sum("credit_amount"),
        )
    )

    movements = {
        row["account_id"]: (
            money(row["debit_total"]),
            money(row["credit_total"]),
        )
        for row in movement_rows
    }

    account_balances = {}

    for account in accounts:
        debit_total, credit_total = movements.get(
            account.pk,
            (ZERO, ZERO),
        )

        account_balances[account.pk] = normal_balance(
            account,
            debit_total,
            credit_total,
        )

    # Account-type groups.
    asset_accounts = [
        a for a in accounts if a.account_type == "asset"
    ]
    liability_accounts = [
        a for a in accounts if a.account_type == "liability"
    ]
    equity_accounts = [
        a for a in accounts if a.account_type == "equity"
    ]
    revenue_accounts = [
        a for a in accounts if a.account_type == "revenue"
    ]
    expense_accounts = [
        a for a in accounts if a.account_type == "expense"
    ]

    # Asset categories.
    current_asset_accounts = [
        a for a in asset_accounts
        if a.category == "current_asset"
    ]
    fixed_asset_accounts = [
        a for a in asset_accounts
        if a.category == "non_current_asset"
    ]
    other_asset_accounts = [
        a for a in asset_accounts
        if a.category not in ("current_asset", "non_current_asset")
    ]

    # Liability categories.
    current_liability_accounts = [
        a for a in liability_accounts
        if a.category == "current_liability"
    ]
    non_current_liability_accounts = [
        a for a in liability_accounts
        if a.category == "non_current_liability"
    ]
    other_liability_accounts = [
        a for a in liability_accounts
        if a.category not in (
            "current_liability",
            "non_current_liability",
        )
    ]

    # Profit and loss for the current financial year.
    year_start = fiscal_year_start(as_of_date)

    profit_loss_lines = JournalEntryLine.objects.filter(
        journal_entry__company_id=company_id,
        journal_entry__status="posted",
        journal_entry__entry_date__gte=year_start,
        journal_entry__entry_date__lte=as_of_date,
    )

    profit_loss_rows = (
        profit_loss_lines
        .values("account__account_type")
        .annotate(
            debit_total=Sum("debit_amount"),
            credit_total=Sum("credit_amount"),
        )
    )

    revenue_net = ZERO
    expense_net = ZERO

    for row in profit_loss_rows:
        debit = money(row["debit_total"])
        credit = money(row["credit_total"])

        if row["account__account_type"] == "revenue":
            revenue_net += credit - debit
        elif row["account__account_type"] == "expense":
            expense_net += debit - credit

    current_year_profit = money(revenue_net - expense_net)

    # Main totals.
    total_assets = sum_balances(
        account_balances,
        asset_accounts,
    )
    total_liabilities = sum_balances(
        account_balances,
        liability_accounts,
    )
    posted_equity = sum_balances(
        account_balances,
        equity_accounts,
    )

    # Current-year profit is added to equity, not to assets.
    total_equity = money(posted_equity + current_year_profit)

    total_liabilities_and_equity = money(
        total_liabilities + total_equity
    )

    balance_difference = money(
        total_assets - total_liabilities_and_equity
    )

    # Subtotals.
    current_assets = sum_balances(
        account_balances,
        current_asset_accounts,
    )
    fixed_assets = sum_balances(
        account_balances,
        fixed_asset_accounts,
    )
    other_assets = sum_balances(
        account_balances,
        other_asset_accounts,
    )

    current_liabilities = sum_balances(
        account_balances,
        current_liability_accounts,
    )
    non_current_liabilities = sum_balances(
        account_balances,
        non_current_liability_accounts,
    )
    other_liabilities = sum_balances(
        account_balances,
        other_liability_accounts,
    )

    working_capital = money(
        current_assets - current_liabilities
    )

    # Breakdown helper: each group shows its matching accounts and total.
    def group_data(group_accounts):
        rows = [
            account_row(
                account,
                account_balances.get(account.pk, ZERO),
            )
            for account in group_accounts
        ]

        return {
            "total": amount_string(
                sum_balances(account_balances, group_accounts)
            ),
            "accounts": rows,
        }

    # Keyword mapping is a fallback because ChartOfAccount has no
    # dedicated fields for these subcategories.
    bank_accounts = [
        a for a in current_asset_accounts
        if matches(a, ("bank", "checking", "savings"))
    ]
    cash_accounts = [
        a for a in current_asset_accounts
        if matches(a, ("cash", "petty cash", "cash in hand"))
    ]
    receivable_accounts = [
        a for a in current_asset_accounts
        if matches(
            a,
            (
                "accounts receivable",
                "account receivable",
                "trade receivable",
                "trade debtor",
                "debtors",
                "customer receivable",
            ),
        )
    ]

    vendor_payable_accounts = [
        a for a in current_liability_accounts
        if matches(
            a,
            (
                "accounts payable",
                "account payable",
                "vendor payable",
                "supplier payable",
                "trade payable",
                "creditors",
            ),
        )
    ]
    payroll_payable_accounts = [
        a for a in current_liability_accounts
        if matches(
            a,
            (
                "payroll payable",
                "salary payable",
                "salaries payable",
                "wages payable",
                "employee payable",
            ),
        )
    ]
    tax_payable_accounts = [
        a for a in current_liability_accounts
        if matches(
            a,
            (
                "tax payable",
                "vat payable",
                "gst payable",
                "sales tax payable",
                "output vat",
                "output gst",
            ),
        )
    ]

    capital_accounts = [
        a for a in equity_accounts
        if matches(
            a,
            (
                "capital",
                "owner investment",
                "capital investment",
                "share capital",
                "contributed capital",
            ),
        )
    ]
    retained_earnings_accounts = [
        a for a in equity_accounts
        if matches(
            a,
            (
                "retained earnings",
                "retained earning",
                "accumulated profit",
                "accumulated earnings",
                "prior year profit",
            ),
        )
    ]

    computer_accounts = [
        a for a in fixed_asset_accounts
        if matches(a, ("computer", "laptop", "desktop", "server"))
    ]
    furniture_accounts = [
        a for a in fixed_asset_accounts
        if matches(a, ("furniture", "desk", "chair", "cabinet"))
    ]
    equipment_accounts = [
        a for a in fixed_asset_accounts
        if matches(a, ("equipment", "machinery", "printer", "scanner"))
    ]

    # Avoid counting the same account in the "other fixed assets" group.
    identified_fixed_ids = {
        a.pk
        for a in (
            computer_accounts
            + furniture_accounts
            + equipment_accounts
        )
    }
    other_fixed_asset_accounts = [
        a for a in fixed_asset_accounts
        if a.pk not in identified_fixed_ids
    ]

    return {
        "as_of_date": as_of_date.isoformat(),
        "financial_year_start": year_start.isoformat(),

        "summary": {
            "total_assets": amount_string(total_assets),
            "total_liabilities": amount_string(total_liabilities),
            "total_equity": amount_string(total_equity),
            "working_capital": amount_string(working_capital),
            "total_liabilities_and_equity": amount_string(
                total_liabilities_and_equity
            ),
            "balance_difference": amount_string(balance_difference),
            "is_balanced": abs(balance_difference) <= CENT,
            "balance_status": (
                "balanced"
                if abs(balance_difference) <= CENT
                else "not_balanced"
            ),
        },

        "liabilities_and_equity": {
            "total_liabilities": amount_string(total_liabilities),
            "current_liabilities": group_data(
                current_liability_accounts
            ),
            "vendor_payable": group_data(vendor_payable_accounts),
            "payroll_payable": group_data(payroll_payable_accounts),
            "tax_payable": group_data(tax_payable_accounts),
            "non_current_liabilities": group_data(
                non_current_liability_accounts
            ),
            "other_liabilities": group_data(other_liability_accounts),
            "equity": {
                "total": amount_string(total_equity),
                "posted_equity_accounts": group_data(equity_accounts),
                "capital_investment": group_data(capital_accounts),
                "retained_earnings": group_data(
                    retained_earnings_accounts
                ),
                "current_year_profit": amount_string(
                    current_year_profit
                ),
            },
            "total_liabilities_and_equity": amount_string(
                total_liabilities_and_equity
            ),
        },

        "assets": {
            "total_assets": amount_string(total_assets),
            "current_assets": {
                "total": amount_string(current_assets),
                "accounts": [
                    account_row(
                        a,
                        account_balances.get(a.pk, ZERO),
                    )
                    for a in current_asset_accounts
                ],
                "bank_balance": group_data(bank_accounts),
                "cash_balance": group_data(cash_accounts),
                "accounts_receivable": group_data(receivable_accounts),
            },
            "fixed_assets": {
                "total": amount_string(fixed_assets),
                "computers_and_laptops": group_data(computer_accounts),
                "office_furniture": group_data(furniture_accounts),
                "office_equipment": group_data(equipment_accounts),
                "other_fixed_assets": group_data(
                    other_fixed_asset_accounts
                ),
                "accounts": [
                    account_row(
                        a,
                        account_balances.get(a.pk, ZERO),
                    )
                    for a in fixed_asset_accounts
                ],
            },
            "other_assets": group_data(other_asset_accounts),
        },

        "totals": {
            "total_assets": amount_string(total_assets),
            "total_liabilities_and_equity": amount_string(
                total_liabilities_and_equity
            ),
            "difference": amount_string(balance_difference),
        },
    }
