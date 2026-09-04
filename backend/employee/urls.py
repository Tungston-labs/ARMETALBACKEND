from django.urls import path
from employee import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # employee basic details
    path('employees/', views.EmployeeListCreateView.as_view(), name='employee-list-create'),
    path('employeelist/', views.EmployeeListView.as_view(), name='employee-list'),
    path('employees/<int:pk>/', views.EmployeeRetrieveUpdateDestroyView.as_view(), name='employee-detail'),

    
       # employee bank payment details  
    path('employees/<int:employee_id>/bank-payments/', views.EmpBankPaymentCreateListView.as_view(), name='employee-bank-payment-list-create'),
    path('employees/<int:employee_id>/bank-payments/<int:pk>/', views.EmpBankPaymentEmployeeScopedDetailView.as_view(), name='employee-bank-payment-detail'),


  # document upload
    path('employees/<int:employee_id>/documents/', views.EmployeeDocumentsView.as_view(), name='employee-documents'),
    path('upload-image/', views.UploadImageView.as_view(), name='upload-temp-image'),
    path('upload-image/<int:pk>/', views.UploadImageDetailView.as_view(), name='upload-image-detail'),
    path('employees/my-department/', views.EmployeesInMyDepartmentView.as_view(), name='employees-in-my-department'),


    path('admin/dashboard-summary/', views.DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('dashboard/employee/<int:id>/', views.EmployeeDashboardAPIView.as_view(), name='employee-dashboard'),
    path("employees/upcoming-expiry/", views.UpcomingExpiryEmployeeListView.as_view(), name="upcoming-expiry"),
    path("email/send/", views.SendEmailAPIView.as_view(), name="send_email"),



    # mobile application

    path('profile/', views.EmployeeProfileView.as_view(), name='employee-profile'),

    path('employee/document-summary/', views.EmployeeDocumentSummaryView.as_view()),

    path("attendance/summary/", views.AttendanceSummaryView.as_view(), name="attendance-summary"),
    path("reminders/", views.ReminderListCreateView.as_view(), name="reminder-list-create"),
    path("reminders/<int:pk>/", views.ReminderRetrieveUpdateDestroyView.as_view(), name="reminder-detail"),
    path('employee-monthly-summary/', views.EmployeeMonthlySummaryView.as_view(), name='employee-monthly-summary'),
    path(
        "salary-increment/<int:employee_id>/",
        views.SalaryIncrementListCreateView.as_view(),
        name="salary-increment",
      
    ),
    path(
        "employees/deleted/",
        views.DeletedEmployeeListView.as_view(),
        name="deleted-employees"
    ),
    path(
    "employees/<int:id>/rehire/",
    views.EmployeeRehireView.as_view(),
    name="employee-rehire"
),
path(
        "employees/designations/",
        views.CompanyDesignationListView.as_view(),
        name="company-designations"
    ),

    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



