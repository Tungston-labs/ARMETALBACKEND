from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    VendorViewSet,
    VendorDashboardView,VendorOverviewView,VendorPurchaseOrderListView
)

router = DefaultRouter()

router.register(
    "vendors",
    VendorViewSet,
    basename="vendor",
)

urlpatterns = [
    path(
        "dashboard/",
        VendorDashboardView.as_view(),
        name="vendor-dashboard",
    ),
      path(
        "<int:vendor_id>/overview/",
        VendorOverviewView.as_view(),
        name="vendor-overview",
    ),

    path(
        "<int:vendor_id>/purchase-orders/",
        VendorPurchaseOrderListView.as_view(),
        name="vendor-purchase-orders",
    ),
]

urlpatterns += router.urls