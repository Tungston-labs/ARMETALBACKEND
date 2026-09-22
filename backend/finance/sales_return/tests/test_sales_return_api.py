from decimal import Decimal
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from superadmin.models import Company
from user.models import User
from finance.customer.models import Customer
from finance.product.models import Product
from finance.invoice.models import Invoice, InvoiceItem
from finance.sales_return.models import SalesReturn, SalesReturnItem


@pytest.fixture
def company(db):
    return Company.objects.create(
        name="Tungston Labs",
        address="Tungston Labs, Ullampilly Building",
        contact_number="+91 97783 77526",
        email="info@tungstonlabs.com",
        is_active=True,
    )


@pytest.fixture
def second_company(db):
    return Company.objects.create(
        name="Second Tech Corp",
        address="Second Building, Kochi",
        contact_number="+91 88888 88888",
        email="info@secondtech.com",
        is_active=True,
    )


@pytest.fixture
def hr_admin(db, company):
    return User.objects.create_user(
        username="sr_admin",
        email="sr_admin@tungstonlabs.com",
        password="TestPassword123",
        is_hr_admin=True,
        company=company,
        is_active=True,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer(db, company, hr_admin):
    return Customer.objects.create(
        company=company,
        customer_name="Chicking",
        company_name="Chicking Corp",
        admin_email="info@chicking.com",
        phno="+91 90000 00001",
        billing_address="Chicking HQ, Dubai",
        created_by=hr_admin,
    )


@pytest.fixture
def product1(db, company, hr_admin):
    return Product.objects.create(
        company=company,
        product_name="Product 1",
        cost_price=Decimal("30.00"),
        selling_price=Decimal("42.00"),
        quantity=Decimal("120.00"),
        current_stock=Decimal("120.00"),
        created_by=hr_admin,
    )


@pytest.fixture
def product2(db, company, hr_admin):
    return Product.objects.create(
        company=company,
        product_name="Product 2",
        cost_price=Decimal("40.00"),
        selling_price=Decimal("58.00"),
        quantity=Decimal("40.00"),
        current_stock=Decimal("40.00"),
        created_by=hr_admin,
    )


@pytest.fixture
def product3(db, company, hr_admin):
    return Product.objects.create(
        company=company,
        product_name="Product 3",
        cost_price=Decimal("10.00"),
        selling_price=Decimal("13.00"),
        quantity=Decimal("210.00"),
        current_stock=Decimal("210.00"),
        created_by=hr_admin,
    )


@pytest.fixture
def invoice(db, company, customer, product1, product2, product3, hr_admin):
    inv = Invoice.objects.create(
        company=company,
        customer=customer,
        invoice_number="INV 0123",
        invoice_date="2026-04-17",
        due_date="2026-05-01",
        customer_name=customer.customer_name,
        customer_email=customer.admin_email,
        customer_phone=customer.phno,
        customer_address=customer.billing_address,
        company_name=company.name,
        company_email=company.email,
        company_phone=company.contact_number,
        company_address=company.address,
        subtotal=Decimal("15000.00"),
        total_amount=Decimal("15000.00"),
        created_by=hr_admin,
    )

    InvoiceItem.objects.create(
        invoice=inv,
        product=product1,
        particular="Product 1",
        quantity=Decimal("120.00"),
        rate=Decimal("42.00"),
    )

    InvoiceItem.objects.create(
        invoice=inv,
        product=product2,
        particular="Product 2",
        quantity=Decimal("40.00"),
        rate=Decimal("58.00"),
    )

    InvoiceItem.objects.create(
        invoice=inv,
        product=product3,
        particular="Product 3",
        quantity=Decimal("210.00"),
        rate=Decimal("13.00"),
    )

    return inv


# ============================================================
# TESTS
# ============================================================


@pytest.mark.django_db
def test_create_sales_return_auto_increment(api_client, hr_admin, customer, invoice, product1, product3):
    api_client.force_authenticate(user=hr_admin)

    payload = {
        "invoice": invoice.id,
        "invoice_ref": "INV 0123",
        "customer": customer.id,
        "return_date": "2026-04-17",
        "reason": "wrong_item",
        "invoice_value": "15000.00",
        "already_returned": "0.00",
        "notes": "Damaged and wrong item return from customer",
        "items": [
            {
                "product": product1.id,
                "product_name": "Product 1",
                "invoiced_qty": "120.00",
                "already_returned_qty": "0.00",
                "returning_now_qty": "10.00",
                "condition": "Wrong Item",
                "unit_price": "42.00",
            },
            {
                "product": product3.id,
                "product_name": "Product 3",
                "invoiced_qty": "210.00",
                "already_returned_qty": "0.00",
                "returning_now_qty": "200.00",
                "condition": "Wrong Item",
                "unit_price": "13.00",
            },
        ],
    }

    res = api_client.post("/api/finance/sales-return/", payload, format="json")

    assert res.status_code == status.HTTP_201_CREATED
    assert res.data["return_number"] == "SR - 0123"
    assert Decimal(str(res.data["return_value"])) == Decimal("3020.00")
    assert res.data["items_returned"] == 210
    assert len(res.data["items"]) == 2


@pytest.mark.django_db
def test_sales_return_validation_exceeding_qty(api_client, hr_admin, customer, invoice, product1):
    api_client.force_authenticate(user=hr_admin)

    payload = {
        "invoice": invoice.id,
        "customer": customer.id,
        "return_date": "2026-04-17",
        "reason": "wrong_item",
        "items": [
            {
                "product": product1.id,
                "product_name": "Product 1",
                "invoiced_qty": "120.00",
                "already_returned_qty": "0.00",
                "returning_now_qty": "150.00",
                "unit_price": "42.00",
            }
        ],
    }

    res = api_client.post("/api/finance/sales-return/", payload, format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "items" in res.data


@pytest.mark.django_db
def test_list_sales_returns_with_kpi_and_filters(api_client, hr_admin, customer, invoice):
    api_client.force_authenticate(user=hr_admin)

    SalesReturn.objects.create(
        company=hr_admin.company,
        customer=customer,
        invoice=invoice,
        invoice_ref="INV 0123",
        return_date="2026-04-28",
        reason="damaged_product",
        status="approved",
        return_value=Decimal("25000.00"),
        refunded_amount=Decimal("25000.00"),
        created_by=hr_admin,
    )

    SalesReturn.objects.create(
        company=hr_admin.company,
        customer=customer,
        invoice=invoice,
        invoice_ref="INV 0124",
        return_date="2026-04-28",
        reason="wrong_item",
        status="pending",
        return_value=Decimal("15000.00"),
        refunded_amount=Decimal("0.00"),
        created_by=hr_admin,
    )

    res = api_client.get("/api/finance/sales-return/")
    assert res.status_code == status.HTTP_200_OK
    assert res.data["total_returns"] == 2
    assert Decimal(str(res.data["total_return_value"])) == Decimal("40000.00")
    assert Decimal(str(res.data["refunded_amount"])) == Decimal("25000.00")

    # Filter by status
    res_status = api_client.get("/api/finance/sales-return/?status=approved")
    assert res_status.status_code == status.HTTP_200_OK
    assert len(res_status.data["results"]) == 1
    assert res_status.data["results"][0]["status"] == "approved"

    # Filter by reason
    res_reason = api_client.get("/api/finance/sales-return/?reason=wrong_item")
    assert res_reason.status_code == status.HTTP_200_OK
    assert len(res_reason.data["results"]) == 1

    # Search
    res_search = api_client.get("/api/finance/sales-return/?search=INV 0123")
    assert res_search.status_code == status.HTTP_200_OK
    assert len(res_search.data["results"]) == 1


@pytest.mark.django_db
def test_sales_return_kpi_endpoint(api_client, hr_admin, customer):
    api_client.force_authenticate(user=hr_admin)

    SalesReturn.objects.create(
        company=hr_admin.company,
        customer=customer,
        return_date="2026-04-28",
        reason="quality_issue",
        status="refunded",
        return_value=Decimal("30000.00"),
        refunded_amount=Decimal("30000.00"),
        applied_credits=Decimal("0.00"),
        created_by=hr_admin,
    )

    SalesReturn.objects.create(
        company=hr_admin.company,
        customer=customer,
        return_date="2026-04-28",
        reason="wrong_item",
        status="cancelled",
        return_value=Decimal("10000.00"),
        applied_credits=Decimal("10000.00"),
        created_by=hr_admin,
    )

    res = api_client.get("/api/finance/sales-return/kpi/")
    assert res.status_code == status.HTTP_200_OK
    data = res.data["data"]
    assert data["total_returns"] == 2
    assert Decimal(str(data["total_return_value"])) == Decimal("40000.00")
    assert Decimal(str(data["refunded_amount"])) == Decimal("30000.00")
    assert Decimal(str(data["applied_credits"])) == Decimal("10000.00")
    assert data["cancelled_credits"] == 1


@pytest.mark.django_db
def test_retrieve_update_delete_sales_return(api_client, hr_admin, customer):
    api_client.force_authenticate(user=hr_admin)

    sr = SalesReturn.objects.create(
        company=hr_admin.company,
        customer=customer,
        return_date="2026-04-28",
        reason="damaged_product",
        status="pending",
        return_value=Decimal("5000.00"),
        created_by=hr_admin,
    )

    # GET detail
    res_get = api_client.get(f"/api/finance/sales-return/{sr.id}/")
    assert res_get.status_code == status.HTTP_200_OK
    assert res_get.data["return_number"] == sr.return_number

    # PATCH update status to approved
    res_patch = api_client.patch(
        f"/api/finance/sales-return/{sr.id}/",
        {"status": "approved", "refunded_amount": "5000.00"},
        format="json",
    )
    assert res_patch.status_code == status.HTTP_200_OK
    assert res_patch.data["status"] == "approved"
    assert Decimal(str(res_patch.data["refunded_amount"])) == Decimal("5000.00")

    # DELETE
    res_del = api_client.delete(f"/api/finance/sales-return/{sr.id}/")
    assert res_del.status_code == status.HTTP_204_NO_CONTENT
    assert not SalesReturn.objects.filter(id=sr.id).exists()


@pytest.mark.django_db
def test_sales_return_export_csv(api_client, hr_admin, customer):
    api_client.force_authenticate(user=hr_admin)

    SalesReturn.objects.create(
        company=hr_admin.company,
        customer=customer,
        invoice_ref="INV-EXPORT-001",
        return_date="2026-04-28",
        reason="wrong_item",
        status="approved",
        return_value=Decimal("12000.00"),
        created_by=hr_admin,
    )

    res = api_client.get("/api/finance/sales-return/export/")
    assert res.status_code == status.HTTP_200_OK
    assert "sales_returns_export.csv" in res["Content-Disposition"]
    content = res.content.decode("utf-8")
    assert "INV-EXPORT-001" in content


@pytest.mark.django_db
def test_invoice_prefill_and_dropdown_for_returns(api_client, hr_admin, invoice):
    api_client.force_authenticate(user=hr_admin)

    # Invoices list
    res_inv = api_client.get("/api/finance/sales-return/invoices/")
    assert res_inv.status_code == status.HTTP_200_OK
    assert len(res_inv.data["data"]) == 1
    assert res_inv.data["data"][0]["invoice_number"] == "INV 0123"

    # Invoice prefill detail
    res_prefill = api_client.get(f"/api/finance/sales-return/invoices/{invoice.id}/")
    assert res_prefill.status_code == status.HTTP_200_OK
    data = res_prefill.data["data"]
    assert data["invoice_ref"] == "INV 0123"
    assert Decimal(str(data["invoice_value"])) == Decimal("15000.00")
    assert len(data["items"]) == 3


@pytest.mark.django_db
def test_multi_company_isolation(api_client, hr_admin, second_company, customer):
    second_admin = User.objects.create_user(
        username="second_sr_admin",
        email="admin2@secondtech.com",
        password="TestPassword123",
        is_hr_admin=True,
        company=second_company,
        is_active=True,
    )

    sr = SalesReturn.objects.create(
        company=hr_admin.company,
        customer=customer,
        return_date="2026-04-28",
        reason="damaged_product",
        return_value=Decimal("15000.00"),
    )

    # Authenticate as admin from second company
    api_client.force_authenticate(user=second_admin)

    # List returns for second company should be empty
    res_list = api_client.get("/api/finance/sales-return/")
    assert res_list.status_code == status.HTTP_200_OK
    assert len(res_list.data["results"]) == 0

    # Detail access should return 404
    res_get = api_client.get(f"/api/finance/sales-return/{sr.id}/")
    assert res_get.status_code == status.HTTP_404_NOT_FOUND
