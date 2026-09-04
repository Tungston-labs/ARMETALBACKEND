from django.urls import path
from .views import DashboardCountsView, ReimbursementCountsView,RecentEmployeesView,ContractExpiry30DaysView,HolidayListAPI,SimpleNotificationsAPI,TodayEmployeeStatsAPI,UpcomingHolidayBirthdayAPI,ReimbursementMonthWiseAmountView,DepartmentDashboardSummaryView,ProjectCountView,WeeklyAttendanceStatsView,MonthlyPayrollSummaryView
urlpatterns = [
 
    path('counts/', DashboardCountsView.as_view(), name='dashboard-counts'),#new dashboard api
    path("today-employee-stats/", TodayEmployeeStatsAPI.as_view(), name="today-employee-stats"),#new dashboard api
    path('reimbursement/counts/', ReimbursementCountsView.as_view(), name='reimbursement-counts'),#new dashboard api


    path('reimbursement/monthwise/', ReimbursementMonthWiseAmountView.as_view(), name='reimbursement-monthwise'),
    path('department/',DepartmentDashboardSummaryView.as_view(),name='department-dashboard'),
    path('recentemployees/',RecentEmployeesView.as_view(),name='recent-employees'),
    path("contract-expiry/30-days/", ContractExpiry30DaysView.as_view(),name="contract-expiry-30-days"),
    path("simple-notifications/", SimpleNotificationsAPI.as_view(), name="simple-notifications"),#new dashboard api
    # path("holiday-summary/", HolidaySummaryAPI.as_view(), name="holiday-summary"),
    path('project/count/',ProjectCountView.as_view(),name='project-employee-count'),#new dashboard api
    path('weekly-attendance/',WeeklyAttendanceStatsView.as_view()),#new dashboard api
    path('payroll/monthly-summary/',MonthlyPayrollSummaryView.as_view()),#new dashboard api
    path(
        "dashboard/upcoming-holidays-birthdays/",
        UpcomingHolidayBirthdayAPI.as_view(),
        name="upcoming-holidays-birthdays"
    ),#new dashboard api

    path(
        "holidays/",
        HolidayListAPI.as_view(),
        name="holiday-list"
    ),#new dashboard api

]
