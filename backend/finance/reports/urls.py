
# reports/urls.py

from django.urls import path
from finance.reports.sales import SalesReportView

urlpatterns = [
    path("sales/", SalesReportView.as_view(), name="sales-report"),
]
