from django.urls import path

from .views import SalesReportView

urlpatterns = [
    path("", SalesReportView.as_view(), name="sales-report"),
]
