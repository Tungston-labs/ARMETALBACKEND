from django.urls import path
from .views import (
    InventoryListView,
    InventoryKPICardView,
    StockAdjustmentListCreateView,
    StockAdjustmentDetailView,
)

urlpatterns = [
    path("", InventoryListView.as_view(), name="inventory-list"),
    path("kpi/", InventoryKPICardView.as_view(), name="inventory-kpi"),
    path("adjustments/", StockAdjustmentListCreateView.as_view(), name="stock-adjustment-list-create"),
    path("adjustments/<int:pk>/", StockAdjustmentDetailView.as_view(), name="stock-adjustment-detail"),
]
