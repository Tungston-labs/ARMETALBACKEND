from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    VendorViewSet,
    VendorDashboardView,
    VendorPaymentViewSet,
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
]

urlpatterns += router.urls