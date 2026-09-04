from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncMonth

from employee.models import Employee_db
from leave.models import LeaveRequest
from attendance.models import Attendance
from reimbursement.models import Reimbursement
from departments.models import Department
from holidays.models import PublicHoliday
from project.models import Project
from user.permissions import IsHRAdmin

from .serializers import ContractExpirySerializer


# --------------------------------------------------------------------
# GENERIC ERROR HANDLER
# --------------------------------------------------------------------
def error(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({"error": message}, status=code)


# --------------------------------------------------------------------
# 1. DASHBOARD COUNTS
# --------------------------------------------------------------------
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from employee.models import Employee_db
from departments.models import Department
from leave.models import LeaveRequest
from payroll.models import EmployeePayrollRecord
from project.models import Project
from user.permissions import IsHRAdmin


class DashboardCountsView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get_percentage(self, current, previous):
        """
        Calculate percentage change.

        Example:
        previous = 100
        current = 120
        result = 20%

        If previous is 0:
            current > 0 -> 100%
            current = 0 -> 0%
        """

        if previous == 0:
            if current > 0:
                return 100
            return 0

        percentage = ((current - previous) / previous) * 100

        return round(percentage, 2)

    def get(self, request):

        try:
            company = getattr(request.user, "company", None)

            if not company:
                return Response(
                    {
                        "detail": "Company not assigned to user."
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            today = date.today()

            # =====================================================
            # CURRENT MONTH
            # =====================================================

            current_year = today.year
            current_month = today.month

            # =====================================================
            # PREVIOUS MONTH
            # =====================================================

            first_day_current_month = today.replace(day=1)

            previous_month_last_day = (
                first_day_current_month - timedelta(days=1)
            )

            previous_year = previous_month_last_day.year
            previous_month = previous_month_last_day.month

            # =====================================================
            # ACTIVE EMPLOYEES
            # =====================================================

            active_employees = Employee_db.objects.filter(
                department__company=company,
                is_deleted=False
            )

            total_employees = active_employees.count()

            # -----------------------------------------------------
            # Active employees at the end of previous month
            # -----------------------------------------------------

            previous_month_employees = Employee_db.objects.filter(
                department__company=company,
                joining_date__lte=previous_month_last_day
            ).filter(
                Q(is_deleted=False) |
                Q(deleted_at__gt=previous_month_last_day)
            )

            previous_employee_count = previous_month_employees.count()

            employee_change_percentage = self.get_percentage(
                total_employees,
                previous_employee_count
            )

            # =====================================================
            # DEPARTMENTS
            # =====================================================

            total_departments = Department.objects.filter(
                company=company
            ).count()

            # Departments created during current month
            new_departments = Department.objects.filter(
                company=company,
                created_at__year=current_year,
                created_at__month=current_month
            ).count()

            # =====================================================
            # PROJECTS
            # =====================================================

            total_projects = Project.objects.filter(
                company=company
            ).count()

            # Projects added during current month
            new_projects = Project.objects.filter(
                company=company,
                created_at__year=current_year,
                created_at__month=current_month
            ).count()

            # =====================================================
            # PENDING LEAVE REQUESTS
            # =====================================================

            pending_leave_requests = LeaveRequest.objects.filter(
                employee__department__company=company,
                employee__is_deleted=False,
                status="pending"
            ).count()

            # Pending leave requests created during previous month
            previous_pending_leave_requests = LeaveRequest.objects.filter(
                employee__department__company=company,
                employee__is_deleted=False,
                status="pending",
                created_at__year=previous_year,
                created_at__month=previous_month
            ).count()

            leave_change_percentage = self.get_percentage(
                pending_leave_requests,
                previous_pending_leave_requests
            )

            # =====================================================
            # PAYROLL
            # =====================================================
            #
            # Current month:
            # Sum of BASIC SALARY only
            # for PAID payroll records
            #
            # Company is determined through:
            #
            # EmployeePayrollRecord
            #       ↓
            # Employee
            #       ↓
            # Department
            #       ↓
            # Company
            #
            # =====================================================

            current_payroll = EmployeePayrollRecord.objects.filter(
                employee__department__company=company,
                year=current_year,
                month=current_month,
                status="Paid"
            ).aggregate(
                total=Sum("basic_salary")
            )["total"] or Decimal("0")

            # Previous month payroll

            previous_payroll = EmployeePayrollRecord.objects.filter(
                employee__department__company=company,
                year=previous_year,
                month=previous_month,
                status="Paid"
            ).aggregate(
                total=Sum("basic_salary")
            )["total"] or Decimal("0")

            payroll_change_percentage = self.get_percentage(
                current_payroll,
                previous_payroll
            )

            # =====================================================
            # VISA / CONTRACT EXPIRY
            # =====================================================

            # Today's upcoming expiry window
            #
            # Today -> next 30 days
            #

            upcoming_expiry_end = today + timedelta(days=30)

            expiry_filter = (
                Q(
                    visa_expiry_date__range=[
                        today,
                        upcoming_expiry_end
                    ]
                )
                |
                Q(
                    contract_expiry_date__range=[
                        today,
                        upcoming_expiry_end
                    ]
                )
            )

            expiry_count = active_employees.filter(
                expiry_filter
            ).count()

            # -----------------------------------------------------
            # Yesterday's expiry window
            #
            # Yesterday -> next 30 days
            #
            # This allows comparison of how many upcoming
            # expiries were visible yesterday vs today.
            # -----------------------------------------------------

            yesterday = today - timedelta(days=1)

            yesterday_expiry_end = yesterday + timedelta(days=30)

            yesterday_expiry_filter = (
                Q(
                    visa_expiry_date__range=[
                        yesterday,
                        yesterday_expiry_end
                    ]
                )
                |
                Q(
                    contract_expiry_date__range=[
                        yesterday,
                        yesterday_expiry_end
                    ]
                )
            )

            previous_expiry_count = active_employees.filter(
                yesterday_expiry_filter
            ).count()

            expiry_change_percentage = self.get_percentage(
                expiry_count,
                previous_expiry_count
            )

            # =====================================================
            # RESPONSE
            # =====================================================

            data = {
                "total_employees": total_employees,
                "employee_change_percentage": employee_change_percentage,

                "total_departments": total_departments,
                "new_departments": new_departments,

                "total_projects": total_projects,
                "new_projects": new_projects,

                "pending_leave_requests": pending_leave_requests,
                "leave_change_percentage": leave_change_percentage,

                "monthly_payroll_amount": current_payroll,
                "payroll_change_percentage": payroll_change_percentage,

                "expiry_count": expiry_count,
                "expiry_change_percentage": expiry_change_percentage,
            }

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:

            return Response(
                {
                    "detail": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# --------------------------------------------------------------------
# 2. REIMBURSEMENT COUNTS
# --------------------------------------------------------------------
from django.db.models import Count, Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

class ReimbursementCountsView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = request.user.company

            if not company:
                return error(
                    "Company not assigned",
                    status.HTTP_404_NOT_FOUND
                )

            qs = Reimbursement.objects.filter(
                employee__department__company=company
            )

            total_requests = qs.count()

            pending_count = qs.filter(
                status="On Hold"
            ).count()

            verification_count = qs.filter(
                status="In Verification"
            ).count()

            approved_qs = qs.filter(
                status="Approve"
            )

            approved_count = approved_qs.count()

            rejected_count = qs.filter(
                status="Reject"
            ).count()

            # Total approved reimbursement amount
            approved_amount = approved_qs.aggregate(
                total=Sum("amount")
            )["total"] or 0

            # Percentages
            pending_percentage = (
                round((pending_count / total_requests) * 100, 2)
                if total_requests else 0
            )

            verification_percentage = (
                round((verification_count / total_requests) * 100, 2)
                if total_requests else 0
            )

            approved_percentage = (
                round((approved_count / total_requests) * 100, 2)
                if total_requests else 0
            )

            rejected_percentage = (
                round((rejected_count / total_requests) * 100, 2)
                if total_requests else 0
            )

            return Response({
                "total_requests": total_requests,

                "pending_count": pending_count,
                "pending_percentage": pending_percentage,

                "verification_count": verification_count,
                "verification_percentage": verification_percentage,

                "approved_count": approved_count,
                "approved_percentage": approved_percentage,

                "rejected_count": rejected_count,
                "rejected_percentage": rejected_percentage,

                "approved_amount": approved_amount,
            })

        except Exception as e:
            return error(
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# --------------------------------------------------------------------
# 3. REIMBURSEMENT MONTH-WISE AMOUNT
# --------------------------------------------------------------------
class ReimbursementMonthWiseAmountView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = request.user.company
            if not company:
                return error("Company not assigned", status.HTTP_404_NOT_FOUND)

            qs = (
                Reimbursement.objects.filter(
                    employee__department__company=company,
                    status="Approve"
                )
                .annotate(month=TruncMonth("created_at"))
                .values("month")
                .annotate(total_amount=Sum("amount"))
                .order_by("month")
            )

            data = {
                item["month"].strftime("%Y-%m"): float(item["total_amount"] or 0)
                for item in qs
            }

            return Response(data)

        except Exception as e:
            return error(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------------------------------------------------
# 4. DEPARTMENT SUMMARY
# --------------------------------------------------------------------
class DepartmentDashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = request.user.company
            if not company:
                return error("Company not assigned", status.HTTP_404_NOT_FOUND)

            total_departments = Department.objects.filter(company=company).count()

            recent_qs = Department.objects.filter(company=company).order_by("-created_at")[:4]

            recent_departments = [
                {
                    "id": d.id,
                    "name": d.name,
                    "created_at": d.created_at.date()
                }
                for d in recent_qs
            ]

            return Response({
                "total_departments": total_departments,
                "recent_departments": recent_departments
            })

        except Exception as e:
            return error(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------------------------------------------------
# 5. RECENT EMPLOYEES
# --------------------------------------------------------------------
class RecentEmployeesView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = request.user.company
            if not company:
                return error("Company not assigned", status.HTTP_404_NOT_FOUND)

            qs = Employee_db.objects.filter(
                department__company=company,is_deleted=False
            ).order_by("-created_at")[:5]

            employees = [
                {
                    "id": e.id,
                    "name": e.name,
                    "employee_id": e.employee_id,
                    "department": e.department.name if e.department else None,
                    "profile_pic": request.build_absolute_uri(e.profile_pic.url)
                    if e.profile_pic else None,
                    "added_date": e.created_at.date(),
                }
                for e in qs
            ]

            return Response({"recent_employees": employees})

        except Exception as e:
            return error(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------------------------------------------------
# 6. CONTRACT EXPIRY WITHIN 30 DAYS
# --------------------------------------------------------------------


class ContractExpiry30DaysView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        company = getattr(request.user, "company", None)

        if not company:
            return Response(
                {"error": "Company not associated with user"},
                status=status.HTTP_400_BAD_REQUEST
            )

        today = timezone.now().date()
        next_30 = today + timedelta(days=30)

        qs = Employee_db.objects.filter(is_deleted=False,
            contract_expiry_date__isnull=False,
            contract_expiry_date__range=(today, next_30),
            department__company=company   
        ).order_by("contract_expiry_date")

        serializer = ContractExpirySerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# --------------------------------------------------------------------
# 7. NOTIFICATIONS
# --------------------------------------------------------------------
def time_since(dt):
    now = timezone.now()
    diff = now - dt

    if diff.days == 0:
        sec = diff.seconds
        if sec < 60:
            return "just now"
        if sec < 3600:
            return f"{sec // 60} minutes ago"
        return f"{sec // 3600} hours ago"

    if diff.days == 1:
        return "1 day ago"

    return f"{diff.days} days ago"


class SimpleNotificationsAPI(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = request.user.company
            if not company:
                return error("Company not assigned", status.HTTP_404_NOT_FOUND)

            notifications = []

            # Leave Requests
            leaves = LeaveRequest.objects.filter(
                employee__department__company=company,
                status="pending"
            ).order_by("-created_at")[:10]

            for l in leaves:
                notifications.append({
                    "text": f"New leave request from {l.employee.department.name}",
                    "time": time_since(l.created_at)
                })

            # Reimbursements
            reimb = Reimbursement.objects.filter(
                employee__department__company=company,
                status="On Hold"
            ).order_by("-created_at")[:10]

            for r in reimb:
                notifications.append({
                    "text": f"New reimbursement request from {r.employee.department.name}",
                    "time": time_since(r.created_at)
                })

            return Response({"notifications": notifications[:10]})

        except Exception as e:
            return error(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------------------------------------------------
# 8. TODAY EMPLOYEE ATTENDANCE STATS
# --------------------------------------------------------------------
class TodayEmployeeStatsAPI(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            today = date.today()
            company = request.user.company

            if not company:
                return error(
                    "Company not assigned to user",
                    status.HTTP_404_NOT_FOUND
                )

            # -----------------------------------------
            # TOTAL ACTIVE EMPLOYEES
            # -----------------------------------------
            employees = Employee_db.objects.filter(
                department__company=company,
                is_deleted=False
            )

            total_employees = employees.count()

            # -----------------------------------------
            # CHECKED-IN / PRESENT TODAY
            # -----------------------------------------
            present_count = Attendance.objects.filter(
                date=today,
                employee__department__company=company,
                employee__is_deleted=False
            ).values(
                "employee"
            ).distinct().count()

            # -----------------------------------------
            # APPROVED LEAVE TODAY
            # -----------------------------------------
            on_leave_count = LeaveRequest.objects.filter(
                status="approved",
                from_date__lte=today,
                to_date__gte=today,
                employee__department__company=company,
                employee__is_deleted=False
            ).values(
                "employee"
            ).distinct().count()

            # -----------------------------------------
            # PERCENTAGES
            # -----------------------------------------
            present_percentage = (
                round((present_count / total_employees) * 100, 2)
                if total_employees else 0
            )

            leave_percentage = (
                round((on_leave_count / total_employees) * 100, 2)
                if total_employees else 0
            )

            return Response({
                "total_employees": total_employees,
                "present_today_count": present_count,
                "on_leave_today_count": on_leave_count,
                "present_percentage": present_percentage,
                "leave_percentage": leave_percentage,
            })

        except Exception as e:
            return error(
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# --------------------------------------------------------------------
# 9. HOLIDAY SUMMARY
# --------------------------------------------------------------------
# class HolidaySummaryAPI(APIView):
#     permission_classes = [IsAuthenticated, IsHRAdmin]

#     def get(self, request):
#         try:
#             today = date.today()
#             company = request.user.company

#             holidays = PublicHoliday.objects.filter(company=company).order_by("date")

#             holiday_data = [
#                 {
#                     "id": h.id,
#                     "date": h.date,
#                     "day": h.day,
#                     "description": h.description,
#                     "holiday_type": h.holiday_type,
#                 }
#                 for h in holidays
#             ]

#             upcoming = PublicHoliday.objects.filter(
#                 company=company,
#                 date__gte=today
#             ).exclude(
#                 holiday_type__in=["off_day", "weekend"]
#             ).order_by("date")[:5]

#             upcoming_data = [
#                 {
#                     "date": h.date,
#                     "description": h.description,
#                     "holiday_type": h.holiday_type,
#                     "days_left": (h.date - today).days
#                 }
#                 for h in upcoming
#             ]

#             return Response({
#                 "upcoming_holidays": upcoming_data,
#                 "all_holidays": {
#                     "count": holidays.count(),
#                     "list": holiday_data
#                 }
#             })

#         except Exception as e:
#             return error(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)
from datetime import date
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from employee.models import Employee_db
from holidays.models import PublicHoliday


class UpcomingHolidayBirthdayAPI(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = request.user.company

            if not company:
                return error(
                    "Company not assigned",
                    status.HTTP_404_NOT_FOUND
                )

            today = date.today()

            # =====================================================
            # UPCOMING HOLIDAYS
            # =====================================================

            upcoming_holidays = PublicHoliday.objects.filter(
                company=company,
                date__gte=today
            ).exclude(
                holiday_type__in=["off_day", "weekend"]
            ).order_by("date")[:5]

            holiday_data = []

            for holiday in upcoming_holidays:
                holiday_data.append({
                    "id": holiday.id,
                    "date": holiday.date,
                    "day": holiday.day,
                    "description": holiday.description,
                    "holiday_type": holiday.holiday_type,
                    "days_left": (
                        holiday.date - today
                    ).days
                })

            # =====================================================
            # UPCOMING EMPLOYEE BIRTHDAYS
            # =====================================================

            employees = Employee_db.objects.filter(
                department__company=company,
                is_deleted=False,
                dob__isnull=False
            )

            birthday_data = []

            for employee in employees:

                # Birthday in current year
                birthday = employee.dob.replace(
                    year=today.year
                )

                # If birthday already passed, use next year
                if birthday < today:
                    birthday = birthday.replace(
                        year=today.year + 1
                    )

                days_left = (
                    birthday - today
                ).days

                birthday_data.append({
                    "employee_id": employee.employee_id,
                    "employee_name": employee.name,
                    "date_of_birth": employee.dob,
                    "birthday": birthday,
                    "days_left": days_left,
                    "department": (
                        employee.department.name
                        if employee.department
                        else None
                    ),
                    "profile_pic": (
                        request.build_absolute_uri(
                            employee.profile_pic.url
                        )
                        if employee.profile_pic
                        else None
                    )
                })

            # Sort by nearest birthday
            birthday_data.sort(
                key=lambda x: x["days_left"]
            )

            # Only next 5 birthdays
            birthday_data = birthday_data[:5]

            # =====================================================
            # RESPONSE
            # =====================================================

            return Response({
                "upcoming_holidays": holiday_data,
                "upcoming_birthdays": birthday_data
            })

        except Exception as e:
            return error(
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class HolidayListAPI(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = request.user.company

            if not company:
                return error(
                    "Company not assigned",
                    status.HTTP_404_NOT_FOUND
                )

            holidays = PublicHoliday.objects.filter(
                company=company
            )

            # =====================================================
            # YEAR FILTER
            # =====================================================

            year = request.query_params.get("year")

            if year:
                try:
                    year = int(year)
                except ValueError:
                    return error(
                        "Invalid year",
                        status.HTTP_400_BAD_REQUEST
                    )

                holidays = holidays.filter(
                    date__year=year
                )

            # =====================================================
            # MONTH FILTER
            # =====================================================

            month = request.query_params.get("month")

            if month:
                try:
                    month = int(month)

                    if month < 1 or month > 12:
                        raise ValueError

                except ValueError:
                    return error(
                        "Invalid month",
                        status.HTTP_400_BAD_REQUEST
                    )

                holidays = holidays.filter(
                    date__month=month
                )

            # =====================================================
            # ORDER
            # =====================================================

            holidays = holidays.order_by("date")

            # =====================================================
            # RESPONSE
            # =====================================================

            holiday_data = []

            for holiday in holidays:
                holiday_data.append({
                    "id": holiday.id,
                    "date": holiday.date,
                    "day": holiday.day,
                    "description": holiday.description,
                    "holiday_type": holiday.holiday_type
                })

            return Response({
                "count": len(holiday_data),
                "results": holiday_data
            })

        except Exception as e:
            return error(
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# --------------------------------------------------------------------
# 10. PROJECT EMPLOYEE COUNT (ON-SITE / VARIANT / BENCH)
# --------------------------------------------------------------------
class ProjectCountView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = request.user.company

            if not company:
                return error(
                    "Company not assigned to user",
                    status.HTTP_404_NOT_FOUND
                )

            projects = Project.objects.filter(company=company)

            counts = {
                "on_site": projects.filter(
                    punch_type="on_site"
                ).count(),

                "variant": projects.filter(
                    punch_type="variant"
                ).count(),

                "bench": projects.filter(
                    punch_type="bench"
                ).count(),
            }

            counts["total"] = (
                counts["on_site"]
                + counts["variant"]
                + counts["bench"]
            )

            return Response(counts)

        except Exception as e:
            return error(
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        


from datetime import date, datetime, time, timedelta

from django.db.models import Min
from attendance.models import AttendanceSession
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status


class WeeklyAttendanceStatsView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    # Employees punching after this time are considered late
    LATE_TIME = time(9, 0)

    def get(self, request):
        try:
            company = request.user.company

            if not company:
                return error(
                    "Company not assigned",
                    status.HTTP_404_NOT_FOUND
                )

            today = date.today()

            # Monday = 0, Sunday = 6
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)

            # Active employees of this company
            employees = Employee_db.objects.filter(
                department__company=company,
                is_deleted=False
            )

            total_employees = employees.count()

            data = []

            for i in range(7):

                current_date = week_start + timedelta(days=i)

                # Don't calculate attendance for future dates
                if current_date > today:
                    data.append({
                        "date": current_date,
                        "day": current_date.strftime("%A"),
                        "present": 0,
                        "late": 0,
                        "absent": 0
                    })
                    continue

                # -------------------------------------------------
                # APPROVED LEAVE
                # -------------------------------------------------

                leave_employee_ids = set(
                    LeaveRequest.objects.filter(
                        employee__in=employees,
                        status="approved",
                        from_date__lte=current_date,
                        to_date__gte=current_date
                    ).values_list(
                        "employee_id",
                        flat=True
                    )
                )

                # -------------------------------------------------
                # ATTENDANCE FOR THE DAY
                # -------------------------------------------------

                attendance_qs = Attendance.objects.filter(
                    employee__in=employees,
                    date=current_date
                )

                attendance_employee_ids = set(
                    attendance_qs.values_list(
                        "employee_id",
                        flat=True
                    )
                )

                # -------------------------------------------------
                # PRESENT
                # -------------------------------------------------

                present_count = len(attendance_employee_ids)

                # -------------------------------------------------
                # LATE
                # -------------------------------------------------

                late_count = 0

                sessions = AttendanceSession.objects.filter(
                    attendance__in=attendance_qs,
                    time_in__isnull=False
                ).values(
                    "attendance__employee_id"
                ).annotate(
                    first_time_in=Min("time_in")
                )

                for session in sessions:

                    employee_id = session["attendance__employee_id"]
                    first_time_in = session["first_time_in"]

                    if not first_time_in:
                        continue

                    # Convert datetime to local time
                    punch_time = first_time_in.time()

                    if punch_time > self.LATE_TIME:
                        late_count += 1

                # -------------------------------------------------
                # ABSENT
                # -------------------------------------------------

                # Employees who didn't punch and aren't on approved
                # leave are absent.
                absent_count = max(
                    total_employees
                    - present_count
                    - len(leave_employee_ids),
                    0
                )

                data.append({
                    "date": current_date,
                    "day": current_date.strftime("%A"),
                    "present": present_count,
                    "late": late_count,
                    "absent": absent_count
                })

            return Response({
                "week_start": week_start,
                "week_end": week_end,
                "total_employees": total_employees,
                "data": data
            })

        except Exception as e:
            return error(
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.db import models
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from employee.models import Employee_db
from payroll.models import EmployeePayrollRecord

class MonthlyPayrollSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = request.user.company

            if not company:
                return error(
                    "Company not assigned",
                    status.HTTP_404_NOT_FOUND
                )

            # ---------------------------------------------
            # YEAR FILTER
            # ---------------------------------------------
            year = request.query_params.get("year")

            if not year:
                year = date.today().year
            else:
                try:
                    year = int(year)
                except ValueError:
                    return error(
                        "Invalid year",
                        status.HTTP_400_BAD_REQUEST
                    )

            # ---------------------------------------------
            # COMPANY PAYROLL
            # ---------------------------------------------
            payroll_qs = EmployeePayrollRecord.objects.filter(
                employee__department__company=company,
                employee__is_deleted=False,
                year=year,
                status="Paid"
            )

            # ---------------------------------------------
            # MONTH-WISE DATA
            # ---------------------------------------------
            monthly_data = []

            for month in range(1, 13):

                month_qs = payroll_qs.filter(
                    month=month
                )

                totals = month_qs.aggregate(
                    paid_salary=Coalesce(
                        Sum("basic_salary"),
                        Decimal("0")
                    ),
                    salary_increment=Coalesce(
                        Sum("salary_increment"),
                        Decimal("0")
                    ),
                    incentive=Coalesce(
                        Sum("incentive_amount"),
                        Decimal("0")
                    ),
                    deduction=Coalesce(
                        Sum("deduction_amount"),
                        Decimal("0")
                    )
                )

                monthly_data.append({
                    "month": month,
                    "month_name": date(
                        year,
                        month,
                        1
                    ).strftime("%B"),

                    "paid_salary": float(
                        totals["paid_salary"]
                    ),

                    "salary_increment": float(
                        totals["salary_increment"]
                    ),

                    "incentive": float(
                        totals["incentive"]
                    ),

                    "deduction": float(
                        totals["deduction"]
                    )
                })

            # ---------------------------------------------
            # YEAR TOTAL
            # ---------------------------------------------
            yearly_totals = payroll_qs.aggregate(
                paid_salary=Coalesce(
                    Sum("basic_salary"),
                    Decimal("0")
                ),
                salary_increment=Coalesce(
                    Sum("salary_increment"),
                    Decimal("0")
                ),
                incentive=Coalesce(
                    Sum("incentive_amount"),
                    Decimal("0")
                ),
                deduction=Coalesce(
                    Sum("deduction_amount"),
                    Decimal("0")
                )
            )

            return Response({
                "year": year,

                "year_total": {
                    "paid_salary": float(
                        yearly_totals["paid_salary"]
                    ),

                    "salary_increment": float(
                        yearly_totals["salary_increment"]
                    ),

                    "incentive": float(
                        yearly_totals["incentive"]
                    ),

                    "deduction": float(
                        yearly_totals["deduction"]
                    )
                },

                "monthly_data": monthly_data
            })

        except Exception as e:
            return error(
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )