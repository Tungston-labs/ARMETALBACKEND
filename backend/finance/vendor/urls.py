from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    VendorViewSet,
    VendorDashboardView,VendorOverviewView,VendorPurchaseOrderListView,VendorPaymentViewSet
)

router = DefaultRouter()

router.register(
    "vendors",
    VendorViewSet,
    basename="vendor",
)

router.register(
    "payments",
    VendorPaymentViewSet,
    basename="vendor-payment",
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