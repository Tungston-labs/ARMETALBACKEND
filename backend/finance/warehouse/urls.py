from django.urls import path
from .views import WarehouseListCreateView, WarehouseDetailView, WarehouseKPICardView

urlpatterns = [
    path("", WarehouseListCreateView.as_view(), name="warehouse-list-create"),
    path("kpi/", WarehouseKPICardView.as_view(), name="warehouse-kpi"),
    path("<int:pk>/", WarehouseDetailView.as_view(), name="warehouse-detail"),
]
