from rest_framework.test import APITestCase
from rest_framework import status
from superadmin.models import Company
from user.models import User
from finance.warehouse.models import Warehouse


class WarehouseAPITestCase(APITestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name="Armetal Test Company",
            email="wh_test@armetal.com"
        )
        self.user = User.objects.create_user(
            username="wh_admin",
            email="wh_admin@armetal.com",
            password="Password123",
            company=self.company,
            is_active=True
        )
        self.client.force_authenticate(user=self.user)

    def test_create_warehouse_auto_increment(self):
        # 1. Create first warehouse without explicit code
        response1 = self.client.post("/api/finance/warehouse/", {
            "warehouse_name": "Riyadh Central Warehouse",
            "warehouse_type": "main",
            "city": "Riyadh",
            "country": "Saudi Arabia"
        }, format="json")
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response1.data["code"], "WH-001")

        # 2. Create second warehouse without explicit code
        response2 = self.client.post("/api/finance/warehouse/", {
            "warehouse_name": "Jeddah Distribution Center",
            "warehouse_type": "distribution",
            "city": "Jeddah",
            "country": "Saudi Arabia"
        }, format="json")
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response2.data["code"], "WH-002")

    def test_list_warehouses_with_stats(self):
        Warehouse.objects.create(
            company=self.company,
            code="WH-001",
            warehouse_name="Active WH",
            status="active"
        )
        Warehouse.objects.create(
            company=self.company,
            code="WH-002",
            warehouse_name="Inactive WH",
            status="inactive"
        )

        response = self.client.get("/api/finance/warehouse/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_warehouses"], 2)
        self.assertEqual(response.data["active_warehouses"], 1)
        self.assertEqual(response.data["inactive_warehouses"], 1)

    def test_retrieve_update_delete_warehouse(self):
        wh = Warehouse.objects.create(
            company=self.company,
            code="WH-001",
            warehouse_name="Dammam WH",
            city="Dammam"
        )

        # GET Detail
        get_res = self.client.get(f"/api/finance/warehouse/{wh.id}/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["warehouse_name"], "Dammam WH")

        # PATCH Update
        patch_res = self.client.patch(f"/api/finance/warehouse/{wh.id}/", {
            "warehouse_name": "Dammam Regional Warehouse",
            "phone_number": "+966500000000"
        }, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["warehouse_name"], "Dammam Regional Warehouse")

        # DELETE
        del_res = self.client.delete(f"/api/finance/warehouse/{wh.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Warehouse.objects.filter(id=wh.id).exists())

    def test_unique_code_per_company(self):
        Warehouse.objects.create(
            company=self.company,
            code="WH-CUSTOM-1",
            warehouse_name="First WH"
        )
        response = self.client.post("/api/finance/warehouse/", {
            "code": "WH-CUSTOM-1",
            "warehouse_name": "Duplicate WH"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", response.data)

    def test_warehouse_kpi_card_endpoint(self):
        Warehouse.objects.create(
            company=self.company,
            code="WH-101",
            warehouse_name="Active WH 1",
            status="active"
        )
        Warehouse.objects.create(
            company=self.company,
            code="WH-102",
            warehouse_name="Active WH 2",
            status="active"
        )
        Warehouse.objects.create(
            company=self.company,
            code="WH-103",
            warehouse_name="Inactive WH 1",
            status="inactive"
        )

        response = self.client.get("/api/finance/warehouse/kpi/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_warehouses"], 3)
        self.assertEqual(response.data["active_warehouses"], 2)
        self.assertEqual(response.data["inactive_warehouses"], 1)

    def test_put_full_update_warehouse(self):
        wh = Warehouse.objects.create(
            company=self.company,
            code="WH-001",
            warehouse_name="Original WH",
            warehouse_type="main",
            status="active",
            city="Riyadh"
        )

        put_res = self.client.put(f"/api/finance/warehouse/{wh.id}/", {
            "warehouse_name": "Fully Replaced Warehouse",
            "warehouse_type": "regional",
            "status": "inactive",
            "city": "Al Khobar",
            "country": "Saudi Arabia",
            "address_line_1": "Industrial Area Phase 2",
            "postal_code": "31952",
            "phone_number": "+966138001122",
            "email": "khobar@armetal.com",
            "storage_capacity": "50000 SQM",
            "notes": "Replaced completely via HTTP PUT"
        }, format="json")

        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.assertEqual(put_res.data["warehouse_name"], "Fully Replaced Warehouse")
        self.assertEqual(put_res.data["warehouse_type"], "regional")
        self.assertEqual(put_res.data["status"], "inactive")
        self.assertEqual(put_res.data["city"], "Al Khobar")
        self.assertEqual(put_res.data["email"], "khobar@armetal.com")

        wh.refresh_from_db()
        self.assertEqual(wh.warehouse_name, "Fully Replaced Warehouse")
        self.assertEqual(wh.status, "inactive")

    def test_patch_partial_update_warehouse(self):
        wh = Warehouse.objects.create(
            company=self.company,
            code="WH-002",
            warehouse_name="Partial Update WH",
            warehouse_type="main",
            status="active",
            city="Jeddah"
        )

        patch_res = self.client.patch(f"/api/finance/warehouse/{wh.id}/", {
            "status": "inactive",
            "notes": "Deactivated temporarily via HTTP PATCH"
        }, format="json")

        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["status"], "inactive")
        self.assertEqual(patch_res.data["notes"], "Deactivated temporarily via HTTP PATCH")
        # Ensure unchanged fields remained intact
        self.assertEqual(patch_res.data["warehouse_name"], "Partial Update WH")
        self.assertEqual(patch_res.data["city"], "Jeddah")

    def test_warehouse_filter_and_search(self):
        Warehouse.objects.create(
            company=self.company,
            code="WH-RDH",
            warehouse_name="Riyadh Central Hub",
            warehouse_type="main",
            status="active",
            city="Riyadh"
        )
        Warehouse.objects.create(
            company=self.company,
            code="WH-JDD",
            warehouse_name="Jeddah Port Depot",
            warehouse_type="distribution",
            status="inactive",
            city="Jeddah"
        )

        # Filter by status
        res_filter = self.client.get("/api/finance/warehouse/?status=active")
        self.assertEqual(res_filter.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_filter.data["results"]), 1)
        self.assertEqual(res_filter.data["results"][0]["code"], "WH-RDH")

        # Search by warehouse name
        res_search = self.client.get("/api/finance/warehouse/?search=Jeddah")
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_search.data["results"]), 1)
        self.assertEqual(res_search.data["results"][0]["code"], "WH-JDD")


