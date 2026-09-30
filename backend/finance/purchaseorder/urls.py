# purchase_order/urls.py

from django.urls import path

from .views import (
    PurchaseOrderCreateListView,
    PurchaseOrderDetailView,
    PurchaseOrderDashboardView,
    VendorDropdownView,
    WarehouseDropdownView,
    ProductDropdownView,
)

urlpatterns = [
    # Purchase Order create and list
    path(
        "",
        PurchaseOrderCreateListView.as_view(),
        name="purchase-order-list-create",
    ),

    # Purchase Order detail
    path(
        "<int:pk>/",
        PurchaseOrderDetailView.as_view(),
        name="purchase-order-detail",
    ),

    # Dashboard
    path(
        "dashboard/",
        PurchaseOrderDashboardView.as_view(),
        name="purchase-order-dashboard",
    ),

    # Dropdown APIs
    path(
        "dropdowns/vendors/",
        VendorDropdownView.as_view(),
        name="purchase-order-vendors",
    ),

    path(
        "dropdowns/warehouses/",
        WarehouseDropdownView.as_view(),
        name="purchase-order-warehouses",
    ),

    path(
        "dropdowns/products/",
        ProductDropdownView.as_view(),
        name="purchase-order-products",
    ),
]