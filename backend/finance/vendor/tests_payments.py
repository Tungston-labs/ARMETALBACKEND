from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from superadmin.models import Company
from user.models import User
from finance.vendor.models import Vendor, VendorPayment
from finance.bill.models import Bill, BillItem


class VendorPaymentAPITestCase(APITestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name="Armetal Test Company",
            email="vp_test@armetal.com"
        )
        self.user = User.objects.create_user(
            username="vp_admin",
            email="vp_admin@armetal.com",
            password="Password123",
            company=self.company,
            is_active=True
        )
        self.client.force_authenticate(user=self.user)

        self.vendor = Vendor.objects.create(
            company=self.company,
            name="Mediora Tech",
            vendor_type="equipment",
            billing_address="Riyadh Industrial Area",
            phno="+966 500000000",
            admin_email="info@mediora.com",
            created_by=self.user
        )

        self.bill = Bill.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill_number="INV 0123",
            bill_date="2026-04-10",
            due_date="2026-04-30",
            total_amount=Decimal("10000.00"),
            amount_paid=Decimal("0.00"),
            created_by=self.user
        )

    def test_record_vendor_payment_and_sync_bill(self):
        self.assertEqual(self.bill.status, "unpaid")

        # 1. Record partial payment
        payload1 = {
            "vendor": self.vendor.id,
            "bill": self.bill.id,
            "payment_date": "2026-04-28",
            "payment_type": "partial_payment",
            "payment_method": "cheque",
            "amount_paid": "4000.00",
            "reference_number": "CHQ-1001",
            "notes": "First installment"
        }

        res1 = self.client.post("/api/finance/vendor/payments/", payload1, format="json")
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data["data"]["receipt_number"], "REC001")
        self.assertEqual(res1.data["data"]["vendor_name"], "Mediora Tech")
        self.assertEqual(res1.data["data"]["bill_number"], "INV 0123")

        # Verify Bill was updated
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.amount_paid, Decimal("4000.00"))
        self.assertEqual(self.bill.status, "partially_paid")
        self.assertEqual(self.bill.balance, Decimal("6000.00"))

        # 2. Record second payment for remaining amount
        payload2 = {
            "vendor": self.vendor.id,
            "bill": self.bill.id,
            "payment_date": "2026-04-29",
            "payment_type": "full_payment",
            "payment_method": "bank_transfer",
            "amount_paid": "6000.00",
            "reference_number": "TRF-2002",
            "notes": "Final settlement"
        }

        res2 = self.client.post("/api/finance/vendor/payments/", payload2, format="json")
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.data["data"]["receipt_number"], "REC002")

        # Verify Bill is fully paid
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.amount_paid, Decimal("10000.00"))
        self.assertEqual(self.bill.status, "paid")
        self.assertEqual(self.bill.balance, Decimal("0.00"))

    def test_delete_vendor_payment_recalculates_bill(self):
        p1 = VendorPayment.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill=self.bill,
            payment_date="2026-04-28",
            payment_type="partial_payment",
            payment_method="bank_transfer",
            amount_paid=Decimal("5000.00"),
            status="completed"
        )
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.amount_paid, Decimal("5000.00"))
        self.assertEqual(self.bill.status, "partially_paid")

        # Delete payment
        res_del = self.client.delete(f"/api/finance/vendor/payments/{p1.id}/")
        self.assertEqual(res_del.status_code, status.HTTP_200_OK)

        self.bill.refresh_from_db()
        self.assertEqual(self.bill.amount_paid, Decimal("0.00"))
        self.assertEqual(self.bill.status, "unpaid")

    def test_vendor_payment_kpi_endpoint(self):
        today_str = timezone.now().date().strftime("%Y-%m-%d")

        # Completed payment
        VendorPayment.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill=self.bill,
            payment_date=today_str,
            payment_type="full_payment",
            payment_method="bank_transfer",
            amount_paid=Decimal("4000.00"),
            status="completed"
        )

        # Advance payment
        VendorPayment.objects.create(
            company=self.company,
            vendor=self.vendor,
            payment_date=today_str,
            payment_type="advance_payment",
            payment_method="online_payment",
            amount_paid=Decimal("1500.00"),
            status="completed"
        )

        res = self.client.get("/api/finance/vendor/payments/kpi/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data["data"]
        self.assertEqual(Decimal(str(data["total_payments"])), Decimal("5500.00"))
        self.assertEqual(Decimal(str(data["payments_this_month"])), Decimal("5500.00"))
        self.assertEqual(Decimal(str(data["advance_payments"])), Decimal("1500.00"))
        self.assertEqual(Decimal(str(data["outstanding"])), Decimal("6000.00"))

    def test_list_vendor_payments_filtering_and_search(self):
        VendorPayment.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill=self.bill,
            receipt_number="REC 0123",
            payment_date="2026-04-28",
            payment_type="full_payment",
            payment_method="bank_transfer",
            amount_paid=Decimal("250000.00"),
            status="completed"
        )
        VendorPayment.objects.create(
            company=self.company,
            vendor=self.vendor,
            receipt_number="REC 0124",
            payment_date="2026-04-28",
            payment_type="advance_payment",
            payment_method="cheque",
            amount_paid=Decimal("75000.00"),
            status="cancelled"
        )

        # List all
        res = self.client.get("/api/finance/vendor/payments/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)

        # Filter by status
        res_status = self.client.get("/api/finance/vendor/payments/?status=completed")
        self.assertEqual(res_status.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_status.data["results"]), 1)
        self.assertEqual(res_status.data["results"][0]["receipt_number"], "REC 0123")

        # Filter by payment_type
        res_type = self.client.get("/api/finance/vendor/payments/?payment_type=advance_payment")
        self.assertEqual(res_type.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_type.data["results"]), 1)

        # Search by receipt_number
        res_search = self.client.get("/api/finance/vendor/payments/?search=REC 0123")
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_search.data["results"]), 1)

    def test_vendor_payment_csv_export(self):
        VendorPayment.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill=self.bill,
            payment_date="2026-04-28",
            payment_type="full_payment",
            payment_method="bank_transfer",
            amount_paid=Decimal("100.00"),
            status="completed"
        )

        res = self.client.get("/api/finance/vendor/payments/export/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertIn("Payment No,Vendor,Bill No", res.content.decode())

    def test_multi_company_isolation(self):
        other_company = Company.objects.create(
            name="Other Company",
            email="other_vp@armetal.com"
        )
        other_user = User.objects.create_user(
            username="other_vp_user",
            email="other_vp@armetal.com",
            password="Password123",
            company=other_company,
            is_active=True
        )

        p = VendorPayment.objects.create(
            company=self.company,
            vendor=self.vendor,
            payment_date="2026-04-28",
            amount_paid=Decimal("500.00")
        )

        self.client.force_authenticate(user=other_user)

        res_list = self.client.get("/api/finance/vendor/payments/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data["results"]), 0)

        res_get = self.client.get(f"/api/finance/vendor/payments/{p.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)
