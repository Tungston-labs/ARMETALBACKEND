from rest_framework.routers import DefaultRouter
from .views import VendorPaymentViewSet

router = DefaultRouter()
router.register(r"", VendorPaymentViewSet, basename="purchase-payment")

urlpatterns = router.urls
