from django.urls import path
from .views import (
    AttendanceSwipeView,AttendanceAdminListView,AttendanceManualUpdateView,AttendanceDetailByDateView,AttendanceAdminDetailView,AddPunchOutNoteView,GenerateEmployeeAttendanceExcelView,AttendanceLocationUpdateView,BackgroundLocationUpdateView,EmployeeAttendanceSummaryView,AttendanceCorrectionRequestCreateView,AttendanceCorrectionStatusUpdateView
,GenerateSingleEmployeeAttendanceExcelView
)

urlpatterns = [
    path('attendance/swipe/', AttendanceSwipeView.as_view(), name='attendance-swipe'),
    path('admin/attendance/', AttendanceAdminListView.as_view(), name='admin-attendance-list'),
    path('attendance/today/', AttendanceDetailByDateView.as_view(), name='attendance-today-detail'),
    path('admin/attendance/<int:employee_id>/', AttendanceAdminDetailView.as_view(), name='attendance-detail'),
    path('attendance/add-note/', AddPunchOutNoteView.as_view(), name='attendance-add-note'),
    path('attendance/update-location/', AttendanceLocationUpdateView.as_view(), name='attendance-update-location'),
    path('background-location/<int:employee_id>/', BackgroundLocationUpdateView.as_view(), name='background-location'),
    path('employee-attendance/summary/', EmployeeAttendanceSummaryView.as_view()),
    path("attendance/correction-request/",AttendanceCorrectionRequestCreateView.as_view(),name="attendance-correction-request"
),
path(
    "attendance-correction/<int:pk>/status/",
    AttendanceCorrectionStatusUpdateView.as_view(),
    name="attendance-correction-status-update",
),
path(
        "attendance-summary/excel/",
        GenerateEmployeeAttendanceExcelView.as_view(),
        name="attendance-summary-excel"
    ),

path(
        "attendance/update/",
        AttendanceManualUpdateView.as_view(),
        name="attendance-manual-update"
    ),
    path(
    "attendance/employee-excel/",
    GenerateSingleEmployeeAttendanceExcelView.as_view(),
    name="generate-single-employee-attendance-excel"
),

]



