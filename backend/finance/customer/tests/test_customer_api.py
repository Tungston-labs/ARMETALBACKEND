import io
from datetime import timedelta
from decimal import Decimal

import pytest

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from finance.customer.models import Customer, CustomerDocument


# ============================================================
# HELPERS
# ============================================================

def get_user_model():
    from django.contrib.auth import get_user_model
    return get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def company(db):
    """
    Creates a company for testing.

    If your Company model has additional mandatory fields,
    add them here.
    """
    from superadmin.models import Company

    return Company.objects.create(
        name="Test Company"
    )


@pytest.fixture
def another_company(db):
    from superadmin.models import Company

    return Company.objects.create(
        name="Another Company",
        email="anothercompany@test.com"
    )


@pytest.fixture
def user(company):
    """
    HR Admin user.

    Adjust the fields below if your User model uses
    different role/status field names.
    """
    User = get_user_model()

    user = User.objects.create_user(
        username="customer_admin",
        email="customeradmin@test.com",
        password="Test@12345",
    )

    user.company = company

    # Adjust according to your existing user model.
    if hasattr(user, "role"):
        user.role = "hr_admin"

    if hasattr(user, "is_hr_admin"):
        user.is_hr_admin = True

    user.save()

    return user


@pytest.fixture
def another_user(another_company):
    User = get_user_model()

    user = User.objects.create_user(
        username="another_admin",
        email="anotheradmin@test.com",
        password="Test@12345",
    )

    user.company = another_company

    if hasattr(user, "role"):
        user.role = "hr_admin"

    if hasattr(user, "is_hr_admin"):
        user.is_hr_admin = True

    user.save()

    return user


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def customer(company, user):
    return Customer.objects.create(
        company=company,
        customer_name="ABC Trading LLC",
        company_name="ABC Trading Company",
        industry="manufacturing",
        website="https://www.abctrading.com",
        cr_number="CR123456",
        currency="AED",
        vat_number="VAT123456789",
        payment_term="30_days",
        cr_expiry_date="2027-12-31",
        billing_address="123 Business Street",
        city="Dubai",
        state="Dubai",
        country="UAE",
        postal="00000",
        phno="+971501234567",
        admin_email="admin@abctrading.com",
        financial_email="finance@abctrading.com",
        technical_email="technical@abctrading.com",
        client_status="active",
        credit_limit=Decimal("50000.00"),
        opening_balance=Decimal("10000.00"),
        notes="Test customer",
        created_by=user,
    )


@pytest.fixture
def inactive_customer(company, user):
    return Customer.objects.create(
        company=company,
        customer_name="Inactive Customer",
        company_name="Inactive Company",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="inactive",
        credit_limit=Decimal("10000.00"),
        opening_balance=Decimal("0.00"),
        created_by=user,
    )


def customer_url(customer):
    return f"/api/finance/customer/{customer.id}/"


def customer_list_url():
    return "/api/finance/customer/"


def customer_summary_url():
    return "/api/finance/customer/summary/"


# ============================================================
# 1. CREATE CUSTOMER
# ============================================================

@pytest.mark.django_db
def test_create_customer(authenticated_client, company):

    payload = {
        "customer_name": "New Customer",
        "company_name": "New Customer Company",
        "industry": "technology",
        "website": "https://www.newcustomer.com",
        "cr_number": "CR999999",
        "currency": "AED",
        "vat_number": "VAT999999",
        "payment_term": "30_days",
        "cr_expiry_date": "2028-12-31",
        "billing_address": "Business Street",
        "city": "Dubai",
        "state": "Dubai",
        "country": "UAE",
        "postal": "00000",
        "phno": "+971501234567",
        "admin_email": "admin@newcustomer.com",
        "financial_email": "finance@newcustomer.com",
        "technical_email": "technical@newcustomer.com",
        "client_status": "active",
        "credit_limit": "50000.00",
        "opening_balance": "1000.00",
        "notes": "New customer",
    }

    response = authenticated_client.post(
        customer_list_url(),
        payload,
        format="json",
    )

    assert response.status_code == 201

    assert response.data["message"] == (
        "Customer created successfully."
    )

    data = response.data["data"]

    assert data["customer_name"] == "New Customer"
    assert data["customer_id"] == "CUS001"
    assert data["company"] == company.id

    assert Customer.objects.filter(
        customer_name="New Customer"
    ).exists()


# ============================================================
# 2. CUSTOMER ID AUTO GENERATION
# ============================================================

@pytest.mark.django_db
def test_customer_id_auto_generated(
    authenticated_client,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "First Customer",
            "industry": "retail",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 201

    assert response.data["data"]["customer_id"] == "CUS001"


@pytest.mark.django_db
def test_customer_id_increments(
    authenticated_client,
):

    first_response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Customer One",
            "industry": "retail",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert first_response.status_code == 201
    assert first_response.data["data"]["customer_id"] == "CUS001"

    second_response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Customer Two",
            "industry": "retail",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert second_response.status_code == 201
    assert second_response.data["data"]["customer_id"] == "CUS002"


# ============================================================
# 3. LIST CUSTOMERS
# ============================================================

@pytest.mark.django_db
def test_list_customers(
    authenticated_client,
    customer,
    inactive_customer,
):

    response = authenticated_client.get(
        customer_list_url()
    )

    assert response.status_code == 200

    assert "results" in response.data

    results = response.data["results"]

    assert len(results) == 2


# ============================================================
# 4. RETRIEVE CUSTOMER
# ============================================================

@pytest.mark.django_db
def test_retrieve_customer(
    authenticated_client,
    customer,
):

    response = authenticated_client.get(
        customer_url(customer)
    )

    assert response.status_code == 200

    assert response.data["message"] == (
        "Customer retrieved successfully."
    )

    data = response.data["data"]

    assert data["id"] == customer.id
    assert data["customer_id"] == customer.customer_id
    assert data["customer_name"] == "ABC Trading LLC"


# ============================================================
# 5. UPDATE CUSTOMER
# ============================================================

@pytest.mark.django_db
def test_update_customer(
    authenticated_client,
    customer,
):

    payload = {
        "customer_name": "ABC Trading Updated",
        "company_name": "Updated Company",
        "industry": "technology",
        "website": "https://www.updated.com",
        "cr_number": "CR123456",
        "currency": "USD",
        "vat_number": "VAT123456789",
        "payment_term": "60_days",
        "cr_expiry_date": "2029-12-31",
        "billing_address": "Updated Address",
        "city": "Abu Dhabi",
        "state": "Abu Dhabi",
        "country": "UAE",
        "postal": "11111",
        "phno": "+971501111111",
        "admin_email": "updated@customer.com",
        "financial_email": "finance@customer.com",
        "technical_email": "tech@customer.com",
        "client_status": "active",
        "credit_limit": "75000.00",
        "opening_balance": "15000.00",
        "notes": "Updated information",
    }

    response = authenticated_client.put(
        customer_url(customer),
        payload,
        format="json",
    )

    assert response.status_code == 200

    assert response.data["message"] == (
        "Customer updated successfully."
    )

    customer.refresh_from_db()

    assert customer.customer_name == (
        "ABC Trading Updated"
    )

    assert customer.currency == "USD"

    assert customer.payment_term == "60_days"

    assert customer.credit_limit == Decimal(
        "75000.00"
    )


# ============================================================
# 6. PATCH CUSTOMER
# ============================================================

@pytest.mark.django_db
def test_patch_customer(
    authenticated_client,
    customer,
):

    response = authenticated_client.patch(
        customer_url(customer),
        {
            "customer_name": "Patched Customer",
            "credit_limit": "90000.00",
        },
        format="json",
    )

    assert response.status_code == 200

    customer.refresh_from_db()

    assert customer.customer_name == (
        "Patched Customer"
    )

    assert customer.credit_limit == Decimal(
        "90000.00"
    )


# ============================================================
# 7. DELETE CUSTOMER
# ============================================================

@pytest.mark.django_db
def test_delete_customer(
    authenticated_client,
    customer,
):

    customer_id = customer.id

    response = authenticated_client.delete(
        customer_url(customer)
    )

    assert response.status_code == 200

    assert response.data["message"] == (
        f"Customer '{customer.customer_name}' "
        "deleted successfully."
    )

    assert not Customer.objects.filter(
        id=customer_id
    ).exists()


# ============================================================
# 8. SEARCH CUSTOMER
# ============================================================

@pytest.mark.django_db
def test_search_customer_by_name(
    authenticated_client,
    customer,
    inactive_customer,
):

    response = authenticated_client.get(
        customer_list_url(),
        {
            "search": "ABC"
        },
    )

    assert response.status_code == 200

    results = response.data["results"]

    assert len(results) == 1

    assert results[0]["customer_name"] == (
        "ABC Trading LLC"
    )


@pytest.mark.django_db
def test_search_customer_by_customer_id(
    authenticated_client,
    customer,
):

    response = authenticated_client.get(
        customer_list_url(),
        {
            "search": customer.customer_id
        },
    )

    assert response.status_code == 200

    results = response.data["results"]

    assert len(results) == 1

    assert results[0]["customer_id"] == (
        customer.customer_id
    )


@pytest.mark.django_db
def test_search_customer_by_company_name(
    authenticated_client,
    customer,
):

    response = authenticated_client.get(
        customer_list_url(),
        {
            "search": "ABC Trading Company"
        },
    )

    assert response.status_code == 200

    results = response.data["results"]

    assert len(results) == 1


# ============================================================
# 9. FILTER ACTIVE
# ============================================================

@pytest.mark.django_db
def test_filter_active_customers(
    authenticated_client,
    customer,
    inactive_customer,
):

    response = authenticated_client.get(
        customer_list_url(),
        {
            "client_status": "active"
        },
    )

    assert response.status_code == 200

    results = response.data["results"]

    assert len(results) == 1

    assert results[0]["client_status"] == "active"


# ============================================================
# 10. FILTER INACTIVE
# ============================================================

@pytest.mark.django_db
def test_filter_inactive_customers(
    authenticated_client,
    customer,
    inactive_customer,
):

    response = authenticated_client.get(
        customer_list_url(),
        {
            "client_status": "inactive"
        },
    )

    assert response.status_code == 200

    results = response.data["results"]

    assert len(results) == 1

    assert results[0]["client_status"] == "inactive"


# ============================================================
# 11. ORDERING - LATEST
# ============================================================

@pytest.mark.django_db
def test_ordering_latest_first(
    authenticated_client,
    company,
    user,
):

    old_customer = Customer.objects.create(
        company=company,
        customer_name="Old Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=user,
    )

    new_customer = Customer.objects.create(
        company=company,
        customer_name="New Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=user,
    )

    response = authenticated_client.get(
        customer_list_url(),
        {
            "ordering": "-created_at"
        },
    )

    assert response.status_code == 200

    results = response.data["results"]

    assert results[0]["id"] == new_customer.id


# ============================================================
# 12. ORDERING - OLDEST
# ============================================================

@pytest.mark.django_db
def test_ordering_oldest_first(
    authenticated_client,
    company,
    user,
):

    old_customer = Customer.objects.create(
        company=company,
        customer_name="Old Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=user,
    )

    new_customer = Customer.objects.create(
        company=company,
        customer_name="New Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=user,
    )

    response = authenticated_client.get(
        customer_list_url(),
        {
            "ordering": "created_at"
        },
    )

    assert response.status_code == 200

    results = response.data["results"]

    assert results[0]["id"] == old_customer.id


# ============================================================
# 13. ORDERING - CUSTOMER NAME ASC
# ============================================================

@pytest.mark.django_db
def test_ordering_customer_name_ascending(
    authenticated_client,
    company,
    user,
):

    Customer.objects.create(
        company=company,
        customer_name="Zebra Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=user,
    )

    Customer.objects.create(
        company=company,
        customer_name="Alpha Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=user,
    )

    response = authenticated_client.get(
        customer_list_url(),
        {
            "ordering": "customer_name"
        },
    )

    assert response.status_code == 200

    results = response.data["results"]

    assert results[0]["customer_name"] == (
        "Alpha Customer"
    )


# ============================================================
# 14. ORDERING - CUSTOMER NAME DESC
# ============================================================

@pytest.mark.django_db
def test_ordering_customer_name_descending(
    authenticated_client,
    company,
    user,
):

    Customer.objects.create(
        company=company,
        customer_name="Alpha Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=user,
    )

    Customer.objects.create(
        company=company,
        customer_name="Zebra Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=user,
    )

    response = authenticated_client.get(
        customer_list_url(),
        {
            "ordering": "-customer_name"
        },
    )

    assert response.status_code == 200

    results = response.data["results"]

    assert results[0]["customer_name"] == (
        "Zebra Customer"
    )


# ============================================================
# 15. CUSTOMER SUMMARY
# ============================================================

@pytest.mark.django_db
def test_customer_summary(
    authenticated_client,
    customer,
    inactive_customer,
):

    response = authenticated_client.get(
        customer_summary_url()
    )

    assert response.status_code == 200

    assert response.data["message"] == (
        "Customer summary retrieved successfully."
    )

    data = response.data["data"]

    assert data["total_customers"] == 2

    assert data["active_customers"] == 1

    assert data["inactive_customers"] == 1

    assert "new_customers_this_month" in data

    assert "payment_received" in data

    assert data["payment_received"] == 0


# ============================================================
# 16. NEW CUSTOMERS THIS MONTH
# ============================================================

@pytest.mark.django_db
def test_new_customers_this_month(
    authenticated_client,
    company,
    user,
):

    Customer.objects.create(
        company=company,
        customer_name="This Month Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=user,
    )

    response = authenticated_client.get(
        customer_summary_url()
    )

    assert response.status_code == 200

    data = response.data["data"]

    assert data["new_customers_this_month"] == 1


# ============================================================
# 17. MULTIPLE DOCUMENTS
# ============================================================

@pytest.mark.django_db
def test_create_customer_with_multiple_documents(
    authenticated_client,
):

    file1 = SimpleUploadedFile(
        "license.pdf",
        b"fake license content",
        content_type="application/pdf",
    )

    file2 = SimpleUploadedFile(
        "certificate.pdf",
        b"fake certificate content",
        content_type="application/pdf",
    )

    payload = {
        "customer_name": "Document Customer",
        "industry": "technology",
        "currency": "AED",
        "payment_term": "30_days",
        "client_status": "active",
        "credit_limit": "50000",
        "opening_balance": "0",
    }

    response = authenticated_client.post(
        customer_list_url(),
        {
            **payload,
            "documents": [file1, file2],
        },
        format="multipart",
    )

    assert response.status_code == 201

    customer = Customer.objects.get(
        customer_name="Document Customer"
    )

    assert CustomerDocument.objects.filter(
        customer=customer
    ).count() == 2


# ============================================================
# 18. CREATE WITHOUT REQUIRED CUSTOMER NAME
# ============================================================

@pytest.mark.django_db
def test_create_customer_without_name(
    authenticated_client,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "industry": "retail",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 400

    assert "errors" in response.data


# ============================================================
# 19. EMPTY CUSTOMER NAME
# ============================================================

@pytest.mark.django_db
def test_create_customer_with_empty_name(
    authenticated_client,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "   ",
            "industry": "retail",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 400

    assert "customer_name" in response.data["errors"]


# ============================================================
# 20. NEGATIVE CREDIT LIMIT
# ============================================================

@pytest.mark.django_db
def test_negative_credit_limit(
    authenticated_client,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Negative Credit Customer",
            "industry": "retail",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "-1000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 400

    assert "credit_limit" in response.data["errors"]


# ============================================================
# 21. NEGATIVE OPENING BALANCE
# ============================================================

@pytest.mark.django_db
def test_negative_opening_balance(
    authenticated_client,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Negative Balance Customer",
            "industry": "retail",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "-500",
        },
        format="json",
    )

    assert response.status_code == 400

    assert "opening_balance" in response.data["errors"]


# ============================================================
# 22. INVALID EMAIL
# ============================================================

@pytest.mark.django_db
def test_invalid_email(
    authenticated_client,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Invalid Email Customer",
            "industry": "retail",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "admin_email": "invalid-email",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 400

    assert "admin_email" in response.data["errors"]


# ============================================================
# 23. INVALID WEBSITE
# ============================================================

@pytest.mark.django_db
def test_invalid_website(
    authenticated_client,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Invalid Website Customer",
            "industry": "retail",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "website": "not-a-url",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 400

    assert "website" in response.data["errors"]


# ============================================================
# 24. INVALID INDUSTRY
# ============================================================

@pytest.mark.django_db
def test_invalid_industry(
    authenticated_client,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Invalid Industry Customer",
            "industry": "invalid_industry",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 400

    assert "industry" in response.data["errors"]


# ============================================================
# 25. INVALID CURRENCY
# ============================================================

@pytest.mark.django_db
def test_invalid_currency(
    authenticated_client,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Invalid Currency Customer",
            "industry": "retail",
            "currency": "INVALID",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 400

    assert "currency" in response.data["errors"]


# ============================================================
# 26. INVALID PAYMENT TERM
# ============================================================

@pytest.mark.django_db
def test_invalid_payment_term(
    authenticated_client,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Invalid Payment Term Customer",
            "industry": "retail",
            "currency": "AED",
            "payment_term": "999_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 400

    assert "payment_term" in response.data["errors"]


# ============================================================
# 27. INVALID CLIENT STATUS
# ============================================================

@pytest.mark.django_db
def test_invalid_client_status(
    authenticated_client,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Invalid Status Customer",
            "industry": "retail",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "unknown",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 400

    assert "client_status" in response.data["errors"]


# ============================================================
# 28. UNAUTHENTICATED USER
# ============================================================

@pytest.mark.django_db
def test_unauthenticated_user_cannot_list_customers(
    api_client,
):

    response = api_client.get(
        customer_list_url()
    )

    assert response.status_code in [
        401,
        403,
    ]


@pytest.mark.django_db
def test_unauthenticated_user_cannot_create_customer(
    api_client,
):

    response = api_client.post(
        customer_list_url(),
        {
            "customer_name": "Unauthorized Customer",
            "industry": "retail",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code in [
        401,
        403,
    ]


# ============================================================
# 29. COMPANY ISOLATION - LIST
# ============================================================

@pytest.mark.django_db
def test_customer_company_isolation(
    authenticated_client,
    company,
    another_company,
    user,
    another_user,
):

    own_customer = Customer.objects.create(
        company=company,
        customer_name="Own Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=user,
    )

    other_customer = Customer.objects.create(
        company=another_company,
        customer_name="Other Company Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=another_user,
    )

    response = authenticated_client.get(
        customer_list_url()
    )

    assert response.status_code == 200

    results = response.data["results"]

    ids = [
        item["id"]
        for item in results
    ]

    assert own_customer.id in ids

    assert other_customer.id not in ids


# ============================================================
# 30. COMPANY ISOLATION - RETRIEVE
# ============================================================

@pytest.mark.django_db
def test_cannot_retrieve_other_company_customer(
    authenticated_client,
    another_company,
    another_user,
):

    other_customer = Customer.objects.create(
        company=another_company,
        customer_name="Other Company Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=another_user,
    )

    response = authenticated_client.get(
        customer_url(other_customer)
    )

    assert response.status_code == 404


# ============================================================
# 31. COMPANY ISOLATION - UPDATE
# ============================================================

@pytest.mark.django_db
def test_cannot_update_other_company_customer(
    authenticated_client,
    another_company,
    another_user,
):

    other_customer = Customer.objects.create(
        company=another_company,
        customer_name="Other Company Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=another_user,
    )

    response = authenticated_client.patch(
        customer_url(other_customer),
        {
            "customer_name": "Hacked Customer"
        },
        format="json",
    )

    assert response.status_code == 404

    other_customer.refresh_from_db()

    assert other_customer.customer_name == (
        "Other Company Customer"
    )


# ============================================================
# 32. COMPANY ISOLATION - DELETE
# ============================================================

@pytest.mark.django_db
def test_cannot_delete_other_company_customer(
    authenticated_client,
    another_company,
    another_user,
):

    other_customer = Customer.objects.create(
        company=another_company,
        customer_name="Other Company Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=another_user,
    )

    response = authenticated_client.delete(
        customer_url(other_customer)
    )

    assert response.status_code == 404

    assert Customer.objects.filter(
        id=other_customer.id
    ).exists()


# ============================================================
# 33. CUSTOMER RESPONSE DISPLAY FIELDS
# ============================================================

@pytest.mark.django_db
def test_customer_response_contains_display_fields(
    authenticated_client,
    customer,
):

    response = authenticated_client.get(
        customer_url(customer)
    )

    assert response.status_code == 200

    data = response.data["data"]

    assert data["industry_name"] == "Manufacturing"

    assert data["currency_name"] == "AED"

    assert data["payment_term_name"] == "30 Days"

    assert data["client_status_name"] == "Active"


# ============================================================
# 34. CREATED BY
# ============================================================

@pytest.mark.django_db
def test_customer_created_by_user(
    authenticated_client,
    user,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Created By Test",
            "industry": "technology",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 201

    customer = Customer.objects.get(
        customer_name="Created By Test"
    )

    assert customer.created_by == user


# ============================================================
# 35. COMPANY AUTOMATICALLY ASSIGNED
# ============================================================

@pytest.mark.django_db
def test_company_automatically_assigned(
    authenticated_client,
    user,
):

    response = authenticated_client.post(
        customer_list_url(),
        {
            "customer_name": "Company Assignment Test",
            "industry": "technology",
            "currency": "AED",
            "payment_term": "30_days",
            "client_status": "active",
            "credit_limit": "10000",
            "opening_balance": "0",
        },
        format="json",
    )

    assert response.status_code == 201

    customer = Customer.objects.get(
        customer_name="Company Assignment Test"
    )

    assert customer.company == user.company


# ============================================================
# 36. CUSTOMER ID CANNOT BE CHANGED
# ============================================================

@pytest.mark.django_db
def test_customer_id_is_read_only(
    authenticated_client,
    customer,
):

    original_customer_id = customer.customer_id

    response = authenticated_client.patch(
        customer_url(customer),
        {
            "customer_id": "CUS999"
        },
        format="json",
    )

    assert response.status_code == 200

    customer.refresh_from_db()

    assert customer.customer_id == original_customer_id


# ============================================================
# 37. COMPANY CANNOT BE CHANGED
# ============================================================

@pytest.mark.django_db
def test_company_is_read_only(
    authenticated_client,
    customer,
    another_company,
):

    original_company = customer.company

    response = authenticated_client.patch(
        customer_url(customer),
        {
            "company": another_company.id
        },
        format="json",
    )

    assert response.status_code == 200

    customer.refresh_from_db()

    assert customer.company == original_company


# ============================================================
# 38. DOCUMENTS RETURNED IN DETAIL
# ============================================================

@pytest.mark.django_db
def test_customer_documents_returned(
    authenticated_client,
    customer,
):

    document = SimpleUploadedFile(
        "license.pdf",
        b"license content",
        content_type="application/pdf",
    )

    CustomerDocument.objects.create(
        customer=customer,
        document=document,
        document_name="Trade License",
    )

    response = authenticated_client.get(
        customer_url(customer)
    )

    assert response.status_code == 200

    data = response.data["data"]

    assert "documents" in data

    assert len(data["documents"]) == 1

    assert data["documents"][0]["document_name"] == (
        "Trade License"
    )


# ============================================================
# 39. UPDATE WITH ADDITIONAL DOCUMENT
# ============================================================

@pytest.mark.django_db
def test_update_customer_with_document(
    authenticated_client,
    customer,
):

    document = SimpleUploadedFile(
        "updated_license.pdf",
        b"updated license content",
        content_type="application/pdf",
    )

    response = authenticated_client.patch(
        customer_url(customer),
        {
            "customer_name": "Updated With Document",
            "documents": document,
        },
        format="multipart",
    )

    assert response.status_code == 200

    assert CustomerDocument.objects.filter(
        customer=customer
    ).count() == 1


# ============================================================
# 40. SUMMARY COMPANY ISOLATION
# ============================================================

@pytest.mark.django_db
def test_summary_company_isolation(
    authenticated_client,
    company,
    another_company,
    user,
    another_user,
):

    Customer.objects.create(
        company=company,
        customer_name="Own Active Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=user,
    )

    Customer.objects.create(
        company=another_company,
        customer_name="Other Active Customer",
        industry="retail",
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=another_user,
    )

    response = authenticated_client.get(
        customer_summary_url()
    )

    assert response.status_code == 200

    data = response.data["data"]

    assert data["total_customers"] == 1

    assert data["active_customers"] == 1

    assert data["inactive_customers"] == 0