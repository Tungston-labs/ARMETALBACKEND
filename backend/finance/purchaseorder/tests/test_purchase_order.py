from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from finance.purchaseorder.models import (
    PurchaseOrder,
    PurchaseOrderItem,
)
from finance.vendor.models import Vendor
from finance.warehouse.models import Warehouse
from finance.product.models import Product
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
# VENDOR FIXTURES
# =============================================================================

@pytest.fixture
def vendor(db, company):
    return Vendor.objects.create(
        company=company,
        vendor_id="VEN00001",
        name="ABC Suppliers",
    )


@pytest.fixture
def another_vendor(db, another_company):
    return Vendor.objects.create(
        company=another_company,
        vendor_id="VEN00002",
        name="XYZ Suppliers",
    )


# =============================================================================
# WAREHOUSE FIXTURES
# =============================================================================

@pytest.fixture
def warehouse(db, company):
    return Warehouse.objects.create(
        company=company,
        code="WH001",
        warehouse_name="Main Warehouse",
    )


@pytest.fixture
def another_warehouse(db, another_company):
    return Warehouse.objects.create(
        company=another_company,
        code="WH002",
        warehouse_name="Other Warehouse",
    )


# =============================================================================
# PRODUCT FIXTURES
# =============================================================================

@pytest.fixture
def product(db, company):
    return Product.objects.create(
        company=company,
        code="PRD001",
        product_name="Network Cable",
        sku="SKU001",
        product_type="goods",
        cost_price=Decimal("20.00"),
        selling_price=Decimal("30.00"),
        opening_stock_qty=Decimal("0.00"),
        quantity=Decimal("0.00"),
        current_stock=Decimal("0.00"),
        reserved_qty=Decimal("0.00"),
        reorder_level=Decimal("10.00"),
        tax_type="percentage",
        tax_rate=Decimal("5.00"),
        hsn_sac_code="854449",
        description="Network cable",
        status="active",
    )


@pytest.fixture
def another_product(db, another_company):
    return Product.objects.create(
        company=another_company,
        code="PRD002",
        product_name="Other Product",
        sku="SKU002",
        product_type="goods",
        cost_price=Decimal("100.00"),
        selling_price=Decimal("150.00"),
        opening_stock_qty=Decimal("0.00"),
        quantity=Decimal("0.00"),
        current_stock=Decimal("0.00"),
        reserved_qty=Decimal("0.00"),
        reorder_level=Decimal("5.00"),
        tax_type="percentage",
        tax_rate=Decimal("10.00"),
        hsn_sac_code="123456",
        description="Other company product",
        status="active",
    )


# =============================================================================
# PURCHASE ORDER FIXTURE
# =============================================================================

@pytest.fixture
def purchase_order(
    db,
    company,
    user,
    vendor,
    warehouse,
    product,
):
    purchase_order = PurchaseOrder.objects.create(
        company=company,
        vendor=vendor,
        warehouse=warehouse,
        created_by=user,
        po_number="PO00001",
        pr_reference="PR-2026-001",
        order_date="2026-09-29",
        expected_delivery_date="2026-10-10",
        payment_terms="30 days",
        status="pending",
        receipt_status="pending",
        bill_status="pending",
        shipping_method="road",
        subtotal=Decimal("1000.00"),
        total_vat=Decimal("50.00"),
        discount=Decimal("0.00"),
        round_off=Decimal("0.00"),
        total_amount=Decimal("1050.00"),
        notes="Test purchase order",
    )

    PurchaseOrderItem.objects.create(
        purchase_order=purchase_order,
        product=product,
        description="Network Cable",
        quantity=Decimal("10.00"),
        hs_code="854449",
        rate=Decimal("100.00"),
        vat_percentage=Decimal("5.00"),
        vat_amount=Decimal("50.00"),
        amount=Decimal("1050.00"),
    )

    return purchase_order


# =============================================================================
# URL FIXTURES
# =============================================================================

@pytest.fixture
def purchase_order_list_url():
    return reverse("purchase-order-list-create")


@pytest.fixture
def purchase_order_detail_url(purchase_order):
    return reverse(
        "purchase-order-detail",
        kwargs={"pk": purchase_order.pk},
    )


@pytest.fixture
def dashboard_url():
    return reverse("purchase-order-dashboard")


@pytest.fixture
def vendor_dropdown_url():
    return reverse("purchase-order-vendors")


@pytest.fixture
def warehouse_dropdown_url():
    return reverse("purchase-order-warehouses")


@pytest.fixture
def product_dropdown_url():
    return reverse("purchase-order-products")


# =============================================================================
# CREATE PURCHASE ORDER
# =============================================================================

@pytest.mark.django_db
def test_create_purchase_order(
    authenticated_client,
    purchase_order_list_url,
    vendor,
    warehouse,
    product,
    user,
):
    payload = {
        "vendor": vendor.id,
        "pr_reference": "PR-2026-100",
        "order_date": "2026-09-29",
        "expected_delivery_date": "2026-10-10",
        "payment_terms": "30 days",
        "status": "pending",
        "warehouse": warehouse.id,
        "shipping_method": "road",
        "discount": "100.00",
        "round_off": "0.00",
        "notes": "Test PO",
        "items": [
            {
                "product": product.id,
                "description": "Network Cable",
                "quantity": "10.00",
                "hs_code": "854449",
                "rate": "100.00",
                "vat_percentage": "5.00",
            }
        ],
    }

    response = authenticated_client.post(
        purchase_order_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 201

    assert PurchaseOrder.objects.filter(
        pr_reference="PR-2026-100"
    ).exists()

    po = PurchaseOrder.objects.get(
        pr_reference="PR-2026-100"
    )

    assert po.company_id == vendor.company_id
    assert po.vendor_id == vendor.id
    assert po.warehouse_id == warehouse.id
    assert po.created_by_id == user.id

    assert po.subtotal == Decimal("1000.00")
    assert po.total_vat == Decimal("50.00")
    assert po.discount == Decimal("100.00")
    assert po.total_amount == Decimal("950.00")
    assert po.items.count() == 1


# =============================================================================
# CREATE - MULTIPLE ITEMS
# =============================================================================

@pytest.mark.django_db
def test_create_purchase_order_with_multiple_items(
    authenticated_client,
    purchase_order_list_url,
    vendor,
    warehouse,
    product,
):
    payload = {
        "vendor": vendor.id,
        "pr_reference": "PR-MULTI-001",
        "order_date": "2026-09-29",
        "expected_delivery_date": "2026-10-10",
        "payment_terms": "30 days",
        "status": "draft",
        "warehouse": warehouse.id,
        "shipping_method": "road",
        "discount": "0.00",
        "round_off": "0.00",
        "notes": "Multiple items",
        "items": [
            {
                "product": product.id,
                "quantity": "10.00",
                "rate": "100.00",
                "vat_percentage": "5.00",
            },
            {
                "product": product.id,
                "quantity": "5.00",
                "rate": "200.00",
                "vat_percentage": "10.00",
            },
        ],
    }

    response = authenticated_client.post(
        purchase_order_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 201

    po = PurchaseOrder.objects.get(
        pr_reference="PR-MULTI-001"
    )

    assert po.items.count() == 2

    # First item = 1000 + 50 VAT
    # Second item = 1000 + 100 VAT
    # Subtotal = 2000
    # VAT = 150
    # Total = 2150

    assert po.subtotal == Decimal("2000.00")
    assert po.total_vat == Decimal("150.00")
    assert po.total_amount == Decimal("2150.00")


# =============================================================================
# LIST PURCHASE ORDERS
# =============================================================================

@pytest.mark.django_db
def test_list_purchase_orders(
    authenticated_client,
    purchase_order_list_url,
    purchase_order,
):
    response = authenticated_client.get(
        purchase_order_list_url
    )

    assert response.status_code == 200

    results = get_response_results(response)

    assert len(results) >= 1


# =============================================================================
# SEARCH BY PO NUMBER
# =============================================================================

@pytest.mark.django_db
def test_search_purchase_order_by_po_number(
    authenticated_client,
    purchase_order_list_url,
    purchase_order,
):
    response = authenticated_client.get(
        purchase_order_list_url,
        {"search": "PO00001"},
    )

    assert response.status_code == 200

    results = get_response_results(response)

    assert any(
        item["po_number"] == "PO00001"
        for item in results
    )


# =============================================================================
# SEARCH BY VENDOR NAME
# =============================================================================

@pytest.mark.django_db
def test_search_purchase_order_by_vendor_name(
    authenticated_client,
    purchase_order_list_url,
    purchase_order,
):
    response = authenticated_client.get(
        purchase_order_list_url,
        {"search": "ABC"},
    )

    assert response.status_code == 200

    results = get_response_results(response)

    assert len(results) >= 1
    assert results[0]["vendor_name"] == "ABC Suppliers"


# =============================================================================
# SEARCH BY PR REFERENCE
# =============================================================================

@pytest.mark.django_db
def test_search_purchase_order_by_pr_reference(
    authenticated_client,
    purchase_order_list_url,
    purchase_order,
):
    response = authenticated_client.get(
        purchase_order_list_url,
        {"search": "PR-2026-001"},
    )

    assert response.status_code == 200

    results = get_response_results(response)

    assert len(results) >= 1


# =============================================================================
# FILTER BY VENDOR
# =============================================================================

@pytest.mark.django_db
def test_filter_purchase_orders_by_vendor(
    authenticated_client,
    purchase_order_list_url,
    purchase_order,
    vendor,
):
    response = authenticated_client.get(
        purchase_order_list_url,
        {"vendor": vendor.id},
    )

    assert response.status_code == 200

    results = get_response_results(response)

    assert len(results) >= 1

    assert all(
        item["vendor"] == vendor.id
        for item in results
    )


# =============================================================================
# INVALID VENDOR FILTER
# =============================================================================

@pytest.mark.django_db
def test_filter_with_invalid_vendor_id(
    authenticated_client,
    purchase_order_list_url,
):
    response = authenticated_client.get(
        purchase_order_list_url,
        {"vendor": "abc"},
    )

    assert response.status_code == 400
    assert "vendor" in response.json()


# =============================================================================
# FILTER BY STATUS
# =============================================================================

@pytest.mark.django_db
def test_filter_purchase_orders_by_status(
    authenticated_client,
    purchase_order_list_url,
    purchase_order,
):
    response = authenticated_client.get(
        purchase_order_list_url,
        {"status": "pending"},
    )

    assert response.status_code == 200

    results = get_response_results(response)

    assert len(results) >= 1

    assert all(
        item["status"] == "pending"
        for item in results
    )


# =============================================================================
# FILTER BY RECEIPT STATUS
# =============================================================================

@pytest.mark.django_db
def test_filter_purchase_orders_by_receipt_status(
    authenticated_client,
    purchase_order_list_url,
    purchase_order,
):
    response = authenticated_client.get(
        purchase_order_list_url,
        {"receipt_status": "pending"},
    )

    assert response.status_code == 200


# =============================================================================
# FILTER BY BILL STATUS
# =============================================================================

@pytest.mark.django_db
def test_filter_purchase_orders_by_bill_status(
    authenticated_client,
    purchase_order_list_url,
    purchase_order,
):
    response = authenticated_client.get(
        purchase_order_list_url,
        {"bill_status": "pending"},
    )

    assert response.status_code == 200


# =============================================================================
# PURCHASE ORDER DETAIL
# =============================================================================

@pytest.mark.django_db
def test_purchase_order_detail(
    authenticated_client,
    purchase_order_detail_url,
    purchase_order,
):
    response = authenticated_client.get(
        purchase_order_detail_url
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == purchase_order.id
    assert data["po_number"] == "PO00001"
    assert data["vendor"] == purchase_order.vendor_id
    assert data["warehouse"] == purchase_order.warehouse_id

    assert "item_details" in data
    assert len(data["item_details"]) == 1


# =============================================================================
# DASHBOARD
# =============================================================================

@pytest.mark.django_db
def test_purchase_order_dashboard(
    authenticated_client,
    dashboard_url,
    purchase_order,
):
    response = authenticated_client.get(
        dashboard_url
    )

    assert response.status_code == 200

    data = response.json()

    assert "total_purchase_orders" in data
    assert "total_purchase_value" in data
    assert "pending_orders" in data
    assert "partially_received" in data
    assert "completed_orders_this_month" in data

    assert data["total_purchase_orders"] >= 1


# =============================================================================
# VENDOR DROPDOWN
# =============================================================================

@pytest.mark.django_db
def test_vendor_dropdown(
    authenticated_client,
    vendor_dropdown_url,
    vendor,
):
    response = authenticated_client.get(
        vendor_dropdown_url
    )

    assert response.status_code == 200

    data = get_response_results(response)

    assert len(data) >= 1

    vendor_data = next(
        item
        for item in data
        if item["id"] == vendor.id
    )

    assert vendor_data["vendor_id"] == vendor.vendor_id
    assert vendor_data["name"] == vendor.name


# =============================================================================
# WAREHOUSE DROPDOWN
# =============================================================================

@pytest.mark.django_db
def test_warehouse_dropdown(
    authenticated_client,
    warehouse_dropdown_url,
    warehouse,
):
    response = authenticated_client.get(
        warehouse_dropdown_url
    )

    assert response.status_code == 200

    data = get_response_results(response)

    assert len(data) >= 1

    warehouse_data = next(
        item
        for item in data
        if item["id"] == warehouse.id
    )

    assert warehouse_data["code"] == warehouse.code
    assert (
        warehouse_data["warehouse_name"]
        == warehouse.warehouse_name
    )


# =============================================================================
# PRODUCT DROPDOWN
# =============================================================================

@pytest.mark.django_db
def test_product_dropdown(
    authenticated_client,
    product_dropdown_url,
    product,
):
    response = authenticated_client.get(
        product_dropdown_url
    )

    assert response.status_code == 200

    data = get_response_results(response)

    assert len(data) >= 1

    product_data = next(
        item
        for item in data
        if item["id"] == product.id
    )

    assert product_data["code"] == product.code
    assert product_data["product_name"] == product.product_name
    assert product_data["sku"] == product.sku


# =============================================================================
# PRODUCT DROPDOWN SEARCH
# =============================================================================

@pytest.mark.django_db
def test_product_dropdown_search(
    authenticated_client,
    product_dropdown_url,
    product,
):
    response = authenticated_client.get(
        product_dropdown_url,
        {"search": "Network"},
    )

    assert response.status_code == 200

    data = get_response_results(response)

    assert len(data) >= 1

    assert any(
        item["product_name"] == "Network Cable"
        for item in data
    )


# =============================================================================
# PRODUCT DROPDOWN SEARCH BY SKU
# =============================================================================

@pytest.mark.django_db
def test_product_dropdown_search_by_sku(
    authenticated_client,
    product_dropdown_url,
    product,
):
    response = authenticated_client.get(
        product_dropdown_url,
        {"search": "SKU001"},
    )

    assert response.status_code == 200

    data = get_response_results(response)

    assert len(data) >= 1

    assert any(
        item["sku"] == "SKU001"
        for item in data
    )


# =============================================================================
# PRODUCT DROPDOWN - ONLY ACTIVE PRODUCTS
# =============================================================================

@pytest.mark.django_db
def test_product_dropdown_only_returns_active_products(
    authenticated_client,
    product_dropdown_url,
    company,
):
    inactive_product = Product.objects.create(
        company=company,
        code="INACTIVE01",
        product_name="Inactive Product",
        sku="INACTIVE-SKU",
        product_type="goods",
        cost_price=Decimal("50.00"),
        selling_price=Decimal("70.00"),
        opening_stock_qty=Decimal("0.00"),
        quantity=Decimal("0.00"),
        current_stock=Decimal("0.00"),
        reserved_qty=Decimal("0.00"),
        reorder_level=Decimal("5.00"),
        tax_type="percentage",
        tax_rate=Decimal("5.00"),
        status="inactive",
    )

    response = authenticated_client.get(
        product_dropdown_url
    )

    assert response.status_code == 200

    data = get_response_results(response)

    assert not any(
        item["id"] == inactive_product.id
        for item in data
    )


# =============================================================================
# COMPANY ISOLATION - PURCHASE ORDERS
# =============================================================================

@pytest.mark.django_db
def test_purchase_orders_are_company_scoped(
    authenticated_client,
    purchase_order_list_url,
    another_company,
    another_user,
    another_vendor,
    another_warehouse,
    another_product,
):
    other_po = PurchaseOrder.objects.create(
        company=another_company,
        vendor=another_vendor,
        warehouse=another_warehouse,
        created_by=another_user,
        po_number="PO99999",
        pr_reference="OTHER-PR",
        order_date="2026-09-29",
        status="pending",
        receipt_status="pending",
        bill_status="pending",
        shipping_method="road",
        subtotal=Decimal("100.00"),
        total_vat=Decimal("5.00"),
        discount=Decimal("0.00"),
        round_off=Decimal("0.00"),
        total_amount=Decimal("105.00"),
    )

    response = authenticated_client.get(
        purchase_order_list_url
    )

    assert response.status_code == 200

    results = get_response_results(response)

    assert not any(
        item["id"] == other_po.id
        for item in results
    )


# =============================================================================
# COMPANY ISOLATION - VENDOR DROPDOWN
# =============================================================================

@pytest.mark.django_db
def test_vendor_dropdown_is_company_scoped(
    authenticated_client,
    vendor_dropdown_url,
    vendor,
    another_vendor,
):
    response = authenticated_client.get(
        vendor_dropdown_url
    )

    assert response.status_code == 200

    data = get_response_results(response)

    assert any(
        item["id"] == vendor.id
        for item in data
    )

    assert not any(
        item["id"] == another_vendor.id
        for item in data
    )


# =============================================================================
# COMPANY ISOLATION - WAREHOUSE DROPDOWN
# =============================================================================

@pytest.mark.django_db
def test_warehouse_dropdown_is_company_scoped(
    authenticated_client,
    warehouse_dropdown_url,
    warehouse,
    another_warehouse,
):
    response = authenticated_client.get(
        warehouse_dropdown_url
    )

    assert response.status_code == 200

    data = get_response_results(response)

    assert any(
        item["id"] == warehouse.id
        for item in data
    )

    assert not any(
        item["id"] == another_warehouse.id
        for item in data
    )


# =============================================================================
# COMPANY ISOLATION - PRODUCT DROPDOWN
# =============================================================================

@pytest.mark.django_db
def test_product_dropdown_is_company_scoped(
    authenticated_client,
    product_dropdown_url,
    product,
    another_product,
):
    response = authenticated_client.get(
        product_dropdown_url
    )

    assert response.status_code == 200

    data = get_response_results(response)

    assert any(
        item["id"] == product.id
        for item in data
    )

    assert not any(
        item["id"] == another_product.id
        for item in data
    )


# =============================================================================
# CREATE - NO ITEMS
# =============================================================================

@pytest.mark.django_db
def test_create_purchase_order_without_items(
    authenticated_client,
    purchase_order_list_url,
    vendor,
    warehouse,
):
    payload = {
        "vendor": vendor.id,
        "pr_reference": "PR-NO-ITEMS",
        "order_date": "2026-09-29",
        "warehouse": warehouse.id,
        "status": "draft",
        "shipping_method": "road",
        "items": [],
    }

    response = authenticated_client.post(
        purchase_order_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400
    assert "items" in response.json()


# =============================================================================
# CREATE - ZERO QUANTITY
# =============================================================================

@pytest.mark.django_db
def test_create_purchase_order_zero_quantity(
    authenticated_client,
    purchase_order_list_url,
    vendor,
    warehouse,
    product,
):
    payload = {
        "vendor": vendor.id,
        "pr_reference": "PR-ZERO-QTY",
        "order_date": "2026-09-29",
        "warehouse": warehouse.id,
        "status": "draft",
        "shipping_method": "road",
        "items": [
            {
                "product": product.id,
                "quantity": "0",
                "rate": "100.00",
                "vat_percentage": "5.00",
            }
        ],
    }

    response = authenticated_client.post(
        purchase_order_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400


# =============================================================================
# CREATE - NEGATIVE RATE
# =============================================================================

@pytest.mark.django_db
def test_create_purchase_order_negative_rate(
    authenticated_client,
    purchase_order_list_url,
    vendor,
    warehouse,
    product,
):
    payload = {
        "vendor": vendor.id,
        "pr_reference": "PR-NEGATIVE-RATE",
        "order_date": "2026-09-29",
        "warehouse": warehouse.id,
        "status": "draft",
        "shipping_method": "road",
        "items": [
            {
                "product": product.id,
                "quantity": "10.00",
                "rate": "-100.00",
                "vat_percentage": "5.00",
            }
        ],
    }

    response = authenticated_client.post(
        purchase_order_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400


# =============================================================================
# CREATE - INVALID VAT
# =============================================================================

@pytest.mark.django_db
def test_create_purchase_order_invalid_vat(
    authenticated_client,
    purchase_order_list_url,
    vendor,
    warehouse,
    product,
):
    payload = {
        "vendor": vendor.id,
        "pr_reference": "PR-INVALID-VAT",
        "order_date": "2026-09-29",
        "warehouse": warehouse.id,
        "status": "draft",
        "shipping_method": "road",
        "items": [
            {
                "product": product.id,
                "quantity": "10.00",
                "rate": "100.00",
                "vat_percentage": "101.00",
            }
        ],
    }

    response = authenticated_client.post(
        purchase_order_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400


# =============================================================================
# CREATE - DELIVERY DATE BEFORE ORDER DATE
# =============================================================================

@pytest.mark.django_db
def test_create_purchase_order_invalid_delivery_date(
    authenticated_client,
    purchase_order_list_url,
    vendor,
    warehouse,
    product,
):
    payload = {
        "vendor": vendor.id,
        "pr_reference": "PR-INVALID-DATE",
        "order_date": "2026-10-10",
        "expected_delivery_date": "2026-10-01",
        "warehouse": warehouse.id,
        "status": "draft",
        "shipping_method": "road",
        "items": [
            {
                "product": product.id,
                "quantity": "10.00",
                "rate": "100.00",
                "vat_percentage": "5.00",
            }
        ],
    }

    response = authenticated_client.post(
        purchase_order_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400
    assert "expected_delivery_date" in response.json()


# =============================================================================
# CREATE - INVALID COMPANY VENDOR
# =============================================================================

@pytest.mark.django_db
def test_create_purchase_order_with_other_company_vendor(
    authenticated_client,
    purchase_order_list_url,
    another_vendor,
    warehouse,
    product,
):
    payload = {
        "vendor": another_vendor.id,
        "pr_reference": "PR-OTHER-VENDOR",
        "order_date": "2026-09-29",
        "warehouse": warehouse.id,
        "status": "draft",
        "shipping_method": "road",
        "items": [
            {
                "product": product.id,
                "quantity": "10.00",
                "rate": "100.00",
                "vat_percentage": "5.00",
            }
        ],
    }

    response = authenticated_client.post(
        purchase_order_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400


# =============================================================================
# CREATE - INVALID COMPANY WAREHOUSE
# =============================================================================

@pytest.mark.django_db
def test_create_purchase_order_with_other_company_warehouse(
    authenticated_client,
    purchase_order_list_url,
    vendor,
    another_warehouse,
    product,
):
    payload = {
        "vendor": vendor.id,
        "pr_reference": "PR-OTHER-WH",
        "order_date": "2026-09-29",
        "warehouse": another_warehouse.id,
        "status": "draft",
        "shipping_method": "road",
        "items": [
            {
                "product": product.id,
                "quantity": "10.00",
                "rate": "100.00",
                "vat_percentage": "5.00",
            }
        ],
    }

    response = authenticated_client.post(
        purchase_order_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400


# =============================================================================
# CREATE - INVALID COMPANY PRODUCT
# =============================================================================

@pytest.mark.django_db
def test_create_purchase_order_with_other_company_product(
    authenticated_client,
    purchase_order_list_url,
    vendor,
    warehouse,
    another_product,
):
    payload = {
        "vendor": vendor.id,
        "pr_reference": "PR-OTHER-PRODUCT",
        "order_date": "2026-09-29",
        "warehouse": warehouse.id,
        "status": "draft",
        "shipping_method": "road",
        "items": [
            {
                "product": another_product.id,
                "quantity": "10.00",
                "rate": "100.00",
                "vat_percentage": "5.00",
            }
        ],
    }

    response = authenticated_client.post(
        purchase_order_list_url,
        payload,
        format="json",
    )

    assert response.status_code == 400


# =============================================================================
# UNAUTHENTICATED - LIST
# =============================================================================

@pytest.mark.django_db
def test_purchase_order_list_requires_authentication(
    api_client,
    purchase_order_list_url,
):
    response = api_client.get(
        purchase_order_list_url
    )

    assert response.status_code in [401, 403]


# =============================================================================
# UNAUTHENTICATED - DASHBOARD
# =============================================================================

@pytest.mark.django_db
def test_purchase_order_dashboard_requires_authentication(
    api_client,
    dashboard_url,
):
    response = api_client.get(
        dashboard_url
    )

    assert response.status_code in [401, 403]


# =============================================================================
# UNAUTHENTICATED - VENDOR DROPDOWN
# =============================================================================

@pytest.mark.django_db
def test_vendor_dropdown_requires_authentication(
    api_client,
    vendor_dropdown_url,
):
    response = api_client.get(
        vendor_dropdown_url
    )

    assert response.status_code in [401, 403]


# =============================================================================
# UNAUTHENTICATED - WAREHOUSE DROPDOWN
# =============================================================================

@pytest.mark.django_db
def test_warehouse_dropdown_requires_authentication(
    api_client,
    warehouse_dropdown_url,
):
    response = api_client.get(
        warehouse_dropdown_url
    )

    assert response.status_code in [401, 403]


# =============================================================================
# UNAUTHENTICATED - PRODUCT DROPDOWN
# =============================================================================

@pytest.mark.django_db
def test_product_dropdown_requires_authentication(
    api_client,
    product_dropdown_url,
):
    response = api_client.get(
        product_dropdown_url
    )

    assert response.status_code in [401, 403]