from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from superadmin.models import Company
from user.models import User
from finance.customer.models import Customer
from finance.warehouse.models import Warehouse
from finance.product.models import Product
from finance.quotation.models import Quotation, QuotationItem
from finance.sales_order.models import SalesOrder, SalesOrderItem
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
            quantity=100,
            current_stock=100,
            reserved_qty=30,
            created_by=self.user
        )

        self.quotation = Quotation.objects.create(
            company=self.company,
            customer=self.customer,
            quote_number="QT-001",
            issue_date="2026-04-01",
            valid_till="2026-12-31",
            status="approved",
            created_by=self.user
        )

        self.so = SalesOrder.objects.create(
            company=self.company,
            quotation=self.quotation,
            customer=self.customer,
            so_number="SO 0123",
            order_date="2026-04-01",
            order_value=Decimal("20000.00"),
            created_by=self.user
        )

        self.so_item = SalesOrderItem.objects.create(
            sales_order=self.so,
            product=self.product,
            quantity=Decimal("20.00"),
            delivered_quantity=Decimal("0.00"),
            rate=Decimal("1000.00"),
            vat_percentage=Decimal("15.00")
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

    def test_create_delivery_note_with_items_deducts_inventory_and_reserved_qty(self):
        # Initial stock: 100, reserved: 30
        payload = {
            "sales_order": self.so.id,
            "so_ref": "SO 0123",
            "customer": self.customer.id,
            "warehouse": self.warehouse.id,
            "delivery_date": "2026-04-28",
            "delivery_status": "delivered",
            "invoice_status": "fully_invoiced",
            "notes": "Delivered to Riyadh Site",
            "items": [
                {
                    "sales_order_item": self.so_item.id,
                    "product": self.product.id,
                    "item_name": "Metal Sheet",
                    "quantity": "12.00",
                    "rate": "1000.00",
                    "vat_percentage": "15.00"
                }
            ]
        }

        res = self.client.post("/api/finance/delivery-notes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data["items"]), 1)
        
        item_res = res.data["items"][0]
        self.assertEqual(item_res["delivering_now"], Decimal("12.00"))
        self.assertEqual(Decimal(str(item_res["ordered_qty"])), Decimal("20.00"))
        self.assertEqual(Decimal(str(item_res["already_delivered"])), Decimal("0.00"))
        self.assertEqual(Decimal(str(item_res["balance"])), Decimal("8.00"))
        self.assertEqual(item_res["status"], "Partial")

        # Verify product inventory stock & reserved_qty deducted
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 88)  # 100 - 12
        self.assertEqual(self.product.reserved_qty, 18)    # 30 - 12

        # Verify SO item delivered quantity updated
        self.so_item.refresh_from_db()
        self.assertEqual(self.so_item.delivered_quantity, Decimal("12.00"))

        # Verify SO delivery_status is partially_delivered
        self.so.refresh_from_db()
        self.assertEqual(self.so.delivery_status, "partially_delivered")

    def test_delivery_note_fully_delivered_item_status(self):
        payload = {
            "sales_order": self.so.id,
            "customer": self.customer.id,
            "delivery_date": "2026-04-28",
            "items": [
                {
                    "sales_order_item": self.so_item.id,
                    "product": self.product.id,
                    "quantity": "20.00",
                    "rate": "1000.00",
                    "vat_percentage": "15.00"
                }
            ]
        }

        res = self.client.post("/api/finance/delivery-notes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        item_res = res.data["items"][0]
        self.assertEqual(Decimal(str(item_res["balance"])), Decimal("0.00"))
        self.assertEqual(item_res["status"], "Fully Delivered")

        self.so.refresh_from_db()
        self.assertEqual(self.so.delivery_status, "completed")

    def test_sales_order_prefill_endpoint(self):
        res = self.client.get(f"/api/finance/delivery-notes/so-prefill/{self.so.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["sales_order"], self.so.id)
        self.assertEqual(res.data["so_ref"], "SO 0123")
        self.assertEqual(len(res.data["items"]), 1)
        self.assertEqual(Decimal(str(res.data["items"][0]["ordered_qty"])), Decimal("20.00"))
        self.assertEqual(Decimal(str(res.data["items"][0]["delivering_now"])), Decimal("20.00"))

    def test_delete_delivery_note_restores_inventory(self):
        payload = {
            "sales_order": self.so.id,
            "customer": self.customer.id,
            "delivery_date": "2026-04-28",
            "items": [
                {
                    "sales_order_item": self.so_item.id,
                    "product": self.product.id,
                    "quantity": "10.00",
                    "rate": "1000.00"
                }
            ]
        }

        res = self.client.post("/api/finance/delivery-notes/", payload, format="json")
        dn_id = res.data["id"]

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 90)
        self.assertEqual(self.product.reserved_qty, 20)

        # Delete Delivery Note
        res_del = self.client.delete(f"/api/finance/delivery-notes/{dn_id}/")
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)

        # Check inventory restored
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 100)
        self.assertEqual(self.product.reserved_qty, 30)

        self.so_item.refresh_from_db()
        self.assertEqual(self.so_item.delivered_quantity, Decimal("0.00"))
