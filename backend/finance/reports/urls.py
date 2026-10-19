
# reports/urls.py

from django.urls import path
from finance.reports.sales import SalesReportView
from finance.reports.purchase import PurchaseReportView

urlpatterns = [
    path("sales/", SalesReportView.as_view(), name="sales-report"),
    path("purchase/", PurchaseReportView.as_view(), name="purchase-report"),
]
