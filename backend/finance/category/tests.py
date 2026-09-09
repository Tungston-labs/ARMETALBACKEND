from rest_framework.test import APITestCase
from rest_framework import status
from superadmin.models import Company
from user.models import User
from finance.category.models import Category


class CategoryAPITestCase(APITestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name="Category Test Company",
            email="cat_test@armetal.com"
        )
        self.user = User.objects.create_user(
            username="cat_admin",
            email="cat_admin@armetal.com",
            password="Password123",
            company=self.company,
            is_active=True
        )
        self.client.force_authenticate(user=self.user)

    def test_create_category_auto_increment(self):
        res1 = self.client.post("/api/finance/category/", {
            "category_name": "Networking",
            "category_type": "product",
            "status": "active"
        }, format="json")
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data["code"], "CAT-001")

        res2 = self.client.post("/api/finance/category/", {
            "category_name": "Cloud Services",
            "category_type": "service",
            "status": "active"
        }, format="json")
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.data["code"], "CAT-002")

    def test_list_categories_with_stats(self):
        Category.objects.create(
            company=self.company,
            code="CAT-001",
            category_name="Hardware",
            category_type="product",
            status="active"
        )
        Category.objects.create(
            company=self.company,
            code="CAT-002",
            category_name="Consulting",
            category_type="service",
            status="inactive"
        )

        res = self.client.get("/api/finance/category/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_categories"], 2)
        self.assertEqual(res.data["active_categories"], 1)
        self.assertEqual(res.data["inactive_categories"], 1)
        self.assertEqual(res.data["product_categories"], 1)
        self.assertEqual(res.data["service_categories"], 1)

    def test_category_kpi_card_endpoint(self):
        Category.objects.create(
            company=self.company,
            code="CAT-101",
            category_name="Electronics",
            category_type="product",
            status="active"
        )
        Category.objects.create(
            company=self.company,
            code="CAT-102",
            category_name="Support Services",
            category_type="service",
            status="active"
        )
        Category.objects.create(
            company=self.company,
            code="CAT-103",
            category_name="Legacy Systems",
            category_type="product",
            status="inactive"
        )

        res = self.client.get("/api/finance/category/kpi/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_categories"], 3)
        self.assertEqual(res.data["active_categories"], 2)
        self.assertEqual(res.data["inactive_categories"], 1)
        self.assertEqual(res.data["product_categories"], 2)
        self.assertEqual(res.data["service_categories"], 1)

    def test_retrieve_update_delete_category(self):
        cat = Category.objects.create(
            company=self.company,
            code="CAT-TEST",
            category_name="Initial Category",
            category_type="product"
        )

        # GET Detail
        get_res = self.client.get(f"/api/finance/category/{cat.id}/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["category_name"], "Initial Category")

        # PATCH Update
        patch_res = self.client.patch(f"/api/finance/category/{cat.id}/", {
            "category_name": "Updated Category Name"
        }, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["category_name"], "Updated Category Name")

        # DELETE
        del_res = self.client.delete(f"/api/finance/category/{cat.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(id=cat.id).exists())

    def test_unique_category_code_per_company(self):
        Category.objects.create(
            company=self.company,
            code="CAT-DUP",
            category_name="First Category",
            category_type="product"
        )
        res = self.client.post("/api/finance/category/", {
            "code": "CAT-DUP",
            "category_name": "Duplicate Category",
            "category_type": "product"
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", res.data)
