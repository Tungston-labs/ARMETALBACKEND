
from rest_framework.routers import DefaultRouter

from .views import (
    BankAccountViewSet,
    BankTransactionViewSet,
    LoanAccountViewSet,
)

router = DefaultRouter()
router.register("accounts", BankAccountViewSet, basename="bank-account")
router.register(
    "transactions", BankTransactionViewSet, basename="bank-transaction"
)
router.register("loans", LoanAccountViewSet, basename="loan-account")

urlpatterns = router.urls
