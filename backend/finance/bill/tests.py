from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from superadmin.models import Company
from user.models import User
from finance.vendor.models import Vendor
from finance.product.models import Product
from finance.bill.models import Bill, BillItem


class BillAPITestCase(APITestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name="Armetal Test Company",
            email="bill_test@armetal.com"
        )
        self.user = User.objects.create_user(
            username="bill_admin",
            email="bill_admin@armetal.com",
            password="Password123",
            company=self.company,
            is_active=True
        )
        self.client.force_authenticate(user=self.user)

        self.vendor = Vendor.objects.create(
            company=self.company,
            name="Chicking Vendor",
            vendor_type="equipment",
            billing_address="Tungston Labs, Ullampilly Building",
            phno="+91 97783 77526",
            admin_email="info@chicking.com",
            financial_email="finance@chicking.com",
            created_by=self.user
        )

        self.product = Product.objects.create(
            company=self.company,
            product_name="Product 1",
            product_type="goods",
            selling_price=Decimal("197.00"),
            unit="PCS",
            tax_rate=Decimal("15.00"),
            created_by=self.user
        )

    def test_create_bill_auto_number_and_snapshot(self):
        payload = {
            "vendor": self.vendor.id,
            "po_reference": "INV 0123 - Chicking",
            "bill_date": "2026-04-17",
            "due_date": "2026-04-30",
            "payment_terms": "NET 10",
            "due_date_note": "Damaged Goods",
            "note": "Test Note",
            "items": [
                {
                    "product": self.product.id,
                    "particular": "Product 1 description",
                    "quantity": "1.00",
                    "hs_code": "25366",
                    "rate": "197.00",
                    "vat_percentage": "15.00"
                }
            ]
        }

        res = self.client.post("/api/finance/bill/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["bill_number"], "BIL00001")
        self.assertEqual(res.data["vendor_name"], "Chicking Vendor")
        self.assertEqual(res.data["bill_to_name"], "Chicking Vendor")
        self.assertEqual(res.data["bill_to_address"], "Tungston Labs, Ullampilly Building")
        self.assertEqual(res.data["bill_to_email"], "info@chicking.com")
        self.assertEqual(res.data["status"], "unpaid")
        self.assertEqual(Decimal(str(res.data["subtotal"])), Decimal("197.00"))
        self.assertEqual(Decimal(str(res.data["total_vat"])), Decimal("29.55"))
        self.assertEqual(Decimal(str(res.data["total_amount"])), Decimal("226.55"))
        self.assertEqual(Decimal(str(res.data["balance"])), Decimal("226.55"))

    def test_create_second_bill_auto_increment(self):
        Bill.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill_number="BIL00001",
            bill_date="2026-04-17",
            total_amount=Decimal("100.00")
        )

        payload = {
            "vendor": self.vendor.id,
            "po_reference": "PO 0124",
            "bill_date": "2026-04-18",
            "items": [
                {
                    "particular": "Item 2",
                    "quantity": "2.00",
                    "rate": "500.00",
                    "vat_percentage": "15.00"
                }
            ]
        }

        res = self.client.post("/api/finance/bill/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["bill_number"], "BIL00002")
        self.assertEqual(Decimal(str(res.data["subtotal"])), Decimal("1000.00"))
        self.assertEqual(Decimal(str(res.data["total_vat"])), Decimal("150.00"))
        self.assertEqual(Decimal(str(res.data["total_amount"])), Decimal("1150.00"))

    def test_bill_status_transitions(self):
        bill = Bill.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill_date="2026-04-17",
            due_date="2026-04-30",
            total_amount=Decimal("1000.00"),
            amount_paid=Decimal("0.00")
        )
        self.assertEqual(bill.status, "unpaid")

        # Partial payment update
        res_patch1 = self.client.patch(f"/api/finance/bill/{bill.id}/", {
            "amount_paid": "400.00"
        }, format="json")
        self.assertEqual(res_patch1.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch1.data["status"], "partially_paid")
        self.assertEqual(Decimal(str(res_patch1.data["balance"])), Decimal("600.00"))

        # Full payment update
        res_patch2 = self.client.patch(f"/api/finance/bill/{bill.id}/", {
            "amount_paid": "1000.00"
        }, format="json")
        self.assertEqual(res_patch2.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch2.data["status"], "paid")
        self.assertEqual(Decimal(str(res_patch2.data["balance"])), Decimal("0.00"))

    def test_list_bills_filters_search_and_kpis(self):
        # 1. Unpaid Bill
        Bill.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill_number="DN 0123",
            po_reference="SO 0123",
            bill_date="2026-04-01",
            due_date="2026-04-15",
            total_amount=Decimal("22852.00"),
            amount_paid=Decimal("0.00")
        )
        # 2. Fully Paid Bill
        Bill.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill_number="DN 0124",
            po_reference="SO 0124",
            bill_date="2026-04-05",
            due_date="2026-04-20",
            total_amount=Decimal("10000.00"),
            amount_paid=Decimal("10000.00")
        )

        res = self.client.get("/api/finance/bill/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)
        self.assertEqual(res.data["total_bills"], 2)
        self.assertEqual(Decimal(str(res.data["total_bill_value"])), Decimal("32852.00"))
        self.assertEqual(Decimal(str(res.data["total_payables"])), Decimal("22852.00"))
        self.assertEqual(Decimal(str(res.data["overdue_payables"])), Decimal("22852.00"))

        # Filter by status
        res_filter = self.client.get("/api/finance/bill/?status=paid")
        self.assertEqual(res_filter.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_filter.data["results"]), 1)
        self.assertEqual(res_filter.data["results"][0]["bill_number"], "DN 0124")

        # Search by bill number or po_reference
        res_search = self.client.get("/api/finance/bill/?search=SO 0123")
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_search.data["results"]), 1)
        self.assertEqual(res_search.data["results"][0]["bill_number"], "DN 0123")

    def test_bill_kpi_card_endpoint(self):
        Bill.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill_date="2026-04-01",
            due_date="2026-04-10",
            total_amount=Decimal("5000.00"),
            amount_paid=Decimal("2000.00")
        )

        res = self.client.get("/api/finance/bill/kpi/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_bills"], 1)
        self.assertEqual(Decimal(str(res.data["total_bill_value"])), Decimal("5000.00"))
        self.assertEqual(Decimal(str(res.data["total_payables"])), Decimal("3000.00"))
        self.assertEqual(Decimal(str(res.data["overdue_payables"])), Decimal("3000.00"))

    def test_retrieve_update_delete_bill(self):
        bill = Bill.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill_number="BIL999",
            bill_date="2026-04-10",
            due_date="2026-04-20",
            total_amount=Decimal("1000.00")
        )

        # GET detail
        res_get = self.client.get(f"/api/finance/bill/{bill.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["bill_number"], "BIL999")

        # PUT update
        res_put = self.client.put(f"/api/finance/bill/{bill.id}/", {
            "vendor": self.vendor.id,
            "bill_number": "BIL999-REV",
            "po_reference": "REV-PO",
            "bill_date": "2026-04-11",
            "payment_terms": "NET 30",
            "items": [
                {
                    "particular": "Revised Product",
                    "quantity": "3.00",
                    "rate": "200.00",
                    "vat_percentage": "15.00"
                }
            ]
        }, format="json")
        self.assertEqual(res_put.status_code, status.HTTP_200_OK)
        self.assertEqual(res_put.data["bill_number"], "BIL999-REV")
        self.assertEqual(Decimal(str(res_put.data["subtotal"])), Decimal("600.00"))
        self.assertEqual(Decimal(str(res_put.data["total_vat"])), Decimal("90.00"))
        self.assertEqual(Decimal(str(res_put.data["total_amount"])), Decimal("690.00"))

        # DELETE
        res_del = self.client.delete(f"/api/finance/bill/{bill.id}/")
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Bill.objects.filter(id=bill.id).exists())

    def test_multi_company_isolation(self):
        other_company = Company.objects.create(
            name="Other Company",
            email="other_bill@armetal.com"
        )
        other_user = User.objects.create_user(
            username="other_bill_user",
            email="other_bill@armetal.com",
            password="Password123",
            company=other_company,
            is_active=True
        )

        bill = Bill.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill_date="2026-04-10",
            total_amount=Decimal("500.00")
        )

        self.client.force_authenticate(user=other_user)

        res_list = self.client.get("/api/finance/bill/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data["results"]), 0)

        res_get = self.client.get(f"/api/finance/bill/{bill.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)
