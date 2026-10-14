from django.urls import path
from .views import GeneralLedgerView

urlpatterns = [
    path("", GeneralLedgerView.as_view(), name="general-ledger"),
]