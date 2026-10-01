from decimal import Decimal
from datetime import date

import pytest

from django.urls import reverse
from rest_framework.test import APIClient

from superadmin.models import Company
from user.models import User
from finance.vendor.models import Vendor, VendorPayment
from finance.bill.models import Bill
from finance.vendorledger.models import VendorLedger
from finance.vendorledger.services import (
    sync_bill_ledger,
    sync_vendor_payment_ledger,
)


@pytest.fixture
def company(db):
    return Company.objects.create(
        name="Test Company",
        address="Test Address",
        location="Dubai",
        country="AE",
        contact_number="+971500000001",
        email="testcompany@example.com",
        modules={
            "attendance": True,
            "leave": True,
        },
    )


@pytest.fixture
def another_company(db):
    return Company.objects.create(
        name="Another Company",
        address="Another Address",
        location="Abu Dhabi",
        country="AE",
        contact_number="+971500000002",
        email="anothercompany@example.com",
        modules={
            "attendance": True,
            "leave": True,
        },
    )


@pytest.fixture
def authenticated_user(db, company):
    user = User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="Test@12345",
        company=company,
        is_hr_admin=True,
        is_active=True,
    )

    return user


@pytest.fixture
def another_user(db, another_company):
    user = User.objects.create_user(
        username="anotheruser",
        email="anotheruser@example.com",
        password="Test@12345",
        company=another_company,
        is_hr_admin=True,
        is_active=True,
    )

    return user


@pytest.fixture
def vendor(db, company, authenticated_user):
    return Vendor.objects.create(
        company=company,
        name="ABC Suppliers",
        vendor_type="equipment",
        opening_balance=Decimal("5000.00"),
        credit_limit=Decimal("50000.00"),
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=authenticated_user,
    )


@pytest.fixture
def another_vendor(db, another_company, another_user):
    return Vendor.objects.create(
        company=another_company,
        name="Another Supplier",
        vendor_type="equipment",
        opening_balance=Decimal("1000.00"),
        credit_limit=Decimal("20000.00"),
        currency="AED",
        payment_term="30_days",
        client_status="active",
        created_by=another_user,
    )


@pytest.fixture
def bill(db, company, vendor, authenticated_user):
    return Bill.objects.create(
        company=company,
        vendor=vendor,
        bill_number="BIL00001",
        po_reference="PO00001",
        bill_date=date(2026, 9, 5),
        due_date=date(2026, 10, 5),
        payment_terms="NET 30",
        status="unpaid",
        note="Test vendor bill",
        bill_to_name=vendor.name,
        total_amount=Decimal("10000.00"),
        amount_paid=Decimal("0.00"),
        created_by=authenticated_user,
    )


@pytest.fixture
def payment(
    db,
    company,
    vendor,
    bill,
    authenticated_user,
):
    return VendorPayment.objects.create(
        company=company,
        vendor=vendor,
        bill=bill,
        receipt_number="REC001",
        payment_date=date(2026, 9, 10),
        payment_type="partial_payment",
        payment_method="bank_transfer",
        amount_paid=Decimal("4000.00"),
        reference_number="PAY001",
        notes="Test payment",
        status="completed",
        created_by=authenticated_user,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client(
    api_client,
    authenticated_user,
):
    api_client.force_authenticate(
        user=authenticated_user
    )

    return api_client


@pytest.mark.django_db
class TestVendorLedger:

    # ============================================================
    # Helper
    # ============================================================

    def create_ledger(
        self,
        company,
        vendor,
        entry_date,
        transaction_type,
        debit="0.00",
        credit="0.00",
        reference="",
        description="",
    ):
        return VendorLedger.objects.create(
            company=company,
            vendor=vendor,
            entry_date=entry_date,
            transaction_type=transaction_type,
            debit_amount=Decimal(debit),
            credit_amount=Decimal(credit),
            reference_number=reference,
            description=description,
        )

    # ============================================================
    # 1. Vendor Ledger List API
    # ============================================================

    def test_vendor_ledger_api_returns_entries(
        self,
        company,
        vendor,
        authenticated_client,
    ):
        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 1),
            transaction_type="opening_balance",
            debit="5000.00",
            reference="OB001",
            description="Opening balance",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 5),
            transaction_type="bill",
            debit="10000.00",
            reference="BIL001",
            description="Vendor bill",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 10),
            transaction_type="payment",
            credit="4000.00",
            reference="PAY001",
            description="Vendor payment",
        )

        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.id}/"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["vendor"]["id"] == vendor.id
        assert data["vendor"]["vendor_id"] == vendor.vendor_id
        assert data["vendor"]["name"] == vendor.name

        assert len(data["data"]) == 3

    # ============================================================
    # 2. Running Balance
    # ============================================================

    def test_running_balance(
        self,
        company,
        vendor,
        authenticated_client,
    ):
        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 1),
            transaction_type="opening_balance",
            debit="5000.00",
            reference="OB001",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 5),
            transaction_type="bill",
            debit="10000.00",
            reference="BIL001",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 10),
            transaction_type="payment",
            credit="4000.00",
            reference="PAY001",
        )

        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.id}/"
        )

        assert response.status_code == 200

        entries = response.json()["data"]

        assert entries[0]["running_balance"] == "5000.00"
        assert entries[1]["running_balance"] == "15000.00"
        assert entries[2]["running_balance"] == "11000.00"

    # ============================================================
    # 3. Date Range
    # ============================================================

    def test_date_range_filter(
        self,
        company,
        vendor,
        authenticated_client,
    ):
        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 8, 1),
            transaction_type="bill",
            debit="5000.00",
            reference="AUG001",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 10),
            transaction_type="bill",
            debit="10000.00",
            reference="SEP001",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 10, 1),
            transaction_type="bill",
            debit="15000.00",
            reference="OCT001",
        )

        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.id}/",
            {
                "date_from": "2026-09-01",
                "date_to": "2026-09-30",
            },
        )

        assert response.status_code == 200

        entries = response.json()["data"]

        assert len(entries) == 1
        assert entries[0]["reference_number"] == "SEP001"

    # ============================================================
    # 4. Date From
    # ============================================================

    def test_date_from_filter(
        self,
        company,
        vendor,
        authenticated_client,
    ):
        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 8, 1),
            transaction_type="bill",
            debit="5000.00",
            reference="AUG001",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 1),
            transaction_type="bill",
            debit="10000.00",
            reference="SEP001",
        )

        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.id}/",
            {
                "date_from": "2026-09-01",
            },
        )

        assert response.status_code == 200

        entries = response.json()["data"]

        assert len(entries) == 1
        assert entries[0]["reference_number"] == "SEP001"

    # ============================================================
    # 5. Date To
    # ============================================================

    def test_date_to_filter(
        self,
        company,
        vendor,
        authenticated_client,
    ):
        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 1),
            transaction_type="bill",
            debit="10000.00",
            reference="SEP001",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 10, 1),
            transaction_type="bill",
            debit="15000.00",
            reference="OCT001",
        )

        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.id}/",
            {
                "date_to": "2026-09-30",
            },
        )

        assert response.status_code == 200

        entries = response.json()["data"]

        assert len(entries) == 1
        assert entries[0]["reference_number"] == "SEP001"

    # ============================================================
    # 6. Transaction Type Filter
    # ============================================================

    def test_transaction_type_filter(
        self,
        company,
        vendor,
        authenticated_client,
    ):
        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 1),
            transaction_type="bill",
            debit="10000.00",
            reference="BIL001",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 5),
            transaction_type="payment",
            credit="5000.00",
            reference="PAY001",
        )

        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.id}/",
            {
                "type": "bill",
            },
        )

        assert response.status_code == 200

        entries = response.json()["data"]

        assert len(entries) == 1
        assert entries[0]["type"] == "Bill"

    # ============================================================
    # 7. Search
    # ============================================================

    def test_ledger_search(
        self,
        company,
        vendor,
        authenticated_client,
    ):
        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 1),
            transaction_type="bill",
            debit="10000.00",
            reference="BIL00001",
            description="Office material purchase",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 5),
            transaction_type="payment",
            credit="5000.00",
            reference="PAY00001",
            description="Bank payment",
        )

        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.id}/",
            {
                "search": "BIL00001",
            },
        )

        assert response.status_code == 200

        entries = response.json()["data"]

        assert len(entries) == 1
        assert entries[0]["reference_number"] == "BIL00001"

    # ============================================================
    # 8. Search By Description
    # ============================================================

    def test_search_by_description(
        self,
        company,
        vendor,
        authenticated_client,
    ):
        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 1),
            transaction_type="manual",
            debit="2500.00",
            reference="MAN001",
            description="Special equipment purchase",
        )

        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.id}/",
            {
                "search": "equipment",
            },
        )

        assert response.status_code == 200

        entries = response.json()["data"]

        assert len(entries) == 1
        assert entries[0]["reference_number"] == "MAN001"

    # ============================================================
    # 9. Summary Cards
    # ============================================================

    def test_ledger_summary(
        self,
        company,
        vendor,
        authenticated_client,
    ):
        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 1),
            transaction_type="opening_balance",
            debit="5000.00",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 5),
            transaction_type="bill",
            debit="10000.00",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 10),
            transaction_type="payment",
            credit="4000.00",
        )

        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.id}/"
        )

        assert response.status_code == 200

        cards = response.json()["cards"]

        assert cards["total_opening_balance"] == "5000.00"
        assert cards["total_billed"] == "10000.00"
        assert cards["total_paid_and_debit_note"] == "4000.00"
        assert cards["outstanding_payable"] == "11000.00"
        assert cards["total_transactions"] == 3

    # ============================================================
    # 10. Combined Filters
    # ============================================================

    def test_date_range_and_type_filter(
        self,
        company,
        vendor,
        authenticated_client,
    ):
        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 8, 10),
            transaction_type="bill",
            debit="5000.00",
            reference="AUG-BILL",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 10),
            transaction_type="bill",
            debit="10000.00",
            reference="SEP-BILL",
        )

        self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 15),
            transaction_type="payment",
            credit="3000.00",
            reference="SEP-PAY",
        )

        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.id}/",
            {
                "date_from": "2026-09-01",
                "date_to": "2026-09-30",
                "type": "bill",
            },
        )

        assert response.status_code == 200

        entries = response.json()["data"]

        assert len(entries) == 1
        assert entries[0]["reference_number"] == "SEP-BILL"

    # ============================================================
    # 11. Company Isolation
    # ============================================================

    def test_vendor_company_isolation(
        self,
        another_vendor,
        authenticated_client,
    ):
        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{another_vendor.id}/"
        )

        assert response.status_code == 404

    # ============================================================
    # 12. Invalid Vendor
    # ============================================================

    def test_invalid_vendor(
        self,
        authenticated_client,
    ):
        response = authenticated_client.get(
            "/api/vendor-ledger/vendor/999999/"
        )

        assert response.status_code == 404

    # ============================================================
    # 13. Manual Ledger Creation
    # ============================================================

    def test_create_manual_ledger_entry(
        self,
        vendor,
        authenticated_client,
    ):
        payload = {
            "vendor": vendor.id,
            "entry_date": "2026-09-15",
            "reference_number": "MAN001",
            "transaction_type": "manual",
            "description": "Manual adjustment",
            "debit_amount": "2500.00",
            "credit_amount": "0.00",
        }

        response = authenticated_client.post(
            "/api/vendor-ledger/",
            payload,
            format="json",
        )

        assert response.status_code in [200, 201]

        ledger = VendorLedger.objects.get(
            reference_number="MAN001"
        )

        assert ledger.vendor == vendor
        assert ledger.debit_amount == Decimal("2500.00")
        assert ledger.credit_amount == Decimal("0.00")

    # ============================================================
    # 14. Debit + Credit Validation
    # ============================================================

    def test_cannot_create_debit_and_credit_together(
        self,
        vendor,
        authenticated_client,
    ):
        payload = {
            "vendor": vendor.id,
            "entry_date": "2026-09-15",
            "reference_number": "MAN002",
            "transaction_type": "manual",
            "description": "Invalid entry",
            "debit_amount": "1000.00",
            "credit_amount": "500.00",
        }

        response = authenticated_client.post(
            "/api/vendor-ledger/",
            payload,
            format="json",
        )

        assert response.status_code == 400

        assert not VendorLedger.objects.filter(
            reference_number="MAN002"
        ).exists()

    # ============================================================
    # 15. Zero Debit + Zero Credit Validation
    # ============================================================

    def test_cannot_create_zero_debit_and_credit(
        self,
        vendor,
        authenticated_client,
    ):
        payload = {
            "vendor": vendor.id,
            "entry_date": "2026-09-15",
            "reference_number": "MAN003",
            "transaction_type": "manual",
            "description": "Invalid zero entry",
            "debit_amount": "0.00",
            "credit_amount": "0.00",
        }

        response = authenticated_client.post(
            "/api/vendor-ledger/",
            payload,
            format="json",
        )

        assert response.status_code == 400

    # ============================================================
    # 16. Bill Creates Ledger
    # ============================================================

    def test_bill_creates_vendor_ledger(
        self,
        bill,
        authenticated_user,
    ):
        ledger = sync_bill_ledger(
            bill,
            created_by=authenticated_user,
        )

        assert ledger is not None

        ledger.refresh_from_db()

        assert ledger.vendor == bill.vendor
        assert ledger.bill == bill
        assert ledger.transaction_type == "bill"

        assert ledger.debit_amount == (
            bill.total_amount
        )

        assert ledger.credit_amount == Decimal("0.00")

        assert ledger.reference_number == (
            bill.bill_number
        )

    # ============================================================
    # 17. Bill Ledger Duplicate Protection
    # ============================================================

    def test_bill_ledger_is_not_duplicated(
        self,
        bill,
        authenticated_user,
    ):
        sync_bill_ledger(
            bill,
            created_by=authenticated_user,
        )

        sync_bill_ledger(
            bill,
            created_by=authenticated_user,
        )

        assert VendorLedger.objects.filter(
            bill=bill
        ).count() == 1

    # ============================================================
    # 18. Cancelled Bill Removes Ledger
    # ============================================================

    def test_cancelled_bill_removed_from_ledger(
        self,
        bill,
    ):
        sync_bill_ledger(bill)

        assert VendorLedger.objects.filter(
            bill=bill
        ).exists()

        bill.status = "cancelled"
        bill.save()

        sync_bill_ledger(bill)

        assert not VendorLedger.objects.filter(
            bill=bill
        ).exists()

    # ============================================================
    # 19. Draft Bill Does Not Create Ledger
    # ============================================================

    def test_draft_bill_does_not_create_ledger(
        self,
        bill,
    ):
        bill.status = "draft"
        bill.save()

        sync_bill_ledger(bill)

        assert not VendorLedger.objects.filter(
            bill=bill
        ).exists()

    # ============================================================
    # 20. Bill Without Vendor Does Not Create Ledger
    # ============================================================

    def test_bill_without_vendor_does_not_create_ledger(
        self,
        company,
        authenticated_user,
    ):
        bill = Bill.objects.create(
            company=company,
            vendor=None,
            bill_number="BIL99999",
            bill_date=date(2026, 9, 5),
            due_date=date(2026, 10, 5),
            payment_terms="NET 30",
            status="unpaid",
            total_amount=Decimal("5000.00"),
            amount_paid=Decimal("0.00"),
            created_by=authenticated_user,
        )

        result = sync_bill_ledger(bill)

        assert result is None

        assert not VendorLedger.objects.filter(
            bill=bill
        ).exists()

    # ============================================================
    # 21. Completed Payment Creates Credit
    # ============================================================

    def test_completed_payment_creates_credit(
        self,
        payment,
    ):
        ledger = sync_vendor_payment_ledger(payment)

        assert ledger is not None

        ledger.refresh_from_db()

        assert ledger.payment == payment
        assert ledger.vendor == payment.vendor
        assert ledger.transaction_type == "payment"

        assert ledger.credit_amount == (
            payment.amount_paid
        )

        assert ledger.debit_amount == Decimal("0.00")

    # ============================================================
    # 22. Payment Ledger Duplicate Protection
    # ============================================================

    def test_payment_ledger_is_not_duplicated(
        self,
        payment,
    ):
        sync_vendor_payment_ledger(payment)

        sync_vendor_payment_ledger(payment)

        assert VendorLedger.objects.filter(
            payment=payment
        ).count() == 1

    # ============================================================
    # 23. Pending Payment Should Not Affect Ledger
    # ============================================================

    def test_pending_payment_does_not_create_ledger(
        self,
        payment,
    ):
        payment.status = "pending"

        # Avoid relying on payment.save() for this test.
        # We only test ledger synchronization behavior.
        payment.save()

        sync_vendor_payment_ledger(payment)

        assert not VendorLedger.objects.filter(
            payment=payment
        ).exists()

    # ============================================================
    # 24. Cancelled Payment Should Not Affect Ledger
    # ============================================================

    def test_cancelled_payment_does_not_create_ledger(
        self,
        payment,
    ):
        payment.status = "cancelled"
        payment.save()

        sync_vendor_payment_ledger(payment)

        assert not VendorLedger.objects.filter(
            payment=payment
        ).exists()

    # ============================================================
    # 25. Payment Amount Is Credit
    # ============================================================

    def test_payment_is_credit_not_debit(
        self,
        payment,
    ):
        sync_vendor_payment_ledger(payment)

        ledger = VendorLedger.objects.get(
            payment=payment
        )

        assert ledger.credit_amount == Decimal("4000.00")
        assert ledger.debit_amount == Decimal("0.00")

    # ============================================================
    # 26. Vendor Ledger Only Belongs To Its Company
    # ============================================================

    def test_ledger_company_is_correct(
        self,
        company,
        vendor,
    ):
        ledger = self.create_ledger(
            company=company,
            vendor=vendor,
            entry_date=date(2026, 9, 1),
            transaction_type="bill",
            debit="5000.00",
            reference="BIL001",
        )

        assert ledger.company == company
        assert ledger.vendor.company == company

    # ============================================================
    # 27. Vendor ID In URL Is Primary Key
    # ============================================================

    def test_vendor_endpoint_uses_vendor_primary_key(
        self,
        vendor,
        authenticated_client,
    ):
        self.create_ledger(
            company=vendor.company,
            vendor=vendor,
            entry_date=date(2026, 9, 1),
            transaction_type="bill",
            debit="5000.00",
            reference="BIL001",
        )

        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.id}/"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["vendor"]["id"] == vendor.id

    # ============================================================
    # 28. Vendor Business ID Is Not Used In URL
    # ============================================================

    def test_vendor_endpoint_does_not_use_vendor_business_id(
        self,
        vendor,
        authenticated_client,
    ):
        response = authenticated_client.get(
            f"/api/vendor-ledger/vendor/{vendor.vendor_id}/"
        )

        # vendor_id is something like VEN00001,
        # therefore it does not match <int:vendor_id>.
        assert response.status_code == 404