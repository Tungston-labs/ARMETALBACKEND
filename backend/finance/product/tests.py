from rest_framework.test import APITestCase
from rest_framework import status
from superadmin.models import Company
from user.models import User
from finance.warehouse.models import Warehouse
from finance.category.models import Category
from finance.product.models import Product


class ProductAPITestCase(APITestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name="Product Test Company",
            email="prd_test@armetal.com"
        )
        self.user = User.objects.create_user(
            username="prd_admin",
            email="prd_admin@armetal.com",
            password="Password123",
            company=self.company,
            is_active=True
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            code="WH-001",
            warehouse_name="Riyadh Central Warehouse"
        )
        self.category = Category.objects.create(
            company=self.company,
            code="CAT-001",
            category_name="Networking",
            category_type="product"
        )
        self.client.force_authenticate(user=self.user)

    def test_create_product_auto_increment(self):
        # Create product 1
        res1 = self.client.post("/api/finance/product/", {
            "product_name": "Cisco Router C9300",
            "product_type": "product",
            "cost_price": "9500.00",
            "selling_price": "12000.00"
        }, format="json")
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data["code"], "PRD-001")

        # Create product 2
        res2 = self.client.post("/api/finance/product/", {
            "product_name": "CAT6 Network Cable",
            "product_type": "product",
            "cost_price": "320.00",
            "selling_price": "500.00"
        }, format="json")
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.data["code"], "PRD-002")

    def test_product_with_warehouse_and_category_fk(self):
        res = self.client.post("/api/finance/product/", {
            "product_name": "Network Rack 42U",
            "product_type": "product",
            "category": self.category.id,
            "warehouse": self.warehouse.id,
            "brand": "APC",
            "supplier": "Cisco",
            "cost_price": "4800.00",
            "selling_price": "6000.00",
            "opening_stock_qty": 50,
            "reorder_level": 10
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["category"], self.category.id)
        self.assertEqual(res.data["category_name"], "Networking")
        self.assertEqual(res.data["warehouse"], self.warehouse.id)
        self.assertEqual(res.data["warehouse_name"], "Riyadh Central Warehouse")
        self.assertEqual(res.data["stock_status"], "In Stock")

    def test_stock_status_property(self):
        # Out of stock product (0 stock)
        p_out = Product.objects.create(
            company=self.company,
            code="PRD-OUT",
            product_name="Out of Stock Item",
            current_stock=0,
            reorder_level=10
        )
        self.assertEqual(p_out.stock_status, "Out of Stock")

        # Low stock product (5 stocks, less than 10)
        p_low = Product.objects.create(
            company=self.company,
            code="PRD-LOW",
            product_name="Low Stock Item",
            current_stock=5,
            reorder_level=10
        )
        self.assertEqual(p_low.stock_status, "Low Stock")

        # Boundary low stock product (9 stocks, less than 10)
        p_low9 = Product.objects.create(
            company=self.company,
            code="PRD-LOW9",
            product_name="Low Stock Item 9",
            current_stock=9,
            reorder_level=10
        )
        self.assertEqual(p_low9.stock_status, "Low Stock")

        # Stock 10 product (10 stocks, In Stock)
        p_stock10 = Product.objects.create(
            company=self.company,
            code="PRD-10",
            product_name="Stock 10 Item",
            current_stock=10,
            reorder_level=10
        )
        self.assertEqual(p_stock10.stock_status, "In Stock")

        # Normal product (50 stocks)
        p_norm = Product.objects.create(
            company=self.company,
            code="PRD-NORM",
            product_name="Normal Stock Item",
            current_stock=50,
            reorder_level=10
        )
        self.assertEqual(p_norm.stock_status, "In Stock")

    def test_list_products_with_summary_stats(self):
        Product.objects.create(
            company=self.company,
            code="PRD-1",
            product_name="Item 1",
            category=self.category,
            current_stock=100,
            reorder_level=10,
            status="active"
        )
        Product.objects.create(
            company=self.company,
            code="PRD-2",
            product_name="Item 2",
            category=self.category,
            current_stock=5,
            reorder_level=10,
            status="active"
        )
        Product.objects.create(
            company=self.company,
            code="PRD-3",
            product_name="Item 3",
            category=self.category,
            current_stock=0,
            reorder_level=10,
            status="inactive"
        )

        res = self.client.get("/api/finance/product/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_products"], 3)
        self.assertEqual(res.data["active_products"], 2)
        self.assertEqual(res.data["low_stock"], 1)
        self.assertEqual(res.data["out_of_stock"], 1)
        self.assertEqual(res.data["total_categories"], 1)

    def test_retrieve_update_delete_product(self):
        prd = Product.objects.create(
            company=self.company,
            code="PRD-TEST",
            product_name="Initial Product",
            selling_price="100.00"
        )

        # GET Detail
        get_res = self.client.get(f"/api/finance/product/{prd.id}/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["product_name"], "Initial Product")

        # PATCH Update
        patch_res = self.client.patch(f"/api/finance/product/{prd.id}/", {
            "product_name": "Updated Product Name",
            "selling_price": "150.00"
        }, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["product_name"], "Updated Product Name")

        # DELETE
        del_res = self.client.delete(f"/api/finance/product/{prd.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(id=prd.id).exists())

    def test_product_kpi_card_endpoint(self):
        cat2 = Category.objects.create(
            company=self.company,
            code="CAT-002",
            category_name="Cables",
            category_type="product"
        )
        Product.objects.create(
            company=self.company,
            code="PRD-101",
            product_name="Product In Stock Active",
            category=self.category,
            current_stock=100,
            reorder_level=10,
            status="active",
            product_type="product"
        )
        Product.objects.create(
            company=self.company,
            code="PRD-102",
            product_name="Product Low Stock Active",
            category=cat2,
            current_stock=5,
            reorder_level=10,
            status="active",
            product_type="product"
        )
        Product.objects.create(
            company=self.company,
            code="PRD-103",
            product_name="Product Out Stock Inactive",
            category=self.category,
            current_stock=0,
            reorder_level=10,
            status="inactive",
            product_type="product"
        )

        res = self.client.get("/api/finance/product/kpi/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_products"], 3)
        self.assertEqual(res.data["active_products"], 2)
        self.assertEqual(res.data["low_stock"], 1)
        self.assertEqual(res.data["out_of_stock"], 1)
        self.assertEqual(res.data["total_categories"], 2)

    def test_create_product_with_quantity_increases_current_stock(self):
        res = self.client.post("/api/finance/product/", {
            "product_name": "Ethernet Switch 24P",
            "product_type": "product",
            "opening_stock_qty": 10,
            "quantity": 25,
            "cost_price": "1500.00",
            "selling_price": "2000.00"
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["quantity"], 25)
        self.assertEqual(res.data["opening_stock_qty"], 10)
        # current_stock should equal opening_stock_qty (10) + quantity (25) = 35
        self.assertEqual(res.data["current_stock"], 35)

    def test_put_full_update_product(self):
        prd = Product.objects.create(
            company=self.company,
            code="PRD-PUT-01",
            product_name="Original Product",
            product_type="product",
            cost_price="100.00",
            selling_price="150.00"
        )

        put_res = self.client.put(f"/api/finance/product/{prd.id}/", {
            "product_name": "Fully Updated Product Name",
            "product_type": "product",
            "sku": "SKU-998877",
            "category": self.category.id,
            "warehouse": self.warehouse.id,
            "brand": "Schneider",
            "supplier": "Global Supplies Ltd",
            "unit": "PCS",
            "cost_price": "120.00",
            "selling_price": "180.00",
            "tax_type": "vat",
            "tax_rate": "15.00",
            "reorder_level": 15,
            "description": "Full replace update test via PUT",
            "status": "active"
        }, format="json")

        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.assertEqual(put_res.data["product_name"], "Fully Updated Product Name")
        self.assertEqual(put_res.data["sku"], "SKU-998877")
        self.assertEqual(put_res.data["cost_price"], "120.00")
        self.assertEqual(put_res.data["selling_price"], "180.00")
        self.assertEqual(put_res.data["category_name"], "Networking")
        self.assertEqual(put_res.data["warehouse_name"], "Riyadh Central Warehouse")

        prd.refresh_from_db()
        self.assertEqual(prd.product_name, "Fully Updated Product Name")

    def test_patch_partial_update_product_prices_and_fk(self):
        prd = Product.objects.create(
            company=self.company,
            code="PRD-PATCH-01",
            product_name="Base Product",
            product_type="product",
            cost_price="500.00",
            selling_price="750.00"
        )

        patch_res = self.client.patch(f"/api/finance/product/{prd.id}/", {
            "selling_price": "850.00",
            "brand": "Dell",
            "category": self.category.id
        }, format="json")

        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["selling_price"], "850.00")
        self.assertEqual(patch_res.data["brand"], "Dell")
        self.assertEqual(patch_res.data["category_name"], "Networking")
        # Ensure product name wasn't modified
        self.assertEqual(patch_res.data["product_name"], "Base Product")

    def test_product_filter_and_search(self):
        Product.objects.create(
            company=self.company,
            code="PRD-FLT-1",
            product_name="Optical Fiber Cable",
            product_type="product",
            category=self.category,
            status="active"
        )
        Product.objects.create(
            company=self.company,
            code="PRD-FLT-2",
            product_name="Consulting Support",
            product_type="service",
            status="inactive"
        )

        # Filter by product_type
        res_filter = self.client.get("/api/finance/product/?product_type=service")
        self.assertEqual(res_filter.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_filter.data["results"]), 1)
        self.assertEqual(res_filter.data["results"][0]["code"], "PRD-FLT-2")

        # Search by product_name
        res_search = self.client.get("/api/finance/product/?search=Optical")
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_search.data["results"]), 1)
        self.assertEqual(res_search.data["results"][0]["code"], "PRD-FLT-1")



