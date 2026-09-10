from rest_framework.test import APITestCase
from rest_framework import status
from superadmin.models import Company
from user.models import User
from finance.warehouse.models import Warehouse
from finance.category.models import Category
from finance.product.models import Product
from finance.inventory.models import StockAdjustment


class InventoryAPITestCase(APITestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name="Inventory Test Company",
            email="inv_test@armetal.com"
        )
        self.user = User.objects.create_user(
            username="inv_admin",
            email="inv_admin@armetal.com",
            password="Password123",
            company=self.company,
            is_active=True
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            code="WH-INV-01",
            warehouse_name="Riyadh Inventory Warehouse"
        )
        self.category = Category.objects.create(
            company=self.company,
            code="CAT-INV-01",
            category_name="Networking Hardware",
            category_type="product"
        )
        self.product = Product.objects.create(
            company=self.company,
            code="CAT-001",
            product_name="Cisco Router C9300",
            product_type="product",
            sku="1253698",
            category=self.category,
            warehouse=self.warehouse,
            opening_stock_qty=100,
            current_stock=120,
            selling_price="1000.00",
            reorder_level=20,
            unit="PCS"
        )
        self.client.force_authenticate(user=self.user)

    def test_inventory_list_and_kpi(self):
        # KPI Card View
        kpi_res = self.client.get("/api/finance/inventory/kpi/")
        self.assertEqual(kpi_res.status_code, status.HTTP_200_OK)
        self.assertEqual(kpi_res.data["total_stock_items"], 1)
        self.assertEqual(kpi_res.data["in_stock"], 1)
        self.assertEqual(kpi_res.data["total_inventory_value"], 120000.00)

        # Inventory List View
        list_res = self.client.get("/api/finance/inventory/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(list_res.data["total_stock_items"], 1)
        self.assertEqual(len(list_res.data["results"]), 1)
        item = list_res.data["results"][0]
        self.assertEqual(item["code"], "CAT-001")
        self.assertEqual(item["available_qty"], 120)
        self.assertEqual(item["stock_status"], "In Stock")

    def test_stock_adjustment_addition_increases_current_stock(self):
        res = self.client.post("/api/finance/inventory/adjustments/", {
            "product": self.product.id,
            "warehouse": self.warehouse.id,
            "adjustment_type": "addition",
            "adjustment_quantity": 30,
            "reason": "inventory_count",
            "note": "Stock count recount addition"
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["code"].startswith("SA"))
        self.assertEqual(res.data["current_available_qty"], 120)
        self.assertEqual(res.data["adjustment_quantity"], 30)

        # Refresh product from DB and check stock
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 150)

    def test_stock_adjustment_subtraction_decreases_current_stock(self):
        res = self.client.post("/api/finance/inventory/adjustments/", {
            "product": self.product.id,
            "warehouse": self.warehouse.id,
            "adjustment_type": "subtraction",
            "adjustment_quantity": 20,
            "reason": "damaged",
            "reference_document": "DMG-551"
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["code"].startswith("SA"))

        # Refresh product from DB and check stock
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 100)

    def test_stock_adjustment_subtraction_exceeds_stock_fails(self):
        res = self.client.post("/api/finance/inventory/adjustments/", {
            "product": self.product.id,
            "warehouse": self.warehouse.id,
            "adjustment_type": "subtraction",
            "adjustment_quantity": 500,
            "reason": "damaged"
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("adjustment_quantity", res.data)

    def test_stock_adjustment_modal_add_and_reduce_stock_types(self):
        # Test add_stock with modal fields
        res_add = self.client.post("/api/finance/inventory/adjustments/", {
            "product": self.product.id,
            "warehouse": self.warehouse.id,
            "adjustment_type": "add_stock",
            "adjustment_quantity": 25,
            "reason": "Inventory Count",
            "note": "Modal add stock test"
        }, format="json")
        self.assertEqual(res_add.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res_add.data["code"].startswith("SA"))
        self.assertEqual(res_add.data["adjustment_number"], res_add.data["code"])
        self.assertEqual(res_add.data["current_available_qty"], 120)
        self.assertEqual(res_add.data["adjusted_stock"], 145)

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 145)

        # Test reduce_stock with modal fields
        res_reduce = self.client.post("/api/finance/inventory/adjustments/", {
            "product": self.product.id,
            "warehouse": self.warehouse.id,
            "adjustment_type": "reduce_stock",
            "adjustment_quantity": 15,
            "reason": "Damaged Stock",
            "note": "Modal reduce stock test"
        }, format="json")
        self.assertEqual(res_reduce.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_reduce.data["current_available_qty"], 145)
        self.assertEqual(res_reduce.data["adjusted_stock"], 130)

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 130)

    def test_stock_adjustment_remove_stock_and_set_exact_quantity(self):
        # Test Remove Stock
        res_remove = self.client.post("/api/finance/inventory/adjustments/", {
            "product": self.product.id,
            "warehouse": self.warehouse.id,
            "adjustment_type": "Remove Stock",
            "adjustment_quantity": 10,
            "reason": "Lost/Missing",
            "note": "Items lost during transport"
        }, format="json")
        self.assertEqual(res_remove.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_remove.data["current_available_qty"], 120)
        self.assertEqual(res_remove.data["adjusted_stock"], 110)

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 110)

        # Test Set Exact Quantity
        res_exact = self.client.post("/api/finance/inventory/adjustments/", {
            "product": self.product.id,
            "warehouse": self.warehouse.id,
            "adjustment_type": "Set Exact Quantity",
            "adjustment_quantity": 115,
            "reason": "New Stock Received",
            "note": "Reconciled stock to 115"
        }, format="json")
        self.assertEqual(res_exact.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_exact.data["current_available_qty"], 110)
        self.assertEqual(res_exact.data["adjusted_stock"], 115)

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 115)


