import pytest

from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from superadmin.models import Company
from finance.accounting.models import ChartOfAccount
from finance.journal.models import JournalEntry, JournalEntryLine


User = get_user_model()


# ============================================================
# URLS
# ============================================================

GENERAL_LEDGER_URL = "/api/finance/general-ledger/"


# ============================================================
# HELPERS
# ============================================================

def get_list_results(response):
    assert response.status_code == 200

    if isinstance(response.data, list):
        return response.data

    return response.data.get("results", [])


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def company(db):
    return Company.objects.create(
        name="Test Company",
        email="testcompany@example.com",
        contact_number="1234567890",
        address="Test Company Address",
        location="Riyadh",
    )


@pytest.fixture
def second_company(db):
    return Company.objects.create(
        name="Second Company",
        email="secondcompany@example.com",
        contact_number="9876543210",
        address="Second Company Address",
        location="Jeddah",
    )


@pytest.fixture
def company_admin(company):
    return User.objects.create_user(
        username="companyadmin",
        email="companyadmin@example.com",
        password="Test@12345",
        company=company,
    )


@pytest.fixture
def second_company_user(second_company):
    return User.objects.create_user(
        username="secondcompanyuser",
        email="seconduser@example.com",
        password="Test@12345",
        company=second_company,
    )


@pytest.fixture
def authenticated_client(api_client, company_admin):
    api_client.force_authenticate(user=company_admin)
    return api_client


@pytest.fixture
def second_authenticated_client(
    api_client,
    second_company_user,
):
    api_client.force_authenticate(user=second_company_user)
    return api_client


# ============================================================
# CHART OF ACCOUNTS
# ============================================================

@pytest.fixture
def asset_account(company, company_admin):
    return ChartOfAccount.objects.create(
        company=company,
        account_type="asset",
        account_name="Cash",
        account_code="1001",
        category="current_asset",
        opening_balance=Decimal("0.00"),
        opening_balance_type="debit",
        status="active",
        created_by=company_admin,
    )


@pytest.fixture
def revenue_account(company, company_admin):
    return ChartOfAccount.objects.create(
        company=company,
        account_type="revenue",
        account_name="Sales Revenue",
        account_code="4001",
        category="operating_revenue",
        opening_balance=Decimal("0.00"),
        opening_balance_type="credit",
        status="active",
        created_by=company_admin,
    )


@pytest.fixture
def expense_account(company, company_admin):
    return ChartOfAccount.objects.create(
        company=company,
        account_type="expense",
        account_name="Office Expense",
        account_code="5001",
        category="operating_expense",
        opening_balance=Decimal("0.00"),
        opening_balance_type="debit",
        status="active",
        created_by=company_admin,
    )


@pytest.fixture
def liability_account(company, company_admin):
    return ChartOfAccount.objects.create(
        company=company,
        account_type="liability",
        account_name="Accounts Payable",
        account_code="2001",
        category="current_liability",
        opening_balance=Decimal("0.00"),
        opening_balance_type="credit",
        status="active",
        created_by=company_admin,
    )


@pytest.fixture
def second_company_account(
    second_company,
    second_company_user,
):
    return ChartOfAccount.objects.create(
        company=second_company,
        account_type="asset",
        account_name="Other Company Cash",
        account_code="1001",
        category="current_asset",
        opening_balance=Decimal("0.00"),
        opening_balance_type="debit",
        status="active",
        created_by=second_company_user,
    )


# ============================================================
# JOURNAL ENTRY FIXTURES
# ============================================================

@pytest.fixture
def posted_journal(
    company,
    company_admin,
):
    """
    Adjust reference_number if your JournalEntry model uses
    a different journal number field.
    """
    return JournalEntry.objects.create(
        company=company,
        entry_date=date(2026, 10, 10),
        reference_number="JV-TEST-001",
        description="Test sales transaction",
        source="auto",
        source_module="invoice",
        source_id="1",
        status="posted",
        created_by=company_admin,
        posted_by=company_admin,
    )


@pytest.fixture
def second_posted_journal(
    company,
    company_admin,
):
    return JournalEntry.objects.create(
        company=company,
        entry_date=date(2026, 10, 12),
        reference_number="JV-TEST-002",
        description="Test office expense",
        source="auto",
        source_module="payment",
        source_id="2",
        status="posted",
        created_by=company_admin,
        posted_by=company_admin,
    )


@pytest.fixture
def draft_journal(company, company_admin):
    return JournalEntry.objects.create(
        company=company,
        entry_date=date(2026, 10, 13),
        reference_number="JV-DRAFT-001",
        description="Draft transaction",
        source="manual",
        source_module="manual_journal",
        source_id="3",
        status="draft",
        created_by=company_admin,
    )


@pytest.fixture
def posted_journal_lines(
    posted_journal,
    asset_account,
    revenue_account,
):
    debit_line = JournalEntryLine.objects.create(
        journal_entry=posted_journal,
        account=asset_account,
        description="Cash received",
        debit_amount=Decimal("1000.00"),
        credit_amount=Decimal("0.00"),
    )

    credit_line = JournalEntryLine.objects.create(
        journal_entry=posted_journal,
        account=revenue_account,
        description="Sales income",
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("1000.00"),
    )

    return debit_line, credit_line


@pytest.fixture
def expense_journal_lines(
    second_posted_journal,
    expense_account,
    liability_account,
):
    debit_line = JournalEntryLine.objects.create(
        journal_entry=second_posted_journal,
        account=expense_account,
        description="Office supplies",
        debit_amount=Decimal("200.00"),
        credit_amount=Decimal("0.00"),
    )

    credit_line = JournalEntryLine.objects.create(
        journal_entry=second_posted_journal,
        account=liability_account,
        description="Expense payable",
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("200.00"),
    )

    return debit_line, credit_line


# ============================================================
# LIST GENERAL LEDGER
# ============================================================

@pytest.mark.django_db
def test_general_ledger_list(
    authenticated_client,
    posted_journal_lines,
):
    response = authenticated_client.get(GENERAL_LEDGER_URL)

    results = get_list_results(response)

    assert len(results) == 2

    assert all(
        item["journal_number"] == "JV-TEST-001"
        for item in results
    )


@pytest.mark.django_db
def test_general_ledger_returns_expected_fields(
    authenticated_client,
    posted_journal_lines,
):
    response = authenticated_client.get(GENERAL_LEDGER_URL)

    results = get_list_results(response)

    item = next(
        item for item in results
        if item["account_code"] == "1001"
    )

    assert item["date"] == "2026-10-10"
    assert item["account_name"] == "Cash"
    assert item["type"] == "asset"
    assert item["description"] == "Cash received"
    assert item["source"] == "invoice"
    assert Decimal(item["debit_amount"]) == Decimal("1000.00")
    assert Decimal(item["credit_amount"]) == Decimal("0.00")


@pytest.mark.django_db
def test_general_ledger_excludes_draft_entries(
    authenticated_client,
    posted_journal_lines,
    draft_journal,
    asset_account,
):
    JournalEntryLine.objects.create(
        journal_entry=draft_journal,
        account=asset_account,
        description="Draft cash entry",
        debit_amount=Decimal("500.00"),
        credit_amount=Decimal("0.00"),
    )

    response = authenticated_client.get(GENERAL_LEDGER_URL)

    results = get_list_results(response)

    assert all(
        item["journal_number"] != "JV-DRAFT-001"
        for item in results
    )


# ============================================================
# DASHBOARD TOTALS
# ============================================================

@pytest.mark.django_db
def test_general_ledger_dashboard_totals(
    authenticated_client,
    posted_journal_lines,
    expense_journal_lines,
):
    response = authenticated_client.get(GENERAL_LEDGER_URL)

    assert response.status_code == 200

    dashboard = response.data["dashboard"]

    assert dashboard["total_lines"] == 4
    assert dashboard["asset_lines"] == 1
    assert dashboard["liability_lines"] == 1
    assert dashboard["income_lines"] == 1
    assert dashboard["expense_lines"] == 1

    assert Decimal(dashboard["total_debit"]) == Decimal("1200.00")
    assert Decimal(dashboard["total_credit"]) == Decimal("1200.00")
    assert Decimal(dashboard["difference"]) == Decimal("0.00")
    assert dashboard["balance_status"] == "balanced"


@pytest.mark.django_db
def test_general_ledger_dashboard_totals_are_calculated_before_pagination(
    authenticated_client,
    posted_journal_lines,
    expense_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"page": 1, "page_size": 1},
    )

    assert response.status_code == 200

    dashboard = response.data["dashboard"]
    pagination = response.data["pagination"]

    assert len(response.data["results"]) == 1
    assert pagination["count"] == 4
    assert dashboard["total_lines"] == 4

    assert Decimal(dashboard["total_debit"]) == Decimal("1200.00")
    assert Decimal(dashboard["total_credit"]) == Decimal("1200.00")


# ============================================================
# FILTER BY DATE
# ============================================================

@pytest.mark.django_db
def test_general_ledger_filter_date_from(
    authenticated_client,
    posted_journal_lines,
    expense_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"date_from": "2026-10-11"},
    )

    results = get_list_results(response)

    assert len(results) == 2
    assert all(item["date"] >= "2026-10-11" for item in results)


@pytest.mark.django_db
def test_general_ledger_filter_date_to(
    authenticated_client,
    posted_journal_lines,
    expense_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"date_to": "2026-10-10"},
    )

    results = get_list_results(response)

    assert len(results) == 2
    assert all(item["date"] <= "2026-10-10" for item in results)


@pytest.mark.django_db
def test_general_ledger_filter_date_range(
    authenticated_client,
    posted_journal_lines,
    expense_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {
            "date_from": "2026-10-10",
            "date_to": "2026-10-10",
        },
    )

    results = get_list_results(response)

    assert len(results) == 2
    assert all(item["date"] == "2026-10-10" for item in results)


# ============================================================
# FILTER BY ACCOUNT
# ============================================================

@pytest.mark.django_db
def test_general_ledger_filter_by_account(
    authenticated_client,
    posted_journal_lines,
    asset_account,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"account_id": asset_account.id},
    )

    results = get_list_results(response)

    assert len(results) == 1
    assert results[0]["account_id"] == asset_account.id
    assert results[0]["account_name"] == "Cash"


# ============================================================
# FILTER BY SOURCE
# ============================================================

@pytest.mark.django_db
def test_general_ledger_filter_by_source(
    authenticated_client,
    posted_journal_lines,
    expense_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"source": "invoice"},
    )

    results = get_list_results(response)

    assert len(results) == 2
    assert all(item["source"] == "invoice" for item in results)


# ============================================================
# FILTER BY ACCOUNT TYPE
# ============================================================

@pytest.mark.django_db
def test_general_ledger_filter_by_asset_type(
    authenticated_client,
    posted_journal_lines,
    expense_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"type": "asset"},
    )

    results = get_list_results(response)

    assert len(results) == 1
    assert results[0]["type"] == "asset"


@pytest.mark.django_db
def test_general_ledger_filter_by_revenue_type(
    authenticated_client,
    posted_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"type": "revenue"},
    )

    results = get_list_results(response)

    assert len(results) == 1
    assert results[0]["type"] == "revenue"


# ============================================================
# SEARCH
# ============================================================

@pytest.mark.django_db
def test_general_ledger_search_by_journal_number(
    authenticated_client,
    posted_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"search": "JV-TEST-001"},
    )

    results = get_list_results(response)

    assert len(results) == 2
    assert all(
        item["journal_number"] == "JV-TEST-001"
        for item in results
    )


@pytest.mark.django_db
def test_general_ledger_search_by_account_name(
    authenticated_client,
    posted_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"search": "Cash"},
    )

    results = get_list_results(response)

    assert len(results) == 1
    assert results[0]["account_name"] == "Cash"


@pytest.mark.django_db
def test_general_ledger_search_by_description(
    authenticated_client,
    posted_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"search": "Sales income"},
    )

    results = get_list_results(response)

    assert len(results) == 1
    assert results[0]["description"] == "Sales income"


# ============================================================
# PAGINATION
# ============================================================

@pytest.mark.django_db
def test_general_ledger_pagination(
    authenticated_client,
    posted_journal_lines,
    expense_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"page": 1, "page_size": 2},
    )

    assert response.status_code == 200
    assert len(response.data["results"]) == 2
    assert response.data["pagination"]["count"] == 4
    assert response.data["pagination"]["total_pages"] == 2
    assert response.data["pagination"]["current_page"] == 1
    assert response.data["pagination"]["next_page"] == 2
    assert response.data["pagination"]["previous_page"] is None


@pytest.mark.django_db
def test_general_ledger_invalid_page(
    authenticated_client,
    posted_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"page": 0, "page_size": 20},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_general_ledger_invalid_page_size(
    authenticated_client,
    posted_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"page": 1, "page_size": "abc"},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_general_ledger_page_beyond_available_results(
    authenticated_client,
    posted_journal_lines,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {"page": 9999, "page_size": 20},
    )

    assert response.status_code == 404


# ============================================================
# COMPANY ISOLATION
# ============================================================

@pytest.mark.django_db
def test_general_ledger_company_isolation(
    authenticated_client,
    posted_journal_lines,
    second_company,
    second_company_user,
    second_company_account,
):
    other_journal = JournalEntry.objects.create(
        company=second_company,
        entry_date=date(2026, 10, 10),
        reference_number="JV-OTHER-001",
        description="Other company transaction",
        source="auto",
        source_module="invoice",
        source_id="10",
        status="posted",
        created_by=second_company_user,
        posted_by=second_company_user,
    )

    JournalEntryLine.objects.create(
        journal_entry=other_journal,
        account=second_company_account,
        description="Other company cash",
        debit_amount=Decimal("500.00"),
        credit_amount=Decimal("0.00"),
    )

    response = authenticated_client.get(GENERAL_LEDGER_URL)

    results = get_list_results(response)

    assert all(
        item["journal_number"] != "JV-OTHER-001"
        for item in results
    )


# ============================================================
# AUTHENTICATION
# ============================================================

@pytest.mark.django_db
def test_general_ledger_requires_authentication(api_client):
    response = api_client.get(GENERAL_LEDGER_URL)

    assert response.status_code in [401, 403]


# ============================================================
# COMBINED FILTERS
# ============================================================

@pytest.mark.django_db
def test_general_ledger_combined_filters(
    authenticated_client,
    posted_journal_lines,
    asset_account,
):
    response = authenticated_client.get(
        GENERAL_LEDGER_URL,
        {
            "date_from": "2026-10-01",
            "date_to": "2026-10-31",
            "account_id": asset_account.id,
            "source": "invoice",
            "type": "asset",
            "page": 1,
            "page_size": 10,
        },
    )

    results = get_list_results(response)

    assert len(results) == 1
    assert results[0]["account_id"] == asset_account.id
    assert results[0]["source"] == "invoice"
    assert results[0]["type"] == "asset"
