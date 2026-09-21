from django.urls import path
from .views import (
    PublicHolidayCreateListView,
    PublicHolidayDetailUpdateDeleteView,
    PublicHolidayEmployeeListView,HolidayTypeListView
)

urlpatterns = [
    # HR Admin
    path('holidays/', PublicHolidayCreateListView.as_view(), name='holiday-create-list'),
    path('holidays/<int:pk>/', PublicHolidayDetailUpdateDeleteView.as_view(), name='holiday-detail'),
    path("holiday-types/", HolidayTypeListView.as_view(), name="holiday-types"),

    # Employee
    path('holidays/employee/', PublicHolidayEmployeeListView.as_view(), name='holiday-employee-list'),

]
