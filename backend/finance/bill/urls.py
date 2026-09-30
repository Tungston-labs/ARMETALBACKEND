from django.urls import path
from .views import (
    BillListCreateView,
    BillDetailView,
    BillKPICardView,
)

app_name = "bill"

urlpatterns = [
    path("", BillListCreateView.as_view(), name="bill-list-create"),
    path("kpi/", BillKPICardView.as_view(), name="bill-kpi"),
    path("<int:pk>/", BillDetailView.as_view(), name="bill-detail"),
]
