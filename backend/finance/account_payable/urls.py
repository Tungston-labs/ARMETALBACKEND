
from django.urls import path

from .views import AccountsPayableView

urlpatterns = [
    path(
        "",
        AccountsPayableView.as_view(),
        name="accounts-payable",
    ),
]
