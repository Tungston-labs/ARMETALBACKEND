from django.shortcuts import render
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from datetime import datetime,time,date,timedelta
from rest_framework import status, generics, filters
from rest_framework.generics import RetrieveAPIView
from employee.models import Employee_db
from .serializers import AttendanceSerializer, AttendanceSessionSerializer, AttendanceDetailSerializer,AttendanceLocationSerializer
from .utils.timezone_utils import (
    COUNTRY_TIMEZONE_MAPPING,
    get_company_timezone,
    ensure_timezone,
    safe_parse_datetime,
)
from django.db.models import (
    OuterRef,
    Subquery,
    Case,
    When,
    Value,
    BooleanField,
    CharField,
    F,
)
from user.permissions import IsEmployee, IsHRAdmin, IsHRorIsEmployee
import pytz
from geopy.distance import geodesic
import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from project.models import Project
from django.db.models import Q
from geopy.geocoders import Nominatim
from django.utils import timezone
from attendance.models import AttendanceSession, Attendance
from shared.pagination import CustomPagination
from rest_framework.exceptions import ValidationError
from rest_framework import status
logger = logging.getLogger(__name__)
from leave.models import LeaveRequest

# --------------------------------------------------------------view for swipe in/out
class AttendanceSwipeView(APIView):
    permission_classes = [IsAuthenticated]
 
    def post(self, request):
        try:
            user = request.user
            employee = getattr(user, "employee_profile", None)

            if not employee:
                return Response({'error': 'Employee not found'}, status=404)

            emp_lat = request.data.get("latitude")
            emp_lon = request.data.get("longitude")
            if emp_lat is None or emp_lon is None:
                return Response({"error": "Latitude and longitude are required"}, status=400)

            emp_lat, emp_lon = float(emp_lat), float(emp_lon)

            project = Project.objects.filter(employees=employee).first()

            if project:
                if project.status != "in_progress":
                    return Response(
                        {"error": f"Your project '{project.name}' is not active (status: {project.status}). Punching is not allowed."},
                        status=400
                    )
                punch_type = project.punch_type.lower()
            else:
                punch_type = "company"  # No project then company punch rules



            if punch_type == "onsite":
                project_location = (float(project.latitude), float(project.longitude))
                employee_location = (emp_lat, emp_lon)
                distance_project = geodesic(employee_location, project_location).meters

                company = employee.department.company
                company_location = (float(company.latitude), float(company.longitude))
                distance_company = geodesic(employee_location, company_location).meters

                # Allow if within 50m of project OR company
                if distance_project > 50 and distance_company > 50:
                    return Response(
                        {"error": f"You are too far from project/company site "
                                f"(Project: {int(distance_project)}m, Company: {int(distance_company)}m). "
                                f"Must be within 50m of either."},
                        status=400
                    )
                
            elif punch_type == "bench":
                company = employee.department.company
                company_location = (float(company.latitude), float(company.longitude))
                employee_location = (emp_lat, emp_lon)
                distance = geodesic(employee_location, company_location).meters
                if distance > 50:
                    return Response(
                        {"error": f"Bench employees must punch from company location ({int(distance)}m). Allowed within 50m."},
                        status=400
                    )    

            elif punch_type == "company":
                company = employee.department.company
                company_location = (float(company.latitude), float(company.longitude))
                employee_location = (emp_lat, emp_lon)
                distance = geodesic(employee_location, company_location).meters
                if distance > 50:
                    return Response(
                        {"error": f"You are too far from company location ({int(distance)}m). Must be within 50m."},
                        status=400
                    )

            elif punch_type == "variant":
                # Variant employees can punch in/out from anywhere
                pass
            else:
                # Default fallback (optional)
                return Response({"error": f"Invalid punch type: {punch_type}"}, status=400)

            address = self._get_location_address(emp_lat, emp_lon)
            company_tz = get_company_timezone(employee)
            now_utc = timezone.now()
            now_company_tz = now_utc.astimezone(company_tz)
            today = now_company_tz.date()

            # =========================================================
            # APPROVED LEAVE CHECK
            # =========================================================

            is_on_full_day_leave = LeaveRequest.objects.filter(
                employee=employee,
                status="approved",
                from_date__lte=today,
                to_date__gte=today,
                from_date_type="full",
                to_date_type="full",
            ).exists()

            if is_on_full_day_leave:
                return Response(
                    {
                        "error":
                            "You are currently on approved full-day leave and cannot mark attendance."
                    },
                    status=400
                )

            attendance, _ = Attendance.objects.get_or_create(employee=employee, date=today)
            latest_session = attendance.sessions.last()
            should_punch_in = self._should_punch_in(latest_session)

            if should_punch_in:
                return self._handle_punch_in(attendance, now_company_tz, company_tz, emp_lat, emp_lon, address)
            else:
                return self._handle_punch_out(latest_session, now_company_tz, company_tz, emp_lat, emp_lon, address, attendance)

        except Exception as e:
            logger.critical(f"Unhandled error in AttendanceSwipeView: {e}", exc_info=True)
            return Response({'error': 'Internal server error'}, status=500)

    def _should_punch_in(self, latest_session):
        if not latest_session:
            return True
        if not latest_session.time_out:
            return False
        return True

    def _handle_punch_in(self, attendance, now_company_tz, company_tz, lat, lon, address):
        try:
            session = AttendanceSession.objects.create(
                attendance=attendance,
                time_in=now_company_tz,
                timezone=company_tz.zone,
                punch_in_latitude=lat,
                punch_in_longitude=lon,
                punch_in_location=address
            )
            return Response({
                'status': 'success',
                'action': 'punch_in',
                'time': now_company_tz.strftime("%H:%M:%S"),
                'date': now_company_tz.date().isoformat(),
                'session_id': session.id,
                'location': address
            }, status=201)
        except Exception as e:
            logger.error(f"Error during punch in: {e}")
            return Response({'error': 'Failed to punch in'}, status=500)

    def _handle_punch_out(self, latest_session, now_company_tz, company_tz, lat, lon, address, attendance):
        try:
            time_in = latest_session.time_in
            if isinstance(time_in, time):
                time_in = datetime.combine(attendance.date, time_in)
                time_in = company_tz.localize(time_in)

            
            latest_session.time_out = now_company_tz
            latest_session.punch_out_latitude = lat
            latest_session.punch_out_longitude = lon
            latest_session.punch_out_location = address
            latest_session.save()

            session_duration = latest_session.get_duration()

            return Response({
                'status': 'success',
                'action': 'punch_out',
                'time': now_company_tz.strftime("%H:%M:%S"),
                'session_duration': session_duration,
                'location': address,
                'timezone': company_tz.zone
            }, status=200)
        except Exception as e:
            logger.error(f"Error during punch out: {e}")
            return Response({'error': 'Failed to punch out'}, status=500)

    def _get_location_address(self, lat, lon):
        """Convert lat/lon to human-readable address (optional)"""
        try:
            geolocator = Nominatim(user_agent="attendance_app")
            location = geolocator.reverse(f"{lat}, {lon}")
            return location.address if location else None
        except Exception as e:
            logger.warning(f"Geocoding failed: {e}")
            return None


# ----------------------------------to add a note to the corresponding punch out section



class AddPunchOutNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        note = request.data.get('note', '').strip()
        user = request.user
        employee = getattr(user, 'employee_db', None)

        if not employee:
            return Response({'error': 'Employee not found'}, status=404)

        today = timezone.localdate()

        try:
            attendance = Attendance.objects.get(employee=employee, date=today)
        except Attendance.DoesNotExist:
            return Response({'error': 'No attendance found for today.'}, status=404)

        latest_session = attendance.sessions.filter(time_out__isnull=False).order_by('-time_out').first()

        if not latest_session:
            return Response({'error': 'No punch-out session found to add note.'}, status=400)

        latest_session.note = note if note else None
        latest_session.save()

        return Response({
            'status': 'success',
            'message': 'Note added to the latest attendance session'
        }, status=200)






# -----------------------------------------------------view for list attendance for admin

from datetime import date as today_date
from rest_framework import generics, filters
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from employee.models import Employee_db
from .serializers import AttendanceSerializer
from django.db import models
from django.db.models.functions import Coalesce
from django.db.models import OuterRef, Subquery, BooleanField, Case, When, Value, F,OuterRef
from attendance.models import Attendance, AttendanceSession





class AttendanceAdminListView(generics.ListAPIView):
    serializer_class = AttendanceSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]

    def _get_default_selected_date(self):
        company = getattr(self.request.user, "company", None)
        country = getattr(company, "country", None)
        tz_name = COUNTRY_TIMEZONE_MAPPING.get(
            country,
            str(timezone.get_current_timezone()),
        )

        try:
            company_tz = pytz.timezone(tz_name)
        except Exception:
            company_tz = timezone.get_current_timezone()

        return timezone.now().astimezone(company_tz).date()

    def get_queryset(self):
        department_id = self.request.query_params.get("department_id")
        selected_date_param = self.request.query_params.get("date")

        if selected_date_param:
            selected_date = parse_date(selected_date_param)
            if not selected_date:
                raise ValidationError({"date": "Invalid date format. Use YYYY-MM-DD"})
        else:
            selected_date = self._get_default_selected_date()

        attendance_qs = Attendance.objects.filter(
            employee=OuterRef("pk"),
            date=selected_date,
        )

        first_session = AttendanceSession.objects.filter(
            attendance__employee=OuterRef("pk"),
            attendance__date=selected_date,
            time_in__isnull=False,
        ).order_by("time_in")

        last_session = AttendanceSession.objects.filter(
                attendance__employee=OuterRef("pk"),
                attendance__date=selected_date,
                time_out__isnull=False,
            ).order_by("-time_out")

        base_qs = Employee_db.objects.filter(is_deleted=False)

        if department_id:
            # Optional now: only filter by department if it's explicitly passed
            base_qs = base_qs.filter(department_id=department_id)
        else:
            # No department_id -> return the FULL list, scoped to the admin's company
            company = getattr(self.request.user, "company", None)
            if company:
                base_qs = base_qs.filter(department__company=company)

        queryset = (
            base_qs
            .annotate(
                date=Subquery(attendance_qs.values("date")[:1]),
                total_hours=Subquery(attendance_qs.values("total_hours")[:1]),
                attendance_id=Subquery(attendance_qs.values("id")[:1]),
                attendance_type=Subquery(
                    attendance_qs.values("attendance_type")[:1]
                ),
                first_swipe_in=Subquery(first_session.values("time_in")[:1]),
                last_swipe_out=Subquery(last_session.values("time_out")[:1]),
                attendance_today=Case(
                    When(
                        first_swipe_in__isnull=False,
                        then=Value(True)
                    ),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                attendance_status=Case(

                    # Paid attendance
                    When(
                        attendance_type="paid",
                        then=Value("paid")
                    ),

                    # No attendance record
                    When(
                        attendance_id__isnull=True,
                        then=Value("absent")
                    ),

                    # Attendance record exists but no punch-in
                    When(
                        first_swipe_in__isnull=True,
                        then=Value("missed_punch_in")
                    ),

                    # Punch-in exists but punch-out doesn't
                    When(
                        first_swipe_in__isnull=False,
                        last_swipe_out__isnull=True,
                        then=Value("missed_punch_out")
                    ),

                    # Both punch-in and punch-out exist
                    When(
                        first_swipe_in__isnull=False,
                        last_swipe_out__isnull=False,
                        then=Value("present")
                    ),

                    default=Value("absent"),
                    output_field=CharField(),
                ),
            )
            .order_by(F("first_swipe_in").asc(nulls_last=True))
        )

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        swiped_count = queryset.filter(attendance_today=True).count()
        total_count = queryset.count()

        response = super().list(request, *args, **kwargs)

        response.data["swiped_employee_count"] = swiped_count
        response.data["total_employee_count"] = total_count

        return response

    def get(self, request, *args, **kwargs):
        query = request.GET.get("q", "").strip()

        if not query:
            return super().get(request, *args, **kwargs)

        employees = (Employee_db.objects.filter(name_search__icontains=query,is_deleted=False).select_related("department").prefetch_related("attendances")
)

        final_results = []

        for emp in employees:
            # Get latest attendance
            attendance = emp.attendances.order_by('-date').first()

            # Prepare response
            final_results.append({
                "id": emp.id,
                "employee_name": emp.name,
                "employee_id": emp.employee_id,
                "department": {
                    "id": emp.department.id,
                    "name": emp.department.name
                },
                "date": attendance.date if attendance else None,
                "time_in":
                    attendance.sessions.first().time_in
                    if attendance and attendance.sessions.exists()
                    else None,
                "time_out":
                    attendance.sessions.last().time_out
                    if attendance and attendance.sessions.exists()
                    else None,
            })

        return Response(final_results)



from django.utils.dateparse import parse_date, parse_datetime

class AttendanceDetailByDateView(APIView):
    permission_classes = [IsAuthenticated, IsHRorIsEmployee]

    def get(self, request):
        user = request.user
        employee = getattr(user, 'employee_db', None)
        print("USER ID:", request.user.id)
        print("USERNAME:", request.user.username)
        print("HAS EMPLOYEE:", hasattr(request.user, "employee_db"))


        if not employee:
            return Response(
                {'detail': 'Employee not found.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        date_param = request.query_params.get('date')

        if date_param:
            parsed_date = parse_date(date_param)

            if not parsed_date:
                parsed_datetime = parse_datetime(date_param)
                if parsed_datetime:
                    parsed_date = parsed_datetime.date()

            if not parsed_date:
                return Response(
                    {'detail': 'Invalid date format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            selected_date = parsed_date
        else:
            selected_date = timezone.localdate()

        attendance = Attendance.objects.filter(
            employee=employee,
            date=selected_date
        ).first()

        if not attendance:
            return Response(
                {
                    'detail': 'No attendance found',
                    'date': selected_date
                },
                status=status.HTTP_200_OK  # IMPORTANT for mobile
            )

        serializer = AttendanceDetailSerializer(attendance)
        return Response(serializer.data)



from datetime import datetime
from django.db.models import Sum
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Attendance
from .serializers import AttendanceDetailSerializer
from django.utils.timezone import now
from django.utils import timezone


def format_local_time(self, dt):
    if not dt:
        return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())

    return timezone.localtime(dt).strftime("%H:%M")
class AttendanceAdminDetailView(RetrieveAPIView):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceDetailSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    lookup_field = 'employee_id'

    def get_today_punch_times(self, employee_id):
        today = now().date()

        today_attendance = Attendance.objects.filter(
            employee__id=employee_id,
            date=today
        ).prefetch_related("sessions").first()

        if not today_attendance or not today_attendance.sessions.exists():
            return None, None

        first_session = today_attendance.sessions.order_by("time_in").first()
        last_session = today_attendance.sessions.order_by("-time_out").first()

        first_in = (
            first_session.time_in.strftime("%H:%M")
            if first_session and first_session.time_in else None
        )

        last_out = (
            last_session.time_out.strftime("%H:%M")
            if last_session and last_session.time_out else None
        )


        return first_in, last_out

    def get(self, request, *args, **kwargs):
        employee_id = kwargs.get(self.lookup_field)
        date_str = request.query_params.get('date')

        base_attendance = Attendance.objects.filter(
            employee__id=employee_id
        ).order_by('-date').first()

        first_in, last_out = self.get_today_punch_times(employee_id)

        if not base_attendance:
            data = {
                "id": None,
                "date": date_str or str(datetime.today().date()),
                "total_hours": None,
                "total_hours_formatted": "00:00",
                "weekly_hours_formatted": "00:00",
                "monthly_hours_formatted": "00:00",
                "remark": "",
                "employee": {"id": employee_id},
                "sessions": [],
                "status": "Absent",
                "note": "No attendance available",
                "today_first_punch_in": first_in,
                "today_last_punch_out": last_out,
            }
            return Response(data, status=200)

        if date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"},
                    status=400
                )

            attendance = Attendance.objects.filter(
                employee__id=employee_id,
                date=date_obj
            ).first()

            if not attendance:
                serializer = self.get_serializer(base_attendance)
                data = serializer.data
                data.update({
                    "date": str(date_obj),
                    "sessions": [],
                    "total_hours": None,
                    "total_hours_formatted": "00:00",
                    "weekly_hours_formatted": "00:00",
                    "monthly_hours_formatted": "00:00",
                    "status": "Absent",
                    "note": f"No attendance available for {date_obj}",
                    "today_first_punch_in": first_in,
                    "today_last_punch_out": last_out,
                })
                return Response(data, status=200)

            serializer = self.get_serializer(attendance)
            data = serializer.data
            data["today_first_punch_in"] = first_in
            data["today_last_punch_out"] = last_out
            return Response(data)

        serializer = self.get_serializer(base_attendance)
        data = serializer.data
        data["today_first_punch_in"] = first_in
        data["today_last_punch_out"] = last_out

        return Response(data)


# -----------------------------------------------------one hour location update from mobile app and view by admin

logger = logging.getLogger(__name__)

class AttendanceLocationUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Append employee's current location to today's attendance.
        Must be called after first punch-in.
        """
        serializer = AttendanceLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = request.user
            employee = Employee_db.objects.get(user=user,is_deleted=False)
        except Employee_db.DoesNotExist:
            return Response({"detail": "Employee not found."}, status=404)

        today = timezone.localdate()
        try:
            attendance = Attendance.objects.get(employee=employee, date=today)
        except Attendance.DoesNotExist:
            return Response({"detail": "No active attendance session. Punch in first."},
                            status=400)

        loc_data = {
            "location": serializer.validated_data["location"],
            "timestamp": serializer.validated_data.get("timestamp", timezone.now().isoformat())
        }

        if attendance.locations is None:
            attendance.locations = []

        attendance.locations.append(loc_data)
        attendance.save(update_fields=['locations'])

        logger.info(f"Location updated for employee {employee.id}: {loc_data}")

        return Response({
            "detail": "Location updated successfully.",
            "locations": attendance.locations
        })

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import datetime, time

from employee.models import Employee_db
from .models import HourlyLocationLog
from .serializers import HourlyLocationLogSerializer,AttendanceCorrectionRequestSerializer
from .utils.geocoding_utils import get_location_name_sync
from shared.pagination import HourlyLocationLogPagination  # Import the pagination class

class BackgroundLocationUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        """
        Return background location logs for the given employee filtered by date
        with pagination.
        """
        try:
            employee = Employee_db.objects.get(id=employee_id,is_deleted=False)
        except Employee_db.DoesNotExist:
            return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

        logs_qs = HourlyLocationLog.objects.filter(employee=employee).order_by("-logged_at")

        date_str = request.query_params.get("date")
        from_date_str = request.query_params.get("from_date")
        to_date_str = request.query_params.get("to_date")

        try:
            if date_str:
                date_obj = parse_date(date_str)
                if date_obj:
                    start = timezone.make_aware(datetime.combine(date_obj, time.min))
                    end = timezone.make_aware(datetime.combine(date_obj, time.max))
                    logs_qs = logs_qs.filter(logged_at__gte=start, logged_at__lte=end)
            
            elif from_date_str or to_date_str:
                if from_date_str:
                    from_date = parse_date(from_date_str)
                    if from_date:
                        start = timezone.make_aware(datetime.combine(from_date, time.min))
                        logs_qs = logs_qs.filter(logged_at__gte=start)
                if to_date_str:
                    to_date = parse_date(to_date_str)
                    if to_date:
                        end = timezone.make_aware(datetime.combine(to_date, time.max))
                        logs_qs = logs_qs.filter(logged_at__lte=end)
        except Exception:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paginator = HourlyLocationLogPagination()
        page = paginator.paginate_queryset(logs_qs, request)
        serializer = HourlyLocationLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, employee_id):
        """
        Save background location updates from mobile app.
        Reverse geocode latitude & longitude to get location_name.
        """
        try:
            employee = Employee_db.objects.get(id=employee_id)
        except Employee_db.DoesNotExist:
            return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        data["employee"] = employee.id
        if "logged_at" not in data and "captured_at" in data:
            data["logged_at"] = data["captured_at"]

        serializer = HourlyLocationLogSerializer(data=data)
        if serializer.is_valid():
            obj = serializer.save()
            print(f" Calling geocoding for lat={obj.latitude}, lon={obj.longitude}")

            if obj.latitude is not None and obj.longitude is not None:
                try:
                    obj.location_name = get_location_name_sync(obj.latitude, obj.longitude)
                    obj.save(update_fields=["location_name"])
                    print(f" Saved location_name '{obj.location_name}' for employee {employee_id}")
                except Exception as e:
                    print(f"⚠️ Geocoding failed for employee {employee_id}: {e}")

            return Response({"status": "success"}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from datetime import date
import calendar

from employee.models import Employee_db
from payroll.models import EmployeePayrollRecord
from .serializers import EmployeeAttendanceSummarySerializer
from .utils.dayscalculations import build_employee_month_calendar

from datetime import date
import calendar

from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from employee.models import Employee_db
from payroll.models import EmployeePayrollRecord


class EmployeeAttendanceSummaryView(generics.ListAPIView):
    serializer_class = EmployeeAttendanceSummarySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user

        if not user.company:
            return Employee_db.objects.none()

        today = date.today()

        year = int(
            self.request.query_params.get(
                "year",
                today.year
            )
        )

        month = int(
            self.request.query_params.get(
                "month",
                today.month
            )
        )

        # -------------------------------------------------
        # Selected month's first and last day
        # -------------------------------------------------

        start_date = date(year, month, 1)

        last_day = calendar.monthrange(year, month)[1]

        end_date = date(
            year,
            month,
            last_day
        )

        # -------------------------------------------------
        # Company employees
        # -------------------------------------------------

        # -------------------------------------------------
        # Company employees
        # -------------------------------------------------

        qs = Employee_db.objects.select_related(
            "department",
            "department__company"
        ).filter(
            department__company=user.company,
            is_deleted=False
        )

        # -------------------------------------------------
        # Search by employee name / employee ID / code
        # -------------------------------------------------

        search = self.request.query_params.get("search", "").strip()

        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(employee_code__icontains=search)
            )

        # -------------------------------------------------
        # Employee / HR role
        # -------------------------------------------------

        # if user.is_employee:
        #     qs = qs.filter(user=user)

        # -------------------------------------------------
        # Employee must have joined on or before the
        # selected month's last day.
        #
        # This prevents a July employee from appearing
        # when June is selected.
        # -------------------------------------------------

        qs = qs.filter(
            joining_date__lte=end_date
        )

        # -------------------------------------------------
        # Deleted employee handling
        #
        # If employee was deleted after the selected month,
        # they should still be available for historical
        # attendance.
        #
        # If employee was already deleted before the
        # selected month started, don't show them.
        # -------------------------------------------------

        qs = qs.filter(
            Q(is_deleted=False) |
            Q(deleted_at__gte=start_date)
        )

        return qs.order_by(
            "department__name",
            "name_search"
        )

    def list(self, request, *args, **kwargs):

        today = date.today()

        year = int(
            request.query_params.get(
                "year",
                today.year
            )
        )

        month = int(
            request.query_params.get(
                "month",
                today.month
            )
        )

        start_date = date(
            year,
            month,
            1
        )

        last_day = calendar.monthrange(
            year,
            month
        )[1]

        end_date = date(
            year,
            month,
            last_day
        )

        results = []

        # -------------------------------------------------
        # Don't generate attendance for a future month
        # -------------------------------------------------

        if start_date > today.replace(day=1):

            for emp in self.get_queryset():

                results.append({
                    "employee_id": emp.employee_id,
                    "employee_name": emp.name,
                    "department": (
                        emp.department.name
                        if emp.department
                        else None
                    ),
                    "working_days": 0,
                    "present_days": 0,
                    "absent_days": 0,
                    "lop_days": 0,
                    "daily_records": [],
                })

        else:

            for emp in self.get_queryset():

                # -------------------------------------------------
                # Build attendance calendar
                # -------------------------------------------------

                (
                    calendar_working_days,
                    calendar_present_days,
                    calendar_absent_days,
                    calendar_lop_days,
                    daily_records
                ) = build_employee_month_calendar(
                    emp,
                    start_date,
                    end_date
                )

                # -------------------------------------------------
                # Payroll snapshot
                # -------------------------------------------------

                payroll = EmployeePayrollRecord.objects.filter(
                    employee=emp,
                    year=year,
                    month=month
                ).first()

                # -------------------------------------------------
                # If payroll is PAID, use payroll snapshot
                # Otherwise use attendance calendar
                # -------------------------------------------------

                if payroll and payroll.status.lower() == "paid":

                    working_days = (
                        payroll.working_days
                        if payroll.working_days is not None
                        else calendar_working_days
                    )

                    present_days = (
                        payroll.days_present
                        if payroll.days_present is not None
                        else calendar_present_days
                    )

                    lop_days = (
                        payroll.lop_days
                        if payroll.lop_days is not None
                        else calendar_lop_days
                    )

                    absent_days = max(
                        working_days - present_days,
                        0
                    )

                else:

                    working_days = calendar_working_days
                    present_days = calendar_present_days
                    absent_days = calendar_absent_days
                    lop_days = calendar_lop_days

                results.append({
                    "employee_id": emp.employee_id,
                    "employee_name": emp.name,
                    "department": (
                        emp.department.name
                        if emp.department
                        else None
                    ),
                    "working_days": working_days,
                    "present_days": present_days,
                    "absent_days": absent_days,
                    "lop_days": lop_days,
                    "daily_records": daily_records,
                })

        # -------------------------------------------------
        # Pagination
        # -------------------------------------------------

        page = self.paginate_queryset(results)

        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = self.get_serializer(
            results,
            many=True
        )

        return Response(
            serializer.data
        )
    
from rest_framework import serializers
class AttendanceCorrectionRequestCreateView(
    generics.CreateAPIView
):

    serializer_class = AttendanceCorrectionRequestSerializer

    permission_classes = [
        IsAuthenticated
    ]

    def perform_create(self, serializer):

        employee = getattr(
            self.request.user,
            "employee_profile",
            None
        )

        if not employee:
            raise serializers.ValidationError({
                "employee": "Employee profile not found."
            })

        serializer.save(
            employee=employee
        )


from django.utils import timezone

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AttendanceCorrectionRequest
from .serializers import AttendanceCorrectionRequestSerializer


class AttendanceCorrectionStatusUpdateView(
    generics.UpdateAPIView
):
    permission_classes = [IsAuthenticated]
    serializer_class = AttendanceCorrectionRequestSerializer

    def get_queryset(self):
        user = self.request.user

        company = getattr(user, "company", None)

        if not company:
            return AttendanceCorrectionRequest.objects.none()

        return AttendanceCorrectionRequest.objects.filter(
            employee__department__company=company
        )

    def patch(self, request, *args, **kwargs):

        correction_request = self.get_object()

        new_status = request.data.get("status")
        admin_reason = request.data.get("admin_reason", "")

        # ---------------------------------------------
        # STATUS VALIDATION
        # ---------------------------------------------

        if new_status not in ["approved", "rejected"]:
            return Response(
                {
                    "status": [
                        "Status must be either approved or rejected."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---------------------------------------------
        # ONLY PENDING REQUEST CAN BE REVIEWED
        # ---------------------------------------------

        if correction_request.status != "pending":
            return Response(
                {
                    "detail": (
                        "This request has already been reviewed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---------------------------------------------
        # REJECTION REASON
        # ---------------------------------------------

        if new_status == "rejected" and not admin_reason.strip():
            return Response(
                {
                    "admin_reason": [
                        "Admin reason is required when rejecting "
                        "an attendance correction request."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---------------------------------------------
        # UPDATE
        # ---------------------------------------------

        correction_request.status = new_status

        correction_request.admin_reason = (
            admin_reason.strip()
            if admin_reason
            else None
        )

        correction_request.reviewed_by = request.user
        correction_request.reviewed_at = timezone.now()

        correction_request.save(
            update_fields=[
                "status",
                "admin_reason",
                "reviewed_by",
                "reviewed_at",
                "updated_at",
            ]
        )

        # ---------------------------------------------
        # RESPONSE
        # ---------------------------------------------

        return Response(
            {
                "message": (
                    f"Attendance correction request "
                    f"{new_status} successfully."
                ),
                "request": AttendanceCorrectionRequestSerializer(
                    correction_request,
                    context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK
        )
    

from django.core.files.base import ContentFile
from django.db import transaction

from attendance.models import EmployeeAttendanceReport

from attendance.utils.attendance_excel import (
    generate_attendance_excel
)

from .utils.dayscalculations import (
    build_employee_month_calendar
)
class GenerateEmployeeAttendanceExcelView(
    generics.GenericAPIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def post(self, request, *args, **kwargs):

        user = request.user

        # =====================================================
        # COMPANY
        # =====================================================

        if not user.company:

            return Response(
                {
                    "detail":
                        "User is not associated with a company."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # YEAR / MONTH
        # =====================================================

        today = date.today()

        try:

            year = int(
                request.data.get(
                    "year",
                    today.year
                )
            )

            month = int(
                request.data.get(
                    "month",
                    today.month
                )
            )

        except (
            TypeError,
            ValueError
        ):

            return Response(
                {
                    "detail":
                        "Invalid year or month."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # VALIDATE MONTH
        # =====================================================

        if month < 1 or month > 12:

            return Response(
                {
                    "detail":
                        "Month must be between 1 and 12."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # SELECTED MONTH
        # =====================================================

        start_date = date(
            year,
            month,
            1
        )

        last_day = calendar.monthrange(
            year,
            month
        )[1]

        end_date = date(
            year,
            month,
            last_day
        )

        # =====================================================
        # FUTURE MONTH
        # =====================================================

        if start_date > today.replace(day=1):

            return Response(
                {
                    "detail":
                        "Cannot generate attendance report for a future month."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # EMPLOYEES
        # =====================================================

        employees = (
            Employee_db.objects
            .select_related(
                "department",
                "department__company"
            )
            .filter(
                department__company=user.company,
                joining_date__lte=end_date
            )
            .filter(
                is_deleted=False
            )
            .order_by(
                "department__name",
                "name_search"
            )
        )

        # =====================================================
        # GENERATE EXCEL
        # =====================================================

        excel_file = generate_attendance_excel(
            employees=employees,
            year=year,
            month=month,
            build_calendar_func=
                build_employee_month_calendar
        )

        # =====================================================
        # FILE NAME
        # =====================================================

        file_name = (
            f"Attendance_"
            f"{year}_"
            f"{month:02d}.xlsx"
        )

        # =====================================================
        # REPLACE EXISTING REPORT
        # =====================================================

        with transaction.atomic():

            existing_report = (
                EmployeeAttendanceReport.objects
                .filter(
                    company=user.company,
                    year=year,
                    month=month
                )
                .first()
            )

            if existing_report:

                # Delete old physical file
                if existing_report.report_file:

                    existing_report.report_file.delete(
                        save=False
                    )

                existing_report.report_file.save(
                    file_name,
                    ContentFile(
                        excel_file.getvalue()
                    ),
                    save=True
                )

                report = existing_report

            else:

                report = (
                    EmployeeAttendanceReport.objects
                    .create(
                        company=user.company,
                        year=year,
                        month=month
                    )
                )

                report.report_file.save(
                    file_name,
                    ContentFile(
                        excel_file.getvalue()
                    ),
                    save=True
                )

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {
                "message":
                    "Attendance report generated successfully.",

                "year":
                    year,

                "month":
                    month,

                "report_id":
                    report.id,

                "file_name":
                    file_name,

                "download_url":
                    request.build_absolute_uri(
                        report.report_file.url
                    ),

                "created_at":
                    report.created_at,

                "updated_at":
                    report.updated_at,
            },
            status=status.HTTP_200_OK
        )
    


from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from attendance.models import Attendance
from .serializers import AttendanceManualUpdateSerializer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from attendance.models import Attendance
from .serializers import AttendanceManualUpdateSerializer

from django.db import transaction

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from attendance.models import Attendance

from .serializers import AttendanceManualUpdateSerializer


class AttendanceManualUpdateView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request):

        # ==================================================
        # REQUEST DATA
        # ==================================================

        employee_value = request.data.get("employee")
        attendance_date = request.data.get("date")

        attendance_type = request.data.get(
            "attendance_type"
        )

        day_limit = request.data.get(
            "day_limit"
        )

        remark = request.data.get(
            "remark",
            ""
        )

        # ==================================================
        # REQUIRED FIELDS
        # ==================================================

        if not employee_value:
            return Response(
                {
                    "error": "employee is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not attendance_date:
            return Response(
                {
                    "error": "date is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ==================================================
        # PERMISSION CHECK
        # ==================================================

        user = request.user

        if not (
            getattr(user, "is_superadmin", False)
            or getattr(user, "is_hr_admin", False)
            or getattr(user, "is_hr", False)
        ):
            return Response(
                {
                    "error": (
                        "You do not have permission "
                        "to update attendance."
                    )
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # ==================================================
        # ATTENDANCE TYPE
        # ==================================================

        if attendance_type:
            attendance_type = str(
                attendance_type
            ).lower().strip()

        elif day_limit:
            attendance_type = str(
                day_limit
            ).lower().strip()

        else:
            attendance_type = "unpaid"

        if attendance_type not in [
            "paid",
            "unpaid"
        ]:
            return Response(
                {
                    "error": (
                        "attendance_type must be "
                        "'paid' or 'unpaid'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ==================================================
        # FIND EMPLOYEE
        # ==================================================

        employee = None

        # --------------------------------------------------
        # 1. Employee primary key
        # --------------------------------------------------

        try:
            if str(employee_value).isdigit():

                employee = Employee_db.objects.filter(
                    id=int(employee_value)
                ).first()

        except (
            ValueError,
            TypeError
        ):
            employee = None

        # --------------------------------------------------
        # 2. Employee ID
        # --------------------------------------------------

        if employee is None:

            employee = Employee_db.objects.filter(
                employee_id=str(employee_value)
            ).first()

        # --------------------------------------------------
        # 3. Employee email
        # --------------------------------------------------

        if employee is None:

            employee = Employee_db.objects.filter(
                email__iexact=str(employee_value)
            ).first()

        # ==================================================
        # EMPLOYEE NOT FOUND
        # ==================================================

        if employee is None:

            return Response(
                {
                    "error": (
                        f"No employee found for "
                        f"'{employee_value}'."
                    )
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # ==================================================
        # COMPANY PERMISSION
        # ==================================================

        department = getattr(
            employee,
            "department",
            None
        )

        company = getattr(
            department,
            "company",
            None
        )

        user_company = getattr(
            user,
            "company",
            None
        )

        if (
            user_company
            and company
            and user_company.id != company.id
        ):
            return Response(
                {
                    "error": (
                        "You do not have permission "
                        "to modify this employee's "
                        "attendance."
                    )
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # ==================================================
        # GET OR CREATE ATTENDANCE
        # ==================================================

        attendance, created = (
            Attendance.objects.select_related(
                "employee",
                "employee__department",
                "employee__department__company",
                "updated_by"
            ).get_or_create(

                employee=employee,

                date=attendance_date,

                defaults={
                    "attendance_type": attendance_type,
                    "remark": (
                        remark.strip()
                        if remark.strip()
                        else None
                    ),

                    # Employee did not swipe,
                    # therefore there are no sessions.
                    "total_hours": 0,

                    # Admin who manually created
                    # this attendance record.
                    "updated_by": user,
                }
            )
        )

        # ==================================================
        # UPDATE EXISTING ATTENDANCE
        # ==================================================

        if not created:

            attendance.attendance_type = (
                attendance_type
            )

            attendance.remark = (
                remark.strip()
                if remark.strip()
                else None
            )

            attendance.updated_by = user

            # IMPORTANT:
            #
            # Do NOT change total_hours here.
            #
            # If employee has actual swipe sessions,
            # preserve the calculated hours.

            attendance.save(
                update_fields=[
                    "attendance_type",
                    "remark",
                    "updated_by",
                    "updated_at",
                ]
            )

        # ==================================================
        # SERIALIZER
        # ==================================================

        serializer = AttendanceManualUpdateSerializer(
            attendance,
            context={
                "request": request
            }
        )

        # ==================================================
        # RESPONSE
        # ==================================================

        return Response(
            {
                "message": (
                    "Attendance record created successfully."
                    if created
                    else
                    "Attendance updated successfully."
                ),

                "created": created,

                "data": serializer.data
            },
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            )
        )


from django.http import HttpResponse


class GenerateSingleEmployeeAttendanceExcelView(
    generics.GenericAPIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def post(self, request, *args, **kwargs):

        user = request.user

        # =====================================================
        # COMPANY
        # =====================================================

        if not user.company:

            return Response(
                {
                    "detail":
                        "User is not associated with a company."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # EMPLOYEE
        # =====================================================

        employee_value = request.data.get("employee")

        if not employee_value:

            return Response(
                {
                    "detail": "employee is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        employee = None

        try:
            if str(employee_value).isdigit():

                employee = Employee_db.objects.filter(
                    id=int(employee_value)
                ).first()

        except (ValueError, TypeError):
            employee = None

        if employee is None:

            employee = Employee_db.objects.filter(
                employee_id=str(employee_value)
            ).first()

        if employee is None:

            employee = Employee_db.objects.filter(
                email__iexact=str(employee_value)
            ).first()

        if employee is None:

            return Response(
                {
                    "detail": (
                        f"No employee found for "
                        f"'{employee_value}'."
                    )
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # COMPANY OWNERSHIP CHECK
        # =====================================================

        department = getattr(employee, "department", None)
        company = getattr(department, "company", None)

        if company and user.company_id != company.id:

            return Response(
                {
                    "detail": (
                        "You do not have permission to "
                        "generate a report for this employee."
                    )
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # =====================================================
        # YEAR / MONTH
        # =====================================================

        today = date.today()

        try:

            year = int(
                request.data.get("year", today.year)
            )

            month = int(
                request.data.get("month", today.month)
            )

        except (TypeError, ValueError):

            return Response(
                {
                    "detail": "Invalid year or month."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if month < 1 or month > 12:

            return Response(
                {
                    "detail": "Month must be between 1 and 12."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        start_date = date(year, month, 1)

        last_day = calendar.monthrange(year, month)[1]

        end_date = date(year, month, last_day)

        if start_date > today.replace(day=1):

            return Response(
                {
                    "detail": (
                        "Cannot generate attendance report "
                        "for a future month."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================
        # GENERATE EXCEL (single employee)
        # =====================================================

        excel_file = generate_attendance_excel(
            employees=[employee],
            year=year,
            month=month,
            build_calendar_func=build_employee_month_calendar
        )

        file_name = (
            f"Attendance_"
            f"{employee.employee_id}_"
            f"{year}_"
            f"{month:02d}.xlsx"
        )

        # =====================================================
        # RESPONSE — direct file download
        # (not saved to EmployeeAttendanceReport, since that
        # model is unique per company/year/month, not per employee)
        # =====================================================

        response = HttpResponse(
            excel_file.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            )
        )

        response["Content-Disposition"] = (
            f'attachment; filename="{file_name}"'
        )

        return response