import csv
import io
from datetime import date
from decimal import Decimal

import openpyxl
from rest_framework import status
from rest_framework.test import APITestCase

from finance.customer.models import Customer
from finance.product.models import Product
from finance.quotation.models import Quotation
from finance.sales_order.models import SalesOrder
from finance.warehouse.models import Warehouse
from superadmin.models import Company
from user.models import User


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
        self.assertEqual(response1.data["total_units"], "0.00")
        self.assertEqual(response1.data["stock_value"], "0.00")

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

    def test_warehouse_metrics_total_units_stock_value_and_capacity(self):
        wh1 = Warehouse.objects.create(
            company=self.company,
            code="WH-001",
            warehouse_name="Riyadh Central Warehouse",
            warehouse_type="main",
            manager="Ahmed Ali",
            city="Riyadh",
            storage_capacity="400",
            status="active",
        )
        wh2 = Warehouse.objects.create(
            company=self.company,
            code="WH-002",
            warehouse_name="Jeddah Distribution Center",
            warehouse_type="distribution",
            manager="Omar Khan",
            city="Jeddah",
            storage_capacity="100",
            status="active",
        )
        wh3 = Warehouse.objects.create(
            company=self.company,
            code="WH-003",
            warehouse_name="Dammam Warehouse",
            warehouse_type="regional",
            manager="Faisal Noor",
            city="Dammam",
            storage_capacity="120",
            status="active",
        )
        wh4 = Warehouse.objects.create(
            company=self.company,
            code="WH-004",
            warehouse_name="Abha Service Store",
            warehouse_type="service",
            manager="Khalid Hassan",
            city="Abha",
            storage_capacity="50",
            status="active",
        )
        wh5 = Warehouse.objects.create(
            company=self.company,
            code="WH-005",
            warehouse_name="Madinah Spare Parts",
            warehouse_type="spare_parts",
            manager="Salman Ahmed",
            city="Madinah",
            storage_capacity="100",
            status="inactive",
        )

        # WH-001: 304 units, 93440.00 cost value (split across 2 products + 1 service excluded)
        Product.objects.create(
            company=self.company,
            code="PRD-1",
            product_name="Router A",
            product_type="product",
            warehouse=wh1,
            current_stock=Decimal("200.00"),
            cost_price=Decimal("300.00"),
            selling_price=Decimal("500.00"),
        )
        Product.objects.create(
            company=self.company,
            code="PRD-2",
            product_name="Switch B",
            product_type="product",
            warehouse=wh1,
            current_stock=Decimal("104.00"),
            cost_price=Decimal("321.5385") if False else Decimal("321.54"),
            selling_price=Decimal("450.00"),
        )
        # Service assigned to WH-001 must NOT be counted in total_units or stock_value
        Product.objects.create(
            company=self.company,
            code="SRV-1",
            product_name="Install Service",
            product_type="service",
            warehouse=wh1,
            current_stock=Decimal("99.00"),
            cost_price=Decimal("5000.00"),
        )
        Product.objects.create(
            company=self.company,
            code="PRD-3",
            product_name="Cable Pack",
            product_type="product",
            warehouse=wh2,
            current_stock=Decimal("33.00"),
            cost_price=Decimal("455.45"),
        )
        Product.objects.create(
            company=self.company,
            code="PRD-4",
            product_name="Panel Box",
            product_type="product",
            warehouse=wh3,
            current_stock=Decimal("83.00"),
            cost_price=Decimal("224.28"),
        )
        Product.objects.create(
            company=self.company,
            code="PRD-5",
            product_name="Spare Kit",
            product_type="product",
            warehouse=wh4,
            current_stock=Decimal("4.00"),
            cost_price=Decimal("3200.00"),
        )
        Product.objects.create(
            company=self.company,
            code="PRD-6",
            product_name="Parts Kit",
            product_type="product",
            warehouse=wh5,
            current_stock=Decimal("33.00"),
            cost_price=Decimal("100.00"),
        )

        # Total units = 304 + 33 + 83 + 4 + 33 = 457; Total capacity = 770 -> 59%
        list_res = self.client.get("/api/finance/warehouse/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(list_res.data["total_warehouses"], 5)
        self.assertEqual(list_res.data["active_warehouses"], 4)
        self.assertEqual(list_res.data["inactive_warehouses"], 1)
        self.assertEqual(list_res.data["average_capacity_used"], 59)
        self.assertEqual(list_res.data["near_full_capacity"], 0)

        rows_by_code = {row["code"]: row for row in list_res.data["results"]}
        self.assertEqual(rows_by_code["WH-001"]["total_units"], "304.00")
        self.assertEqual(rows_by_code["WH-001"]["capacity_used"], "76% (304/400)")
        self.assertEqual(rows_by_code["WH-001"]["capacity_used_percentage"], 76)
        self.assertEqual(rows_by_code["WH-001"]["capacity_limit"], 400)
        self.assertFalse(rows_by_code["WH-001"]["near_full_capacity"])
        self.assertEqual(rows_by_code["WH-001"]["location"], "Riyadh")

        self.assertEqual(rows_by_code["WH-003"]["capacity_used"], "69% (83/120)")
        self.assertEqual(rows_by_code["WH-004"]["capacity_used"], "8% (4/50)")

        expected_wh1_val = Decimal("200.00") * Decimal("300.00") + Decimal("104.00") * Decimal("321.54")
        self.assertEqual(Decimal(rows_by_code["WH-001"]["stock_value"]), expected_wh1_val.quantize(Decimal("0.01")))

        kpi_res = self.client.get("/api/finance/warehouse/kpi/")
        self.assertEqual(kpi_res.status_code, status.HTTP_200_OK)
        self.assertEqual(kpi_res.data["total_warehouses"], 5)
        self.assertEqual(kpi_res.data["active_warehouses"], 4)
        self.assertEqual(kpi_res.data["average_capacity_used"], 59)
        self.assertEqual(kpi_res.data["near_full_capacity"], 0)
        self.assertEqual(kpi_res.data["total_stock_value"], list_res.data["total_stock_value"])

        # Detail endpoint must also return computed metrics + product stock breakdown
        Product.objects.create(
            company=self.company,
            code="PRD-LOW-1",
            product_name="Low Item",
            product_type="product",
            warehouse=wh1,
            current_stock=Decimal("5.00"),
            reorder_level=10,
            cost_price=Decimal("0.00"),
        )
        Product.objects.create(
            company=self.company,
            code="PRD-OUT-1",
            product_name="Out Item",
            product_type="product",
            warehouse=wh1,
            current_stock=Decimal("0.00"),
            reorder_level=10,
            cost_price=Decimal("0.00"),
        )
        detail_res = self.client.get(f"/api/finance/warehouse/{wh1.id}/")
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_res.data["total_units"], "309.00")
        self.assertEqual(Decimal(detail_res.data["stock_quantity"]), Decimal("309.00"))
        self.assertEqual(detail_res.data["total_products"], 4)
        self.assertEqual(detail_res.data["low_stock_products"], 1)
        self.assertEqual(detail_res.data["out_of_stock_products"], 1)
        self.assertEqual(detail_res.data["currency"], self.company.currency)
        self.assertEqual(kpi_res.data["currency"], self.company.currency)
        self.assertEqual(Decimal(detail_res.data["stock_value"]), expected_wh1_val.quantize(Decimal("0.01")))

    def test_near_full_capacity_threshold_and_filter(self):
        wh_near = Warehouse.objects.create(
            company=self.company,
            code="WH-NF-1",
            warehouse_name="Almost Full WH",
            storage_capacity="100",
            status="active",
        )
        wh_ok = Warehouse.objects.create(
            company=self.company,
            code="WH-OK-1",
            warehouse_name="Normal WH",
            storage_capacity="100",
            status="active",
        )
        wh_empty_cap = Warehouse.objects.create(
            company=self.company,
            code="WH-NOCAP",
            warehouse_name="No Capacity WH",
            storage_capacity="",
            status="active",
        )

        Product.objects.create(
            company=self.company,
            code="PRD-NF",
            product_name="Heavy Stock",
            product_type="product",
            warehouse=wh_near,
            current_stock=Decimal("80.00"),
            cost_price=Decimal("10.00"),
        )
        Product.objects.create(
            company=self.company,
            code="PRD-OK",
            product_name="Below Threshold",
            product_type="product",
            warehouse=wh_ok,
            current_stock=Decimal("79.00"),
            cost_price=Decimal("10.00"),
        )
        Product.objects.create(
            company=self.company,
            code="PRD-NC",
            product_name="Uncapacitated Stock",
            product_type="product",
            warehouse=wh_empty_cap,
            current_stock=Decimal("500.00"),
            cost_price=Decimal("10.00"),
        )

        kpi_res = self.client.get("/api/finance/warehouse/kpi/")
        self.assertEqual(kpi_res.status_code, status.HTTP_200_OK)
        self.assertEqual(kpi_res.data["near_full_capacity"], 1)
        # (80 + 79) / (100 + 100) = 79.5% -> rounds to 80%
        self.assertEqual(kpi_res.data["average_capacity_used"], 80)

        near_res = self.client.get("/api/finance/warehouse/?near_full=true")
        self.assertEqual(near_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(near_res.data["results"]), 1)
        self.assertEqual(near_res.data["results"][0]["code"], "WH-NF-1")
        self.assertTrue(near_res.data["results"][0]["near_full_capacity"])

    def test_create_warehouse_with_ui_form_inputs_and_validation(self):
        res = self.client.post("/api/finance/warehouse/", {
            "code": "1253698",
            "warehouse_name": "Riyadh Main Hub",
            "warehouse_type": "Main",
            "manager": "Ahmed Ali",
            "status": "Active",
            "operating_since": "09-09-2026",
            "country": "Saudi Arabia",
            "city": "Riyadh",
            "address_line_1": "Industrial City",
            "address_line_2": None,
            "postal_code": "12211",
            "phone_number": "+966500000000",
            "email": "",
            "storage_capacity": 400,
            "notes": None,
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["code"], "1253698")
        self.assertEqual(res.data["warehouse_type"], "main")
        self.assertEqual(res.data["status"], "active")
        self.assertEqual(res.data["operating_since"], "2026-09-09")
        self.assertEqual(res.data["storage_capacity"], "400")
        self.assertEqual(res.data["capacity_limit"], 400)
        self.assertEqual(res.data["capacity_used"], "0% (0/400)")
        self.assertEqual(res.data["total_units"], "0.00")
        self.assertEqual(res.data["stock_value"], "0.00")

        # Negative storage capacity rejected
        neg_res = self.client.post("/api/finance/warehouse/", {
            "warehouse_name": "Invalid Capacity WH",
            "storage_capacity": "-10",
        }, format="json")
        self.assertEqual(neg_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("storage_capacity", neg_res.data)

        # Updating with blank code preserves existing code
        wh_id = res.data["id"]
        put_res = self.client.patch(f"/api/finance/warehouse/{wh_id}/", {
            "code": "",
            "storage_capacity": "500",
        }, format="json")
        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.assertEqual(put_res.data["code"], "1253698")
        self.assertEqual(put_res.data["capacity_used"], "0% (0/500)")

    def test_case_insensitive_filters_and_metric_ordering(self):
        wh_low = Warehouse.objects.create(
            company=self.company,
            code="WH-A",
            warehouse_name="Alpha Store",
            warehouse_type="spare_parts",
            status="active",
            city="Riyadh",
        )
        wh_high = Warehouse.objects.create(
            company=self.company,
            code="WH-B",
            warehouse_name="Beta Store",
            warehouse_type="main",
            status="inactive",
            city="Jeddah",
        )
        Product.objects.create(
            company=self.company,
            code="PRD-LOW",
            product_name="Low Qty",
            product_type="product",
            warehouse=wh_low,
            current_stock=Decimal("5.00"),
            cost_price=Decimal("10.00"),
        )
        Product.objects.create(
            company=self.company,
            code="PRD-HIGH",
            product_name="High Qty",
            product_type="product",
            warehouse=wh_high,
            current_stock=Decimal("50.00"),
            cost_price=Decimal("100.00"),
        )

        # Case-insensitive status and warehouse_type
        res_active = self.client.get("/api/finance/warehouse/?status=Active&warehouse_type=Spare%20Parts")
        self.assertEqual(res_active.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_active.data["results"]), 1)
        self.assertEqual(res_active.data["results"][0]["code"], "WH-A")

        # ?status=all returns all
        res_all = self.client.get("/api/finance/warehouse/?status=all")
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_all.data["results"]), 2)

        # Ordering by -total_units and -stock_value
        res_ord = self.client.get("/api/finance/warehouse/?ordering=-stock_value")
        self.assertEqual(res_ord.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ord.data["results"][0]["code"], "WH-B")
        self.assertEqual(res_ord.data["results"][1]["code"], "WH-A")

    def test_warehouse_export_csv_and_xlsx(self):
        wh = Warehouse.objects.create(
            company=self.company,
            code="WH-EXP-1",
            warehouse_name="Export Test Warehouse",
            warehouse_type="main",
            manager="Ahmed Ali",
            city="Riyadh",
            storage_capacity="100",
            status="active",
        )
        Warehouse.objects.create(
            company=self.company,
            code="WH-EXP-2",
            warehouse_name="Excluded Inactive WH",
            warehouse_type="service",
            city="Abha",
            storage_capacity="50",
            status="inactive",
        )
        Product.objects.create(
            company=self.company,
            code="PRD-EXP",
            product_name="Export Item",
            product_type="product",
            warehouse=wh,
            current_stock=Decimal("40.00"),
            cost_price=Decimal("250.00"),
        )

        # 1. List endpoint ?export=csv with status filter
        csv_res = self.client.get("/api/finance/warehouse/?export=csv&status=active")
        self.assertEqual(csv_res.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", csv_res["Content-Type"])
        self.assertIn("warehouses.csv", csv_res["Content-Disposition"])

        rows = list(csv.reader(io.StringIO(csv_res.content.decode("utf-8"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "Code")
        self.assertEqual(rows[1][0], "WH-EXP-1")
        self.assertEqual(rows[1][5], "40")
        self.assertEqual(rows[1][6], "10000.00")
        self.assertEqual(rows[1][8], "40% (40/100)")

        # 2. Dedicated /export/ endpoint (CSV default)
        dedicated_csv = self.client.get("/api/finance/warehouse/export/")
        self.assertEqual(dedicated_csv.status_code, status.HTTP_200_OK)
        dedicated_rows = list(csv.reader(io.StringIO(dedicated_csv.content.decode("utf-8"))))
        self.assertEqual(len(dedicated_rows), 3)

        # 3. Dedicated /export/?export=xlsx
        xlsx_res = self.client.get("/api/finance/warehouse/export/?export=xlsx&search=Export%20Test")
        self.assertEqual(xlsx_res.status_code, status.HTTP_200_OK)
        self.assertIn("spreadsheetml.sheet", xlsx_res["Content-Type"])
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_res.content))
        ws = wb.active
        xlsx_rows = list(ws.iter_rows(values_only=True))
        self.assertEqual(len(xlsx_rows), 2)
        self.assertEqual(xlsx_rows[1][0], "WH-EXP-1")

    def test_company_isolation_and_protected_delete(self):
        other_company = Company.objects.create(
            name="Other Co",
            email="other@co.com",
        )
        other_wh = Warehouse.objects.create(
            company=other_company,
            code="WH-OTHER",
            warehouse_name="Other Warehouse",
            storage_capacity="100",
        )
        Product.objects.create(
            company=other_company,
            code="PRD-OTHER",
            product_name="Other Item",
            product_type="product",
            warehouse=other_wh,
            current_stock=Decimal("50.00"),
            cost_price=Decimal("999.00"),
        )

        # Other company's warehouse must not leak into list, KPIs, or detail
        self.assertEqual(self.client.get("/api/finance/warehouse/").data["total_warehouses"], 0)
        self.assertEqual(self.client.get("/api/finance/warehouse/kpi/").data["total_stock_value"], Decimal("0.00"))
        self.assertEqual(self.client.get(f"/api/finance/warehouse/{other_wh.id}/").status_code, status.HTTP_404_NOT_FOUND)

        # Protected delete returns 400 when referenced by SalesOrder
        wh = Warehouse.objects.create(
            company=self.company,
            code="WH-PROT",
            warehouse_name="Protected WH",
        )
        customer = Customer.objects.create(
            company=self.company,
            customer_id="CUST-1",
            customer_name="Acme Customer",
            industry="manufacturing",
            currency="SAR",
            payment_term="30_days",
            client_status="active",
        )
        quotation = Quotation.objects.create(
            company=self.company,
            quote_number="QT-1",
            customer=customer,
            issue_date=date(2026, 9, 9),
        )
        SalesOrder.objects.create(
            company=self.company,
            quotation=quotation,
            customer=customer,
            warehouse=wh,
            so_number="SO-1",
            order_date=date(2026, 9, 9),
        )

        del_res = self.client.delete(f"/api/finance/warehouse/{wh.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Warehouse.objects.filter(id=wh.id).exists())
