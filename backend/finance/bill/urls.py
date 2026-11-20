from django.urls import path
from .views import (
    BillListCreateView,
    BillDetailView,
    BillKPICardView,
    ApprovedPurchaseOrderReferenceListView,
    ApprovedPurchaseOrderDetailView,
)

app_name = "bill"

urlpatterns = [
    path("", BillListCreateView.as_view(), name="bill-list-create"),
    path("kpi/", BillKPICardView.as_view(), name="bill-kpi"),
    path("purchase-orders/", ApprovedPurchaseOrderReferenceListView.as_view(), name="bill-approved-purchase-orders"),
    path("purchase-orders/<int:po_id>/", ApprovedPurchaseOrderDetailView.as_view(), name="bill-approved-purchase-order-detail"),
    path("<int:pk>/", BillDetailView.as_view(), name="bill-detail"),
]
