
from django.urls import path

from .views import (
    TrialBalanceDashboardAPIView,
    TrialBalanceListAPIView,
)

urlpatterns = [
    path(
        "dashboard/",
        TrialBalanceDashboardAPIView.as_view(),
        name="trial-balance-dashboard",
    ),
    path(
        "",
        TrialBalanceListAPIView.as_view(),
        name="trial-balance-list",
    ),
]
