from django.urls import path

from .views import ChartOfAccountListCreateView,ChartOfAccountKPIView


urlpatterns = [
    path(
        "",
        ChartOfAccountListCreateView.as_view(),
        name="chart-of-account-list-create"
    ),
    path(
        "kpi/",
        ChartOfAccountKPIView.as_view(),
        name="chart-of-account-kpi"
    ),
]