from datetime import timedelta
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from finance.customer.models import Customer
from finance.invoice.models import Invoice
from finance.payment.models import Payment
from superadmin.models import Company

User = get_user_model()


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def company(db):
    return Company.objects.create(name="Armetal Test Company", email="armetal@test.com")


@pytest.fixture
def another_company(db):
    return Company.objects.create(name="Other Company LLC", email="other@test.com")


@pytest.fixture
def user(company):
    user_obj = User.objects.create_user(
        username="payment_admin",
        email="paymentadmin@test.com",
        password="TestPassword@123",
    )
    user_obj.company = company
    if hasattr(user_obj, "role"):
        user_obj.role = "hr_admin"
    if hasattr(user_obj, "is_hr_admin"):
        user_obj.is_hr_admin = True
    user_obj.save()
    return user_obj


@pytest.fixture
def another_user(another_company):
    user_obj = User.objects.create_user(
        username="other_admin",
        email="otheradmin@test.com",
        password="TestPassword@123",
    )
    user_obj.company = another_company
    if hasattr(user_obj, "role"):
        user_obj.role = "hr_admin"
    if hasattr(user_obj, "is_hr_admin"):
        user_obj.is_hr_admin = True
    user_obj.save()
    return user_obj


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def customer(company, user):
    return Customer.objects.create(
        company=company,
        customer_name="Mediora Tech",
        industry="technology",
        currency="SAR",
        created_by=user,
    )


@pytest.fixture
def another_customer(company, user):
    return Customer.objects.create(
        company=company,
        customer_name="Chicking Ltd",
        industry="retail",
        currency="SAR",
        created_by=user,
    )


@pytest.fixture
def other_company_customer(another_company, another_user):
    return Customer.objects.create(
        company=another_company,
        customer_name="Foreign Customer",
        industry="retail",
        currency="SAR",
        created_by=another_user,
    )


@pytest.fixture
def invoice(company, customer, user):
    today = timezone.now().date()
    return Invoice.objects.create(
        company=company,
        customer=customer,
        invoice_date=today,
        due_date=today + timedelta(days=30),
        subtotal=Decimal("200000.00"),
        total_vat=Decimal("30000.00"),
        total_amount=Decimal("230000.00"),
        amount_paid=Decimal("0.00"),
        payment_status="unpaid",
        created_by=user,
    )


@pytest.fixture
def overdue_invoice(company, customer, user):
    today = timezone.now().date()
    return Invoice.objects.create(
        company=company,
        customer=customer,
        invoice_date=today - timedelta(days=45),
        due_date=today - timedelta(days=15),
        subtotal=Decimal("100000.00"),
        total_vat=Decimal("15000.00"),
        total_amount=Decimal("115000.00"),
        amount_paid=Decimal("0.00"),
        payment_status="unpaid",
        created_by=user,
    )


def payment_list_url():
    return "/api/finance/payment/"


def payment_detail_url(payment_id):
    return f"/api/finance/payment/{payment_id}/"


def payment_kpi_url():
    return "/api/finance/payment/kpi/"


def payment_export_url():
    return "/api/finance/payment/export/"


# ============================================================
# 1. CREATE PAYMENT & RECEIPT NUMBER AUTO-INCREMENT
# ============================================================

@pytest.mark.django_db
def test_create_payment_success(authenticated_client, company, customer, invoice):
    today = str(timezone.now().date())
    payload = {
        "customer": customer.id,
        "invoice": invoice.id,
        "payment_date": today,
        "payment_type": "full_payment",
        "payment_method": "bank_transfer",
        "amount_received": "230000.00",
        "reference_number": "REF-998877",
        "notes": "Full payment via bank transfer",
        "status": "completed",
    }

    response = authenticated_client.post(payment_list_url(), payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["message"] == "Payment recorded successfully."

    data = response.data["data"]
    assert data["receipt_number"] == "REC001"
    assert data["customer"] == customer.id
    assert data["customer_name"] == customer.customer_name
    assert data["invoice"] == invoice.id
    assert data["invoice_number"] == invoice.invoice_number
    assert Decimal(data["amount_received"]) == Decimal("230000.00")

    # Verify Invoice status sync
    invoice.refresh_from_db()
    assert invoice.amount_paid == Decimal("230000.00")
    assert invoice.payment_status == "paid"


@pytest.mark.django_db
def test_receipt_number_auto_increments(authenticated_client, customer, invoice):
    today = str(timezone.now().date())

    res1 = authenticated_client.post(payment_list_url(), {
        "customer": customer.id,
        "invoice": invoice.id,
        "payment_date": today,
        "amount_received": "50000.00",
    }, format="json")
    assert res1.status_code == status.HTTP_201_CREATED
    assert res1.data["data"]["receipt_number"] == "REC001"

    res2 = authenticated_client.post(payment_list_url(), {
        "customer": customer.id,
        "invoice": invoice.id,
        "payment_date": today,
        "amount_received": "50000.00",
    }, format="json")
    assert res2.status_code == status.HTTP_201_CREATED
    assert res2.data["data"]["receipt_number"] == "REC002"


@pytest.mark.django_db
def test_auto_derives_customer_from_invoice(authenticated_client, invoice):
    today = str(timezone.now().date())
    res = authenticated_client.post(payment_list_url(), {
        "invoice": invoice.id,
        "payment_date": today,
        "amount_received": "10000.00",
    }, format="json")
    assert res.status_code == status.HTTP_201_CREATED
    assert res.data["data"]["customer"] == invoice.customer.id


# ============================================================
# 2. VALIDATIONS
# ============================================================

@pytest.mark.django_db
def test_invoice_customer_mismatch_validation(authenticated_client, invoice, another_customer):
    today = str(timezone.now().date())
    res = authenticated_client.post(payment_list_url(), {
        "customer": another_customer.id,
        "invoice": invoice.id,
        "payment_date": today,
        "amount_received": "10000.00",
    }, format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "invoice" in res.data


@pytest.mark.django_db
def test_cross_company_customer_validation(authenticated_client, other_company_customer):
    today = str(timezone.now().date())
    res = authenticated_client.post(payment_list_url(), {
        "customer": other_company_customer.id,
        "payment_date": today,
        "amount_received": "10000.00",
    }, format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "customer" in res.data


@pytest.mark.django_db
def test_negative_amount_received_validation(authenticated_client, customer):
    today = str(timezone.now().date())
    res = authenticated_client.post(payment_list_url(), {
        "customer": customer.id,
        "payment_date": today,
        "amount_received": "-500.00",
    }, format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "amount_received" in res.data


# ============================================================
# 3. INVOICE PAYMENT STATUS SYNC (PARTIAL, UPDATE, DELETE)
# ============================================================

@pytest.mark.django_db
def test_invoice_partial_payment_status_sync(authenticated_client, invoice):
    today = str(timezone.now().date())
    res = authenticated_client.post(payment_list_url(), {
        "customer": invoice.customer.id,
        "invoice": invoice.id,
        "payment_date": today,
        "payment_type": "partial_payment",
        "amount_received": "100000.00",
        "status": "completed",
    }, format="json")
    assert res.status_code == status.HTTP_201_CREATED

    invoice.refresh_from_db()
    assert invoice.amount_paid == Decimal("100000.00")
    assert invoice.payment_status == "partially_paid"


@pytest.mark.django_db
def test_update_payment_status_recalculates_invoice(authenticated_client, invoice):
    today = str(timezone.now().date())
    res = authenticated_client.post(payment_list_url(), {
        "customer": invoice.customer.id,
        "invoice": invoice.id,
        "payment_date": today,
        "amount_received": "230000.00",
        "status": "completed",
    }, format="json")
    payment_id = res.data["data"]["id"]

    invoice.refresh_from_db()
    assert invoice.payment_status == "paid"

    # Change payment status to cancelled
    patch_res = authenticated_client.patch(payment_detail_url(payment_id), {
        "status": "cancelled"
    }, format="json")
    assert patch_res.status_code == status.HTTP_200_OK

    invoice.refresh_from_db()
    assert invoice.amount_paid == Decimal("0.00")
    assert invoice.payment_status == "unpaid"


@pytest.mark.django_db
def test_delete_payment_recalculates_invoice(authenticated_client, invoice):
    today = str(timezone.now().date())
    res = authenticated_client.post(payment_list_url(), {
        "customer": invoice.customer.id,
        "invoice": invoice.id,
        "payment_date": today,
        "amount_received": "150000.00",
        "status": "completed",
    }, format="json")
    payment_id = res.data["data"]["id"]

    invoice.refresh_from_db()
    assert invoice.amount_paid == Decimal("150000.00")
    assert invoice.payment_status == "partially_paid"

    del_res = authenticated_client.delete(payment_detail_url(payment_id))
    assert del_res.status_code == status.HTTP_200_OK

    invoice.refresh_from_db()
    assert invoice.amount_paid == Decimal("0.00")
    assert invoice.payment_status == "unpaid"


# ============================================================
# 4. LIST, RETRIEVE, SEARCH, FILTER, ORDERING
# ============================================================

@pytest.mark.django_db
def test_list_and_retrieve_payments(authenticated_client, customer, invoice):
    today = timezone.now().date()
    p1 = Payment.objects.create(
        company=customer.company,
        customer=customer,
        invoice=invoice,
        payment_date=today,
        amount_received=Decimal("50000.00"),
        reference_number="REF-001",
        status="completed",
    )

    list_res = authenticated_client.get(payment_list_url())
    assert list_res.status_code == status.HTTP_200_OK
    results = list_res.data.get("results", list_res.data.get("data"))
    assert len(results) == 1

    detail_res = authenticated_client.get(payment_detail_url(p1.id))
    assert detail_res.status_code == status.HTTP_200_OK
    assert detail_res.data["data"]["id"] == p1.id


@pytest.mark.django_db
def test_search_payments(authenticated_client, customer, another_customer):
    today = timezone.now().date()
    Payment.objects.create(
        company=customer.company,
        customer=customer,
        payment_date=today,
        amount_received=Decimal("50000.00"),
        reference_number="CHECK-12345",
    )
    Payment.objects.create(
        company=another_customer.company,
        customer=another_customer,
        payment_date=today,
        amount_received=Decimal("75000.00"),
        reference_number="ONLINE-9999",
    )

    res = authenticated_client.get(payment_list_url(), {"search": "CHECK-12345"})
    assert res.status_code == status.HTTP_200_OK
    results = res.data.get("results", res.data.get("data"))
    assert len(results) == 1
    assert results[0]["reference_number"] == "CHECK-12345"


@pytest.mark.django_db
def test_filter_payments_by_status_and_method(authenticated_client, customer):
    today = timezone.now().date()
    Payment.objects.create(
        company=customer.company,
        customer=customer,
        payment_date=today,
        payment_method="bank_transfer",
        amount_received=Decimal("10000.00"),
        status="completed",
    )
    Payment.objects.create(
        company=customer.company,
        customer=customer,
        payment_date=today,
        payment_method="cheque",
        amount_received=Decimal("20000.00"),
        status="pending",
    )

    res = authenticated_client.get(payment_list_url(), {"payment_method": "cheque", "status": "pending"})
    assert res.status_code == status.HTTP_200_OK
    results = res.data.get("results", res.data.get("data"))
    assert len(results) == 1
    assert results[0]["payment_method"] == "cheque"
    assert results[0]["status"] == "pending"


# ============================================================
# 5. MULTI-COMPANY ISOLATION
# ============================================================

@pytest.mark.django_db
def test_multi_company_isolation(authenticated_client, api_client, customer, other_company_customer, another_user):
    today = timezone.now().date()
    p_comp1 = Payment.objects.create(
        company=customer.company,
        customer=customer,
        payment_date=today,
        amount_received=Decimal("10000.00"),
    )
    p_comp2 = Payment.objects.create(
        company=other_company_customer.company,
        customer=other_company_customer,
        payment_date=today,
        amount_received=Decimal("20000.00"),
    )

    # User 1 sees only company 1 payment
    res1 = authenticated_client.get(payment_list_url())
    results1 = res1.data.get("results", res1.data.get("data"))
    assert len(results1) == 1
    assert results1[0]["id"] == p_comp1.id

    # User 2 sees only company 2 payment
    api_client.force_authenticate(user=another_user)
    res2 = api_client.get(payment_list_url())
    results2 = res2.data.get("results", res2.data.get("data"))
    assert len(results2) == 1
    assert results2[0]["id"] == p_comp2.id

    # User 2 cannot retrieve company 1 payment
    res_detail = api_client.get(payment_detail_url(p_comp1.id))
    assert res_detail.status_code == status.HTTP_404_NOT_FOUND


# ============================================================
# 6. KPI METRICS & EXPORT
# ============================================================

@pytest.mark.django_db
def test_payment_kpi_metrics(authenticated_client, company, customer, invoice, overdue_invoice):
    today = timezone.now().date()

    # Record payment for invoice (230,000 SAR)
    Payment.objects.create(
        company=company,
        customer=customer,
        invoice=invoice,
        payment_date=today,
        amount_received=Decimal("230000.00"),
        status="completed",
    )

    # Overdue invoice has total_amount=115,000 SAR, amount_paid=0.00
    res = authenticated_client.get(payment_kpi_url())
    assert res.status_code == status.HTTP_200_OK

    data = res.data["data"]
    assert Decimal(str(data["total_collections"])) == Decimal("230000.00")
    assert Decimal(str(data["this_month_collections"])) == Decimal("230000.00")
    assert Decimal(str(data["outstanding_receivables"])) == Decimal("115000.00")
    assert Decimal(str(data["overdue_receivables"])) == Decimal("115000.00")
    # Total invoiced = 230000 + 115000 = 345000. 230000/345000 = 66.67%
    assert data["collection_rate"] == 66.67


@pytest.mark.django_db
def test_payment_export_csv(authenticated_client, customer):
    today = timezone.now().date()
    Payment.objects.create(
        company=customer.company,
        customer=customer,
        payment_date=today,
        amount_received=Decimal("50000.00"),
        reference_number="REF-EXPORT-001",
        status="completed",
    )

    res = authenticated_client.get(payment_export_url())
    assert res.status_code == status.HTTP_200_OK
    assert res["Content-Type"] == "text/csv"
    assert "payments_export.csv" in res["Content-Disposition"]

    content = res.content.decode("utf-8")
    assert "Receipt No,Customer,Invoice No" in content
    assert "REF-EXPORT-001" in content
