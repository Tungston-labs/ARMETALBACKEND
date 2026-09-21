from rest_framework.routers import DefaultRouter

from .views import CustomerLedgerViewSet


router = DefaultRouter()

router.register(
    r"",
    CustomerLedgerViewSet,
    basename="ledger",
)

urlpatterns = router.urls