import pytest
from decimal import Decimal

from rest_framework.test import APIClient

from user.models import User
from superadmin.models import Company

from finance.category.models import Category
from finance.customer.models import Customer
from finance.product.models import Product
from finance.warehouse.models import Warehouse
from finance.quotation.models import Quotation, QuotationItem
from finance.sales_order.models import SalesOrder, SalesOrderItem
from finance.invoice.models import Invoice, InvoiceItem


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def company(db):
    return Company.objects.create(
        name="Invoice Test Company",
        address="Invoice Address",
        location="Kerala",
        contact_number="9999999999",
        email="invoicecompany@example.com",
        modules={},
        amount_per_employee=0,
        initial_payment=0,
        is_active=True,
    )


@pytest.fixture
def second_company(db):
    return Company.objects.create(
        name="Second Invoice Company",
        address="Second Address",
        location="Kochi",
        contact_number="8888888888",
        email="secondinvoice@example.com",
        modules={},
        amount_per_employee=0,
        initial_payment=0,
        is_active=True,
    )


@pytest.fixture
def hr_admin(db, company):
    return User.objects.create_user(
        username="invoiceadmin",
        email="invoiceadmin@example.com",
        password="TestPassword123",
        is_hr_admin=True,
        company=company,
        is_active=True,
    )


@pytest.fixture
def employee(db, company):
    return User.objects.create_user(
        username="invoiceemployee",
        email="invoiceemployee@example.com",
        password="TestPassword123",
        is_employee=True,
        company=company,
        is_active=True,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer(db, company):
    return Customer.objects.create(
        company=company,
        customer_name="Invoice Customer",
        admin_email="customer@example.com",
        phno="9876543210",
        billing_address="Customer Address",
        client_status="active",
    )


@pytest.fixture
def category(db, company, hr_admin):
    return Category.objects.create(
        company=company,
        code="CAT001",
        category_name="Invoice Category",
        category_type="product",
        status="active",
        created_by=hr_admin,
    )


@pytest.fixture
def product(db, company, category):
    return Product.objects.create(
        company=company,
        product_name="Invoice Product",
        selling_price=Decimal("1000.00"),
        cost_price=Decimal("700.00"),
        quantity=Decimal("10.00"),
        current_stock=Decimal("10.00"),
        tax_rate=Decimal("15.00"),
        category=category,
        status="active",
    )


@pytest.fixture
def warehouse(db, company):
    return Warehouse.objects.create(
        company=company,
        warehouse_name="Invoice Warehouse",
        warehouse_type="main",
        status="active",
    )


@pytest.fixture
def quotation(db, company, customer, product, hr_admin):
    quotation = Quotation.objects.create(
        company=company,
        customer=customer,
        issue_date="2026-09-17",
        valid_till="2026-09-30",
        status="approved",
        created_by=hr_admin,
    )

    QuotationItem.objects.create(
        quotation=quotation,
        product=product,
        quantity=Decimal("2.00"),
        rate=Decimal("1000.00"),
        vat_percentage=Decimal("15.00"),
    )

    return quotation


@pytest.fixture
def sales_order(
    db,
    company,
    customer,
    warehouse,
    quotation,
    product,
    hr_admin,
):
    sales_order = SalesOrder.objects.create(
        company=company,
        quotation=quotation,
        customer=customer,
        warehouse=warehouse,
        order_date="2026-09-17",
        delivery_date="2026-09-25",
        due_date="2026-10-02",
        payment_terms="net_15",
        order_status="confirmed",
        delivery_status="pending",
        discount=Decimal("0.00"),
        round_off=Decimal("0.00"),
        created_by=hr_admin,
    )

    SalesOrderItem.objects.create(
        sales_order=sales_order,
        product=product,
        service_name="Invoice Product",
        description="Invoice Product Description",
        quantity=Decimal("2.00"),
        rate=Decimal("1000.00"),
        vat_percentage=Decimal("15.00"),
    )

    sales_order.calculate_totals()

    return sales_order


@pytest.fixture
def invoice(
    db,
    company,
    customer,
    sales_order,
    hr_admin,
):
    invoice = Invoice.objects.create(
        company=company,
        customer=customer,
        sales_order=sales_order,
        invoice_date="2026-09-17",
        due_date="2026-10-02",
        customer_name=customer.customer_name,
        customer_email=customer.admin_email,
        customer_phone=customer.phno,
        customer_address=customer.billing_address,
        company_name=company.name,
        company_email=company.email,
        company_phone=company.contact_number,
        company_address=company.address,
        amount_paid=Decimal("0.00"),
        subtotal=Decimal("2000.00"),
        total_vat=Decimal("300.00"),
        total_amount=Decimal("2300.00"),
        created_by=hr_admin,
    )

    so_item = sales_order.items.first()

    InvoiceItem.objects.create(
        invoice=invoice,
        sales_order_item=so_item,
        product=so_item.product,
        particular="Invoice Product",
        quantity=Decimal("2.00"),
        hs_code="HS001",
        rate=Decimal("1000.00"),
        vat_percentage=Decimal("15.00"),
    )

    return invoice


# ============================================================
# SALES ORDER DROPDOWN
# ============================================================


@pytest.mark.django_db
def test_get_sales_order_dropdown(
    api_client,
    hr_admin,
    sales_order,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/invoice/sales-orders/"
    )

    assert response.status_code == 200
    assert response.data["message"] == (
        "Sales orders retrieved successfully."
    )

    data = response.data["data"]

    assert len(data) == 1
    assert data[0]["id"] == sales_order.id
    assert data[0]["so_number"] == sales_order.so_number


# ============================================================
# SALES ORDER DETAILS
# ============================================================


@pytest.mark.django_db
def test_get_sales_order_details(
    api_client,
    hr_admin,
    sales_order,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        f"/api/finance/invoice/sales-orders/{sales_order.id}/"
    )

    assert response.status_code == 200

    assert response.data["message"] == (
        "Sales order details retrieved successfully."
    )

    data = response.data["data"]

    assert data["id"] == sales_order.id
    assert "items" in data
    assert len(data["items"]) == 1

    assert Decimal(str(data["items"][0]["quantity"])) == Decimal("2.00")


# ============================================================
# CREATE INVOICE
# ============================================================


@pytest.mark.django_db
def test_create_invoice_from_sales_order(
    api_client,
    hr_admin,
    sales_order,
):
    api_client.force_authenticate(user=hr_admin)

    payload = {
        "sales_order": sales_order.id,
        "invoice_date": "2026-09-17",
        "due_date": "2026-10-02",
        "account_holder": "Test Bank",
        "account_number": "1234567890",
        "iban": "AE123456789012345678901",
        "amount_paid": "0.00",
    }

    response = api_client.post(
        "/api/finance/invoice/",
        payload,
        format="json",
    )

    assert response.status_code == 201

    assert response.data["message"] == (
        "Invoice created successfully."
    )

    invoice = Invoice.objects.get(
        sales_order=sales_order
    )

    assert invoice.company == sales_order.company
    assert invoice.customer == sales_order.customer
    assert invoice.sales_order == sales_order

    assert invoice.subtotal == Decimal("2000.00")
    assert invoice.total_vat == Decimal("300.00")
    assert invoice.total_amount == Decimal("2300.00")


# ============================================================
# LIST INVOICES
# ============================================================


@pytest.mark.django_db
def test_list_invoices(
    api_client,
    hr_admin,
    invoice,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/invoice/"
    )

    assert response.status_code == 200

    assert "results" in response.data
    assert len(response.data["results"]) == 1


# ============================================================
# RETRIEVE INVOICE
# ============================================================


@pytest.mark.django_db
def test_retrieve_invoice(
    api_client,
    hr_admin,
    invoice,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        f"/api/finance/invoice/{invoice.id}/"
    )

    assert response.status_code == 200

    assert response.data["message"] == (
        "Invoice retrieved successfully."
    )

    data = response.data["data"]

    assert data["id"] == invoice.id


# ============================================================
# UPDATE INVOICE
# ============================================================


@pytest.mark.django_db
def test_update_invoice(
    api_client,
    hr_admin,
    invoice,
):
    api_client.force_authenticate(user=hr_admin)

    payload = {
        "invoice_date": "2026-09-18",
        "due_date": "2026-10-05",
        "account_holder": "Updated Bank",
        "account_number": "9876543210",
        "iban": "AE987654321098765432109",
        "amount_paid": "1000.00",
    }

    response = api_client.put(
        f"/api/finance/invoice/{invoice.id}/",
        payload,
        format="json",
    )

    assert response.status_code == 200

    invoice.refresh_from_db()

    assert invoice.invoice_date.strftime(
        "%Y-%m-%d"
    ) == "2026-09-18"

    assert invoice.due_date.strftime(
        "%Y-%m-%d"
    ) == "2026-10-05"

    assert invoice.account_holder == "Updated Bank"
    assert invoice.account_number == "9876543210"
    assert invoice.iban == "AE987654321098765432109"
    assert invoice.amount_paid == Decimal("1000.00")


# ============================================================
# PATCH PAYMENT
# ============================================================


@pytest.mark.django_db
def test_patch_invoice_payment(
    api_client,
    hr_admin,
    invoice,
):
    api_client.force_authenticate(user=hr_admin)

    payload = {
        "amount_paid": "2300.00"
    }

    response = api_client.patch(
        f"/api/finance/invoice/{invoice.id}/",
        payload,
        format="json",
    )

    assert response.status_code == 200

    invoice.refresh_from_db()

    assert invoice.amount_paid == Decimal("2300.00")
    assert invoice.payment_status == "paid"


# ============================================================
# INVOICE SUMMARY
# ============================================================


@pytest.mark.django_db
def test_invoice_summary(
    api_client,
    hr_admin,
    invoice,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/invoice/summary/"
    )

    assert response.status_code == 200

    data = response.data

    assert "total_invoice_value" in data
    assert "payment_received" in data
    assert "outstanding_amount" in data
    assert "average_invoice_value" in data
    assert "total_invoice_count" in data

    assert Decimal(str(data["total_invoice_value"])) == Decimal("2300.00")
    assert Decimal(str(data["payment_received"])) == Decimal("0.00")
    assert Decimal(str(data["outstanding_amount"])) == Decimal("2300.00")
    assert Decimal(str(data["average_invoice_value"])) == Decimal("2300.00")
    assert data["total_invoice_count"] == 1


# ============================================================
# SEARCH INVOICE
# ============================================================


@pytest.mark.django_db
def test_search_invoice(
    api_client,
    hr_admin,
    invoice,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/invoice/",
        {
            "search": invoice.invoice_number
        },
    )

    assert response.status_code == 200

    assert "results" in response.data
    assert len(response.data["results"]) == 1


# ============================================================
# FILTER PAYMENT STATUS
# ============================================================


@pytest.mark.django_db
def test_filter_by_payment_status(
    api_client,
    hr_admin,
    invoice,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/invoice/",
        {
            "payment_status": "unpaid"
        },
    )

    assert response.status_code == 200

    assert "results" in response.data
    assert len(response.data["results"]) == 1


# ============================================================
# FILTER SALES ORDER
# ============================================================


@pytest.mark.django_db
def test_filter_by_sales_order(
    api_client,
    hr_admin,
    invoice,
    sales_order,
):
    api_client.force_authenticate(user=hr_admin)

    response = api_client.get(
        "/api/finance/invoice/",
        {
            "sales_order": sales_order.id
        },
    )

    assert response.status_code == 200

    assert "results" in response.data
    assert len(response.data["results"]) == 1


# ============================================================
# DUPLICATE INVOICE
# ============================================================


@pytest.mark.django_db
def test_duplicate_invoice_for_sales_order(
    api_client,
    hr_admin,
    invoice,
    sales_order,
):
    api_client.force_authenticate(user=hr_admin)

    payload = {
        "sales_order": sales_order.id,
        "invoice_date": "2026-09-17",
        "due_date": "2026-10-02",
        "account_holder": "Test Bank",
        "account_number": "1234567890",
        "iban": "AE123456789012345678901",
        "amount_paid": "0.00",
    }

    response = api_client.post(
        "/api/finance/invoice/",
        payload,
        format="json",
    )

    assert response.status_code in [400, 409]


# ============================================================
# REJECTED SALES ORDER
# ============================================================


@pytest.mark.django_db
def test_rejected_sales_order_cannot_create_invoice(
    api_client,
    hr_admin,
    sales_order,
):
    sales_order.order_status = "rejected"
    sales_order.save()

    api_client.force_authenticate(user=hr_admin)

    payload = {
        "sales_order": sales_order.id,
        "invoice_date": "2026-09-17",
        "due_date": "2026-10-02",
        "account_holder": "Test Bank",
        "account_number": "1234567890",
        "iban": "AE123456789012345678901",
        "amount_paid": "0.00",
    }

    response = api_client.post(
        "/api/finance/invoice/",
        payload,
        format="json",
    )

    assert response.status_code == 400


# ============================================================
# INVALID DUE DATE
# ============================================================


@pytest.mark.django_db
def test_invoice_due_date_cannot_be_before_invoice_date(
    api_client,
    hr_admin,
    sales_order,
):
    api_client.force_authenticate(user=hr_admin)

    payload = {
        "sales_order": sales_order.id,
        "invoice_date": "2026-09-17",
        "due_date": "2026-09-10",
        "account_holder": "Test Bank",
        "account_number": "1234567890",
        "iban": "AE123456789012345678901",
        "amount_paid": "0.00",
    }

    response = api_client.post(
        "/api/finance/invoice/",
        payload,
        format="json",
    )

    assert response.status_code == 400


# ============================================================
# UNAUTHENTICATED USER
# ============================================================


@pytest.mark.django_db
def test_unauthenticated_user_cannot_create_invoice(
    api_client,
    sales_order,
):
    payload = {
        "sales_order": sales_order.id,
        "invoice_date": "2026-09-17",
        "due_date": "2026-10-02",
        "account_holder": "Test Bank",
        "account_number": "1234567890",
        "iban": "AE123456789012345678901",
        "amount_paid": "0.00",
    }

    response = api_client.post(
        "/api/finance/invoice/",
        payload,
        format="json",
    )

    assert response.status_code in [401, 403]


# ============================================================
# NON HR ADMIN
# ============================================================


@pytest.mark.django_db
def test_non_hr_admin_cannot_create_invoice(
    api_client,
    employee,
    sales_order,
):
    api_client.force_authenticate(user=employee)

    payload = {
        "sales_order": sales_order.id,
        "invoice_date": "2026-09-17",
        "due_date": "2026-10-02",
        "account_holder": "Test Bank",
        "account_number": "1234567890",
        "iban": "AE123456789012345678901",
        "amount_paid": "0.00",
    }

    response = api_client.post(
        "/api/finance/invoice/",
        payload,
        format="json",
    )

    assert response.status_code == 403


# ============================================================
# COMPANY ISOLATION
# ============================================================


@pytest.mark.django_db
def test_invoice_company_isolation(
    api_client,
    invoice,
    second_company,
):
    second_admin = User.objects.create_user(
        username="secondinvoiceadmin",
        email="secondinvoiceadmin@example.com",
        password="TestPassword123",
        is_hr_admin=True,
        company=second_company,
        is_active=True,
    )

    api_client.force_authenticate(user=second_admin)

    response = api_client.get(
        "/api/finance/invoice/"
    )

    assert response.status_code == 200

    assert "results" in response.data
    assert len(response.data["results"]) == 0


# ============================================================
# OTHER COMPANY INVOICE DETAIL
# ============================================================


@pytest.mark.django_db
def test_cannot_retrieve_other_company_invoice(
    api_client,
    invoice,
    second_company,
):
    second_admin = User.objects.create_user(
        username="secondinvoiceadmindetail",
        email="secondinvoiceadmindetail@example.com",
        password="TestPassword123",
        is_hr_admin=True,
        company=second_company,
        is_active=True,
    )

    api_client.force_authenticate(user=second_admin)

    response = api_client.get(
        f"/api/finance/invoice/{invoice.id}/"
    )

    assert response.status_code == 404