from django.urls import path

from .views import ChartOfAccountListCreateView,ChartOfAccountKPIView,ChartOfAccountDetailView


urlpatterns = [
    path(
        "",
        ChartOfAccountListCreateView.as_view(),
        name="chart-of-account-list-create"
    ),
    path( "<int:account_id>/", 
         ChartOfAccountDetailView.as_view(), 
         name="chart-of-account-detail", ),
    path(
        "kpi/",
        ChartOfAccountKPIView.as_view(),
        name="chart-of-account-kpi"
    ),


]