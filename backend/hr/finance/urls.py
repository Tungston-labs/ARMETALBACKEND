from django.urls import path
from .views import (
    FinanceRecordListCreateView,
    FinanceRecordDetailView,FinanceCategoryListCreateView
)

urlpatterns = [
    path("", FinanceRecordListCreateView.as_view(), name="finance-list-create"),
    path("<int:pk>/", FinanceRecordDetailView.as_view(), name="finance-detail"),
    path("categories/", FinanceCategoryListCreateView.as_view(), name="finance-category-list-create"),
]
