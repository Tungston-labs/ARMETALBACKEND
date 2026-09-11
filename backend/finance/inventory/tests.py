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

    def test_put_and_patch_stock_adjustment(self):
        adj = StockAdjustment.objects.create(
            company=self.company,
            product=self.product,
            warehouse=self.warehouse,
            adjustment_type="add_stock",
            adjustment_quantity=10,
            reason="Inventory Count",
            note="Initial note"
        )

        # GET detail
        get_res = self.client.get(f"/api/finance/inventory/adjustments/{adj.id}/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["reason"], "Inventory Count")

        # PATCH update
        patch_res = self.client.patch(f"/api/finance/inventory/adjustments/{adj.id}/", {
            "note": "Updated note via PATCH",
            "reference_document": "REF-1002"
        }, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["note"], "Updated note via PATCH")
        self.assertEqual(patch_res.data["reference_document"], "REF-1002")

        # PUT update
        put_res = self.client.put(f"/api/finance/inventory/adjustments/{adj.id}/", {
            "product": self.product.id,
            "warehouse": self.warehouse.id,
            "adjustment_type": "add_stock",
            "adjustment_quantity": 10,
            "reason": "Data Entry Correction",
            "reference_document": "REF-2000",
            "note": "Fully updated via PUT"
        }, format="json")
        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.assertEqual(put_res.data["reason"], "Data Entry Correction")
        self.assertEqual(put_res.data["note"], "Fully updated via PUT")

    def test_delete_stock_adjustment(self):
        adj = StockAdjustment.objects.create(
            company=self.company,
            product=self.product,
            warehouse=self.warehouse,
            adjustment_type="add_stock",
            adjustment_quantity=5,
            reason="Other"
        )

        del_res = self.client.delete(f"/api/finance/inventory/adjustments/{adj.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(StockAdjustment.objects.filter(id=adj.id).exists())

    def test_inventory_list_filters_by_stock_status(self):
        # Product 1: In stock (stock=120) created in setUp
        # Product 2: Low stock (stock=5)
        Product.objects.create(
            company=self.company,
            code="PRD-LOW-STK",
            product_name="Low Stock Item",
            product_type="product",
            current_stock=5,
            reorder_level=20
        )
        # Product 3: Out of stock (stock=0)
        Product.objects.create(
            company=self.company,
            code="PRD-OUT-STK",
            product_name="Out Stock Item",
            product_type="product",
            current_stock=0,
            reorder_level=10
        )

        # Filter low_stock
        res_low = self.client.get("/api/finance/inventory/?stock_status=low_stock")
        self.assertEqual(res_low.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_low.data["results"]), 1)
        self.assertEqual(res_low.data["results"][0]["code"], "PRD-LOW-STK")

        # Filter out_of_stock
        res_out = self.client.get("/api/finance/inventory/?stock_status=out_of_stock")
        self.assertEqual(res_out.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_out.data["results"]), 1)
        self.assertEqual(res_out.data["results"][0]["code"], "PRD-OUT-STK")



