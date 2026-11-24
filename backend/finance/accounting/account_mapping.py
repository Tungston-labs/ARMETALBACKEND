from django.core.exceptions import ValidationError

from finance.accounting.models import CompanyAccountMapping


def get_company_account(company, purpose):

    mapping = (
        CompanyAccountMapping.objects
        .select_related("account")
        .filter(
            company=company,
            purpose=purpose,
            account__company=company,
            account__status="active",
        )
        .first()
    )

    if mapping is None:
        raise ValidationError(
            f"Active account mapping '{purpose}' "
            f"was not found for company {company.pk}."
        )

    return mapping.account