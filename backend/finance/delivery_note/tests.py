from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from superadmin.models import Company
from user.models import User
from finance.customer.models import Customer
from finance.warehouse.models import Warehouse
from finance.product.models import Product
from finance.delivery_note.models import DeliveryNote, DeliveryNoteItem


class DeliveryNoteAPITestCase(APITestCase):

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

        self.customer = Customer.objects.create(
            company=self.company,
            customer_name="Mediora Tech",
            industry="technology",
            currency="SAR",
            created_by=self.user
        )

        self.warehouse = Warehouse.objects.create(
            company=self.company,
            warehouse_name="Riyadh WH",
            code="WH-001",
            created_by=self.user
        )

        self.product = Product.objects.create(
            company=self.company,
            product_name="Metal Sheet",
            product_type="goods",
            selling_price=Decimal("1000.00"),
            unit="PCS",
            tax_rate=Decimal("15.00"),
            created_by=self.user
        )

    def test_create_delivery_note_auto_increment(self):
        res1 = self.client.post("/api/finance/delivery-notes/", {
            "so_ref": "SO 0123",
            "customer": self.customer.id,
            "warehouse": self.warehouse.id,
            "delivery_date": "2026-04-28",
            "delivery_value": "22852.00",
            "delivery_status": "delivered",
            "invoice_status": "fully_invoiced"
        }, format="json")

        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data["dn_number"], "DN 0123")
        self.assertEqual(res1.data["customer_name"], "Mediora Tech")
        self.assertEqual(res1.data["warehouse_name"], "Riyadh WH")

        res2 = self.client.post("/api/finance/delivery-notes/", {
            "so_ref": "SO 0124",
            "customer": self.customer.id,
            "warehouse": self.warehouse.id,
            "delivery_date": "2026-04-28",
            "delivery_value": "15000.00",
            "delivery_status": "pending",
            "invoice_status": "not_invoiced"
        }, format="json")

        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.data["dn_number"], "DN 0124")

    def test_create_delivery_note_with_items(self):
        payload = {
            "so_ref": "SO 0123",
            "customer": self.customer.id,
            "warehouse": self.warehouse.id,
            "delivery_date": "2026-04-28",
            "delivery_status": "delivered",
            "invoice_status": "fully_invoiced",
            "notes": "Delivered to Riyadh Site",
            "items": [
                {
                    "product": self.product.id,
                    "item_name": "Metal Sheet",
                    "description": "Standard 2mm sheet",
                    "quantity": "2.00",
                    "rate": "1000.00",
                    "vat_percentage": "15.00"
                }
            ]
        }

        res = self.client.post("/api/finance/delivery-notes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data["items"]), 1)
        self.assertEqual(res.data["items"][0]["item_name"], "Metal Sheet")
        self.assertEqual(Decimal(str(res.data["sub_total"])), Decimal("2000.00"))
        self.assertEqual(Decimal(str(res.data["total_vat"])), Decimal("300.00"))
        self.assertEqual(Decimal(str(res.data["delivery_value"])), Decimal("2300.00"))

    def test_list_delivery_notes_with_kpi(self):
        DeliveryNote.objects.create(
            company=self.company,
            customer=self.customer,
            warehouse=self.warehouse,
            delivery_date="2026-04-28",
            delivery_value=Decimal("22852.00"),
            delivery_status="delivered",
            invoice_status="fully_invoiced"
        )
        DeliveryNote.objects.create(
            company=self.company,
            customer=self.customer,
            warehouse=self.warehouse,
            delivery_date="2026-04-28",
            delivery_value=Decimal("10000.00"),
            delivery_status="pending",
            invoice_status="not_invoiced"
        )
        DeliveryNote.objects.create(
            company=self.company,
            customer=self.customer,
            warehouse=self.warehouse,
            delivery_date="2026-04-28",
            delivery_value=Decimal("5000.00"),
            delivery_status="partially_delivered",
            invoice_status="partially_invoiced"
        )

        res = self.client.get("/api/finance/delivery-notes/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 3)
        self.assertEqual(res.data["total_deliveries"], 3)
        self.assertEqual(res.data["pending_deliveries"], 1)
        self.assertEqual(res.data["partially_delivered"], 1)
        self.assertEqual(res.data["delivered"], 1)
        self.assertEqual(Decimal(str(res.data["delivery_value"])), Decimal("37852.00"))

    def test_delivery_note_kpi_card_endpoint(self):
        DeliveryNote.objects.create(
            company=self.company,
            customer=self.customer,
            warehouse=self.warehouse,
            delivery_date="2026-04-28",
            delivery_value=Decimal("22852.00"),
            delivery_status="delivered",
            invoice_status="fully_invoiced"
        )
        DeliveryNote.objects.create(
            company=self.company,
            customer=self.customer,
            warehouse=self.warehouse,
            delivery_date="2026-04-28",
            delivery_value=Decimal("12000.00"),
            delivery_status="pending",
            invoice_status="not_invoiced"
        )

        res = self.client.get("/api/finance/delivery-notes/kpi/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_deliveries"], 2)
        self.assertEqual(res.data["pending_deliveries"], 1)
        self.assertEqual(res.data["delivered"], 1)
        self.assertEqual(Decimal(str(res.data["delivery_value"])), Decimal("34852.00"))

    def test_retrieve_update_delete_delivery_note(self):
        dn = DeliveryNote.objects.create(
            company=self.company,
            customer=self.customer,
            warehouse=self.warehouse,
            delivery_date="2026-04-28",
            delivery_value=Decimal("22852.00"),
            delivery_status="dispatched"
        )

        # GET detail
        res_get = self.client.get(f"/api/finance/delivery-notes/{dn.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["dn_number"], dn.dn_number)

        # PATCH update
        res_patch = self.client.patch(f"/api/finance/delivery-notes/{dn.id}/", {
            "delivery_status": "delivered",
            "invoice_status": "fully_invoiced"
        }, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch.data["delivery_status"], "delivered")
        self.assertEqual(res_patch.data["invoice_status"], "fully_invoiced")

        # DELETE
        res_del = self.client.delete(f"/api/finance/delivery-notes/{dn.id}/")
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DeliveryNote.objects.filter(id=dn.id).exists())

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

        dn = DeliveryNote.objects.create(
            company=self.company,
            customer=self.customer,
            warehouse=self.warehouse,
            delivery_date="2026-04-28",
            delivery_value=Decimal("5000.00"),
            delivery_status="pending"
        )

        # Switch authentication to other_user
        self.client.force_authenticate(user=other_user)

        # List should not show dn from first company
        res_list = self.client.get("/api/finance/delivery-notes/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data["results"]), 0)

        # GET detail should return 404
        res_get = self.client.get(f"/api/finance/delivery-notes/{dn.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)
