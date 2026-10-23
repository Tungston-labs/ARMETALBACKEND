
# reports/urls.py

from django.urls import path
from finance.reports.sales import SalesReportView
from finance.reports.customer import CustomerReportView
from finance.reports.purchase import PurchaseReportView
from finance.reports.vendor import VendorReportView
from finance.reports.payment import PaymentReportView
from finance.reports.profit_loss import ProfitLossReportView
from finance.reports.cash_flow import CashFlowReportView
from finance.reports.expense import ExpenseReportView
from finance.reports.inventory import InventoryReportView
from finance.reports.tax import TaxReportView





urlpatterns = [
    path("sales/", SalesReportView.as_view(), name="sales-report"),
    path("purchase/", PurchaseReportView.as_view(), name="purchase-report"),
    path("customer/", CustomerReportView.as_view(), name="customer-report"),
    path("vendor/", VendorReportView.as_view(), name="vendor-report"),
    path("payment/", PaymentReportView.as_view(), name="payment-report"),
    path("profit-loss/", ProfitLossReportView.as_view(), name="profit-loss-report"),
    path("cash-flow/", CashFlowReportView.as_view(), name="cash-flow-report"),
    path("expense/", ExpenseReportView.as_view(), name="expense-report"),
    path("inventory/", InventoryReportView.as_view(), name="inventory-report"),
    path("tax/", TaxReportView.as_view(), name="tax-report")


]
