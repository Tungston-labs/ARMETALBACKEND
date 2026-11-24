#  default_accounts.py
from django.core.exceptions import ValidationError
from django.db import transaction

from finance.accounting.models import (
    ChartOfAccount,
    CompanyAccountMapping,
)


DEFAULT_ACCOUNTS = [
    {
        "purpose": "bank",
        "account_code": "1000",
        "account_name": "Bank",
        "account_type": "asset",
        "category": "current_asset",
    },
    {
        "purpose": "cash",
        "account_code": "1010",
        "account_name": "Cash",
        "account_type": "asset",
        "category": "current_asset",
    },
    {
        "purpose": "receivable",
        "account_code": "1100",
        "account_name": "Accounts Receivable",
        "account_type": "asset",
        "category": "current_asset",
    },
    {
        "purpose": "inventory",
        "account_code": "1200",
        "account_name": "Inventory Asset",
        "account_type": "asset",
        "category": "current_asset",
    },
    {
        "purpose": "vat_recoverable",
        "account_code": "1400",
        "account_name": "VAT Recoverable",
        "account_type": "asset",
        "category": "current_asset",
    },
    {
        "purpose": "payable",
        "account_code": "2100",
        "account_name": "Accounts Payable",
        "account_type": "liability",
        "category": "current_liability",
    },
    {
        "purpose": "vat_payable",
        "account_code": "2200",
        "account_name": "VAT Payable",
        "account_type": "liability",
        "category": "current_liability",
    },
    {
        "purpose": "sales_revenue",
        "account_code": "4100",
        "account_name": "Sales Revenue",
        "account_type": "revenue",
        "category": "operating_revenue",
    },
    {
        "purpose": "sales_returns",
        "account_code": "4200",
        "account_name": "Sales Returns",
        "account_type": "revenue",
        "category": "operating_revenue",
    },
    {
        "purpose": "purchase_expense",
        "account_code": "5100",
        "account_name": "Purchase Expense",
        "account_type": "expense",
        "category": "operating_expense",
    },
    {
        "purpose": "cogs",
        "account_code": "5200",
        "account_name": "Cost of Goods Sold",
        "account_type": "expense",
        "category": "cost_of_goods_sold",
    },
    {
        "purpose": "round_off_gain",
        "account_code": "4300",
        "account_name": "Round Off Gain",
        "account_type": "revenue",
        "category": "other_revenue",
    },
    {
        "purpose": "round_off_loss",
        "account_code": "5300",
        "account_name": "Round Off Loss",
        "account_type": "expense",
        "category": "other_expense",
    },
]


@transaction.atomic
def create_default_accounts_and_mappings(company):

    if CompanyAccountMapping.objects.filter(company=company).exists():
        raise ValidationError(
            "Account mappings already exist for this company. "
            "Default setup was not repeated."
        )

    for item in DEFAULT_ACCOUNTS:

        account, created = ChartOfAccount.objects.get_or_create(
            company=company,
            account_code=item["account_code"],
            defaults={
                "account_name": item["account_name"],
                "account_type": item["account_type"],
                "category": item["category"],
                "status": "active",
            }
        )

        # Do not silently map an existing code to an unrelated account.
        if (
            account.account_type != item["account_type"]
            or account.status != "active"
        ):
            raise ValidationError(
                f"Account code {item['account_code']} already exists "
                "with an incompatible type or inactive status."
            )

        CompanyAccountMapping.objects.create(
            company=company,
            purpose=item["purpose"],
            account=account,
        )
