from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from superadmin.models import Company
from user.models import User
from finance.customer.models import Customer
from finance.product.models import Product
from finance.quotation.models import Quotation, QuotationItem, QuotationConversion


class QuotationAPITestCase(APITestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name="Armetal Test Company",
            email="quotation_test@armetal.com"
        )
        self.user = User.objects.create_user(
            username="quotation_admin",
            email="q_admin@armetal.com",
            password="Password123",
            company=self.company,
            is_active=True
        )
        self.client.force_authenticate(user=self.user)

        self.customer = Customer.objects.create(
            company=self.company,
            customer_name="Mediora Tech",
            industry="technology",
            currency="SAR",
            created_by=self.user
        )

        self.product = Product.objects.create(
            company=self.company,
            product_name="App Design",
            product_type="service",
            selling_price=Decimal("1970.00"),
            unit="PCS",
            tax_rate=Decimal("15.00"),
            created_by=self.user
        )

    def test_create_quotation_auto_increment(self):
        # 1. First quote without quote_number
        res1 = self.client.post("/api/finance/quotation/", {
            "customer": self.customer.id,
            "issue_date": "2026-04-28",
            "valid_till": "2026-05-28",
            "quote_amount": "22852.00",
            "status": "pending"
        }, format="json")

        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data["quote_number"], "QUT-001")
        self.assertEqual(res1.data["customer_name"], "Mediora Tech")

        # 2. Second quote auto increment
        res2 = self.client.post("/api/finance/quotation/", {
            "customer": self.customer.id,
            "issue_date": "2026-04-28",
            "valid_till": "2026-05-28",
            "quote_amount": "15000.00",
            "status": "approved"
        }, format="json")

        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.data["quote_number"], "QUT-002")

    def test_create_quotation_with_items(self):
        payload = {
            "customer": self.customer.id,
            "issue_date": "2026-04-28",
            "valid_till": "2026-05-28",
            "status": "pending",
            "discount": "19.69",
            "round_off": "0.00",
            "negotiation_amount": "22852.00",
            "notes": "Wireframe of 15 Pages",
            "items": [
                {
                    "product": self.product.id,
                    "service_name": "App Design",
                    "description": "Wireframe of 15 Pages",
                    "quantity": "1.00",
                    "hs_code": "56322",
                    "rate": "1970.00",
                    "vat_percentage": "15.00"
                }
            ]
        }

        res = self.client.post("/api/finance/quotation/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data["items"]), 1)
        self.assertEqual(res.data["items"][0]["service_name"], "App Design")
        self.assertEqual(Decimal(str(res.data["sub_total"])), Decimal("1970.00"))
        self.assertEqual(Decimal(str(res.data["total_vat"])), Decimal("295.50"))

    def test_list_quotations_with_kpi(self):
        Quotation.objects.create(
            company=self.company,
            customer=self.customer,
            issue_date="2026-04-28",
            quote_amount=Decimal("9850.00"),
            negotiation_amount=Decimal("22852.00"),
            status="pending"
        )
        Quotation.objects.create(
            company=self.company,
            customer=self.customer,
            issue_date="2026-04-28",
            quote_amount=Decimal("22852.00"),
            negotiation_amount=Decimal("0.00"),
            status="approved"
        )
        Quotation.objects.create(
            company=self.company,
            customer=self.customer,
            issue_date="2026-04-28",
            quote_amount=Decimal("5000.00"),
            negotiation_amount=Decimal("0.00"),
            status="rejected"
        )

        res = self.client.get("/api/finance/quotation/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 3)
        self.assertEqual(Decimal(str(res.data["total_quotation_value"])), Decimal("37702.00"))
        self.assertEqual(Decimal(str(res.data["negotiation_amount"])), Decimal("22852.00"))
        self.assertEqual(res.data["approved_quotes"], 1)
        self.assertEqual(res.data["rejected_quotes"], 1)
        self.assertEqual(res.data["pending_quotes"], 1)

    def test_quotation_kpi_card_endpoint(self):
        Quotation.objects.create(
            company=self.company,
            customer=self.customer,
            issue_date="2026-04-28",
            quote_amount=Decimal("9850.00"),
            negotiation_amount=Decimal("22852.00"),
            status="pending"
        )
        Quotation.objects.create(
            company=self.company,
            customer=self.customer,
            issue_date="2026-04-28",
            quote_amount=Decimal("15000.00"),
            negotiation_amount=Decimal("5000.00"),
            status="approved"
        )

        res = self.client.get("/api/finance/quotation/kpi/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(res.data["total_quotation_value"])), Decimal("24850.00"))
        self.assertEqual(Decimal(str(res.data["negotiation_amount"])), Decimal("27852.00"))
        self.assertEqual(res.data["approved_quotes"], 1)
        self.assertEqual(res.data["pending_quotes"], 1)

    def test_retrieve_update_delete_quotation(self):
        quote = Quotation.objects.create(
            company=self.company,
            customer=self.customer,
            issue_date="2026-04-28",
            quote_amount=Decimal("10000.00"),
            status="pending"
        )

        # GET detail
        res_get = self.client.get(f"/api/finance/quotation/{quote.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["quote_number"], quote.quote_number)

        # PATCH update
        res_patch = self.client.patch(f"/api/finance/quotation/{quote.id}/", {
            "status": "approved",
            "negotiation_amount": "2000.00"
        }, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch.data["status"], "approved")
        self.assertEqual(Decimal(str(res_patch.data["negotiation_amount"])), Decimal("2000.00"))

        # DELETE
        res_del = self.client.delete(f"/api/finance/quotation/{quote.id}/")
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Quotation.objects.filter(id=quote.id).exists())

    def test_convert_so_endpoint(self):
        quote = Quotation.objects.create(
            company=self.company,
            customer=self.customer,
            issue_date="2026-04-28",
            quote_amount=Decimal("22852.00"),
            status="approved"
        )

        payload = {
            "invoice_no": "CLT0012563",
            "outstanding_amount": "0.00",
            "payment_date": "2026-04-28",
            "payment_type": "full_payment",
            "payment_method": "bank_transfer",
            "amount_received": "22852.00",
            "reference_number": "REF-998877",
            "notes": "Payment received and converted to Sales Order"
        }

        res = self.client.post(f"/api/finance/quotation/{quote.id}/convert_so/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        quote.refresh_from_db()
        self.assertEqual(quote.status, "converted")

        self.assertTrue(QuotationConversion.objects.filter(quotation=quote).exists())
        conversion = QuotationConversion.objects.get(quotation=quote)
        self.assertEqual(conversion.invoice_no, "CLT0012563")
        self.assertEqual(conversion.payment_method, "bank_transfer")
        self.assertEqual(conversion.amount_received, Decimal("22852.00"))

    def test_multi_company_isolation(self):
        other_company = Company.objects.create(
            name="Other Company",
            email="other@armetal.com"
        )
        other_user = User.objects.create_user(
            username="other_user",
            email="other@armetal.com",
            password="Password123",
            company=other_company,
            is_active=True
        )

        quote = Quotation.objects.create(
            company=self.company,
            customer=self.customer,
            issue_date="2026-04-28",
            quote_amount=Decimal("5000.00"),
            status="pending"
        )

        # Switch authentication to other_user
        self.client.force_authenticate(user=other_user)

        # List should not show quote from first company
        res_list = self.client.get("/api/finance/quotation/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data["results"]), 0)

        # GET detail should return 404
        res_get = self.client.get(f"/api/finance/quotation/{quote.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        # Convert SO should return 404
        res_convert = self.client.post(f"/api/finance/quotation/{quote.id}/convert_so/", {}, format="json")
        self.assertEqual(res_convert.status_code, status.HTTP_404_NOT_FOUND)
