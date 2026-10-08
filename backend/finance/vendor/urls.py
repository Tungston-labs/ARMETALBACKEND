from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    VendorViewSet,
    VendorDashboardView,VendorOverviewView,VendorPurchaseOrderListView,VendorPaymentViewSet,VendorDocumentUploadView,VendorBillListView,VendorPaymentListView,VendorDebitNoteListView
)

router = DefaultRouter()

router.register(
    "vendors",
    VendorViewSet,
    basename="vendor",
)

router.register(
    "payments",
    VendorPaymentViewSet,
    basename="vendor-payment",
)

urlpatterns = [
    path(
        "dashboard/",
        VendorDashboardView.as_view(),
        name="vendor-dashboard",
    ),
      path(
        "<int:vendor_id>/overview/",
        VendorOverviewView.as_view(),
        name="vendor-overview",
    ),

    path(
        "<int:vendor_id>/purchase-orders/",
        VendorPurchaseOrderListView.as_view(),
        name="vendor-purchase-orders",
    ),
    path(
        "documents/upload/",
        VendorDocumentUploadView.as_view(),
        name="vendor-document-upload",
    ),
    path(
        "<int:vendor_id>/bills/",
        VendorBillListView.as_view(),
        name="vendor-bill-list",
    ),
     path(
        "<int:vendor_id>/payments/",
        VendorPaymentListView.as_view(),
        name="vendor-payment-list",
    ),
    path(
        "<int:vendor_id>/debit-notes/",
        VendorDebitNoteListView.as_view(),
        name="vendor-debit-note-list"
    ),
    

]

urlpatterns += router.urls