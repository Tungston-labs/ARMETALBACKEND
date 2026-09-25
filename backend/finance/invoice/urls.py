from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    InvoiceViewSet,
    CustomerInvoiceListView,CustomerInvoiceSummaryView
)

router = DefaultRouter()

router.register(
    "",
    InvoiceViewSet,
    basename="invoice",
)

urlpatterns = [
    path(
        "customer/<int:customer_id>/invoices/",
        CustomerInvoiceListView.as_view(),
        name="customer-invoice-list",
    ),
    path(
        "customer/<int:customer_id>/invoices/summary/",
        CustomerInvoiceSummaryView.as_view(),
        name="customer-invoice-summary",
    ),
]

urlpatterns += router.urls