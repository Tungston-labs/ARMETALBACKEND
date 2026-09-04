from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import PublicHoliday
from .serializers import PublicHolidaySerializer
from user.permissions import IsHRAdmin, IsEmployee
from shared.pagination import CustomPagination
from rest_framework.views import APIView
from rest_framework.response import Response


from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from datetime import date
import calendar

from .models import PublicHoliday
from .serializers import PublicHolidaySerializer
from shared.pagination import CustomPagination
from user.permissions import IsHRAdmin


from django.db.models import Q

class PublicHolidayCreateListView(generics.ListCreateAPIView):
    serializer_class = PublicHolidaySerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    pagination_class = CustomPagination

    def get_queryset(self):
        queryset = PublicHoliday.objects.filter(
            company=self.request.user.company
        )

        year = self.request.query_params.get("year")
        month = self.request.query_params.get("month")

        if year and month:
            queryset = queryset.filter(
                Q(
                    date__year=year,
                    date__month=month
                )
                |
                Q(holiday_type="company_off_day")
            )

        return queryset.order_by("date")

    def perform_create(self, serializer):
        company = self.request.user.company

        holiday_type = serializer.validated_data.get("holiday_type")
        selected_date = serializer.validated_data.get("date")
        off_day_weekday = serializer.validated_data.get("off_day_weekday")

        # SECOND SATURDAY
        if holiday_type == "second_saturday" and selected_date:

            year = selected_date.year

            for month in range(1, 13):

                month_calendar = calendar.monthcalendar(
                    year,
                    month
                )

                saturday_count = 0

                for week in month_calendar:

                    if week[calendar.SATURDAY] != 0:

                        saturday_count += 1

                        if saturday_count == 2:

                            second_sat = date(
                                year,
                                month,
                                week[calendar.SATURDAY]
                            )

                            PublicHoliday.objects.get_or_create(
                                company=company,
                                date=second_sat,
                                defaults={
                                    "description": "Second Saturday",
                                    "holiday_type": "second_saturday",
                                }
                            )

                            break

            return

        # COMPANY OFF DAY
        if holiday_type == "company_off_day":

            PublicHoliday.objects.get_or_create(
                company=company,
                holiday_type="company_off_day",
                off_day_weekday=off_day_weekday,
                defaults={
                    "description": "Company Off Day"
                }
            )

            return

        serializer.save(company=company)

class PublicHolidayDetailUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PublicHolidaySerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    lookup_field = "pk"

    def get_queryset(self):
        return PublicHoliday.objects.filter(company=self.request.user.company)


class PublicHolidayEmployeeListView(generics.ListAPIView):
    serializer_class = PublicHolidaySerializer
    permission_classes = [IsAuthenticated, IsEmployee]

    def get_queryset(self):
        return (
            PublicHoliday.objects
            .filter(company=self.request.user.company)
            .exclude(holiday_type="company_off_day")
            .order_by("date")
        )


class HolidayTypeListView(APIView):
    def get(self, request):
        types = [
            {"key": key, "label": label}
            for key, label in PublicHoliday.HOLIDAY_TYPES
        ]
        return Response(types)
