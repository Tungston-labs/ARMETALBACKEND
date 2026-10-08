from decimal import Decimal
from finance.accounting.models import ChartOfAccount
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from superadmin.models import Company


User = get_user_model()


# =============================================================================
# RESPONSE HELPERS
# =============================================================================

def get_response_results(response):
    """
    Return the actual result list from either:
    - paginated response: {"results": [...]}
    - non-paginated response: [...]
    """
    data = response.json()

    if isinstance(data, dict) and "results" in data:
        return data["results"]

    return data


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def company(db):
    return Company.objects.create(
        name="Test Company",
        email="testcompany@example.com",
    )


@pytest.fixture
def another_company(db):
    return Company.objects.create(
        name="Another Company",
        email="anothercompany@example.com",
    )


@pytest.fixture
def user(db, company):
    user = User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="Test@12345",
    )

    user.company = company
    user.is_company_admin = True
    user.save()

    return user


@pytest.fixture
def another_user(db, another_company):
    user = User.objects.create_user(
        username="anotheruser",
        email="anotheruser@example.com",
        password="Test@12345",
    )

    user.company = another_company
    user.is_company_admin = True
    user.save()

    return user


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


# =============================================================================
# ACCOUNT FIXTURES
# =============================================================================

@pytest.fixture
def asset_account(db, company, user):
    return ChartOfAccount.objects.create(
        company=company,
        account_type="asset",
        account_name="Cash",
        account_code="1100",
        parent_account=None,
        category="current_asset",
        opening_balance=Decimal("25000.00"),
        opening_balance_type="debit",
        status="active",
        description="Company cash account",
        created_by=user,
    )


@pytest.fixture
def bank_account(db, company, user):
    return ChartOfAccount.objects.create(
        company=company,
        account_type="asset",
        account_name="HDFC Bank",
        account_code="1110",
        parent_account=None,
        category="current_asset",
        opening_balance=Decimal("100000.00"),
        opening_balance_type="debit",
        status="active",
        description="Company bank account",
        created_by=user,
    )


@pytest.fixture
def liability_account(db, company, user):
    return ChartOfAccount.objects.create(
        company=company,
        account_type="liability",
        account_name="Accounts Payable",
        account_code="2100",
        parent_account=None,
        category="current_liability",
        opening_balance=Decimal("50000.00"),
        opening_balance_type="credit",
        status="active",
        description="Vendor payable account",
        created_by=user,
    )


@pytest.fixture
def equity_account(db, company, user):
    return ChartOfAccount.objects.create(
        company=company,
        account_type="equity",
        account_name="Owner Capital",
        account_code="3100",
        parent_account=None,
        category="equity",
        opening_balance=Decimal("200000.00"),
        opening_balance_type="credit",
        status="active",
        description="Owner capital account",
        created_by=user,
    )


@pytest.fixture
def revenue_account(db, company, user):
    return ChartOfAccount.objects.create(
        company=company,
        account_type="revenue",
        account_name="Sales Revenue",
        account_code="4100",
        parent_account=None,
        category="operating_revenue",
        opening_balance=Decimal("0.00"),
        opening_balance_type="credit",
        status="active",
        description="Sales revenue account",
        created_by=user,
    )


@pytest.fixture
def expense_account(db, company, user):
    return ChartOfAccount.objects.create(
        company=company,
        account_type="expense",
        account_name="Office Expenses",
        account_code="5100",
        parent_account=None,
        category="operating_expense",
        opening_balance=Decimal("0.00"),
        opening_balance_type="debit",
        status="active",
        description="Office expenses",
        created_by=user,
    )


@pytest.fixture
def inactive_account(db, company, user):
    return ChartOfAccount.objects.create(
        company=company,
        account_type="asset",
        account_name="Old Cash Account",
        account_code="1200",
        parent_account=None,
        category="current_asset",
        opening_balance=Decimal("10000.00"),
        opening_balance_type="debit",
        status="inactive",
        description="Inactive cash account",
        created_by=user,
    )


@pytest.fixture
def another_company_account(db, another_company, another_user):
    return ChartOfAccount.objects.create(
        company=another_company,
        account_type="asset",
        account_name="Another Company Cash",
        account_code="1100",
        parent_account=None,
        category="current_asset",
        opening_balance=Decimal("50000.00"),
        opening_balance_type="debit",
        status="active",
        description="Another company account",
        created_by=another_user,
    )


# =============================================================================
# URL FIXTURES
# =============================================================================

@pytest.fixture
def account_list_url():
    return reverse("chart-of-account-list-create")


@pytest.fixture
def account_kpi_url():
    return reverse("chart-of-account-kpi")


# =============================================================================
# CREATE ACCOUNT
# =============================================================================

@pytest.mark.django_db
def test_create_chart_of_account(
    authenticated_client,
    account_list_url,
    company,
    user,
):
    payload = {
        "account_type": "asset",
        "account_name": "Cash",
        "account_code": "1100",
        "parent_account": None,
        "category": "current_asset",
        "opening_balance": "25000.00",
        "opening_balance_type": "debit",
        "status": "active",
        "description": "Company cash account",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 201

    assert ChartOfAccount.objects.filter(
        account_code="1100"
    ).exists()

    account = ChartOfAccount.objects.get(
        account_code="1100"
    )

    assert account.company_id == company.id
    assert account.account_type == "asset"
    assert account.account_name == "Cash"
    assert account.account_code == "1100"
    assert account.opening_balance == Decimal("25000.00")
    assert account.opening_balance_type == "debit"
    assert account.status == "active"
    assert account.created_by_id == user.id


# =============================================================================
# CREATE LIABILITY ACCOUNT
# =============================================================================

@pytest.mark.django_db
def test_create_liability_account(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "liability",
        "account_name": "Accounts Payable",
        "account_code": "2100",
        "parent_account": None,
        "category": "current_liability",
        "opening_balance": "50000.00",
        "opening_balance_type": "credit",
        "status": "active",
        "description": "Vendor payable account",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 201

    account = ChartOfAccount.objects.get(
        account_code="2100"
    )

    assert account.account_type == "liability"
    assert account.opening_balance == Decimal("50000.00")
    assert account.opening_balance_type == "credit"


# =============================================================================
# CREATE EQUITY ACCOUNT
# =============================================================================

@pytest.mark.django_db
def test_create_equity_account(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "equity",
        "account_name": "Owner Capital",
        "account_code": "3100",
        "parent_account": None,
        "category": "equity",
        "opening_balance": "200000.00",
        "opening_balance_type": "credit",
        "status": "active",
        "description": "Owner capital",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 201

    account = ChartOfAccount.objects.get(
        account_code="3100"
    )

    assert account.account_type == "equity"


# =============================================================================
# CREATE REVENUE ACCOUNT
# =============================================================================

@pytest.mark.django_db
def test_create_revenue_account(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "revenue",
        "account_name": "Sales Revenue",
        "account_code": "4100",
        "parent_account": None,
        "category": "operating_revenue",
        "opening_balance": "0.00",
        "opening_balance_type": "credit",
        "status": "active",
        "description": "Sales revenue",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 201

    account = ChartOfAccount.objects.get(
        account_code="4100"
    )

    assert account.account_type == "revenue"


# =============================================================================
# CREATE EXPENSE ACCOUNT
# =============================================================================

@pytest.mark.django_db
def test_create_expense_account(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "expense",
        "account_name": "Office Expenses",
        "account_code": "5100",
        "parent_account": None,
        "category": "operating_expense",
        "opening_balance": "0.00",
        "opening_balance_type": "debit",
        "status": "active",
        "description": "Office expenses",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 201

    account = ChartOfAccount.objects.get(
        account_code="5100"
    )

    assert account.account_type == "expense"


# =============================================================================
# CREATE CHILD ACCOUNT
# =============================================================================

@pytest.mark.django_db
def test_create_child_account(
    authenticated_client,
    account_list_url,
    asset_account,
):
    payload = {
        "account_type": "asset",
        "account_name": "Petty Cash",
        "account_code": "1101",
        "parent_account": asset_account.id,
        "category": "current_asset",
        "opening_balance": "5000.00",
        "opening_balance_type": "debit",
        "status": "active",
        "description": "Petty cash account",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 201

    child = ChartOfAccount.objects.get(
        account_code="1101"
    )

    assert child.parent_account_id == asset_account.id


# =============================================================================
# LIST ACCOUNTS
# =============================================================================

@pytest.mark.django_db
def test_list_chart_of_accounts(
    authenticated_client,
    account_list_url,
    asset_account,
    liability_account,
    equity_account,
):
    response = authenticated_client.get(
        account_list_url
    )

    assert response.status_code == 200

    data = response.json()

    assert "sections" in data
    assert "totals" in data
    assert "count" in data

    assert "asset" in data["sections"]
    assert "liability" in data["sections"]
    assert "equity" in data["sections"]
    assert "revenue" in data["sections"]
    assert "expense" in data["sections"]


# =============================================================================
# LIST - ACCOUNT DATA
# =============================================================================

@pytest.mark.django_db
def test_list_contains_account_details(
    authenticated_client,
    account_list_url,
    asset_account,
):
    response = authenticated_client.get(
        account_list_url
    )

    assert response.status_code == 200

    data = response.json()

    accounts = data["sections"]["asset"]

    account = next(
        item
        for item in accounts
        if item["id"] == asset_account.id
    )

    assert account["account_name"] == "Cash"
    assert account["account_code"] == "1100"
    assert account["account_type"] == "asset"
    assert account["category"] == "current_asset"
    assert account["status"] == "active"


# =============================================================================
# BALANCE - DEBIT OPENING BALANCE
# =============================================================================

@pytest.mark.django_db
def test_account_balance_for_debit_opening_balance(
    authenticated_client,
    account_list_url,
    asset_account,
):
    response = authenticated_client.get(
        account_list_url
    )

    assert response.status_code == 200

    data = response.json()

    account = next(
        item
        for item in data["sections"]["asset"]
        if item["id"] == asset_account.id
    )

    assert Decimal(str(account["balance"])) == Decimal(
        "25000.00"
    )


# =============================================================================
# BALANCE - CREDIT OPENING BALANCE
# =============================================================================

@pytest.mark.django_db
def test_account_balance_for_credit_opening_balance(
    authenticated_client,
    account_list_url,
    liability_account,
):
    response = authenticated_client.get(
        account_list_url
    )

    assert response.status_code == 200

    data = response.json()

    account = next(
        item
        for item in data["sections"]["liability"]
        if item["id"] == liability_account.id
    )

    assert Decimal(str(account["balance"])) == Decimal(
        "-50000.00"
    )


# =============================================================================
# SEARCH BY ACCOUNT NAME
# =============================================================================

@pytest.mark.django_db
def test_search_account_by_name(
    authenticated_client,
    account_list_url,
    bank_account,
):
    response = authenticated_client.get(
        account_list_url,
        {"search": "HDFC"},
    )

    assert response.status_code == 200

    data = response.json()

    results = data["sections"]["asset"]

    assert len(results) >= 1

    assert any(
        item["account_name"] == "HDFC Bank"
        for item in results
    )


# =============================================================================
# SEARCH BY ACCOUNT CODE
# =============================================================================

@pytest.mark.django_db
def test_search_account_by_code(
    authenticated_client,
    account_list_url,
    asset_account,
):
    response = authenticated_client.get(
        account_list_url,
        {"search": "1100"},
    )

    assert response.status_code == 200

    data = response.json()

    results = data["sections"]["asset"]

    assert any(
        item["account_code"] == "1100"
        for item in results
    )


# =============================================================================
# FILTER BY ASSET
# =============================================================================

@pytest.mark.django_db
def test_filter_accounts_by_asset(
    authenticated_client,
    account_list_url,
    asset_account,
    bank_account,
    liability_account,
):
    response = authenticated_client.get(
        account_list_url,
        {"account_type": "asset"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["sections"]["asset"]) >= 2

    assert len(data["sections"]["liability"]) == 0
    assert len(data["sections"]["equity"]) == 0
    assert len(data["sections"]["revenue"]) == 0
    assert len(data["sections"]["expense"]) == 0


# =============================================================================
# FILTER BY LIABILITY
# =============================================================================

@pytest.mark.django_db
def test_filter_accounts_by_liability(
    authenticated_client,
    account_list_url,
    liability_account,
    asset_account,
):
    response = authenticated_client.get(
        account_list_url,
        {"account_type": "liability"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["sections"]["liability"]) == 1
    assert data["sections"]["liability"][0]["id"] == (
        liability_account.id
    )

    assert len(data["sections"]["asset"]) == 0


# =============================================================================
# FILTER BY EQUITY
# =============================================================================

@pytest.mark.django_db
def test_filter_accounts_by_equity(
    authenticated_client,
    account_list_url,
    equity_account,
    asset_account,
):
    response = authenticated_client.get(
        account_list_url,
        {"account_type": "equity"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["sections"]["equity"]) == 1

    assert data["sections"]["equity"][0]["id"] == (
        equity_account.id
    )


# =============================================================================
# FILTER BY REVENUE
# =============================================================================

@pytest.mark.django_db
def test_filter_accounts_by_revenue(
    authenticated_client,
    account_list_url,
    revenue_account,
):
    response = authenticated_client.get(
        account_list_url,
        {"account_type": "revenue"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["sections"]["revenue"]) == 1

    assert data["sections"]["revenue"][0]["id"] == (
        revenue_account.id
    )


# =============================================================================
# FILTER BY EXPENSE
# =============================================================================

@pytest.mark.django_db
def test_filter_accounts_by_expense(
    authenticated_client,
    account_list_url,
    expense_account,
):
    response = authenticated_client.get(
        account_list_url,
        {"account_type": "expense"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["sections"]["expense"]) == 1

    assert data["sections"]["expense"][0]["id"] == (
        expense_account.id
    )


# =============================================================================
# FILTER ACTIVE ACCOUNTS
# =============================================================================

@pytest.mark.django_db
def test_filter_active_accounts(
    authenticated_client,
    account_list_url,
    asset_account,
    inactive_account,
):
    response = authenticated_client.get(
        account_list_url,
        {"status": "active"},
    )

    assert response.status_code == 200

    data = response.json()

    all_accounts = []

    for section in data["sections"].values():
        all_accounts.extend(section)

    assert any(
        item["id"] == asset_account.id
        for item in all_accounts
    )

    assert not any(
        item["id"] == inactive_account.id
        for item in all_accounts
    )


# =============================================================================
# FILTER INACTIVE ACCOUNTS
# =============================================================================

@pytest.mark.django_db
def test_filter_inactive_accounts(
    authenticated_client,
    account_list_url,
    inactive_account,
    asset_account,
):
    response = authenticated_client.get(
        account_list_url,
        {"status": "inactive"},
    )

    assert response.status_code == 200

    data = response.json()

    all_accounts = []

    for section in data["sections"].values():
        all_accounts.extend(section)

    assert any(
        item["id"] == inactive_account.id
        for item in all_accounts
    )

    assert not any(
        item["id"] == asset_account.id
        for item in all_accounts
    )


# =============================================================================
# COMBINED FILTER
# =============================================================================

@pytest.mark.django_db
def test_combined_account_filter(
    authenticated_client,
    account_list_url,
    bank_account,
    asset_account,
    inactive_account,
):
    response = authenticated_client.get(
        account_list_url,
        {
            "account_type": "asset",
            "status": "active",
            "search": "Bank",
        },
    )

    assert response.status_code == 200

    data = response.json()

    results = data["sections"]["asset"]

    assert len(results) == 1
    assert results[0]["id"] == bank_account.id


# =============================================================================
# KPI
# =============================================================================

@pytest.mark.django_db
def test_chart_of_account_kpi(
    authenticated_client,
    account_kpi_url,
    asset_account,
    bank_account,
    liability_account,
    equity_account,
):
    response = authenticated_client.get(
        account_kpi_url
    )

    assert response.status_code == 200

    data = response.json()

    assert "total_accounts" in data
    assert "active_accounts" in data
    assert "asset_accounts" in data
    assert "liability_accounts" in data
    assert "equity_accounts" in data

    assert data["total_accounts"] == 4
    assert data["active_accounts"] == 4
    assert data["asset_accounts"] == 2
    assert data["liability_accounts"] == 1
    assert data["equity_accounts"] == 1


# =============================================================================
# KPI - INACTIVE ACCOUNT
# =============================================================================

@pytest.mark.django_db
def test_kpi_counts_inactive_accounts_correctly(
    authenticated_client,
    account_kpi_url,
    asset_account,
    inactive_account,
):
    response = authenticated_client.get(
        account_kpi_url
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_accounts"] == 2

    # Current KPI implementation counts only active
    # accounts for active_accounts.
    assert data["active_accounts"] == 1

    # Asset KPI includes both active and inactive assets.
    assert data["asset_accounts"] == 2


# =============================================================================
# KPI - COMPANY ISOLATION
# =============================================================================

@pytest.mark.django_db
def test_kpi_is_company_scoped(
    authenticated_client,
    account_kpi_url,
    asset_account,
    another_company_account,
):
    response = authenticated_client.get(
        account_kpi_url
    )

    assert response.status_code == 200

    data = response.json()

    # Only current user's company account should be counted.
    assert data["total_accounts"] == 1
    assert data["asset_accounts"] == 1


# =============================================================================
# COMPANY ISOLATION - ACCOUNT LIST
# =============================================================================

@pytest.mark.django_db
def test_accounts_are_company_scoped(
    authenticated_client,
    account_list_url,
    asset_account,
    another_company_account,
):
    response = authenticated_client.get(
        account_list_url
    )

    assert response.status_code == 200

    data = response.json()

    all_accounts = []

    for section in data["sections"].values():
        all_accounts.extend(section)

    assert any(
        item["id"] == asset_account.id
        for item in all_accounts
    )

    assert not any(
        item["id"] == another_company_account.id
        for item in all_accounts
    )


# =============================================================================
# DUPLICATE ACCOUNT CODE
# =============================================================================

@pytest.mark.django_db
def test_duplicate_account_code(
    authenticated_client,
    account_list_url,
    asset_account,
):
    payload = {
        "account_type": "asset",
        "account_name": "Duplicate Cash",
        "account_code": "1100",
        "parent_account": None,
        "category": "current_asset",
        "opening_balance": "1000.00",
        "opening_balance_type": "debit",
        "status": "active",
        "description": "Duplicate account code",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400

    data = response.json()

    assert "account_code" in data


# =============================================================================
# INVALID ACCOUNT TYPE
# =============================================================================

@pytest.mark.django_db
def test_invalid_account_type(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "invalid_type",
        "account_name": "Invalid Account",
        "account_code": "9999",
        "parent_account": None,
        "category": "current_asset",
        "opening_balance": "1000.00",
        "opening_balance_type": "debit",
        "status": "active",
        "description": "Invalid account type",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400

    assert "account_type" in response.json()


# =============================================================================
# NEGATIVE OPENING BALANCE
# =============================================================================

@pytest.mark.django_db
def test_negative_opening_balance(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "asset",
        "account_name": "Negative Balance",
        "account_code": "1200",
        "parent_account": None,
        "category": "current_asset",
        "opening_balance": "-5000.00",
        "opening_balance_type": "debit",
        "status": "active",
        "description": "Negative opening balance",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400

    assert "opening_balance" in response.json()


# =============================================================================
# INVALID STATUS
# =============================================================================

@pytest.mark.django_db
def test_invalid_status(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "asset",
        "account_name": "Invalid Status",
        "account_code": "1201",
        "parent_account": None,
        "category": "current_asset",
        "opening_balance": "1000.00",
        "opening_balance_type": "debit",
        "status": "invalid",
        "description": "Invalid status",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400

    assert "status" in response.json()


# =============================================================================
# INVALID OPENING BALANCE TYPE
# =============================================================================

@pytest.mark.django_db
def test_invalid_opening_balance_type(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "asset",
        "account_name": "Invalid Balance Type",
        "account_code": "1202",
        "parent_account": None,
        "category": "current_asset",
        "opening_balance": "1000.00",
        "opening_balance_type": "invalid",
        "status": "active",
        "description": "Invalid balance type",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400

    assert "opening_balance_type" in response.json()


# =============================================================================
# MISSING ACCOUNT NAME
# =============================================================================

@pytest.mark.django_db
def test_missing_account_name(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "asset",
        "account_code": "1203",
        "parent_account": None,
        "category": "current_asset",
        "opening_balance": "1000.00",
        "opening_balance_type": "debit",
        "status": "active",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400

    assert "account_name" in response.json()


# =============================================================================
# MISSING ACCOUNT CODE
# =============================================================================

@pytest.mark.django_db
def test_missing_account_code(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "asset",
        "account_name": "Missing Code",
        "parent_account": None,
        "category": "current_asset",
        "opening_balance": "1000.00",
        "opening_balance_type": "debit",
        "status": "active",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400

    assert "account_code" in response.json()


# =============================================================================
# INVALID PARENT ACCOUNT
# =============================================================================

@pytest.mark.django_db
def test_invalid_parent_account(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "asset",
        "account_name": "Invalid Parent",
        "account_code": "1204",
        "parent_account": 999999,
        "category": "current_asset",
        "opening_balance": "1000.00",
        "opening_balance_type": "debit",
        "status": "active",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400

    assert "parent_account" in response.json()


# =============================================================================
# PARENT ACCOUNT FROM ANOTHER COMPANY
# =============================================================================

@pytest.mark.django_db
def test_parent_account_from_another_company(
    authenticated_client,
    account_list_url,
    another_company_account,
):
    payload = {
        "account_type": "asset",
        "account_name": "Cross Company Child",
        "account_code": "1205",
        "parent_account": another_company_account.id,
        "category": "current_asset",
        "opening_balance": "1000.00",
        "opening_balance_type": "debit",
        "status": "active",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400

    assert "parent_account" in response.json()


# =============================================================================
# INVALID CATEGORY
# =============================================================================

@pytest.mark.django_db
def test_invalid_category(
    authenticated_client,
    account_list_url,
):
    payload = {
        "account_type": "asset",
        "account_name": "Invalid Category",
        "account_code": "1206",
        "parent_account": None,
        "category": "invalid_category",
        "opening_balance": "1000.00",
        "opening_balance_type": "debit",
        "status": "active",
    }

    response = authenticated_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400

    assert "category" in response.json()


# =============================================================================
# UNAUTHENTICATED - LIST
# =============================================================================

@pytest.mark.django_db
def test_account_list_requires_authentication(
    api_client,
    account_list_url,
):
    response = api_client.get(
        account_list_url
    )

    assert response.status_code in [401, 403]


# =============================================================================
# UNAUTHENTICATED - CREATE
# =============================================================================

@pytest.mark.django_db
def test_account_create_requires_authentication(
    api_client,
    account_list_url,
):
    payload = {
        "account_type": "asset",
        "account_name": "Unauthenticated Account",
        "account_code": "9998",
        "parent_account": None,
        "category": "current_asset",
        "opening_balance": "1000.00",
        "opening_balance_type": "debit",
        "status": "active",
    }

    response = api_client.post(
        account_list_url,
        payload,
        format="json",
    )

    assert response.status_code in [401, 403]


# =============================================================================
# UNAUTHENTICATED - KPI
# =============================================================================

@pytest.mark.django_db
def test_account_kpi_requires_authentication(
    api_client,
    account_kpi_url,
):
    response = api_client.get(
        account_kpi_url
    )

    assert response.status_code in [401, 403]


# =============================================================================
# COMBINED SEARCH + TYPE + STATUS
# =============================================================================

@pytest.mark.django_db
def test_search_with_account_type_and_status(
    authenticated_client,
    account_list_url,
    bank_account,
    asset_account,
    inactive_account,
):
    response = authenticated_client.get(
        account_list_url,
        {
            "search": "Bank",
            "account_type": "asset",
            "status": "active",
        },
    )

    assert response.status_code == 200

    data = response.json()

    results = data["sections"]["asset"]

    assert len(results) == 1

    assert results[0]["id"] == bank_account.id
    assert results[0]["account_name"] == "HDFC Bank"


# =============================================================================
# LIST TOTALS
# =============================================================================

@pytest.mark.django_db
def test_account_list_totals(
    authenticated_client,
    account_list_url,
    asset_account,
    liability_account,
    equity_account,
):
    response = authenticated_client.get(
        account_list_url
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(
        str(data["totals"]["asset"])
    ) == Decimal("25000.00")

    assert Decimal(
        str(data["totals"]["liability"])
    ) == Decimal("-50000.00")

    assert Decimal(
        str(data["totals"]["equity"])
    ) == Decimal("-200000.00")


# =============================================================================
# ACCOUNT COUNT
# =============================================================================

@pytest.mark.django_db
def test_account_count(
    authenticated_client,
    account_list_url,
    asset_account,
    liability_account,
    equity_account,
):
    response = authenticated_client.get(
        account_list_url
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 3