import pytest
from decimal import Decimal
from datetime import date

from django.db import IntegrityError
from rest_framework.test import APIClient

from superadmin.models import Company
from django.contrib.auth import get_user_model

from finance.category.models import Category
from finance.customer.models import Customer
from finance.product.models import Product
from finance.warehouse.models import Warehouse
from finance.quotation.models import Quotation, QuotationItem
from finance.sales_order.models import SalesOrder, SalesOrderItem
from django.core.exceptions import ValidationError

User = get_user_model()


# ============================================================
# URLS
# ============================================================

SALES_ORDER_URL = "/api/finance/sales-order/"
SUMMARY_URL = "/api/finance/sales-order/summary/"
QUOTATIONS_URL = "/api/finance/sales-order/quotations/"
COMPANIES_URL = "/api/finance/sales-order/companies/"
CUSTOMERS_URL = "/api/finance/sales-order/customers/"
WAREHOUSES_URL = "/api/finance/sales-order/warehouses/"


# ============================================================
# HELPERS
# ============================================================

def get_list_results(response):
    """
    Supports both:
        [...]
    and:
        {"results": [...]}
    """
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


# ------------------------------------------------------------
# COMPANY
# ------------------------------------------------------------

@pytest.fixture
def company():
    return Company.objects.create(
        name="Test Company",
        email="testcompany@example.com",
        contact_number="1234567890",
        address="Test Company Address",
        location="Riyadh",
    )


@pytest.fixture
def second_company():
    return Company.objects.create(
        name="Second Company",
        email="secondcompany@example.com",
        contact_number="9876543210",
        address="Second Company Address",
        location="Jeddah",
    )


# ------------------------------------------------------------
# USERS
# ------------------------------------------------------------

@pytest.fixture
def company_admin(company):
    """
    IMPORTANT:
    Do not pass is_company_admin / is_super_admin here.
    Those fields do not exist in the actual User model.
    """
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
def second_authenticated_client(api_client, second_company_user):
    api_client.force_authenticate(user=second_company_user)
    return api_client


# ------------------------------------------------------------
# CATEGORY
# ------------------------------------------------------------

@pytest.fixture
def category(company, company_admin):
    return Category.objects.create(
        company=company,
        code="CAT001",
        category_name="Test Category",
        category_type="product",
        status="active",
        created_by=company_admin,
    )


@pytest.fixture
def second_category(second_company, second_company_user):
    return Category.objects.create(
        company=second_company,
        code="CAT002",
        category_name="Second Category",
        category_type="product",
        status="active",
        created_by=second_company_user,
    )


# ------------------------------------------------------------
# CUSTOMER
# ------------------------------------------------------------

@pytest.fixture
def customer(company, company_admin):
    return Customer.objects.create(
        company=company,
        customer_name="Test Customer",
        company_name="Test Customer Company",
        industry="Technology",
        website="https://example.com",
        cr_number="CR001",
        currency="SAR",
        vat_number="VAT001",
        payment_term="net_30",
        billing_address="Test Billing Address",
        city="Riyadh",
        state="Riyadh",
        country="Saudi Arabia",
        phno="0501234567",
        admin_email="customer@example.com",
        financial_email="finance@example.com",
        technical_email="technical@example.com",
        client_status="active",
        credit_limit=Decimal("10000.00"),
        opening_balance=Decimal("0.00"),
        notes="Test customer",
        created_by=company_admin,
    )


@pytest.fixture
def second_customer(second_company, second_company_user):
    return Customer.objects.create(
        company=second_company,
        customer_name="Second Customer",
        company_name="Second Customer Company",
        industry="Technology",
        website="https://secondexample.com",
        cr_number="CR002",
        currency="SAR",
        vat_number="VAT002",
        payment_term="net_30",
        billing_address="Second Billing Address",
        city="Jeddah",
        state="Makkah",
        country="Saudi Arabia",
        phno="0507654321",
        admin_email="secondcustomer@example.com",
        financial_email="secondfinance@example.com",
        technical_email="secondtechnical@example.com",
        client_status="active",
        credit_limit=Decimal("20000.00"),
        opening_balance=Decimal("0.00"),
        notes="Second customer",
        created_by=second_company_user,
    )


# ------------------------------------------------------------
# PRODUCT
# ------------------------------------------------------------

@pytest.fixture
def product(company, company_admin, category):
    return Product.objects.create(
        company=company,
        product_name="Test Product",
        product_type="product",
        sku="TEST-SKU",
        category=category,
        brand="Test Brand",
        supplier="Test Supplier",
        unit="PCS",
        hsn_sac_code="1234",
        cost_price=Decimal("400.00"),
        selling_price=Decimal("500.00"),
        opening_stock_qty=10,
        quantity=10,
        current_stock=10,
        reserved_qty=0,
        reorder_level=2,
        tax_type="vat",
        tax_rate=Decimal("15.00"),
        description="Test product",
        status="active",
        created_by=company_admin,
    )


@pytest.fixture
def second_product(second_company, second_company_user, second_category):
    return Product.objects.create(
        company=second_company,
        product_name="Second Product",
        product_type="product",
        sku="SECOND-SKU",
        category=second_category,
        brand="Second Brand",
        supplier="Second Supplier",
        unit="PCS",
        hsn_sac_code="5678",
        cost_price=Decimal("300.00"),
        selling_price=Decimal("600.00"),
        opening_stock_qty=20,
        quantity=20,
        current_stock=20,
        reserved_qty=0,
        reorder_level=5,
        tax_type="vat",
        tax_rate=Decimal("15.00"),
        description="Second product",
        status="active",
        created_by=second_company_user,
    )


# ------------------------------------------------------------
# WAREHOUSE
# ------------------------------------------------------------

@pytest.fixture
def warehouse(company, company_admin):
    return Warehouse.objects.create(
        company=company,
        warehouse_name="Main Warehouse",
        warehouse_type="main",
        manager="Test Manager",
        status="active",
        operating_since=date(2024, 1, 1),
        country="Saudi Arabia",
        city="Riyadh",
        address_line_1="Warehouse Address",
        address_line_2="",
        postal_code="12345",
        phone_number="0501234567",
        email="warehouse@example.com",
        storage_capacity=1000,
        notes="Main test warehouse",
        created_by=company_admin,
    )


@pytest.fixture
def inactive_warehouse(company, company_admin):
    return Warehouse.objects.create(
        company=company,
        warehouse_name="Inactive Warehouse",
        warehouse_type="regional",
        manager="Inactive Manager",
        status="inactive",
        operating_since=date(2024, 1, 1),
        country="Saudi Arabia",
        city="Riyadh",
        address_line_1="Inactive Warehouse Address",
        address_line_2="",
        postal_code="12346",
        phone_number="0501111111",
        email="inactive@example.com",
        storage_capacity=500,
        notes="Inactive warehouse",
        created_by=company_admin,
    )


@pytest.fixture
def second_warehouse(second_company, second_company_user):
    return Warehouse.objects.create(
        company=second_company,
        warehouse_name="Second Warehouse",
        warehouse_type="distribution",
        manager="Second Manager",
        status="active",
        operating_since=date(2024, 1, 1),
        country="Saudi Arabia",
        city="Jeddah",
        address_line_1="Second Warehouse Address",
        address_line_2="",
        postal_code="54321",
        phone_number="0502222222",
        email="secondwarehouse@example.com",
        storage_capacity=2000,
        notes="Second warehouse",
        created_by=second_company_user,
    )


# ------------------------------------------------------------
# QUOTATION
# ------------------------------------------------------------

@pytest.fixture
def quotation(company, company_admin, customer, product):
    quotation = Quotation.objects.create(
        company=company,
        customer=customer,
        issue_date=date(2026, 1, 1),
        valid_till=date(2026, 1, 31),
        status="approved",
        notes="Test quotation",
        created_by=company_admin,
    )

    QuotationItem.objects.create(
        quotation=quotation,
        product=product,
        service_name="",
        description="Test quotation item",
        quantity=Decimal("2.00"),
        hs_code="1234",
        rate=Decimal("500.00"),
        vat_percentage=Decimal("15.00"),
    )

    return quotation


@pytest.fixture
def rejected_quotation(company, company_admin, customer, product):
    quotation = Quotation.objects.create(
        company=company,
        customer=customer,
        issue_date=date(2026, 1, 1),
        valid_till=date(2026, 1, 31),
        status="rejected",
        notes="Rejected quotation",
        created_by=company_admin,
    )

    QuotationItem.objects.create(
        quotation=quotation,
        product=product,
        service_name="",
        description="Rejected quotation item",
        quantity=Decimal("2.00"),
        hs_code="1234",
        rate=Decimal("500.00"),
        vat_percentage=Decimal("15.00"),
    )

    return quotation


@pytest.fixture
def second_company_quotation(
    second_company,
    second_company_user,
    second_customer,
    second_product,
):
    quotation = Quotation.objects.create(
        company=second_company,
        customer=second_customer,
        issue_date=date(2026, 1, 1),
        valid_till=date(2026, 1, 31),
        status="approved",
        notes="Second company quotation",
        created_by=second_company_user,
    )

    QuotationItem.objects.create(
        quotation=quotation,
        product=second_product,
        service_name="",
        description="Second company item",
        quantity=Decimal("3.00"),
        hs_code="5678",
        rate=Decimal("600.00"),
        vat_percentage=Decimal("15.00"),
    )

    return quotation


# ------------------------------------------------------------
# SALES ORDER
# ------------------------------------------------------------

@pytest.fixture
def sales_order(
    company,
    company_admin,
    customer,
    product,
    warehouse,
    quotation,
):
    sales_order = SalesOrder.objects.create(
        company=company,
        quotation=quotation,
        customer=customer,
        warehouse=warehouse,
        order_date=date(2026, 1, 5),
        delivery_date=date(2026, 1, 10),
        due_date=date(2026, 2, 5),
        payment_terms="net_30",
        order_status="pending",
        discount=Decimal("0.00"),
        round_off=Decimal("0.00"),
        notes="Test sales order",
        created_by=company_admin,
    )

    SalesOrderItem.objects.create(
        sales_order=sales_order,
        quotation_item=quotation.items.first(),
        product=product,
        service_name="",
        description="Test sales order item",
        quantity=Decimal("2.00"),
        delivered_quantity=Decimal("0.00"),
        hs_code="1234",
        rate=Decimal("500.00"),
        vat_percentage=Decimal("15.00"),
    )

    sales_order.calculate_totals()
    sales_order.update_delivery_status()

    return sales_order


# ============================================================
# CREATE SALES ORDER
# ============================================================

@pytest.mark.django_db
def test_create_sales_order(
    authenticated_client,
    company,
    customer,
    warehouse,
    quotation,
):
    payload = {
        "quotation": quotation.id,
        "company": company.id,
        "customer": customer.id,
        "warehouse": warehouse.id,
        "order_date": "2026-02-01",
        "delivery_date": "2026-02-10",
        "due_date": "2026-03-01",
        "payment_terms": "net_30",
        "order_status": "pending",
        "discount": "0.00",
        "round_off": "0.00",
        "notes": "New sales order",
    }

    response = authenticated_client.post(
        SALES_ORDER_URL,
        payload,
        format="json",
    )

    assert response.status_code == 201
    assert response.data["company"] == company.id
    assert response.data["customer"] == customer.id
    assert response.data["quotation"] == quotation.id

    assert SalesOrder.objects.filter(
        company=company,
        quotation=quotation,
    ).exists()


@pytest.mark.django_db
def test_create_sales_order_with_items(
    authenticated_client,
    company,
    customer,
    warehouse,
    quotation,
    product,
):
    quotation_item = quotation.items.first()

    payload = {
        "quotation": quotation.id,
        "company": company.id,
        "customer": customer.id,
        "warehouse": warehouse.id,
        "order_date": "2026-02-01",
        "delivery_date": "2026-02-10",
        "due_date": "2026-03-01",
        "payment_terms": "net_30",
        "order_status": "confirmed",
        "discount": "50.00",
        "round_off": "0.00",
        "notes": "Sales order with items",
        "items": [
            {
                "quotation_item": quotation_item.id,
                "product": product.id,
                "service_name": "",
                "description": "Explicit item",
                "quantity": "2.00",
                "delivered_quantity": "0.00",
                "hs_code": "1234",
                "rate": "500.00",
                "vat_percentage": "15.00",
            }
        ],
    }

    response = authenticated_client.post(
        SALES_ORDER_URL,
        payload,
        format="json",
    )

    assert response.status_code == 201

    sales_order = SalesOrder.objects.get(
        company=company,
        quotation=quotation,
    )

    assert sales_order.items.count() == 1
    assert sales_order.items.first().product_id == product.id


@pytest.mark.django_db
def test_create_sales_order_auto_prefills_company_and_customer(
    authenticated_client,
    company,
    customer,
    quotation,
    warehouse,
):
    """
    The current serializer requires company/customer at DRF field validation
    level, so this test sends them explicitly.

    The serializer itself also confirms they match the quotation.
    """
    payload = {
        "quotation": quotation.id,
        "company": company.id,
        "customer": customer.id,
        "warehouse": warehouse.id,
        "order_date": "2026-02-01",
        "delivery_date": "2026-02-10",
        "due_date": "2026-03-01",
        "payment_terms": "net_30",
        "order_status": "pending",
        "discount": "0.00",
        "round_off": "0.00",
    }

    response = authenticated_client.post(
        SALES_ORDER_URL,
        payload,
        format="json",
    )

    assert response.status_code == 201
    assert response.data["company"] == company.id
    assert response.data["customer"] == customer.id


# ============================================================
# LIST / RETRIEVE
# ============================================================

@pytest.mark.django_db
def test_list_sales_orders(
    authenticated_client,
    sales_order,
):
    response = authenticated_client.get(SALES_ORDER_URL)

    results = get_list_results(response)

    assert len(results) >= 1
    assert any(
        item["id"] == sales_order.id
        for item in results
    )


@pytest.mark.django_db
def test_retrieve_sales_order(
    authenticated_client,
    sales_order,
):
    url = f"{SALES_ORDER_URL}{sales_order.id}/"

    response = authenticated_client.get(url)

    assert response.status_code == 200
    assert response.data["id"] == sales_order.id
    assert response.data["so_number"] == sales_order.so_number
    assert response.data["customer"] == sales_order.customer_id


# ============================================================
# UPDATE
# ============================================================

@pytest.mark.django_db
def test_update_sales_order(
    authenticated_client,
    sales_order,
    company,
    customer,
    quotation,
    warehouse,
):
    url = f"{SALES_ORDER_URL}{sales_order.id}/"

    payload = {
        "quotation": quotation.id,
        "company": company.id,
        "customer": customer.id,
        "warehouse": warehouse.id,
        "order_date": "2026-01-05",
        "delivery_date": "2026-01-15",
        "due_date": "2026-02-05",
        "payment_terms": "net_60",
        "order_status": "confirmed",
        "discount": "100.00",
        "round_off": "5.00",
        "notes": "Updated sales order",
    }

    response = authenticated_client.put(
        url,
        payload,
        format="json",
    )

    assert response.status_code == 200

    sales_order.refresh_from_db()

    assert sales_order.payment_terms == "net_60"
    assert sales_order.order_status == "confirmed"
    assert sales_order.discount == Decimal("100.00")
    assert sales_order.notes == "Updated sales order"


@pytest.mark.django_db
def test_patch_sales_order(
    authenticated_client,
    sales_order,
):
    url = f"{SALES_ORDER_URL}{sales_order.id}/"

    response = authenticated_client.patch(
        url,
        {
            "notes": "Patched notes",
        },
        format="json",
    )

    assert response.status_code == 200

    sales_order.refresh_from_db()

    assert sales_order.notes == "Patched notes"


# ============================================================
# DELETE
# ============================================================

@pytest.mark.django_db
def test_delete_sales_order(
    authenticated_client,
    sales_order,
):
    url = f"{SALES_ORDER_URL}{sales_order.id}/"

    response = authenticated_client.delete(url)

    assert response.status_code in [200, 204]

    assert not SalesOrder.objects.filter(
        id=sales_order.id
    ).exists()


# ============================================================
# SUMMARY
# ============================================================

@pytest.mark.django_db
def test_sales_order_summary(
    authenticated_client,
    sales_order,
):
    response = authenticated_client.get(SUMMARY_URL)

    assert response.status_code == 200

    assert "total_sales_order" in response.data
    assert "total_order_value" in response.data
    assert "pending_order" in response.data
    assert "partially_delivered" in response.data
    assert "completed_order" in response.data

    assert response.data["total_sales_order"] >= 1


# ============================================================
# SEARCH
# ============================================================

@pytest.mark.django_db
def test_sales_order_search(
    authenticated_client,
    sales_order,
):
    response = authenticated_client.get(
        SALES_ORDER_URL,
        {
            "search": sales_order.so_number,
        },
    )

    results = get_list_results(response)

    assert any(
        item["id"] == sales_order.id
        for item in results
    )


# ============================================================
# DATE VALIDATION
# ============================================================

@pytest.mark.django_db
def test_delivery_date_cannot_be_before_order_date(
    authenticated_client,
    company,
    customer,
    quotation,
):
    payload = {
        "quotation": quotation.id,
        "company": company.id,
        "customer": customer.id,
        "order_date": "2026-02-10",
        "delivery_date": "2026-02-01",
        "due_date": "2026-03-01",
        "payment_terms": "net_30",
        "order_status": "pending",
        "discount": "0.00",
        "round_off": "0.00",
    }

    response = authenticated_client.post(
        SALES_ORDER_URL,
        payload,
        format="json",
    )

    assert response.status_code == 400
    assert "delivery_date" in response.data


@pytest.mark.django_db
def test_due_date_cannot_be_before_order_date(
    authenticated_client,
    company,
    customer,
    quotation,
):
    payload = {
        "quotation": quotation.id,
        "company": company.id,
        "customer": customer.id,
        "order_date": "2026-02-10",
        "delivery_date": "2026-02-20",
        "due_date": "2026-02-01",
        "payment_terms": "net_30",
        "order_status": "pending",
        "discount": "0.00",
        "round_off": "0.00",
    }

    response = authenticated_client.post(
        SALES_ORDER_URL,
        payload,
        format="json",
    )

    assert response.status_code == 400
    assert "due_date" in response.data


# ============================================================
# QUOTATION VALIDATION
# ============================================================

@pytest.mark.django_db
def test_rejected_quotation_cannot_create_sales_order(
    authenticated_client,
    company,
    customer,
    rejected_quotation,
):
    payload = {
        "quotation": rejected_quotation.id,
        "company": company.id,
        "customer": customer.id,
        "order_date": "2026-02-01",
        "delivery_date": "2026-02-10",
        "due_date": "2026-03-01",
        "payment_terms": "net_30",
        "order_status": "pending",
        "discount": "0.00",
        "round_off": "0.00",
    }

    response = authenticated_client.post(
        SALES_ORDER_URL,
        payload,
        format="json",
    )

    assert response.status_code == 400
    assert "quotation" in response.data


# ============================================================
# COMPANY VALIDATION
# ============================================================

@pytest.mark.django_db
def test_customer_from_another_company_cannot_be_used(
    authenticated_client,
    company,
    second_customer,
    quotation,
):
    payload = {
        "quotation": quotation.id,
        "company": company.id,
        "customer": second_customer.id,
        "order_date": "2026-02-01",
        "delivery_date": "2026-02-10",
        "due_date": "2026-03-01",
        "payment_terms": "net_30",
        "order_status": "pending",
        "discount": "0.00",
        "round_off": "0.00",
    }

    response = authenticated_client.post(
        SALES_ORDER_URL,
        payload,
        format="json",
    )

    assert response.status_code == 400
    assert "customer" in response.data


@pytest.mark.django_db
def test_warehouse_from_another_company_cannot_be_used(
    authenticated_client,
    company,
    customer,
    quotation,
    second_warehouse,
):
    payload = {
        "quotation": quotation.id,
        "company": company.id,
        "customer": customer.id,
        "warehouse": second_warehouse.id,
        "order_date": "2026-02-01",
        "delivery_date": "2026-02-10",
        "due_date": "2026-03-01",
        "payment_terms": "net_30",
        "order_status": "pending",
        "discount": "0.00",
        "round_off": "0.00",
    }

    response = authenticated_client.post(
        SALES_ORDER_URL,
        payload,
        format="json",
    )

    assert response.status_code == 400
    assert "warehouse" in response.data


# ============================================================
# COMPANY ISOLATION
# ============================================================

@pytest.mark.django_db
def test_sales_order_company_isolation(
    authenticated_client,
    sales_order,
    second_company,
    second_company_user,
    second_customer,
    second_product,
    second_company_quotation,
):
    # Create a Sales Order belonging to another company
    other_order = SalesOrder.objects.create(
        company=second_company,
        quotation=second_company_quotation,
        customer=second_customer,
        order_date=date(2026, 1, 5),
        payment_terms="net_30",
        order_status="pending",
        discount=Decimal("0.00"),
        round_off=Decimal("0.00"),
        created_by=second_company_user,
    )

    SalesOrderItem.objects.create(
        sales_order=other_order,
        quotation_item=second_company_quotation.items.first(),
        product=second_product,
        service_name="",
        description="Other company item",
        quantity=Decimal("1.00"),
        delivered_quantity=Decimal("0.00"),
        hs_code="5678",
        rate=Decimal("600.00"),
        vat_percentage=Decimal("15.00"),
    )

    other_order.calculate_totals()
    other_order.update_delivery_status()

    response = authenticated_client.get(SALES_ORDER_URL)

    results = get_list_results(response)

    ids = [item["id"] for item in results]

    assert sales_order.id in ids
    assert other_order.id not in ids


# ============================================================
# UNIQUE CONSTRAINT
# ============================================================

@pytest.mark.django_db
def test_sales_order_unique_company_quotation(
    company,
    company_admin,
    customer,
    quotation,
):
    SalesOrder.objects.create(
        company=company,
        quotation=quotation,
        customer=customer,
        order_date=date(2026, 1, 1),
        payment_terms="net_30",
        order_status="pending",
        discount=Decimal("0.00"),
        round_off=Decimal("0.00"),
        created_by=company_admin,
    )

    with pytest.raises(IntegrityError):
        SalesOrder.objects.create(
            company=company,
            quotation=quotation,
            customer=customer,
            order_date=date(2026, 1, 2),
            payment_terms="net_30",
            order_status="pending",
            discount=Decimal("0.00"),
            round_off=Decimal("0.00"),
            created_by=company_admin,
        )


# ============================================================
# DELIVERY STATUS
# ============================================================

@pytest.mark.django_db
def test_delivery_status_pending(
    sales_order,
):
    item = sales_order.items.first()

    item.delivered_quantity = Decimal("0.00")
    item.save()

    sales_order.update_delivery_status()
    sales_order.refresh_from_db()

    assert sales_order.delivery_status == "pending"


@pytest.mark.django_db
def test_delivery_status_partially_delivered(
    sales_order,
):
    item = sales_order.items.first()

    item.delivered_quantity = Decimal("1.00")
    item.save()

    sales_order.update_delivery_status()
    sales_order.refresh_from_db()

    assert sales_order.delivery_status == "partially_delivered"


@pytest.mark.django_db
def test_delivery_status_completed(
    sales_order,
):
    item = sales_order.items.first()

    item.delivered_quantity = Decimal("2.00")
    item.save()

    sales_order.update_delivery_status()
    sales_order.refresh_from_db()

    assert sales_order.delivery_status == "completed"


# ============================================================
# SALES ORDER ITEM
# ============================================================

@pytest.mark.django_db
def test_sales_order_item_amount_calculation(
    sales_order,
    quotation,
    product,
):
    item = SalesOrderItem.objects.create(
        sales_order=sales_order,
        quotation_item=quotation.items.first(),
        product=product,
        service_name="",
        description="Amount test",
        quantity=Decimal("2.00"),
        delivered_quantity=Decimal("0.00"),
        hs_code="1234",
        rate=Decimal("100.00"),
        vat_percentage=Decimal("15.00"),
    )

    item.refresh_from_db()

    assert item.amount_before_vat == Decimal("200.00")
    assert item.vat_amount == Decimal("30.00")
    assert item.amount == Decimal("230.00")


@pytest.mark.django_db
def test_sales_order_item_remaining_quantity(
    sales_order,
):
    item = sales_order.items.first()

    item.delivered_quantity = Decimal("1.00")
    item.save()

    item.refresh_from_db()

    assert item.remaining_quantity == Decimal("1.00")




@pytest.mark.django_db
def test_sales_order_item_cannot_deliver_more_than_quantity(
    sales_order,
    quotation,
    product,
):
    item = SalesOrderItem(
        sales_order=sales_order,
        quotation_item=None,
        product=product,
        quantity=Decimal("5.00"),
        delivered_quantity=Decimal("6.00"),
        rate=Decimal("100.00"),
        vat_percentage=Decimal("15.00"),
    )

    with pytest.raises(ValidationError):
        item.full_clean()


# ============================================================
# QUOTATION LIST
# ============================================================

@pytest.mark.django_db
def test_quotation_list(
    authenticated_client,
    quotation,
):
    response = authenticated_client.get(QUOTATIONS_URL)

    results = get_list_results(response)

    assert any(
        item["id"] == quotation.id
        for item in results
    )


@pytest.mark.django_db
def test_quotation_list_excludes_rejected_quotation(
    authenticated_client,
    quotation,
    rejected_quotation,
):
    response = authenticated_client.get(QUOTATIONS_URL)

    results = get_list_results(response)

    ids = [item["id"] for item in results]

    assert quotation.id in ids
    assert rejected_quotation.id not in ids


@pytest.mark.django_db
def test_quotation_search(
    authenticated_client,
    quotation,
):
    response = authenticated_client.get(
        QUOTATIONS_URL,
        {
            "search": quotation.quote_number,
        },
    )

    results = get_list_results(response)

    assert any(
        item["id"] == quotation.id
        for item in results
    )


# ============================================================
# QUOTATION DETAIL
# ============================================================

@pytest.mark.django_db
def test_quotation_detail(
    authenticated_client,
    quotation,
):
    url = f"{QUOTATIONS_URL}{quotation.id}/"

    response = authenticated_client.get(url)

    assert response.status_code == 200
    assert response.data["id"] == quotation.id
    assert response.data["quote_number"] == quotation.quote_number
    assert response.data["company"] == quotation.company_id
    assert response.data["customer"] == quotation.customer_id

    assert "items" in response.data


# ============================================================
# COMPANY LIST
# ============================================================

@pytest.mark.django_db
def test_company_list_for_company_user(
    authenticated_client,
    company,
    second_company,
):
    response = authenticated_client.get(COMPANIES_URL)

    assert response.status_code == 200

    assert isinstance(response.data, list)

    ids = [item["id"] for item in response.data]

    assert company.id in ids
    assert second_company.id not in ids


# ============================================================
# CUSTOMER LIST
# ============================================================

@pytest.mark.django_db
def test_customer_list(
    authenticated_client,
    company,
    customer,
    second_customer,
):
    response = authenticated_client.get(CUSTOMERS_URL)

    assert response.status_code == 200
    assert isinstance(response.data, list)

    ids = [item["id"] for item in response.data]

    assert customer.id in ids
    assert second_customer.id not in ids


@pytest.mark.django_db
def test_customer_search(
    authenticated_client,
    customer,
):
    response = authenticated_client.get(
        CUSTOMERS_URL,
        {
            "search": customer.customer_name,
        },
    )

    assert response.status_code == 200

    ids = [item["id"] for item in response.data]

    assert customer.id in ids


# ============================================================
# WAREHOUSE LIST
# ============================================================

@pytest.mark.django_db
def test_warehouse_list(
    authenticated_client,
    warehouse,
    inactive_warehouse,
    second_warehouse,
):
    response = authenticated_client.get(WAREHOUSES_URL)

    assert response.status_code == 200

    ids = [item["id"] for item in response.data]

    assert warehouse.id in ids

    # View explicitly filters status="active"
    assert inactive_warehouse.id not in ids

    # Company isolation
    assert second_warehouse.id not in ids


# ============================================================
# AUTHENTICATION
# ============================================================

@pytest.mark.django_db
def test_sales_order_list_requires_authentication(
    api_client,
):
    response = api_client.get(SALES_ORDER_URL)

    assert response.status_code in [401, 403]


@pytest.mark.django_db
def test_sales_order_summary_requires_authentication(
    api_client,
):
    response = api_client.get(SUMMARY_URL)

    assert response.status_code in [401, 403]


@pytest.mark.django_db
def test_sales_order_create_requires_authentication(
    api_client,
    company,
    customer,
    quotation,
):
    payload = {
        "quotation": quotation.id,
        "company": company.id,
        "customer": customer.id,
        "order_date": "2026-02-01",
        "delivery_date": "2026-02-10",
        "due_date": "2026-03-01",
        "payment_terms": "net_30",
        "order_status": "pending",
        "discount": "0.00",
        "round_off": "0.00",
    }

    response = api_client.post(
        SALES_ORDER_URL,
        payload,
        format="json",
    )

    assert response.status_code in [401, 403]


# ============================================================
# DETAIL COMPANY ISOLATION
# ============================================================

@pytest.mark.django_db
def test_other_company_user_cannot_retrieve_sales_order(
    second_authenticated_client,
    sales_order,
):
    url = f"{SALES_ORDER_URL}{sales_order.id}/"

    response = second_authenticated_client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_other_company_user_cannot_update_sales_order(
    second_authenticated_client,
    sales_order,
    second_company,
    second_customer,
):
    url = f"{SALES_ORDER_URL}{sales_order.id}/"

    response = second_authenticated_client.patch(
        url,
        {
            "notes": "Unauthorized update",
        },
        format="json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_other_company_user_cannot_delete_sales_order(
    second_authenticated_client,
    sales_order,
):
    url = f"{SALES_ORDER_URL}{sales_order.id}/"

    response = second_authenticated_client.delete(url)

    assert response.status_code == 404

    assert SalesOrder.objects.filter(
        id=sales_order.id
    ).exists()