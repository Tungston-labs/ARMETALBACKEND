from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from superadmin.models import Company
from user.models import User
from finance.vendor.models import Vendor
from finance.product.models import Product
from finance.bill.models import Bill, BillItem
from finance.debit_note.models import DebitNote, DebitNoteItem


class DebitNoteAPITestCase(APITestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name="Armetal Test Company",
            email="dn_test@armetal.com"
        )
        self.user = User.objects.create_user(
            username="dn_admin",
            email="dn_admin@armetal.com",
            password="Password123",
            company=self.company,
            is_active=True
        )
        self.client.force_authenticate(user=self.user)

        self.vendor = Vendor.objects.create(
            company=self.company,
            name="Chicking Vendor",
            vendor_type="equipment",
            billing_address="Riyadh Street",
            phno="+966 5000000",
            admin_email="info@chicking.com",
            created_by=self.user
        )

        self.product = Product.objects.create(
            company=self.company,
            product_name="Product 1",
            product_type="goods",
            selling_price=Decimal("18.50"),
            unit="PCS",
            tax_rate=Decimal("15.00"),
            created_by=self.user
        )

        self.bill = Bill.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill_number="INV 0123",
            bill_date="2026-04-17",
            due_date="2026-04-30",
            subtotal=Decimal("15000.00"),
            total_vat=Decimal("2250.00"),
            total_amount=Decimal("17250.00"),
            created_by=self.user
        )

        self.bill_item = BillItem.objects.create(
            bill=self.bill,
            product=self.product,
            particular="Product 1 description",
            quantity=Decimal("400.00"),
            rate=Decimal("18.50"),
            vat_percentage=Decimal("15.00")
        )

    def test_create_debit_note_auto_increment_and_snapshot(self):
        payload = {
            "vendor": self.vendor.id,
            "bill": self.bill.id,
            "issue_date": "2026-04-28",
            "reason": "damaged_goods",
            "notes": "Damaged items returned",
            "debit_amount": "4200.00",
            "applied_amount": "0.00"
        }

        res = self.client.post("/api/finance/debit-notes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["dn_number"], "DN- 0001")
        self.assertEqual(res.data["vendor_name"], "Chicking Vendor")
        self.assertEqual(res.data["bill_number"], "INV 0123")
        self.assertEqual(res.data["bill_ref"], "INV 0123")
        self.assertEqual(res.data["status"], "open")
        self.assertEqual(Decimal(str(res.data["balance"])), Decimal("4200.00"))

    def test_create_debit_note_with_items_and_calculations(self):
        payload = {
            "vendor": self.vendor.id,
            "bill": self.bill.id,
            "issue_date": "2026-04-28",
            "reason": "returned_goods",
            "items": [
                {
                    "bill_item": self.bill_item.id,
                    "product": self.product.id,
                    "item_name": "Product 1",
                    "billed_qty": "400.00",
                    "already_debited_qty": "0.00",
                    "quantity": "80.00",
                    "rate": "18.50",
                    "vat_percentage": "15.00"
                }
            ]
        }

        res = self.client.post("/api/finance/debit-notes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data["items"]), 1)
        self.assertEqual(Decimal(str(res.data["sub_total"])), Decimal("1480.00"))  # 80 * 18.50
        self.assertEqual(Decimal(str(res.data["total_vat"])), Decimal("222.00"))   # 15% of 1480
        self.assertEqual(Decimal(str(res.data["debit_amount"])), Decimal("1702.00"))

    def test_status_and_balance_transitions_on_applied_amount(self):
        dn = DebitNote.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill=self.bill,
            issue_date="2026-04-28",
            reason="damaged_goods",
            debit_amount=Decimal("10000.00"),
            applied_amount=Decimal("0.00")
        )

        self.assertEqual(dn.status, "open")
        self.assertEqual(dn.balance, Decimal("10000.00"))

        # Partially apply
        res_patch1 = self.client.patch(f"/api/finance/debit-notes/{dn.id}/", {
            "applied_amount": "4000.00"
        }, format="json")
        self.assertEqual(res_patch1.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch1.data["status"], "partially_applied")
        self.assertEqual(Decimal(str(res_patch1.data["balance"])), Decimal("6000.00"))

        # Fully apply
        res_patch2 = self.client.patch(f"/api/finance/debit-notes/{dn.id}/", {
            "applied_amount": "10000.00"
        }, format="json")
        self.assertEqual(res_patch2.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch2.data["status"], "closed")
        self.assertEqual(Decimal(str(res_patch2.data["balance"])), Decimal("0.00"))

    def test_get_bill_debit_note_details(self):
        res = self.client.get(f"/api/finance/debit-notes/bill-details/?bill={self.bill.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data["data"]
        self.assertEqual(data["bill_id"], self.bill.id)
        self.assertEqual(data["bill_number"], "INV 0123")
        self.assertEqual(Decimal(str(data["bill_value"])), Decimal("17250.00"))
        self.assertEqual(Decimal(str(data["already_debited_amount"])), Decimal("0.00"))
        self.assertEqual(Decimal(str(data["remaining_balance"])), Decimal("17250.00"))
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(Decimal(str(data["items"][0]["billed_qty"])), Decimal("400.00"))
        self.assertEqual(Decimal(str(data["items"][0]["already_debited_qty"])), Decimal("0.00"))
        self.assertEqual(Decimal(str(data["items"][0]["max_debitable_qty"])), Decimal("400.00"))

    def test_list_debit_notes_with_filters_search_and_kpi(self):
        DebitNote.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill=self.bill,
            issue_date="2026-04-28",
            reason="returned_goods",
            debit_amount=Decimal("25000.00"),
            applied_amount=Decimal("25000.00")
        )
        DebitNote.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill=self.bill,
            issue_date="2026-04-28",
            reason="damaged_goods",
            debit_amount=Decimal("15000.00"),
            applied_amount=Decimal("10000.00")
        )
        DebitNote.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill=self.bill,
            issue_date="2026-04-28",
            reason="defective_items",
            debit_amount=Decimal("30000.00"),
            applied_amount=Decimal("0.00")
        )

        res = self.client.get("/api/finance/debit-notes/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 3)
        self.assertEqual(res.data["total_debit_notes"], 3)
        self.assertEqual(Decimal(str(res.data["debit_note_value"])), Decimal("70000.00"))
        self.assertEqual(res.data["open_debit_notes"], 1)
        self.assertEqual(res.data["applied_debit_notes"], 2)
        self.assertEqual(res.data["cancelled_debits"], 0)

        # Filter by status
        res_status = self.client.get("/api/finance/debit-notes/?status=open")
        self.assertEqual(res_status.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_status.data["results"]), 1)
        self.assertEqual(res_status.data["results"][0]["reason"], "defective_items")

        # Filter by reason
        res_reason = self.client.get("/api/finance/debit-notes/?reason=damaged_goods")
        self.assertEqual(res_reason.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_reason.data["results"]), 1)

    def test_debit_note_kpi_card_endpoint(self):
        DebitNote.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill=self.bill,
            issue_date="2026-04-28",
            reason="returned_goods",
            debit_amount=Decimal("25000.00"),
            applied_amount=Decimal("25000.00")
        )

        res = self.client.get("/api/finance/debit-notes/kpi/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_debit_notes"], 1)
        self.assertEqual(Decimal(str(res.data["debit_note_value"])), Decimal("25000.00"))

    def test_retrieve_update_delete_debit_note(self):
        dn = DebitNote.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill=self.bill,
            issue_date="2026-04-28",
            reason="pricing_error",
            debit_amount=Decimal("5000.00")
        )

        # GET detail
        res_get = self.client.get(f"/api/finance/debit-notes/{dn.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["dn_number"], dn.dn_number)

        # PUT update
        res_put = self.client.put(f"/api/finance/debit-notes/{dn.id}/", {
            "vendor": self.vendor.id,
            "bill": self.bill.id,
            "issue_date": "2026-04-29",
            "reason": "overbilling",
            "debit_amount": "6000.00",
            "applied_amount": "1000.00",
            "notes": "Revised debit note"
        }, format="json")
        self.assertEqual(res_put.status_code, status.HTTP_200_OK)
        self.assertEqual(res_put.data["reason"], "overbilling")
        self.assertEqual(res_put.data["status"], "partially_applied")

        # DELETE
        res_del = self.client.delete(f"/api/finance/debit-notes/{dn.id}/")
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DebitNote.objects.filter(id=dn.id).exists())

    def test_debit_note_csv_export(self):
        DebitNote.objects.create(
            company=self.company,
            vendor=self.vendor,
            bill=self.bill,
            issue_date="2026-04-28",
            reason="quality_issue",
            debit_amount=Decimal("15000.00")
        )

        res = self.client.get("/api/finance/debit-notes/export/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertIn("Debit Note No,Date,Vendor", res.content.decode())

    def test_multi_company_isolation(self):
        other_company = Company.objects.create(
            name="Other Company",
            email="other_dn@armetal.com"
        )
        other_user = User.objects.create_user(
            username="other_dn_user",
            email="other_dn@armetal.com",
            password="Password123",
            company=other_company,
            is_active=True
        )

        dn = DebitNote.objects.create(
            company=self.company,
            vendor=self.vendor,
            issue_date="2026-04-28",
            debit_amount=Decimal("1000.00")
        )

        self.client.force_authenticate(user=other_user)

        res_list = self.client.get("/api/finance/debit-notes/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data["results"]), 0)

        res_get = self.client.get(f"/api/finance/debit-notes/{dn.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)
