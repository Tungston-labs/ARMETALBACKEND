from django.urls import path
from .views import (
    WarehouseDetailView,
    WarehouseExportView,
    WarehouseKPICardView,
    WarehouseListCreateView,
)

urlpatterns = [
    path("", WarehouseListCreateView.as_view(), name="warehouse-list-create"),
    path("kpi/", WarehouseKPICardView.as_view(), name="warehouse-kpi"),
    path("export/", WarehouseExportView.as_view(), name="warehouse-export"),
    path("<int:pk>/", WarehouseDetailView.as_view(), name="warehouse-detail"),
]
