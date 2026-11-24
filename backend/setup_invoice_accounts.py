from django.db import transaction
from django.core.exceptions import ValidationError

from superadmin.models import Company
from finance.accounting.models import ChartOfAccount, CompanyAccountMapping


company = Company.objects.get(id=1)

accounts_data = [
    ("receivable", "1100", "Accounts Receivable", "asset", "current_asset"),
    ("sales_revenue", "4100", "Sales Revenue", "revenue", "operating_revenue"),
    ("vat_payable", "2200", "VAT Payable", "liability", "current_liability"),
    ("round_off_gain", "4300", "Round Off Gain", "revenue", "other_revenue"),
    ("round_off_loss", "5300", "Round Off Loss", "expense", "other_expense"),
]


@transaction.atomic
def setup_accounts():
    for purpose, code, name, acc_type, category in accounts_data:

        account, created = ChartOfAccount.objects.get_or_create(
            company=company,
            account_code=code,
            defaults={
                "account_name": name,
                "account_type": acc_type,
                "category": category,
                "status": "active",
            },
        )

        if (
            account.account_name != name
            or account.account_type != acc_type
            or account.category != category
            or account.status != "active"
        ):
            raise ValidationError(
                f"Account {code} already exists with different details."
            )

        mapping, mapping_created = CompanyAccountMapping.objects.get_or_create(
            company=company,
            purpose=purpose,
            defaults={"account": account},
        )

        if mapping.account_id != account.id:
            raise ValidationError(
                f"Mapping {purpose} already points to another account."
            )

        print(
            f"{'Created' if created else 'Existing'} account: "
            f"{code} - {name}"
        )

        print(
            f"{'Created' if mapping_created else 'Existing'} mapping: "
            f"{purpose} -> {account.account_code}"
        )


setup_accounts()
print("Invoice account setup completed successfully.")
