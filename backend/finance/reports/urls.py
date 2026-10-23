
# reports/urls.py

from django.urls import path
from finance.reports.sales import SalesReportView
from finance.reports.customer import CustomerReportView
from finance.reports.purchase import PurchaseReportView
from finance.reports.vendor import VendorReportView
from finance.reports.payment import PaymentReportView
from finance.reports.profit_loss import ProfitLossReportView
from finance.reports.cash_flow import CashFlowReportView



urlpatterns = [
    path("sales/", SalesReportView.as_view(), name="sales-report"),
    path("purchase/", PurchaseReportView.as_view(), name="purchase-report"),
    path("customer/", CustomerReportView.as_view(), name="customer-report"),
    path("vendor/", VendorReportView.as_view(), name="vendor-report"),
    path("payment/", PaymentReportView.as_view(), name="payment-report"),
    path("profit-loss/", ProfitLossReportView.as_view(), name="profit-loss-report"),
    path("cash-flow/", CashFlowReportView.as_view(), name="cash-flow-report"),

]
