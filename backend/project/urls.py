from django.urls import path
from .views import ProjectListCreateView, ProjectRetrieveUpdateDestroyView,EmployeesNotInProjectView,RemoveEmployeeFromProjectView,EmployeeAttendanceDetailView, EmployeeProjectView,ProjectCountView

urlpatterns = [
    path('', ProjectListCreateView.as_view(), name='project-list-create'),
    path('<int:pk>/', ProjectRetrieveUpdateDestroyView.as_view(), name='project-detail'),
    path('<int:project_id>/employees-not-in-project/', EmployeesNotInProjectView.as_view(), name='employees-not-in-project'),
    path('<int:project_id>/remove-employee/<int:employee_id>/', RemoveEmployeeFromProjectView.as_view(), name='remove-employee-from-project'),
    path('employee/<int:employee_id>/attendance/', EmployeeAttendanceDetailView.as_view(), name='employee-attendance-detail'),
    path('employee-project/', EmployeeProjectView.as_view(), name='employee-project'),
    path("count/", ProjectCountView.as_view(), name="project-count"),
]
