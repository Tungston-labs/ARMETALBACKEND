import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.mail import EmailMessage
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.models import Attendance
from employee.models import Employee_db
from holidays.models import PublicHoliday
from shared.pagination import CustomPagination
from user.permissions import IsEmployee, IsHRAdmin

from .models import EmployeeLeaveBalance, LeaveRequest
from .serializers import LeaveRequestSerializer, LeaveStatusUpdateSerializer


def error(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({"error": message}, status=code)


# Employee: List + Create Leave Requests
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

            pending_count = queryset.filter(status='pending').count()
            lop_count = queryset.filter(leave_type='earned').count()

            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page, many=True)

            return self.get_paginated_response({
                'leaves': serializer.data,
                'pending_leave_count': pending_count,
                'loss_of_pay_count': lop_count,
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            employee = Employee_db.objects.get(user=request.user)
        except Employee_db.DoesNotExist:
            return Response(
                {"error": "Employee not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from_date = serializer.validated_data.get("from_date")
        to_date = serializer.validated_data.get("to_date")

        # ---------- overlapping check ----------
        overlapping = LeaveRequest.objects.filter(
            employee=employee,
            from_date__lte=to_date,
            to_date__gte=from_date,
        ).exclude(status="rejected")

        if overlapping.exists():
            return Response(
                {"detail": "You already applied leave for one or more selected dates."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------- save ----------
        leave = serializer.save(employee=employee)

        # ---------- balance warning ----------
        warning_message = None
        leave_days = Decimal(str(leave.calculate_leave_days()))

        balance = EmployeeLeaveBalance.objects.filter(
            employee=employee,
            leave_type=leave.leave_type,
        ).first()

        if balance and leave_days > balance.remaining_leave:
            shortage = leave_days - balance.remaining_leave
            warning_message = (
                f"You have only {balance.remaining_leave} "
                f"{leave.leave_type} leave(s) remaining. "
                f"Requested {leave_days} day(s). "
                f"Excess {shortage} day(s) may be treated as Loss Of Pay."
            )

        # ---------- email ----------
        try:
            subject = f"Leave Request from {employee.name}"
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
                    department__company=company,
                    is_deleted=False,
                    role="hr",
                )
                .exclude(email__isnull=True)
                .exclude(email__exact="")
                .values_list("email", flat=True)
            )

            recipient_list = []
            if leave.to_email:
                recipient_list.append(leave.to_email)
            recipient_list.extend(hr_emails)
            recipient_list = list(set(recipient_list))

            cc_list = [leave.cc_email] if leave.cc_email else []

            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=employee.email,
                to=recipient_list,
                cc=cc_list,
            )
            email.send(fail_silently=True)

        except Exception as email_error:
            print("Email sending failed:", str(email_error))

        return Response(
            {
                "message": "Leave request submitted successfully.",
                "warning": warning_message,
                "data": LeaveRequestSerializer(leave).data,
            },
            status=status.HTTP_201_CREATED,
        )


# Employee: Cancel Pending Leave
class LeaveRequestCancelView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsEmployee]

    def get_queryset(self):
        return LeaveRequest.objects.filter(
            employee__user=self.request.user, status='pending'
        )

    def delete(self, request, *args, **kwargs):
        try:
            leave = self.get_queryset().get(pk=kwargs['pk'])
            leave.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except LeaveRequest.DoesNotExist:
            return Response(
                {"detail": "Pending leave not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# HR: Leave List View
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
            company = self.request.user.company

            if not company:
                return LeaveRequest.objects.none()

            queryset = LeaveRequest.objects.filter(
                employee__department__company=company
            )

            params = self.request.query_params

            dept_id = params.get('department_id')
            if dept_id:
                queryset = queryset.filter(employee__department_id=dept_id)

            status_param = params.get('status')
            if status_param:
                queryset = queryset.filter(status=status_param)

            year = params.get('year')
            if year:
                queryset = queryset.filter(from_date__year=year)

            month = params.get('month')
            if month:
                queryset = queryset.filter(from_date__month=month)

            return queryset.order_by('-created_at')

        except Exception:
            return LeaveRequest.objects.none()


# HR: Leave Detail (Approve / Reject)
class LeaveRequestAdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]
    lookup_field = 'pk'

    def get_queryset(self):
        company = self.request.user.company
        if not company:
            return LeaveRequest.objects.none()
        return LeaveRequest.objects.filter(employee__department__company=company)

    def get_serializer_class(self):
        # PATCH/PUT only touches `status`; GET uses the full serializer
        if self.request.method in ("PUT", "PATCH"):
            return LeaveStatusUpdateSerializer
        return LeaveRequestSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()  # LeaveRequest.save() adjusts the leave balance

        instance.refresh_from_db()
        emp = instance.employee

        # Return the full leave object so the frontend reducer can match by id
        data = LeaveRequestSerializer(instance, context={"request": request}).data
        data["employee_leave_summary"] = {
            "employee_id": emp.id,
            "employee_name": emp.name,
            "total_leave": emp.total_leave,
            "paid_leave": emp.paid_leave,
        }
        return Response(data)


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
                employee__department_id=department_id,
                employee__department__company=request.user.company,
            )
            employees = Employee_db.objects.filter(
                is_deleted=False,
                id__in=leaves.values_list('employee_id', flat=True),
            )
            from employee.serializers import EmployeeSerializer
            serializer = EmployeeSerializer(employees, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# Department Employees on a Given Date
class DepartmentEmployeesOnLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({"error": "Please provide ?date=YYYY-MM-DD"}, status=400)

        leave_date = parse_date(date_str)
        if not leave_date:
            return Response({"error": "Invalid date format"}, status=400)

        try:
            employee_qs = Employee_db.objects.filter(id=employee_id, is_deleted=False)
            if request.user.is_hr_admin or request.user.is_hr:
                if not request.user.company:
                    return Response({"error": "Company not assigned to user"}, status=404)
                employee_qs = employee_qs.filter(department__company=request.user.company)
            else:
                employee_qs = employee_qs.filter(user=request.user)
            emp = employee_qs.get()
        except Employee_db.DoesNotExist:
            return Response({"error": "Employee not found"}, status=404)

        if not emp.department:
            return Response({"error": "Employee has no department assigned"}, status=400)

        try:
            dept = emp.department
            dept_emps = Employee_db.objects.filter(department=dept, is_deleted=False)

            leaves = LeaveRequest.objects.filter(
                employee__in=dept_emps,
                status='approved',
                from_date__lte=leave_date,
                to_date__gte=leave_date,
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
                        "from_date_type": l.from_date_type,
                        "to_date_type": l.to_date_type,
                        "paid_leave_count": l.employee.paid_leave,
                        "pending_leave": l.employee.total_leave,
                    }
                    for l in leaves
                ],
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
            return Response(
                {"error": "Leave status is required (?status=pending)"}, status=400
            )

        try:
            emp = Employee_db.objects.get(user=request.user)
        except Employee_db.DoesNotExist:
            return Response({"error": "Employee not found."}, status=404)

        try:
            leaves = LeaveRequest.objects.filter(
                employee=emp, status=status_param
            ).order_by('created_at')
            serializer = LeaveRequestSerializer(leaves, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


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

            # --- Holidays & company off days ---
            holidays_qs = PublicHoliday.objects.filter(
                date__range=(first_day, last_day),
                company=emp.department.company,
            )
            holidays = set()
            company_off_days = set()
            for h in holidays_qs:
                if h.holiday_type == 'company_off_day':
                    company_off_days.add(h.date.weekday())
                else:
                    holidays.add(h.date)

            # --- Working days ---
            working_days = sum(
                1
                for d in range((last_day - first_day).days + 1)
                if (first_day + timedelta(days=d)).weekday() not in company_off_days
                and (first_day + timedelta(days=d)) not in holidays
            )

            # --- Attendance ---
            attendances = Attendance.objects.filter(
                employee=emp, date__range=(first_day, last_day)
            )
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

            # --- Approved leave days ---
            leave_requests = LeaveRequest.objects.filter(
                employee=emp,
                status='approved',
                from_date__lte=last_day,
                to_date__gte=first_day,
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

            # --- Unswiped days ---
            all_days = [
                first_day + timedelta(days=i)
                for i in range((last_day - first_day).days + 1)
            ]
            unswiped_valid_days = [
                d
                for d in all_days
                if d not in attendance_dates
                and d not in holidays
                and d.weekday() not in company_off_days
                and d not in approved_leave_dates
            ]
            unswiped_days = float(len(unswiped_valid_days))

            # --- Paid leave ---
            paid_leave_balance = float(emp.paid_leave or 0.0)
            total_leave = float(emp.total_leave or 0.0)

            # --- LOP ---
            lop_days = max(unswiped_days - paid_leave_balance, 0)

            monthly_salary = float(getattr(emp, "salary", 0) or 0)
            per_day_salary = monthly_salary / working_days if working_days > 0 else 0
            lop_amount = round(per_day_salary * lop_days, 2)

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
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated, IsEmployee]
    lookup_field = 'pk'

    def get_queryset(self):
        # Employees can only touch their own leaves
        return LeaveRequest.objects.filter(employee__user=self.request.user)


class LeaveStatusCountsView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = getattr(request.user, "company", None)

            if not company:
                return error(
                    "Company not assigned to user",
                    status.HTTP_404_NOT_FOUND,
                )

            leave_qs = LeaveRequest.objects.filter(
                employee__department__company=company,
                employee__is_deleted=False,
            )

            counts = leave_qs.values("status").annotate(count=Count("id"))

            status_counts = {"pending": 0, "approved": 0, "rejected": 0}
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
            return error(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

        # HR: Who else in the same department is on leave during this request's dates?
class LeaveConflictsView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request, pk):
        company = getattr(request.user, "company", None)
        if not company:
            return error("Company not assigned to user", status.HTTP_404_NOT_FOUND)

        try:
            leave = LeaveRequest.objects.select_related(
                "employee", "employee__department"
            ).get(pk=pk, employee__department__company=company)
        except LeaveRequest.DoesNotExist:
            return error("Leave request not found", status.HTTP_404_NOT_FOUND)

        department = leave.employee.department
        if not department:
            return error("Employee has no department assigned")

        overlapping = (
            LeaveRequest.objects.filter(
                employee__department=department,
                employee__is_deleted=False,
                from_date__lte=leave.to_date,
                to_date__gte=leave.from_date,
                status__in=["approved", "pending"],
            )
            .exclude(pk=leave.pk)
            .exclude(employee=leave.employee)
            .select_related("employee")
        )

        def serialize(l):
            return {
                "leave_id": l.id,
                "employee_id": l.employee.id,
                "employee_name": l.employee.name,
                "leave_type": l.leave_type,
                "status": l.status,
                "from_date": l.from_date,
                "from_date_type": l.from_date_type,
                "to_date": l.to_date,
                "to_date_type": l.to_date_type,
                "leave_days": l.calculate_leave_days(),
            }

        approved = [serialize(l) for l in overlapping if l.status == "approved"]
        pending = [serialize(l) for l in overlapping if l.status == "pending"]

        return Response({
            "request": {
                "leave_id": leave.id,
                "employee_name": leave.employee.name,
                "department": department.name,
                "from_date": leave.from_date,
                "to_date": leave.to_date,
            },
            "has_conflict": bool(approved),
            "already_on_leave": approved,
            "also_requested": pending,
            "already_on_leave_count": len(approved),
            "also_requested_count": len(pending),
        })
