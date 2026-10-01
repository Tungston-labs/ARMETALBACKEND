from django.urls import path

from .views import (
    VendorLedgerListCreateView,
    VendorLedgerDetailView,VendorLedgerCustomerView,VendorLedgerSummaryView,
)


urlpatterns = [
    # List + Create
    path(
        "",
        VendorLedgerListCreateView.as_view(),
        name="vendor-ledger-list-create",
    ),

    # Detail + Update + Delete
    path(
        "<int:pk>/",
        VendorLedgerDetailView.as_view(),
        name="vendor-ledger-detail",
    ),

    path(
        "vendor/<int:vendor_id>/",
        VendorLedgerCustomerView.as_view(),
        name="vendor-ledger-customer",
    ),
    path(
    "summary/",
    VendorLedgerSummaryView.as_view(),
    name="vendor-ledger-summary",
),
]