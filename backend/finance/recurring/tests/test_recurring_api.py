from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from finance.category.models import Category
from finance.customer.models import Customer
from finance.product.models import Product

from finance.recurring.models import (
    RecurringBilling,
    RecurringBillingOccurrence,
    RecurringPricingPlan,
    RecurringService,
)

from finance.recurring.utils import calculate_next_invoice_date


# ==========================================================
# AUTHENTICATED CLIENTS
# ==========================================================

@pytest.fixture
def authenticated_client(company_admin):
    client = APIClient()
    client.force_authenticate(user=company_admin)
    return client


@pytest.fixture
def second_authenticated_client(second_company_user):
    client = APIClient()
    client.force_authenticate(user=second_company_user)
    return client


# ==========================================================
# URLS
# ==========================================================

SERVICE_URL = "/api/finance/recurring/services/"
BILLING_URL = "/api/finance/recurring/billing/"
CREATE_URL = "/api/finance/recurring/create/"
SUMMARY_URL = "/api/finance/recurring/summary/"
DASHBOARD_URL = "/api/finance/recurring/billing/dashboard/"


# ==========================================================
# HELPERS
# ==========================================================

def get_list_results(response):
    assert response.status_code == 200

    if isinstance(response.data, list):
        return response.data

    return response.data.get("results", [])


def get_model_field_names(model):
    return {
        field.name
        for field in model._meta.get_fields()
        if hasattr(field, "attname")
    }


def get_first_existing_field(model, candidates):
    field_names = get_model_field_names(model)

    for field in candidates:
        if field in field_names:
            return field

    return None


# ==========================================================
# BASIC FIXTURES
# ==========================================================

@pytest.fixture
def company(db):
    """
    Creates a company only if the project does not already expose
    a company fixture.
    """
    from superadmin.models import Company

    field_names = get_model_field_names(Company)

    data = {}

    if "name" in field_names:
        data["name"] = "Recurring Test Company"

    if "company_id" in field_names:
        data["company_id"] = "RTC001"

    if "email" in field_names:
        data["email"] = "recurring@test.com"

    if "address" in field_names:
        data["address"] = "Test Address"

    if "location" in field_names:
        data["location"] = "Test Location"

    if "contact_number" in field_names:
        data["contact_number"] = "9999999999"

    return Company.objects.create(**data)


@pytest.fixture
def second_company(db):
    from superadmin.models import Company

    field_names = get_model_field_names(Company)

    data = {}

    if "name" in field_names:
        data["name"] = "Second Recurring Company"

    if "company_id" in field_names:
        data["company_id"] = "RTC002"

    if "email" in field_names:
        data["email"] = "recurring2@test.com"

    if "address" in field_names:
        data["address"] = "Second Address"

    if "location" in field_names:
        data["location"] = "Second Location"

    if "contact_number" in field_names:
        data["contact_number"] = "8888888888"

    return Company.objects.create(**data)


@pytest.fixture
def company_admin(company, db):
    from user.models import User

    return User.objects.create_user(
        username="recurring_admin",
        email="recurring_admin@test.com",
        password="TestPassword123!",
        company=company,
        is_hr_admin=True,
    )


@pytest.fixture
def second_company_user(second_company, db):
    from user.models import User

    return User.objects.create_user(
        username="recurring_user_2",
        email="recurring_user_2@test.com",
        password="TestPassword123!",
        company=second_company,
        is_hr_admin=True,
    )


# ==========================================================
# CATEGORY
# ==========================================================

@pytest.fixture
def category(company):
    """
    Creates a Category without assuming that the model uses
    a `name` field.

    The actual Category model field is detected dynamically.
    """

    field_names = get_model_field_names(Category)

    data = {
        "company": company,
    }

    # Common possibilities
    if "category_name" in field_names:
        data["category_name"] = "Recurring Services"

    elif "title" in field_names:
        data["title"] = "Recurring Services"

    elif "category" in field_names:
        data["category"] = "Recurring Services"

    elif "label" in field_names:
        data["label"] = "Recurring Services"

    elif "description" in field_names:
        data["description"] = "Recurring Services"

    # If the model has a required CharField that we haven't handled,
    # automatically populate it.
    if len(data) == 1:
        for field in Category._meta.fields:
            if field.name in data:
                continue

            if field.name in {
                "id",
                "created_at",
                "updated_at",
                "company",
            }:
                continue

            if getattr(field, "auto_created", False):
                continue

            if field.null or field.blank or field.has_default():
                continue

            internal_type = field.get_internal_type()

            if internal_type == "CharField":
                data[field.name] = "Recurring Services"
                break

    return Category.objects.create(**data)


@pytest.fixture
def second_category(second_company):
    field_names = get_model_field_names(Category)

    data = {
        "company": second_company,
    }

    if "category_name" in field_names:
        data["category_name"] = "Second Category"

    elif "title" in field_names:
        data["title"] = "Second Category"

    elif "category" in field_names:
        data["category"] = "Second Category"

    elif "label" in field_names:
        data["label"] = "Second Category"

    elif "description" in field_names:
        data["description"] = "Second Category"

    if len(data) == 1:
        for field in Category._meta.fields:
            if field.name in data:
                continue

            if field.name in {
                "id",
                "created_at",
                "updated_at",
                "company",
            }:
                continue

            if getattr(field, "auto_created", False):
                continue

            if field.null or field.blank or field.has_default():
                continue

            if field.get_internal_type() == "CharField":
                data[field.name] = "Second Category"
                break

    return Category.objects.create(**data)


# ==========================================================
# PRODUCT
# ==========================================================

@pytest.fixture
def product(company):
    field_names = get_model_field_names(Product)

    data = {
        "company": company,
    }

    if "product_name" in field_names:
        data["product_name"] = "Recurring Internet Service"

    elif "name" in field_names:
        data["name"] = "Recurring Internet Service"

    if "code" in field_names:
        data["code"] = "REC-PROD-001"

    elif "product_code" in field_names:
        data["product_code"] = "REC-PROD-001"

    if "description" in field_names:
        data["description"] = "Recurring service product"

    if "price" in field_names:
        data["price"] = Decimal("1000.00")

    if "selling_price" in field_names:
        data["selling_price"] = Decimal("1000.00")

    if "unit_price" in field_names:
        data["unit_price"] = Decimal("1000.00")

    if "status" in field_names:
        data["status"] = "active"

    return Product.objects.create(**data)


@pytest.fixture
def second_product(second_company):
    field_names = get_model_field_names(Product)

    data = {
        "company": second_company,
    }

    if "product_name" in field_names:
        data["product_name"] = "Second Company Product"

    elif "name" in field_names:
        data["name"] = "Second Company Product"

    if "code" in field_names:
        data["code"] = "REC-PROD-002"

    elif "product_code" in field_names:
        data["product_code"] = "REC-PROD-002"

    if "description" in field_names:
        data["description"] = "Second company product"

    if "price" in field_names:
        data["price"] = Decimal("2000.00")

    if "selling_price" in field_names:
        data["selling_price"] = Decimal("2000.00")

    if "unit_price" in field_names:
        data["unit_price"] = Decimal("2000.00")

    if "status" in field_names:
        data["status"] = "active"

    return Product.objects.create(**data)


# ==========================================================
# CUSTOMER
# ==========================================================

@pytest.fixture
def customer(company):
    field_names = get_model_field_names(Customer)

    data = {
        "company": company,
    }

    if "customer_name" in field_names:
        data["customer_name"] = "Recurring Test Customer"

    elif "name" in field_names:
        data["name"] = "Recurring Test Customer"

    if "customer_id" in field_names:
        data["customer_id"] = "CUS-REC-001"

    if "admin_email" in field_names:
        data["admin_email"] = "customer@test.com"

    elif "email" in field_names:
        data["email"] = "customer@test.com"

    if "phno" in field_names:
        data["phno"] = "9999999999"

    elif "phone" in field_names:
        data["phone"] = "9999999999"

    elif "contact_number" in field_names:
        data["contact_number"] = "9999999999"

    return Customer.objects.create(**data)


@pytest.fixture
def second_customer(second_company):
    field_names = get_model_field_names(Customer)

    data = {
        "company": second_company,
    }

    if "customer_name" in field_names:
        data["customer_name"] = "Second Company Customer"

    elif "name" in field_names:
        data["name"] = "Second Company Customer"

    if "customer_id" in field_names:
        data["customer_id"] = "CUS-REC-002"

    if "admin_email" in field_names:
        data["admin_email"] = "customer2@test.com"

    elif "email" in field_names:
        data["email"] = "customer2@test.com"

    if "phno" in field_names:
        data["phno"] = "8888888888"

    elif "phone" in field_names:
        data["phone"] = "8888888888"

    elif "contact_number" in field_names:
        data["contact_number"] = "8888888888"

    return Customer.objects.create(**data)


# ==========================================================
# RECURRING SERVICE
# ==========================================================

@pytest.fixture
def recurring_service(
    company,
    company_admin,
    product,
    category,
):
    product_code = getattr(product, "code", None)

    if not product_code:
        product_code = getattr(product, "product_code", "REC-PROD-001")

    return RecurringService.objects.create(
        company=company,
        product=product,
        product_code=product_code,
        product_service_name="Monthly Internet Service",
        category=category,
        hs_code="9984",
        vat_rate=Decimal("15.00"),
        base_price=Decimal("1000.00"),
        unit_price=Decimal("1000.00"),
        unit="Month",
        billing_type="recurring",
        discount=Decimal("100.00"),
        final_price=Decimal("900.00"),
        technology="Fiber",
        database="PostgreSQL",
        status="active",
        created_by=company_admin,
    )


@pytest.fixture
def second_company_service(
    second_company,
    second_company_user,
    second_product,
):
    product_code = getattr(second_product, "code", None)

    if not product_code:
        product_code = getattr(
            second_product,
            "product_code",
            "REC-PROD-002",
        )

    return RecurringService.objects.create(
        company=second_company,
        product=second_product,
        product_code=product_code,
        product_service_name="Second Company Service",
        vat_rate=Decimal("15.00"),
        base_price=Decimal("2000.00"),
        unit_price=Decimal("2000.00"),
        unit="Month",
        billing_type="recurring",
        discount=Decimal("0.00"),
        final_price=Decimal("2000.00"),
        status="active",
        created_by=second_company_user,
    )


# ==========================================================
# PRICING PLAN
# ==========================================================

@pytest.fixture
def recurring_pricing_plan(recurring_service):
    return RecurringPricingPlan.objects.create(
        recurring_service=recurring_service,
        plan_type="starter",
        service_id="SERVICE-001",
        users=5,
        billing_cycle="monthly",
        discount_percent=Decimal("10.00"),
        price=Decimal("810.00"),
    )


# ==========================================================
# BILLING
# ==========================================================

@pytest.fixture
def recurring_billing(
    company,
    company_admin,
    customer,
    recurring_service,
):
    customer_email = getattr(
        customer,
        "admin_email",
        getattr(customer, "email", ""),
    )

    customer_phone = getattr(
        customer,
        "phno",
        getattr(
            customer,
            "phone",
            getattr(customer, "contact_number", ""),
        ),
    )

    return RecurringBilling.objects.create(
        company=company,
        contract_number="REC00001",
        recurring_service=recurring_service,
        customer=customer,
        recurring_type="invoice",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        frequency="monthly",
        total_recurrence=12,
        unlimited_recurrence=False,
        payment_term="30_days",
        reminder_before_due_days=5,
        reminder_before_renewal_days=7,
        billing_cycle="advance",
        auto_email_to=customer_email,
        whatsapp_number=customer_phone,
        auto_generate_invoice=True,
        auto_send=True,
        include_tax=True,
        auto_renew=True,
        recurrence_status="active",
        additional_notes="Monthly recurring service",
        invoice_date=date(2026, 1, 1),
        next_invoice_date=date(2026, 2, 1),
        monthly_amount=Decimal("900.00"),
        created_by=company_admin,
    )


@pytest.fixture
def second_company_billing(
    second_company,
    second_company_user,
    second_customer,
    second_company_service,
):
    customer_email = getattr(
        second_customer,
        "admin_email",
        getattr(second_customer, "email", ""),
    )

    customer_phone = getattr(
        second_customer,
        "phno",
        getattr(
            second_customer,
            "phone",
            getattr(second_customer, "contact_number", ""),
        ),
    )

    return RecurringBilling.objects.create(
        company=second_company,
        contract_number="REC00001",
        recurring_service=second_company_service,
        customer=second_customer,
        recurring_type="invoice",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        frequency="monthly",
        total_recurrence=12,
        unlimited_recurrence=False,
        payment_term="30_days",
        reminder_before_due_days=5,
        reminder_before_renewal_days=7,
        billing_cycle="advance",
        auto_email_to=customer_email,
        whatsapp_number=customer_phone,
        auto_generate_invoice=True,
        auto_send=True,
        include_tax=True,
        auto_renew=True,
        recurrence_status="active",
        additional_notes="Second company recurring service",
        invoice_date=date(2026, 1, 1),
        next_invoice_date=date(2026, 2, 1),
        monthly_amount=Decimal("2000.00"),
        created_by=second_company_user,
    )


# ==========================================================
# SERVICE API
# ==========================================================

@pytest.mark.django_db
def test_recurring_service_create(
    authenticated_client,
    product,
    category,
):
    product_code = getattr(
        product,
        "code",
        getattr(product, "product_code", "REC-PROD-001"),
    )

    payload = {
        "product": product.id,
        "product_code": product_code,
        "product_service_name": "API Recurring Service",
        "category": category.id,
        "hs_code": "9984",
        "vat_rate": "15.00",
        "base_price": "1000.00",
        "unit_price": "1000.00",
        "unit": "Month",
        "billing_type": "recurring",
        "discount": "100.00",
        "final_price": "900.00",
        "technology": "Fiber",
        "database": "PostgreSQL",
        "status": "active",
    }

    response = authenticated_client.post(
        SERVICE_URL,
        payload,
        format="json",
    )

    assert response.status_code in [200, 201], response.data

    assert RecurringService.objects.filter(
        product_service_name="API Recurring Service"
    ).exists()


@pytest.mark.django_db
def test_recurring_service_list(
    authenticated_client,
    recurring_service,
):
    response = authenticated_client.get(SERVICE_URL)

    assert response.status_code == 200

    results = get_list_results(response)

    assert len(results) >= 1


@pytest.mark.django_db
def test_recurring_service_retrieve(
    authenticated_client,
    recurring_service,
):
    response = authenticated_client.get(
        f"{SERVICE_URL}{recurring_service.id}/"
    )

    assert response.status_code == 200
    assert response.data["id"] == recurring_service.id


@pytest.mark.django_db
def test_recurring_service_update(
    authenticated_client,
    recurring_service,
):
    response = authenticated_client.patch(
        f"{SERVICE_URL}{recurring_service.id}/",
        {
            "product_service_name": "Updated Recurring Service",
            "final_price": "1200.00",
        },
        format="json",
    )

    assert response.status_code == 200

    recurring_service.refresh_from_db()

    assert recurring_service.product_service_name == (
        "Updated Recurring Service"
    )
    assert recurring_service.final_price == Decimal("1200.00")


@pytest.mark.django_db
def test_recurring_service_delete(
    authenticated_client,
    recurring_service,
):
    response = authenticated_client.delete(
        f"{SERVICE_URL}{recurring_service.id}/"
    )

    assert response.status_code in [200, 204]

    assert not RecurringService.objects.filter(
        id=recurring_service.id
    ).exists()


@pytest.mark.django_db
def test_recurring_service_company_isolation(
    authenticated_client,
    recurring_service,
    second_company_service,
):
    response = authenticated_client.get(SERVICE_URL)

    assert response.status_code == 200

    results = get_list_results(response)

    ids = [item["id"] for item in results]

    assert recurring_service.id in ids
    assert second_company_service.id not in ids


@pytest.mark.django_db
def test_recurring_service_retrieve_other_company_returns_404(
    authenticated_client,
    second_company_service,
):
    response = authenticated_client.get(
        f"{SERVICE_URL}{second_company_service.id}/"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_recurring_service_search(
    authenticated_client,
    recurring_service,
):
    response = authenticated_client.get(
        SERVICE_URL,
        {"search": "Monthly Internet"},
    )

    assert response.status_code == 200

    results = get_list_results(response)

    assert any(
        item["id"] == recurring_service.id
        for item in results
    )


@pytest.mark.django_db
def test_recurring_service_filter_status(
    authenticated_client,
    recurring_service,
):
    response = authenticated_client.get(
        SERVICE_URL,
        {"status": "active"},
    )

    assert response.status_code == 200


# ==========================================================
# PRICING PLAN
# ==========================================================

@pytest.mark.django_db
def test_recurring_pricing_plan_create(
    recurring_service,
):
    plan = RecurringPricingPlan.objects.create(
        recurring_service=recurring_service,
        plan_type="professional",
        service_id="SERVICE-002",
        users=10,
        billing_cycle="monthly",
        discount_percent=Decimal("5.00"),
        price=Decimal("950.00"),
    )

    assert plan.pk is not None
    assert plan.plan_type == "professional"


@pytest.mark.django_db
def test_recurring_pricing_plan_serializer(
    recurring_pricing_plan,
):
    from finance.recurring.serializers import (
        RecurringPricingPlanSerializer,
    )

    serializer = RecurringPricingPlanSerializer(
        recurring_pricing_plan
    )

    assert serializer.data["plan_type"] == "starter"
    assert serializer.data["service_id"] == "SERVICE-001"


@pytest.mark.django_db
def test_recurring_pricing_plan_unique_constraint(
    recurring_service,
    recurring_pricing_plan,
):
    with pytest.raises(Exception):
        RecurringPricingPlan.objects.create(
            recurring_service=recurring_service,
            plan_type="starter",
            service_id="SERVICE-DUP",
            users=10,
            billing_cycle="monthly",
            price=Decimal("900.00"),
        )


# ==========================================================
# BILLING API
# ==========================================================

@pytest.mark.django_db
def test_recurring_billing_create(
    authenticated_client,
    customer,
    recurring_service,
):
    payload = {
        "recurring_service": recurring_service.id,
        "customer": customer.id,
        "recurring_type": "invoice",
        "start_date": "2026-03-01",
        "end_date": "2026-12-31",
        "frequency": "monthly",
        "total_recurrence": 10,
        "unlimited_recurrence": False,
        "payment_term": "30_days",
        "reminder_before_due_days": 5,
        "reminder_before_renewal_days": 7,
        "billing_cycle": "advance",
        "auto_email_to": "customer@test.com",
        "whatsapp_number": "9999999999",
        "auto_generate_invoice": True,
        "auto_send": True,
        "include_tax": True,
        "auto_renew": True,
        "recurrence_status": "active",
        "additional_notes": "API created recurring billing",
    }

    response = authenticated_client.post(
        BILLING_URL,
        payload,
        format="json",
    )

    assert response.status_code in [200, 201], response.data

    assert RecurringBilling.objects.filter(
        customer=customer,
        recurring_service=recurring_service,
    ).exists()


@pytest.mark.django_db
def test_recurring_billing_list(
    authenticated_client,
    recurring_billing,
):
    response = authenticated_client.get(BILLING_URL)

    assert response.status_code == 200

    results = get_list_results(response)

    assert len(results) >= 1


@pytest.mark.django_db
def test_recurring_billing_retrieve(
    authenticated_client,
    recurring_billing,
):
    response = authenticated_client.get(
        f"{BILLING_URL}{recurring_billing.id}/"
    )

    assert response.status_code == 200
    assert response.data["id"] == recurring_billing.id


@pytest.mark.django_db
def test_recurring_billing_update(
    authenticated_client,
    recurring_billing,
):
    response = authenticated_client.patch(
        f"{BILLING_URL}{recurring_billing.id}/",
        {
            "payment_term": "60_days",
            "auto_renew": False,
        },
        format="json",
    )

    assert response.status_code == 200

    recurring_billing.refresh_from_db()

    assert recurring_billing.payment_term == "60_days"
    assert recurring_billing.auto_renew is False


@pytest.mark.django_db
def test_recurring_billing_delete(
    authenticated_client,
    recurring_billing,
):
    response = authenticated_client.delete(
        f"{BILLING_URL}{recurring_billing.id}/"
    )

    assert response.status_code in [200, 204]

    assert not RecurringBilling.objects.filter(
        id=recurring_billing.id
    ).exists()


@pytest.mark.django_db
def test_recurring_billing_company_isolation(
    authenticated_client,
    recurring_billing,
    second_company_billing,
):
    response = authenticated_client.get(BILLING_URL)

    assert response.status_code == 200

    results = get_list_results(response)

    ids = [item["id"] for item in results]

    assert recurring_billing.id in ids
    assert second_company_billing.id not in ids


@pytest.mark.django_db
def test_recurring_billing_other_company_404(
    authenticated_client,
    second_company_billing,
):
    response = authenticated_client.get(
        f"{BILLING_URL}{second_company_billing.id}/"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_recurring_billing_search(
    authenticated_client,
    recurring_billing,
):
    response = authenticated_client.get(
        BILLING_URL,
        {"search": recurring_billing.contract_number},
    )

    assert response.status_code == 200

    results = get_list_results(response)

    assert any(
        item["id"] == recurring_billing.id
        for item in results
    )


@pytest.mark.django_db
def test_recurring_billing_filter_status(
    authenticated_client,
    recurring_billing,
):
    response = authenticated_client.get(
        BILLING_URL,
        {"recurrence_status": "active"},
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_recurring_billing_filter_frequency(
    authenticated_client,
    recurring_billing,
):
    response = authenticated_client.get(
        BILLING_URL,
        {"frequency": "monthly"},
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_recurring_billing_filter_customer(
    authenticated_client,
    recurring_billing,
    customer,
):
    response = authenticated_client.get(
        BILLING_URL,
        {"customer": customer.id},
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_recurring_billing_renewal_from_filter(
    authenticated_client,
    recurring_billing,
):
    response = authenticated_client.get(
        BILLING_URL,
        {"renewal_from": "2026-01-01"},
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_recurring_billing_renewal_to_filter(
    authenticated_client,
    recurring_billing,
):
    response = authenticated_client.get(
        BILLING_URL,
        {"renewal_to": "2026-12-31"},
    )

    assert response.status_code == 200


# ==========================================================
# COMBINED CREATE
# ==========================================================

@pytest.mark.django_db
def test_recurring_combined_create(
    authenticated_client,
    product,
    category,
    customer,
):
    product_code = getattr(
        product,
        "code",
        getattr(product, "product_code", "REC-PROD-001"),
    )

    payload = {
        "service": {
            "product": product.id,
            "product_code": product_code,
            "product_service_name": "Combined Recurring Service",
            "category": category.id,
            "hs_code": "9984",
            "vat_rate": "15.00",
            "base_price": "1000.00",
            "unit_price": "1000.00",
            "unit": "Month",
            "billing_type": "recurring",
            "discount": "100.00",
            "final_price": "900.00",
            "technology": "Fiber",
            "database": "PostgreSQL",
            "status": "active",
        },
        "pricing_plans": [
            {
                "plan_type": "starter",
                "service_id": "STARTER-001",
                "users": 5,
                "billing_cycle": "monthly",
                "discount_percent": "10.00",
                "price": "810.00",
            },
            {
                "plan_type": "professional",
                "service_id": "PRO-001",
                "users": 20,
                "billing_cycle": "monthly",
                "discount_percent": "5.00",
                "price": "950.00",
            },
        ],
        "billing": {
            "customer": customer.id,
            "recurring_type": "invoice",
            "start_date": "2026-04-01",
            "end_date": "2026-12-31",
            "frequency": "monthly",
            "total_recurrence": 9,
            "unlimited_recurrence": False,
            "payment_term": "30_days",
            "reminder_before_due_days": 5,
            "reminder_before_renewal_days": 7,
            "billing_cycle": "advance",
            "auto_email_to": "customer@test.com",
            "whatsapp_number": "9999999999",
            "auto_generate_invoice": True,
            "auto_send": True,
            "include_tax": True,
            "auto_renew": True,
            "recurrence_status": "active",
            "additional_notes": "Combined recurring creation",
        },
    }

    response = authenticated_client.post(
        CREATE_URL,
        payload,
        format="json",
    )

    assert response.status_code in [200, 201], response.data

    assert RecurringService.objects.filter(
        product_service_name="Combined Recurring Service"
    ).exists()

    assert RecurringBilling.objects.filter(
        customer=customer
    ).exists()


# ==========================================================
# SUMMARY
# ==========================================================

@pytest.mark.django_db
def test_recurring_summary(
    authenticated_client,
    recurring_billing,
):
    response = authenticated_client.get(SUMMARY_URL)

    assert response.status_code == 200

    assert "data" in response.data

    data = response.data["data"]

    assert "active_subscription" in data
    assert "total_monthly_revenue_amount" in data
    assert "upcoming_renewal" in data
    assert "auto_generated_invoice_month" in data
    assert "expired_contract_count" in data

    assert data["active_subscription"] == 1
    assert data["total_monthly_revenue_amount"] == Decimal("900")
# ==========================================================
# DASHBOARD
# ==========================================================

@pytest.mark.django_db
def test_recurring_dashboard(
    authenticated_client,
    recurring_billing,
):
    response = authenticated_client.get(DASHBOARD_URL)

    assert response.status_code == 200

    assert "data" in response.data

    data = response.data["data"]

    assert "total_active_subscription" in data
    assert "monthly_renewal_amount" in data
    assert "upcoming_renewal" in data
    assert "auto_generated_invoice" in data
    assert "expired_contract" in data

    assert data["total_active_subscription"] == 1
    assert data["monthly_renewal_amount"] == Decimal("900")
# ==========================================================
# OCCURRENCE
# ==========================================================

@pytest.mark.django_db
def test_recurring_occurrence_create(
    recurring_billing,
):
    occurrence = RecurringBillingOccurrence.objects.create(
        recurring_billing=recurring_billing,
        occurrence_number=1,
        scheduled_date=date(2026, 2, 1),
        status="pending",
    )

    assert occurrence.pk is not None
    assert occurrence.status == "pending"


@pytest.mark.django_db
def test_recurring_occurrence_unique_number(
    recurring_billing,
):
    RecurringBillingOccurrence.objects.create(
        recurring_billing=recurring_billing,
        occurrence_number=1,
        scheduled_date=date(2026, 2, 1),
        status="pending",
    )

    with pytest.raises(Exception):
        RecurringBillingOccurrence.objects.create(
            recurring_billing=recurring_billing,
            occurrence_number=1,
            scheduled_date=date(2026, 3, 1),
            status="pending",
        )


# ==========================================================
# MODEL VALIDATION
# ==========================================================

@pytest.mark.django_db
def test_recurring_billing_clean_wrong_customer_company(
    company,
    second_customer,
    recurring_service,
):
    billing = RecurringBilling(
        company=company,
        contract_number="VALIDATION-001",
        recurring_service=recurring_service,
        customer=second_customer,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        frequency="monthly",
        total_recurrence=12,
        unlimited_recurrence=False,
    )

    with pytest.raises(ValidationError):
        billing.full_clean()


@pytest.mark.django_db
def test_recurring_billing_clean_invalid_dates(
    company,
    customer,
    recurring_service,
):
    billing = RecurringBilling(
        company=company,
        contract_number="VALIDATION-002",
        recurring_service=recurring_service,
        customer=customer,
        start_date=date(2026, 12, 31),
        end_date=date(2026, 1, 1),
        frequency="monthly",
        total_recurrence=12,
        unlimited_recurrence=False,
    )

    with pytest.raises(ValidationError):
        billing.full_clean()


@pytest.mark.django_db
def test_recurring_billing_clean_requires_recurrence(
    company,
    customer,
    recurring_service,
):
    billing = RecurringBilling(
        company=company,
        contract_number="VALIDATION-003",
        recurring_service=recurring_service,
        customer=customer,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        frequency="monthly",
        total_recurrence=None,
        unlimited_recurrence=False,
    )

    with pytest.raises(ValidationError):
        billing.full_clean()


@pytest.mark.django_db
def test_recurring_billing_unlimited_recurrence_valid(
    company,
    customer,
    recurring_service,
):
    billing = RecurringBilling(
        company=company,
        contract_number="VALIDATION-004",
        recurring_service=recurring_service,
        customer=customer,
        start_date=date(2026, 1, 1),
        end_date=None,
        frequency="monthly",
        total_recurrence=None,
        unlimited_recurrence=True,
    )

    billing.full_clean()


# ==========================================================
# UTILITY TESTS
# ==========================================================

def test_calculate_next_invoice_date_daily():
    result = calculate_next_invoice_date(
        date(2026, 1, 1),
        "daily",
    )

    assert result == date(2026, 1, 2)


def test_calculate_next_invoice_date_weekly():
    result = calculate_next_invoice_date(
        date(2026, 1, 1),
        "weekly",
    )

    assert result == date(2026, 1, 8)


def test_calculate_next_invoice_date_monthly():
    result = calculate_next_invoice_date(
        date(2026, 1, 15),
        "monthly",
    )

    assert result == date(2026, 2, 15)


def test_calculate_next_invoice_date_month_end():
    result = calculate_next_invoice_date(
        date(2026, 1, 31),
        "monthly",
    )

    assert result == date(2026, 2, 28)


def test_calculate_next_invoice_date_quarterly():
    result = calculate_next_invoice_date(
        date(2026, 1, 15),
        "quarterly",
    )

    assert result == date(2026, 4, 15)


def test_calculate_next_invoice_date_yearly():
    result = calculate_next_invoice_date(
        date(2026, 1, 15),
        "yearly",
    )

    assert result == date(2027, 1, 15)


def test_calculate_next_invoice_date_leap_year():
    result = calculate_next_invoice_date(
        date(2024, 2, 29),
        "yearly",
    )

    assert result == date(2025, 2, 28)


def test_calculate_next_invoice_date_unknown_frequency():
    result = calculate_next_invoice_date(
        date(2026, 1, 1),
        "unknown",
    )

    assert result is None


# ==========================================================
# SERIALIZER TESTS
# ==========================================================

@pytest.mark.django_db
def test_recurring_service_serializer(
    recurring_service,
):
    from finance.recurring.serializers import (
        RecurringServiceSerializer,
    )

    serializer = RecurringServiceSerializer(
        recurring_service
    )

    assert serializer.data["id"] == recurring_service.id
    assert serializer.data["product_code"] == recurring_service.product_code
    assert (
        serializer.data["product_service_name"]
        == recurring_service.product_service_name
    )


@pytest.mark.django_db
def test_recurring_billing_serializer(
    recurring_billing,
):
    from finance.recurring.serializers import (
        RecurringBillingSerializer,
    )

    serializer = RecurringBillingSerializer(
        recurring_billing
    )

    assert serializer.data["id"] == recurring_billing.id
    assert (
        serializer.data["contract_number"]
        == recurring_billing.contract_number
    )
    assert serializer.data["auto_renew_display"] == "Yes"


@pytest.mark.django_db
def test_recurring_billing_serializer_auto_renew_no(
    recurring_billing,
):
    from finance.recurring.serializers import (
        RecurringBillingSerializer,
    )

    recurring_billing.auto_renew = False

    serializer = RecurringBillingSerializer(
        recurring_billing
    )

    assert serializer.data["auto_renew_display"] == "No"


@pytest.mark.django_db
def test_recurring_occurrence_serializer(
    recurring_billing,
):
    occurrence = RecurringBillingOccurrence.objects.create(
        recurring_billing=recurring_billing,
        occurrence_number=1,
        scheduled_date=date(2026, 2, 1),
        status="pending",
    )

    from finance.recurring.serializers import (
        RecurringBillingOccurrenceSerializer,
    )

    serializer = RecurringBillingOccurrenceSerializer(
        occurrence
    )

    assert serializer.data["id"] == occurrence.id
    assert (
        serializer.data["contract_number"]
        == recurring_billing.contract_number
    )


# ==========================================================
# UNAUTHENTICATED ACCESS
# ==========================================================

@pytest.mark.django_db
def test_recurring_service_requires_authentication():
    client = APIClient()

    response = client.get(SERVICE_URL)

    assert response.status_code in [401, 403]


@pytest.mark.django_db
def test_recurring_billing_requires_authentication():
    client = APIClient()

    response = client.get(BILLING_URL)

    assert response.status_code in [401, 403]


@pytest.mark.django_db
def test_recurring_summary_requires_authentication():
    client = APIClient()

    response = client.get(SUMMARY_URL)

    assert response.status_code in [401, 403]


@pytest.mark.django_db
def test_recurring_dashboard_requires_authentication():
    client = APIClient()

    response = client.get(DASHBOARD_URL)

    assert response.status_code in [401, 403]


# ==========================================================
# CROSS-COMPANY BILLING VALIDATION
# ==========================================================

@pytest.mark.django_db
def test_billing_rejects_other_company_customer(
    authenticated_client,
    recurring_service,
    second_customer,
):
    payload = {
        "recurring_service": recurring_service.id,
        "customer": second_customer.id,
        "recurring_type": "invoice",
        "start_date": "2026-05-01",
        "end_date": "2026-12-31",
        "frequency": "monthly",
        "total_recurrence": 8,
        "unlimited_recurrence": False,
        "payment_term": "30_days",
        "billing_cycle": "advance",
        "auto_generate_invoice": False,
        "auto_send": False,
        "include_tax": True,
        "auto_renew": True,
        "recurrence_status": "active",
    }

    response = authenticated_client.post(
        BILLING_URL,
        payload,
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_billing_rejects_other_company_service(
    authenticated_client,
    second_company_service,
    customer,
):
    payload = {
        "recurring_service": second_company_service.id,
        "customer": customer.id,
        "recurring_type": "invoice",
        "start_date": "2026-05-01",
        "end_date": "2026-12-31",
        "frequency": "monthly",
        "total_recurrence": 8,
        "unlimited_recurrence": False,
        "payment_term": "30_days",
        "billing_cycle": "advance",
        "auto_generate_invoice": False,
        "auto_send": False,
        "include_tax": True,
        "auto_renew": True,
        "recurrence_status": "active",
    }

    response = authenticated_client.post(
        BILLING_URL,
        payload,
        format="json",
    )

    assert response.status_code == 400


# ==========================================================
# COMBINED CREATE CROSS-COMPANY VALIDATION
# ==========================================================

@pytest.mark.django_db
def test_combined_create_rejects_other_company_customer(
    authenticated_client,
    product,
    category,
    second_customer,
):
    product_code = getattr(
        product,
        "code",
        getattr(product, "product_code", "REC-PROD-001"),
    )

    payload = {
        "service": {
            "product": product.id,
            "product_code": product_code,
            "product_service_name": "Invalid Combined Service",
            "category": category.id,
            "vat_rate": "15.00",
            "base_price": "1000.00",
            "unit_price": "1000.00",
            "unit": "Month",
            "billing_type": "recurring",
            "discount": "0.00",
            "final_price": "1000.00",
            "status": "active",
        },
        "billing": {
            "customer": second_customer.id,
            "recurring_type": "invoice",
            "start_date": "2026-05-01",
            "frequency": "monthly",
            "total_recurrence": 5,
            "unlimited_recurrence": False,
            "payment_term": "30_days",
            "billing_cycle": "advance",
            "recurrence_status": "active",
        },
    }

    response = authenticated_client.post(
        CREATE_URL,
        payload,
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_combined_create_rejects_other_company_product(
    authenticated_client,
    second_product,
    category,
    customer,
):
    product_code = getattr(
        second_product,
        "code",
        getattr(second_product, "product_code", "REC-PROD-002"),
    )

    payload = {
        "service": {
            "product": second_product.id,
            "product_code": product_code,
            "product_service_name": "Invalid Product Service",
            "category": category.id,
            "vat_rate": "15.00",
            "base_price": "1000.00",
            "unit_price": "1000.00",
            "unit": "Month",
            "billing_type": "recurring",
            "discount": "0.00",
            "final_price": "1000.00",
            "status": "active",
        },
        "billing": {
            "customer": customer.id,
            "recurring_type": "invoice",
            "start_date": "2026-05-01",
            "frequency": "monthly",
            "total_recurrence": 5,
            "unlimited_recurrence": False,
            "payment_term": "30_days",
            "billing_cycle": "advance",
            "recurrence_status": "active",
        },
    }

    response = authenticated_client.post(
        CREATE_URL,
        payload,
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_combined_create_rejects_other_company_category(
    authenticated_client,
    product,
    second_category,
    customer,
):
    product_code = getattr(
        product,
        "code",
        getattr(product, "product_code", "REC-PROD-001"),
    )

    payload = {
        "service": {
            "product": product.id,
            "product_code": product_code,
            "product_service_name": "Invalid Category Service",
            "category": second_category.id,
            "vat_rate": "15.00",
            "base_price": "1000.00",
            "unit_price": "1000.00",
            "unit": "Month",
            "billing_type": "recurring",
            "discount": "0.00",
            "final_price": "1000.00",
            "status": "active",
        },
        "billing": {
            "customer": customer.id,
            "recurring_type": "invoice",
            "start_date": "2026-05-01",
            "frequency": "monthly",
            "total_recurrence": 5,
            "unlimited_recurrence": False,
            "payment_term": "30_days",
            "billing_cycle": "advance",
            "recurrence_status": "active",
        },
    }

    response = authenticated_client.post(
        CREATE_URL,
        payload,
        format="json",
    )

    assert response.status_code == 400


# ==========================================================
# CONTRACT NUMBER
# ==========================================================

@pytest.mark.django_db
def test_contract_number_generated_per_company(
    authenticated_client,
    customer,
    recurring_service,
):
    payload = {
        "recurring_service": recurring_service.id,
        "customer": customer.id,
        "recurring_type": "invoice",
        "start_date": "2026-06-01",
        "end_date": "2026-12-31",
        "frequency": "monthly",
        "total_recurrence": 7,
        "unlimited_recurrence": False,
        "payment_term": "30_days",
        "billing_cycle": "advance",
        "recurrence_status": "active",
    }

    response = authenticated_client.post(
        BILLING_URL,
        payload,
        format="json",
    )

    assert response.status_code in [200, 201], response.data

    billing = RecurringBilling.objects.get(
        customer=customer,
        start_date=date(2026, 6, 1),
    )

    assert billing.contract_number.startswith("REC")


# ==========================================================
# NEXT INVOICE DATE
# ==========================================================

@pytest.mark.django_db
def test_next_invoice_date_is_generated(
    authenticated_client,
    customer,
    recurring_service,
):
    payload = {
        "recurring_service": recurring_service.id,
        "customer": customer.id,
        "recurring_type": "invoice",
        "start_date": "2026-07-15",
        "end_date": "2026-12-31",
        "frequency": "monthly",
        "total_recurrence": 5,
        "unlimited_recurrence": False,
        "payment_term": "30_days",
        "billing_cycle": "advance",
        "recurrence_status": "active",
    }

    response = authenticated_client.post(
        BILLING_URL,
        payload,
        format="json",
    )

    assert response.status_code in [200, 201], response.data

    billing = RecurringBilling.objects.get(
        customer=customer,
        start_date=date(2026, 7, 15),
    )

    assert billing.invoice_date == date(2026, 7, 15)
    assert billing.next_invoice_date == date(2026, 8, 15)


# ==========================================================
# MONTHLY AMOUNT
# ==========================================================

@pytest.mark.django_db
def test_monthly_amount_comes_from_service_final_price(
    authenticated_client,
    customer,
    recurring_service,
):
    payload = {
        "recurring_service": recurring_service.id,
        "customer": customer.id,
        "recurring_type": "invoice",
        "start_date": "2026-08-01",
        "frequency": "monthly",
        "total_recurrence": 4,
        "unlimited_recurrence": False,
        "payment_term": "30_days",
        "billing_cycle": "advance",
        "recurrence_status": "active",
    }

    response = authenticated_client.post(
        BILLING_URL,
        payload,
        format="json",
    )

    assert response.status_code in [200, 201], response.data

    billing = RecurringBilling.objects.get(
        customer=customer,
        start_date=date(2026, 8, 1),
    )

    assert billing.monthly_amount == recurring_service.final_price


# ==========================================================
# END
# ==========================================================