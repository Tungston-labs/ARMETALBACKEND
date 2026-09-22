from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SalesReturnViewSet

router = DefaultRouter()
router.register(r"", SalesReturnViewSet, basename="sales-return")

urlpatterns = [
    path("", include(router.urls)),
]
