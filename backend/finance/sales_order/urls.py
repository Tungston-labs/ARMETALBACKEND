from django.urls import path

from .views import (
    SalesOrderListCreateView,
    SalesOrderDetailView,
    SalesOrderSummaryView,
    SalesOrderQuotationListView,
    SalesOrderQuotationDetailView,
    SalesOrderCompanyListView,
    SalesOrderCustomerListView,
    SalesOrderWarehouseListView,
)


urlpatterns = [

    # ---------------------------------------------------------
    # SALES ORDERS
    # ---------------------------------------------------------

    path(
        "",
        SalesOrderListCreateView.as_view(),
        name="sales-order-list-create"
    ),

    path(
        "<int:pk>/",
        SalesOrderDetailView.as_view(),
        name="sales-order-detail"
    ),

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    path(
        "summary/",
        SalesOrderSummaryView.as_view(),
        name="sales-order-summary"
    ),

    # ---------------------------------------------------------
    # QUOTATIONS
    # ---------------------------------------------------------

    path(
        "quotations/",
        SalesOrderQuotationListView.as_view(),
        name="sales-order-quotation-list"
    ),

    path(
        "quotations/<int:pk>/",
        SalesOrderQuotationDetailView.as_view(),
        name="sales-order-quotation-detail"
    ),

    # ---------------------------------------------------------
    # COMPANIES
    # ---------------------------------------------------------

    path(
        "companies/",
        SalesOrderCompanyListView.as_view(),
        name="sales-order-company-list"
    ),

    # ---------------------------------------------------------
    # CUSTOMERS
    # ---------------------------------------------------------

    path(
        "customers/",
        SalesOrderCustomerListView.as_view(),
        name="sales-order-customer-list"
    ),

    # ---------------------------------------------------------
    # WAREHOUSES
    # ---------------------------------------------------------

    path(
        "warehouses/",
        SalesOrderWarehouseListView.as_view(),
        name="sales-order-warehouse-list"
    ),
]