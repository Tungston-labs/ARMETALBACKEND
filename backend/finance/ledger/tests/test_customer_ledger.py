import pytest

from decimal import Decimal

from django.urls import reverse

from rest_framework import status

from rest_framework.test import APIClient

from finance.customer.models import Customer
from finance.ledger.models import CustomerLedger

pytestmark = pytest.mark.django_db


# ============================================================
# HELPERS
# ============================================================


def get_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def company(db):
    """
    Create a company.

    Adjust the required fields according to your actual
    Company model.
    """

    from superadmin.models import Company

    return Company.objects.create(
        name="Test Company",
        email="testcompany@example.com",
    )


@pytest.fixture
def other_company(db):
    """
    Second company used to test tenant isolation.
    """

    from superadmin.models import Company

    return Company.objects.create(
        name="Other Company",
        email="othercompany@example.com",
    )


@pytest.fixture
def user(company):
    """
    Create HR admin user.

    Adjust fields according to your custom User model.
    """

    from django.contrib.auth import get_user_model

    User = get_user_model()

    user = User.objects.create_user(
        username="hradmin",
        email="hradmin@example.com",
        password="Test@123",
    )

    user.company = company
    user.is_hr_admin = True
    user.save()

    return user


@pytest.fixture
def other_company_user(other_company):

    from django.contrib.auth import get_user_model

    User = get_user_model()

    user = User.objects.create_user(
        username="otheradmin",
        email="otheradmin@example.com",
        password="Test@123",
    )

    user.company = other_company
    user.is_hr_admin = True
    user.save()

    return user


@pytest.fixture
def customer(company):

    return Customer.objects.create(
        company=company,
        customer_name="ABC Traders",
        customer_id="CUS-001",
        opening_balance=Decimal("2000.00"),
    )


@pytest.fixture
def other_customer(other_company):

    return Customer.objects.create(
        company=other_company,
        customer_name="XYZ Traders",
        customer_id="CUS-002",
        opening_balance=Decimal("1000.00"),
    )


@pytest.fixture
def ledger_entry(company, customer, user):

    return CustomerLedger.objects.create(
        company=company,
        customer=customer,
        transaction_date="2026-09-20",
        transaction_type="adjustment",
        reference_number="REF-001",
        description="Initial adjustment",
        debit=Decimal("500.00"),
        credit=Decimal("0.00"),
        balance=Decimal("2500.00"),
        created_by=user,
    )


# ============================================================
# URL
# ============================================================


@pytest.fixture
def ledger_url():
    """
    Since your router is:

        router.register(
            r"",
            CustomerLedgerViewSet,
            basename="ledger",
        )

    the create URL is:

        ledger-list
    """

    return reverse("ledger-list")


# ============================================================
# CREATE - DEBIT
# ============================================================


def test_create_customer_ledger_debit(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "customer": customer.id,
        "transaction_date": "2026-09-22",
        "reference_number": "REF-10025",
        "description": "Manual debit adjustment",
        "mode": "debit",
        "amount": "500.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    assert response.data["message"] == (
        "Customer ledger created successfully."
    )

    data = response.data["data"]

    assert data["customer"] == customer.id
    assert data["transaction_date"] == "2026-09-22"
    assert data["reference_number"] == "REF-10025"
    assert data["description"] == (
        "Manual debit adjustment"
    )

    assert Decimal(data["debit"]) == Decimal("500.00")
    assert Decimal(data["credit"]) == Decimal("0.00")

    assert data["transaction_type"] == "adjustment"

    ledger = CustomerLedger.objects.get(
        id=data["id"]
    )

    assert ledger.company == user.company
    assert ledger.customer == customer
    assert ledger.debit == Decimal("500.00")
    assert ledger.credit == Decimal("0.00")
    assert ledger.created_by == user


# ============================================================
# CREATE - CREDIT
# ============================================================


def test_create_customer_ledger_credit(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "customer": customer.id,
        "transaction_date": "2026-09-22",
        "reference_number": "REF-10026",
        "description": "Payment received",
        "mode": "credit",
        "amount": "800.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    data = response.data["data"]

    assert Decimal(data["debit"]) == Decimal("0.00")
    assert Decimal(data["credit"]) == Decimal("800.00")

    ledger = CustomerLedger.objects.get(
        id=data["id"]
    )

    assert ledger.debit == Decimal("0.00")
    assert ledger.credit == Decimal("800.00")


# ============================================================
# BALANCE - FIRST DEBIT
# ============================================================


def test_first_debit_uses_opening_balance(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "customer": customer.id,
        "transaction_date": "2026-09-22",
        "reference_number": "REF-10027",
        "description": "Debit transaction",
        "mode": "debit",
        "amount": "500.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    data = response.data["data"]

    # Opening balance = 2000
    # Debit = 500
    # New balance = 2500

    assert Decimal(data["balance"]) == Decimal(
        "2500.00"
    )


# ============================================================
# BALANCE - FIRST CREDIT
# ============================================================


def test_first_credit_uses_opening_balance(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "customer": customer.id,
        "transaction_date": "2026-09-22",
        "reference_number": "REF-10028",
        "description": "Credit transaction",
        "mode": "credit",
        "amount": "500.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    data = response.data["data"]

    # Opening balance = 2000
    # Credit = 500
    # New balance = 1500

    assert Decimal(data["balance"]) == Decimal(
        "1500.00"
    )


# ============================================================
# BALANCE - MULTIPLE TRANSACTIONS
# ============================================================


def test_balance_calculation_multiple_transactions(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    # --------------------------------------------
    # Transaction 1
    # Opening = 2000
    # Debit 500
    # Balance = 2500
    # --------------------------------------------

    response = client.post(
        ledger_url,
        {
            "customer": customer.id,
            "transaction_date": "2026-09-22",
            "reference_number": "REF-001",
            "description": "Debit",
            "mode": "debit",
            "amount": "500.00",
        },
        format="json",
    )

    assert response.status_code == 201

    assert Decimal(
        response.data["data"]["balance"]
    ) == Decimal("2500.00")

    # --------------------------------------------
    # Transaction 2
    # Previous = 2500
    # Credit 800
    # Balance = 1700
    # --------------------------------------------

    response = client.post(
        ledger_url,
        {
            "customer": customer.id,
            "transaction_date": "2026-09-22",
            "reference_number": "REF-002",
            "description": "Credit",
            "mode": "credit",
            "amount": "800.00",
        },
        format="json",
    )

    assert response.status_code == 201

    assert Decimal(
        response.data["data"]["balance"]
    ) == Decimal("1700.00")

    # --------------------------------------------
    # Transaction 3
    # Previous = 1700
    # Debit 300
    # Balance = 2000
    # --------------------------------------------

    response = client.post(
        ledger_url,
        {
            "customer": customer.id,
            "transaction_date": "2026-09-22",
            "reference_number": "REF-003",
            "description": "Debit",
            "mode": "debit",
            "amount": "300.00",
        },
        format="json",
    )

    assert response.status_code == 201

    assert Decimal(
        response.data["data"]["balance"]
    ) == Decimal("2000.00")


# ============================================================
# INVALID MODE
# ============================================================


def test_create_ledger_invalid_mode(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "customer": customer.id,
        "transaction_date": "2026-09-22",
        "reference_number": "REF-10030",
        "description": "Invalid mode",
        "mode": "something",
        "amount": "500.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == (
        status.HTTP_400_BAD_REQUEST
    )

    assert "mode" in response.data


# ============================================================
# ZERO AMOUNT
# ============================================================


def test_create_ledger_zero_amount(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "customer": customer.id,
        "transaction_date": "2026-09-22",
        "reference_number": "REF-10031",
        "description": "Zero amount",
        "mode": "debit",
        "amount": "0.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == (
        status.HTTP_400_BAD_REQUEST
    )

    assert "amount" in response.data


# ============================================================
# NEGATIVE AMOUNT
# ============================================================


def test_create_ledger_negative_amount(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "customer": customer.id,
        "transaction_date": "2026-09-22",
        "reference_number": "REF-10032",
        "description": "Negative amount",
        "mode": "debit",
        "amount": "-100.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == (
        status.HTTP_400_BAD_REQUEST
    )

    assert "amount" in response.data


# ============================================================
# MISSING CUSTOMER
# ============================================================


def test_create_ledger_missing_customer(
    user,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "transaction_date": "2026-09-22",
        "reference_number": "REF-10033",
        "description": "Missing customer",
        "mode": "debit",
        "amount": "100.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == (
        status.HTTP_400_BAD_REQUEST
    )

    assert "customer" in response.data


# ============================================================
# MISSING DATE
# ============================================================


def test_create_ledger_missing_date(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "customer": customer.id,
        "reference_number": "REF-10034",
        "description": "Missing date",
        "mode": "debit",
        "amount": "100.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == (
        status.HTTP_400_BAD_REQUEST
    )

    assert "transaction_date" in response.data


# ============================================================
# MISSING REFERENCE IS ALLOWED
# ============================================================


def test_create_ledger_without_reference(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "customer": customer.id,
        "transaction_date": "2026-09-22",
        "description": "No reference",
        "mode": "debit",
        "amount": "100.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == (
        status.HTTP_201_CREATED
    )

    data = response.data["data"]

    assert data["reference_number"] == ""


# ============================================================
# MISSING DESCRIPTION IS ALLOWED
# ============================================================


def test_create_ledger_without_description(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "customer": customer.id,
        "transaction_date": "2026-09-22",
        "reference_number": "REF-10035",
        "mode": "debit",
        "amount": "100.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == (
        status.HTTP_201_CREATED
    )

    data = response.data["data"]

    assert data["description"] == ""


# ============================================================
# CUSTOMER FROM ANOTHER COMPANY
# ============================================================


def test_cannot_create_ledger_for_other_company_customer(
    user,
    other_customer,
    ledger_url,
):

    client = get_client(user)

    payload = {
        "customer": other_customer.id,
        "transaction_date": "2026-09-22",
        "reference_number": "REF-10036",
        "description": "Other company customer",
        "mode": "debit",
        "amount": "100.00",
    }

    response = client.post(
        ledger_url,
        payload,
        format="json",
    )

    assert response.status_code == (
        status.HTTP_400_BAD_REQUEST
    )

    assert "customer" in response.data

    assert not CustomerLedger.objects.filter(
        customer=other_customer
    ).exists()


# ============================================================
# COMPANY IS AUTOMATICALLY ASSIGNED
# ============================================================


def test_company_is_taken_from_logged_in_user(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    response = client.post(
        ledger_url,
        {
            "customer": customer.id,
            "transaction_date": "2026-09-22",
            "reference_number": "REF-10037",
            "description": "Company test",
            "mode": "debit",
            "amount": "100.00",
        },
        format="json",
    )

    assert response.status_code == 201

    ledger = CustomerLedger.objects.get(
        id=response.data["data"]["id"]
    )

    assert ledger.company == user.company


# ============================================================
# CREATED_BY IS AUTOMATICALLY ASSIGNED
# ============================================================


def test_created_by_is_logged_in_user(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    response = client.post(
        ledger_url,
        {
            "customer": customer.id,
            "transaction_date": "2026-09-22",
            "reference_number": "REF-10038",
            "description": "Created by test",
            "mode": "debit",
            "amount": "100.00",
        },
        format="json",
    )

    assert response.status_code == 201

    ledger = CustomerLedger.objects.get(
        id=response.data["data"]["id"]
    )

    assert ledger.created_by == user


# ============================================================
# TRANSACTION TYPE AUTOMATICALLY BECOMES ADJUSTMENT
# ============================================================


def test_transaction_type_is_adjustment(
    user,
    customer,
    ledger_url,
):

    client = get_client(user)

    response = client.post(
        ledger_url,
        {
            "customer": customer.id,
            "transaction_date": "2026-09-22",
            "reference_number": "REF-10039",
            "description": "Adjustment test",
            "mode": "debit",
            "amount": "100.00",
        },
        format="json",
    )

    assert response.status_code == 201

    ledger = CustomerLedger.objects.get(
        id=response.data["data"]["id"]
    )

    assert ledger.transaction_type == "adjustment"


# ============================================================
# GET LIST
# ============================================================


def test_get_customer_ledger_list(
    user,
    ledger_entry,
    ledger_url,
):

    client = get_client(user)

    response = client.get(
        ledger_url
    )

    assert response.status_code == (
        status.HTTP_200_OK
    )

    assert "total_items" in response.data
    assert "total_pages" in response.data
    assert "current_page" in response.data

    assert response.data["total_items"] >= 1

    assert len(response.data["results"]) >= 1

    assert response.data["results"][0]["id"] == (
        ledger_entry.id
    )

# ============================================================
# GET CUSTOMER LEDGER
# ============================================================

def test_get_customer_ledger(
    user,
    customer,
    ledger_entry,
):

    client = get_client(user)

    url = reverse(
        "ledger-customer-ledger",
        kwargs={
            "customer_id": customer.id
        },
    )

    response = client.get(url)

    assert response.status_code == (
        status.HTTP_200_OK
    )

    assert "total_items" in response.data
    assert "total_pages" in response.data
    assert "current_page" in response.data

    assert response.data["total_items"] >= 1

    assert len(response.data["results"]) >= 1

    assert response.data["results"][0]["id"] == (
        ledger_entry.id
    )

    assert response.data["results"][0]["customer"] == (
        customer.id
    )
# ============================================================
# GET SUMMARY
# ============================================================


def test_customer_ledger_summary(
    user,
    customer,
    ledger_entry,
):

    client = get_client(user)

    url = reverse(
        "ledger-summary"
    )

    response = client.get(
        url,
        {
            "customer_id": customer.id
        },
    )

    assert response.status_code == (
        status.HTTP_200_OK
    )

    data = response.data["data"]

    assert data["customer_id"] == customer.id

    assert Decimal(
        data["opening_balance"]
    ) == Decimal("2000.00")

    assert Decimal(
        data["total_debit"]
    ) == Decimal("500.00")

    assert Decimal(
        data["total_credit"]
    ) == Decimal("0.00")

    assert Decimal(
        data["closing_balance"]
    ) == Decimal("2500.00")


# ============================================================
# SUMMARY WITHOUT CUSTOMER ID
# ============================================================


def test_summary_requires_customer_id(
    user,
):

    client = get_client(user)

    url = reverse(
        "ledger-summary"
    )

    response = client.get(url)

    assert response.status_code == (
        status.HTTP_400_BAD_REQUEST
    )

    assert response.data["message"] == (
        "customer_id is required."
    )


# ============================================================
# CUSTOMER NOT FOUND
# ============================================================


def test_summary_customer_not_found(
    user,
):

    client = get_client(user)

    url = reverse(
        "ledger-summary"
    )

    response = client.get(
        url,
        {
            "customer_id": 999999
        },
    )

    assert response.status_code == (
        status.HTTP_404_NOT_FOUND
    )

    assert response.data["message"] == (
        "Customer not found."
    )


# ============================================================
# UNAUTHENTICATED USER
# ============================================================


def test_create_ledger_requires_authentication(
    api_client,
    customer,
    ledger_url,
):

    response = api_client.post(
        ledger_url,
        {
            "customer": customer.id,
            "transaction_date": "2026-09-22",
            "reference_number": "REF-10040",
            "description": "Unauthenticated",
            "mode": "debit",
            "amount": "100.00",
        },
        format="json",
    )

    assert response.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ]

# ============================================================
# DASHBOARD SUMMARY
# ============================================================


@pytest.fixture
def dashboard_summary_url():
    return reverse("ledger-dashboard-summary")


def test_customer_financial_dashboard_summary(
    user,
    dashboard_summary_url,
):
    client = get_client(user)

    response = client.get(
        dashboard_summary_url
    )

    assert response.status_code == (
        status.HTTP_200_OK
    )

    assert response.data["message"] == (
        "Customer financial summary retrieved successfully."
    )

    data = response.data["data"]

    assert "total_receivable" in data
    assert "total_invoice" in data
    assert "total_collection" in data
    assert "total_credit" in data
    assert "overdue_amount" in data


def test_customer_financial_dashboard_summary_by_customer(
    user,
    customer,
    dashboard_summary_url,
):
    client = get_client(user)

    response = client.get(
        dashboard_summary_url,
        {
            "customer_id": customer.id
        },
    )

    assert response.status_code == (
        status.HTTP_200_OK
    )

    data = response.data["data"]

    assert "total_receivable" in data
    assert "total_invoice" in data
    assert "total_collection" in data
    assert "total_credit" in data
    assert "overdue_amount" in data
