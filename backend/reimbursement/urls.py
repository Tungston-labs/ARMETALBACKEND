# reimbursements/urls.py
from django.urls import path
from .views import (
    ReimbursementListCreateView,
    ReimbursementDetailView,
    DepartmentReimbursementListView,ReimbursementGroupedByDateView,MyReimbursementListView,MyReimbursementDetailView
)

urlpatterns = [
    path("", ReimbursementListCreateView.as_view(), name="reimbursement-list-create"),
    path("<int:pk>/", ReimbursementDetailView.as_view(), name="reimbursement-detail"),
    path("department/<int:department_id>/", DepartmentReimbursementListView.as_view(), name="reimbursement-by-department"),
    path("grouped/", ReimbursementGroupedByDateView.as_view(), name="reimbursement-grouped"),
    path("my-reimbursements/", MyReimbursementListView.as_view(), name="my-reimbursements"),
    path("my-reimbursements/<int:pk>/", MyReimbursementDetailView.as_view(), name="my-reimbursement-detail"),
]
