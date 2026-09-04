from django.urls import path
from .views import (
    DepartmentCreateListView,
    DepartmentRetrieveUpdateDeleteView,EmployeeByDepartmentView,MyDepartmentHeadEmailView,DepartmentMiniListView,DepartmentAttendanceListView
)

urlpatterns = [
    path('departments/', DepartmentCreateListView.as_view(), name='department-create-list'),
    path('departments/<int:pk>/', DepartmentRetrieveUpdateDeleteView.as_view(), name='department-detail-edit-delete'),
    path('employees/department/<int:department_id>/', EmployeeByDepartmentView.as_view(), name='employees-by-department'),
    path("my-department-head/", MyDepartmentHeadEmailView.as_view(), name="my-department-head"),
    path("deptlist/", DepartmentMiniListView.as_view(), name="department-mini-list"),
    path("dept-attendance/", DepartmentAttendanceListView.as_view(), name="department-attendance-list"),


]
