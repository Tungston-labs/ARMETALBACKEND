from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from superadmin.models import Company
from user.models import User
from finance.customer.models import Customer
from finance.product.models import Product
from finance.credit_note.models import CreditNote, CreditNoteItem


class CreditNoteAPITestCase(APITestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name="Armetal Test Company",
            email="cn_test@armetal.com"
        )
        self.user = User.objects.create_user(
            username="cn_admin",
            email="cn_admin@armetal.com",
            password="Password123",
            company=self.company,
            is_active=True
        )
        self.client.force_authenticate(user=self.user)

        self.customer = Customer.objects.create(
            company=self.company,
            customer_name="Mediora Tech",
            company_name="Mediora",
            industry="technology",
            currency="SAR",
            created_by=self.user
        )

        self.product = Product.objects.create(
            company=self.company,
            product_name="Metal Panel",
            product_type="goods",
            selling_price=Decimal("1000.00"),
            unit="PCS",
            tax_rate=Decimal("15.00"),
            created_by=self.user
        )

    def test_create_credit_note_auto_increment(self):
        res1 = self.client.post("/api/finance/credit-notes/", {
            "customer": self.customer.id,
            "invoice_ref": "INV-0123",
            "issue_date": "2026-04-28",
            "reason": "sales_return",
            "credit_amount": "25000.00",
            "applied_amount": "25000.00"
        }, format="json")

        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data["cn_number"], "CN- 0123")
        self.assertEqual(res1.data["customer_name"], "Mediora Tech")
        self.assertEqual(res1.data["customer_company"], "Mediora")
        self.assertEqual(res1.data["status"], "closed")
        self.assertEqual(Decimal(str(res1.data["balance"])), Decimal("0.00"))

        res2 = self.client.post("/api/finance/credit-notes/", {
            "customer": self.customer.id,
            "invoice_ref": "INV-0124",
            "issue_date": "2026-04-28",
            "reason": "price_adjustment",
            "credit_amount": "15000.00",
            "applied_amount": "10000.00"
        }, format="json")

        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.data["cn_number"], "CN- 0124")
        self.assertEqual(res2.data["status"], "partially_applied")
        self.assertEqual(Decimal(str(res2.data["balance"])), Decimal("5000.00"))

    def test_create_credit_note_with_items_and_calculations(self):
        payload = {
            "customer": self.customer.id,
            "invoice_ref": "INV-0125",
            "issue_date": "2026-04-28",
            "reason": "damaged_goods",
            "notes": "Damaged goods returned by client",
            "items": [
                {
                    "product": self.product.id,
                    "item_name": "Metal Panel",
                    "description": "20mm Metal Panel",
                    "quantity": "2.00",
                    "rate": "1000.00",
                    "vat_percentage": "15.00"
                }
            ]
        }

        res = self.client.post("/api/finance/credit-notes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data["items"]), 1)
        self.assertEqual(res.data["items"][0]["item_name"], "Metal Panel")
        self.assertEqual(Decimal(str(res.data["sub_total"])), Decimal("2000.00"))
        self.assertEqual(Decimal(str(res.data["total_vat"])), Decimal("300.00"))
        self.assertEqual(Decimal(str(res.data["credit_amount"])), Decimal("2300.00"))
        self.assertEqual(Decimal(str(res.data["balance"])), Decimal("2300.00"))
        self.assertEqual(res.data["status"], "open")

    def test_status_and_balance_transitions_on_applied_amount(self):
        cn = CreditNote.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_ref="INV-0126",
            issue_date="2026-04-28",
            reason="sales_return",
            credit_amount=Decimal("30000.00"),
            applied_amount=Decimal("0.00")
        )

        self.assertEqual(cn.status, "open")
        self.assertEqual(cn.balance, Decimal("30000.00"))

        # Partially apply credit
        res_patch1 = self.client.patch(f"/api/finance/credit-notes/{cn.id}/", {
            "applied_amount": "10000.00"
        }, format="json")
        self.assertEqual(res_patch1.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch1.data["status"], "partially_applied")
        self.assertEqual(Decimal(str(res_patch1.data["balance"])), Decimal("20000.00"))

        # Fully apply credit
        res_patch2 = self.client.patch(f"/api/finance/credit-notes/{cn.id}/", {
            "applied_amount": "30000.00"
        }, format="json")
        self.assertEqual(res_patch2.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch2.data["status"], "closed")
        self.assertEqual(Decimal(str(res_patch2.data["balance"])), Decimal("0.00"))

    def test_list_credit_notes_with_filters_search_and_kpi(self):
        # 1. Closed Credit Note
        CreditNote.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_ref="INV-0123",
            issue_date="2026-04-28",
            reason="sales_return",
            credit_amount=Decimal("25000.00"),
            applied_amount=Decimal("25000.00")
        )
        # 2. Partially Applied Credit Note
        CreditNote.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_ref="INV-0124",
            issue_date="2026-04-28",
            reason="price_adjustment",
            credit_amount=Decimal("15000.00"),
            applied_amount=Decimal("10000.00")
        )
        # 3. Open Credit Note
        CreditNote.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_ref="INV-0125",
            issue_date="2026-04-28",
            reason="damaged_goods",
            credit_amount=Decimal("30000.00"),
            applied_amount=Decimal("0.00")
        )
        # 4. Cancelled Credit Note
        CreditNote.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_ref="INV-0126",
            issue_date="2026-04-28",
            reason="pricing_error",
            credit_amount=Decimal("5000.00"),
            applied_amount=Decimal("0.00"),
            status="cancelled"
        )

        res = self.client.get("/api/finance/credit-notes/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 4)
        self.assertEqual(res.data["total_credit_notes"], 4)
        self.assertEqual(Decimal(str(res.data["total_credit_value"])), Decimal("75000.00"))
        self.assertEqual(Decimal(str(res.data["open_credits"])), Decimal("30000.00"))
        self.assertEqual(Decimal(str(res.data["applied_credits"])), Decimal("35000.00"))
        self.assertEqual(res.data["cancelled_credits"], 1)

        # Test filter by status
        res_filter_status = self.client.get("/api/finance/credit-notes/?status=open")
        self.assertEqual(res_filter_status.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_filter_status.data["results"]), 1)
        self.assertEqual(res_filter_status.data["results"][0]["reason"], "damaged_goods")

        # Test filter by reason
        res_filter_reason = self.client.get("/api/finance/credit-notes/?reason=price_adjustment")
        self.assertEqual(res_filter_reason.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_filter_reason.data["results"]), 1)

        # Test search
        res_search = self.client.get("/api/finance/credit-notes/?search=INV-0125")
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_search.data["results"]), 1)

    def test_credit_note_kpi_card_endpoint(self):
        CreditNote.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_ref="INV-0123",
            issue_date="2026-04-28",
            reason="sales_return",
            credit_amount=Decimal("25000.00"),
            applied_amount=Decimal("25000.00")
        )
        CreditNote.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_ref="INV-0125",
            issue_date="2026-04-28",
            reason="damaged_goods",
            credit_amount=Decimal("30000.00"),
            applied_amount=Decimal("0.00")
        )

        res = self.client.get("/api/finance/credit-notes/kpi/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_credit_notes"], 2)
        self.assertEqual(Decimal(str(res.data["total_credit_value"])), Decimal("55000.00"))
        self.assertEqual(Decimal(str(res.data["open_credits"])), Decimal("30000.00"))
        self.assertEqual(Decimal(str(res.data["applied_credits"])), Decimal("25000.00"))
        self.assertEqual(res.data["cancelled_credits"], 0)

    def test_retrieve_update_delete_credit_note(self):
        cn = CreditNote.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_ref="INV-0127",
            issue_date="2026-04-28",
            reason="sales_return",
            credit_amount=Decimal("10000.00"),
            applied_amount=Decimal("0.00")
        )

        # GET detail
        res_get = self.client.get(f"/api/finance/credit-notes/{cn.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["cn_number"], cn.cn_number)

        # PUT update
        res_put = self.client.put(f"/api/finance/credit-notes/{cn.id}/", {
            "customer": self.customer.id,
            "invoice_ref": "INV-0127-REV",
            "issue_date": "2026-04-29",
            "reason": "price_adjustment",
            "credit_amount": "12000.00",
            "applied_amount": "2000.00",
            "notes": "Revised credit note"
        }, format="json")
        self.assertEqual(res_put.status_code, status.HTTP_200_OK)
        self.assertEqual(res_put.data["invoice_ref"], "INV-0127-REV")
        self.assertEqual(res_put.data["status"], "partially_applied")

        # DELETE
        res_del = self.client.delete(f"/api/finance/credit-notes/{cn.id}/")
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CreditNote.objects.filter(id=cn.id).exists())

    def test_multi_company_isolation(self):
        other_company = Company.objects.create(
            name="Other Company",
            email="other_cn@armetal.com"
        )
        other_user = User.objects.create_user(
            username="other_cn_user",
            email="other_cn@armetal.com",
            password="Password123",
            company=other_company,
            is_active=True
        )

        cn = CreditNote.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_ref="INV-0128",
            issue_date="2026-04-28",
            reason="sales_return",
            credit_amount=Decimal("15000.00")
        )

        # Authenticate as user from other company
        self.client.force_authenticate(user=other_user)

        # List should return empty
        res_list = self.client.get("/api/finance/credit-notes/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data["results"]), 0)

        # Detail should return 404
        res_get = self.client.get(f"/api/finance/credit-notes/{cn.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)
