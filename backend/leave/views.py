from rest_framework import generics, status, filters,serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta, date
import calendar

from .models import LeaveRequest,EmployeeLeaveBalance
from .serializers import LeaveRequestSerializer
from employee.models import Employee_db
from user.permissions import IsEmployee, IsHRAdmin
from shared.pagination import CustomPagination
from holidays.models import PublicHoliday
from django.core.mail import EmailMessage
from rest_framework.views import APIView
from rest_framework import status
def error(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({"error": message}, status=code)



#  Employee: List + Create Leave Requests
# Employee: List + Create Leave Requests



from decimal import Decimal
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.core.mail import EmailMessage

class LeaveRequestCreateListView(generics.ListCreateAPIView):

    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated, IsEmployee]
    filter_backends = [filters.SearchFilter]
    search_fields = ['employee__name', 'employee__employee_id', 'employee__employee_code']
    pagination_class = CustomPagination

    def get_queryset(self):
        return LeaveRequest.objects.filter(
            employee__user=self.request.user
        ).order_by("-created_at")

    def list(self, request, *args, **kwargs):

        try:
            queryset = self.get_queryset()

            pending_count = queryset.filter(
                status='pending'
            ).count()

            lop_count = queryset.filter(
                leave_type='earned'
            ).count()

            page = self.paginate_queryset(queryset)

            serializer = self.get_serializer(
                page,
                many=True
            )

            return self.get_paginated_response({
                'leaves': serializer.data,
                'pending_leave_count': pending_count,
                'loss_of_pay_count': lop_count,
            })

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=500
            )

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        try:
            employee = Employee_db.objects.get(
                user=request.user
            )

        except Employee_db.DoesNotExist:
            return Response(
                {"error": "Employee not found."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from_date = serializer.validated_data.get(
            "from_date"
        )

        to_date = serializer.validated_data.get(
            "to_date"
        )

        # ==========================================
        # OVERLAPPING CHECK
        # ==========================================
        overlapping = LeaveRequest.objects.filter(
            employee=employee
        ).filter(
            Q(from_date__lte=to_date)
            &
            Q(to_date__gte=from_date)
        )

        if overlapping.exists():

            return Response(
                {
                    "detail":
                    "You already applied leave for one or more selected dates."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ==========================================
        # SAVE LEAVE
        # ==========================================
        leave = serializer.save(
            employee=employee
        )

        # ==========================================
        # LEAVE BALANCE WARNING
        # ==========================================
        warning_message = None

        leave_days = Decimal(
            str(leave.calculate_leave_days())
        )

        balance = EmployeeLeaveBalance.objects.filter(
            employee=employee,
            leave_type=leave.leave_type
        ).first()

        if balance:

            if leave_days > balance.remaining_leave:

                shortage = (
                    leave_days -
                    balance.remaining_leave
                )

                warning_message = (
                    f"You have only "
                    f"{balance.remaining_leave} "
                    f"{leave.leave_type} leave(s) remaining. "
                    f"Requested {leave_days} day(s). "
                    f"Excess {shortage} day(s) may be treated as Loss Of Pay."
                )

        # ==========================================
        # SEND EMAIL
        # ==========================================
        try:

            subject = (
                f"Leave Request from "
                f"{employee.name}"
            )

            message = (
                f"Employee Name: {employee.name}\n"
                f"Employee ID: {employee.employee_id}\n"
                f"Department: "
                f"{employee.department.name if employee.department else 'N/A'}\n\n"
                f"Leave Type: {leave.leave_type}\n"
                f"From: {leave.from_date}\n"
                f"To: {leave.to_date}\n"
                f"Reason: {leave.reason}\n"
                f"Status: {leave.status}"
            )

            company = employee.department.company

            hr_emails = list(
                Employee_db.objects.filter(
                    department__company=company,is_deleted=False,
                    role="hr"
                )
                .exclude(email__isnull=True)
                .exclude(email__exact="")
                .values_list(
                    "email",
                    flat=True
                )
            )

            recipient_list = []

            if leave.to_email:
                recipient_list.append(
                    leave.to_email
                )

            recipient_list.extend(
                hr_emails
            )

            recipient_list = list(
                set(recipient_list)
            )

            cc_list = []

            if leave.cc_email:
                cc_list.append(
                    leave.cc_email
                )

            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=employee.email,
                to=recipient_list,
                cc=cc_list,
            )

            email.send(
                fail_silently=True
            )

        except Exception as email_error:
            print(
                "Email sending failed:",
                str(email_error)
            )

        # ==========================================
        # RESPONSE
        # ==========================================
        return Response(
            {
                "message":
                "Leave request submitted successfully.",
                "warning":
                warning_message,
                "data":
                LeaveRequestSerializer(
                    leave
                ).data
            },
            status=status.HTTP_201_CREATED
        )

#  Employee: Cancel Pending Leave
class LeaveRequestCancelView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsEmployee]

    def get_queryset(self):
        return LeaveRequest.objects.filter(employee__user=self.request.user, status='pending')

    def delete(self, request, *args, **kwargs):
        try:
            leave = self.get_queryset().get(pk=kwargs['pk'])
            leave.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except LeaveRequest.DoesNotExist:
            return Response({"detail": "Pending leave not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


#  HR: Leave List View



class LeaveRequestAdminListView(generics.ListAPIView):
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
    'employee__name',
    'employee__employee_id',
    'employee__employee_code',
]
    ordering_fields = ['from_date', 'to_date']
    pagination_class = CustomPagination

    def get_queryset(self):
        try:
            user = self.request.user
            company = user.company

            if not company:
                return LeaveRequest.objects.none()

            queryset = LeaveRequest.objects.filter(
                employee__department__company=company
            )

            # Department filter
            dept_id = self.request.query_params.get('department_id')
            if dept_id:
                queryset = queryset.filter(
                    employee__department_id=dept_id
                )

            # Status filter
            status = self.request.query_params.get('status')
            if status:
                queryset = queryset.filter(status=status)

            # Year filter
            year = self.request.query_params.get('year')
            if year:
                queryset = queryset.filter(
                    from_date__year=year
                )

            # Month filter
            month = self.request.query_params.get('month')
            if month:
                queryset = queryset.filter(
                    from_date__month=month
                )

            return queryset.order_by('-created_at')

        except Exception:
            return LeaveRequest.objects.none()


# HR: Leave Detail (Approve / Reject)
class LeaveRequestAdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    lookup_field = 'pk'

    def update(self, request, *args, **kwargs):
        try:
            response = super().update(request, *args, **kwargs)
            instance = self.get_object()
            emp = instance.employee

            response.data["employee_leave_summary"] = {
                "employee_id": emp.id,
                "employee_name": emp.name,
                "total_leave": emp.total_leave,
                "paid_leave": emp.paid_leave,
            }
            return response
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# HR: Employees on Leave (today) by Department
class EmployeesOnLeaveTodayByDepartmentView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request, department_id):

        try:
            today = timezone.now().date()
            leaves = LeaveRequest.objects.filter(
                status='approved',
                from_date__lte=today,
                to_date__gte=today,
                employee__department_id=department_id
            )
            employees = Employee_db.objects.filter(is_deleted=False,id__in=leaves.values_list('employee_id', flat=True))
            from employee.serializers import EmployeeSerializer
            serializer = EmployeeSerializer(employees, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# Department Employees on a Given Date
class DepartmentEmployeesOnLeaveView(APIView):
    def get(self, request, employee_id):
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({"error": "Please provide ?date=YYYY-MM-DD"}, status=400)

        leave_date = parse_date(date_str)
        if not leave_date:
            return Response({"error": "Invalid date format"}, status=400)

        try:
            emp = Employee_db.objects.get(id=employee_id,is_deleted=False)
        except Employee_db.DoesNotExist:
            return Response({"error": "Employee not found"}, status=404)

        if not emp.department:
            return Response({"error": "Employee has no department assigned"}, status=400)
        
        try:

            dept = emp.department
            dept_emps = Employee_db.objects.filter(department=dept,is_deleted=False)

            leaves = LeaveRequest.objects.filter(
                employee__in=dept_emps,
                status='approved',
                from_date__lte=leave_date,
                to_date__gte=leave_date
            ).select_related('employee')

            data = {
                "department": {"id": dept.id, "name": dept.name},
                "on_leave": [
                    {
                        "id": l.id,
                        "employee_name": l.employee.name,
                        "email": l.employee.email,
                        "phone": l.employee.phno,
                        "leave_type": l.leave_type,
                        "from_date": l.from_date,
                        "to_date": l.to_date,
                        "from_date_type":l.from_date_type,
                        "to_date_type":l.to_date_type,
                        "paid_leave_count": l.employee.paid_leave,
                        "pending_leave": l.employee.total_leave,
                    } for l in leaves
                ]
            }
            return Response(data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# Employee: Leave by Status (pending / approved / rejected)
class LeaveByStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_param = request.query_params.get('status')
        if not status_param:
            return Response({"error": "Leave status is required (?status=pending)"}, status=400)

        try:
            emp = Employee_db.objects.get(user=request.user)
        except Employee_db.DoesNotExist:
            return Response({"error": "Employee not found."}, status=404)
        

        try:

            leaves = LeaveRequest.objects.filter(employee=emp, status=status_param).order_by('created_at')
            serializer = LeaveRequestSerializer(leaves, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

from employee.models import Employee_db
from employee.serializers import EmpBankPaymentSerializer
from rest_framework import serializers
from datetime import date, timedelta,datetime
from payroll.models import EmployeePayrollRecord
from attendance.models import Attendance
from leave.models import LeaveRequest
from holidays.models import PublicHoliday
import calendar
class LeaveSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            emp = Employee_db.objects.get(user=request.user)
        except Employee_db.DoesNotExist:
            return Response({"error": "Employee not found."}, status=404)
        
        try:

            today = date.today()
            year, month = today.year, today.month
            first_day = date(year, month, 1)
            last_day = date(year, month, calendar.monthrange(year, month)[1])

            # --- Identify Holidays & Company Off Days ---
            holidays_qs = PublicHoliday.objects.filter(
                date__range=(first_day, last_day),
                company=emp.department.company
            )
            holidays = set()
            company_off_days = set()
            for h in holidays_qs:
                if h.holiday_type == 'company_off_day':
                    company_off_days.add(h.date.weekday())
                else:
                    holidays.add(h.date)

            # --- Working Days ---
            working_days = sum(
                1 for d in range((last_day - first_day).days + 1)
                if (first_day + timedelta(days=d)).weekday() not in company_off_days
                and (first_day + timedelta(days=d)) not in holidays
            )

            # --- Attendance ---
            attendances = Attendance.objects.filter(employee=emp, date__range=(first_day, last_day))
            full_days = half_days = 0
            attendance_dates = set()
            for att in attendances:
                hours = float(att.total_hours or 0)
                attendance_dates.add(att.date)
                if hours >= 8:
                    full_days += 1
                elif 4 <= hours < 8:
                    half_days += 1

            days_present = full_days + 0.5 * half_days

            # --- Approved Leave Days ---
            leave_requests = LeaveRequest.objects.filter(
                employee=emp, status='approved',
                from_date__lte=last_day, to_date__gte=first_day
            )
            approved_leave_dates = set()
            for leave in leave_requests:
                start = max(leave.from_date, first_day)
                end = min(leave.to_date, last_day)
                if isinstance(start, datetime):
                    start = start.date()
                if isinstance(end, datetime):
                    end = end.date()
                if start <= end:
                    for n in range((end - start).days + 1):
                        approved_leave_dates.add(start + timedelta(days=n))

            # --- Unswiped Days ---
            all_days = [(first_day + timedelta(days=i)) for i in range((last_day - first_day).days + 1)]
            unswiped_valid_days = [
                d for d in all_days
                if d not in attendance_dates
                and d not in holidays
                and d.weekday() not in company_off_days
                and d not in approved_leave_dates
            ]
            unswiped_days = float(len(unswiped_valid_days))

            # --- Paid Leave ---
            paid_leave_balance = float(emp.paid_leave or 0.0)
            total_leave = float(emp.total_leave or 0.0)

            # --- LOP Calculation (same as payroll serializer) ---
            lop_days = max(unswiped_days - paid_leave_balance, 0)

            # --- Salary-based LOP Amount ---
            monthly_salary = float(getattr(emp, "salary", 0) or 0)
            per_day_salary = monthly_salary / working_days if working_days > 0 else 0
            lop_amount = round(per_day_salary * lop_days, 2)

            # --- Prepare Response ---
            return Response({
                "employee_name": emp.name,
                "profile_pic": emp.profile_pic.url if emp.profile_pic else None,
                "working_days": working_days,
                "days_present": days_present,
                "unswiped_days": unswiped_days,
                "paid_leave_used": paid_leave_balance,
                "total_leave": total_leave,
                "lop_days": lop_days,
                "lop_amount": lop_amount,
                "monthly_salary": monthly_salary,
            })
        
        except Exception as e:  
            return Response({"error": str(e)}, status=500)



# Employee: Retrieve/Update/Delete own leave
class LeaveRequestEmpDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated, IsEmployee]
    lookup_field = 'pk'


from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class LeaveStatusCountsView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = getattr(request.user, "company", None)

            if not company:
                return error(
                    "Company not assigned to user",
                    status.HTTP_404_NOT_FOUND
                )

            leave_qs = LeaveRequest.objects.filter(
                employee__department__company=company,
                employee__is_deleted=False
            )

            counts = leave_qs.values("status").annotate(
                count=Count("id")
            )

            status_counts = {
                "pending": 0,
                "approved": 0,
                "rejected": 0,
            }

            for item in counts:
                status_counts[item["status"]] = item["count"]

            total = sum(status_counts.values())

            return Response({
                "total": total,
                "pending": status_counts["pending"],
                "approved": status_counts["approved"],
                "rejected": status_counts["rejected"],
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return error(
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )