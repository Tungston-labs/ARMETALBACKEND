
from django.urls import path
from .views import AccountsReceivableView

urlpatterns = [
    path(
        "",
        AccountsReceivableView.as_view(),
        name="accounts-receivable",
    ),
]
