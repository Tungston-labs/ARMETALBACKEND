from django.urls import path
from .views import (
    LeaveRequestCreateListView,
    LeaveRequestCancelView,
    LeaveRequestAdminListView,
    LeaveRequestAdminDetailView,LeaveByStatusView,LeaveSummaryView,LeaveRequestEmpDetailView,EmployeesOnLeaveTodayByDepartmentView,DepartmentEmployeesOnLeaveView,LeaveStatusCountsView
)

urlpatterns = [
    path('leave/', LeaveRequestCreateListView.as_view(), name='leave-create-list'),  # Employee
    path('leave/<int:pk>/cancel/', LeaveRequestCancelView.as_view(), name='leave-cancel'),  # Employee cancel
    path('leave/admin/', LeaveRequestAdminListView.as_view(), name='leave-admin-list'),  # HR Admin list
    path('leave/admin/<int:pk>/', LeaveRequestAdminDetailView.as_view(), name='leave-admin-detail'),  # HR Admin actions
    path('leave/by-status/', LeaveByStatusView.as_view(), name='leave-by-status'),
    path("leave/summary/", LeaveSummaryView.as_view(), name="leave-summary"),
    path('leave/emp/<int:pk>/', LeaveRequestEmpDetailView.as_view(), name='leave-emp-detail'),
    path('departments/<int:department_id>/on-leave-employees/', EmployeesOnLeaveTodayByDepartmentView.as_view()),
    path('department/<int:employee_id>/on-leaves/', DepartmentEmployeesOnLeaveView.as_view(), name='department-opn-leaves'),
    path('leave-counts/',LeaveStatusCountsView.as_view(),name='leave-count'),

    
    
    ]
