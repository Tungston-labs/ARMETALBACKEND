from rest_framework import generics, filters, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from hr.attendance.models import Attendance
from hr.employee.models import Employee_db
from hr.employee.serializers import EmployeeSerializer
from hr.leave.models import LeaveRequest
from hr.reimbursement.models import Reimbursement
from user.permissions import IsHRAdmin

from .models import Department
from .serializers import (
    DepartmentAttendanceSerializer,
    DepartmentMiniSerializer,
    DepartmentSerializer,
)


def dept_count(queryset, distinct_on=None):
    """Per-department count subquery. Returns 0 instead of NULL when empty."""
    qs = (
        queryset
        .filter(employee__department=OuterRef("pk"))
        .values("employee__department")
        .annotate(c=Count(distinct_on or "id", distinct=bool(distinct_on)))
        .values("c")[:1]
    )
    return Coalesce(Subquery(qs, output_field=IntegerField()), 0)


# -------------------- Mini list (admin)
class DepartmentMiniListView(generics.ListAPIView):
    serializer_class = DepartmentMiniSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        today = timezone.localdate()
        return (
            Department.objects
            .filter(company=self.request.user.company)
            .annotate(
                total_employee_count=Count(
                    "employees",
                    filter=Q(employees__is_deleted=False),
                    distinct=True,
                ),
                swiped_employee_count=dept_count(
                    Attendance.objects.filter(employee__is_deleted=False, date=today),
                    distinct_on="employee",
                ),
            )
        )


# -------------------- Create + list (admin)
class DepartmentCreateListView(generics.ListCreateAPIView):
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        today = timezone.localdate()
        return (
            Department.objects
            .filter(company=self.request.user.company)
            .annotate(
                employee_count=Count(
                    "employees",
                    filter=Q(employees__is_deleted=False),
                    distinct=True,
                ),
                attendance_employee_count=dept_count(
                    Attendance.objects.filter(employee__is_deleted=False, date=today),
                    distinct_on="employee",
                ),
                leave_request_count=dept_count(
                    LeaveRequest.objects.filter(employee__is_deleted=False, status="pending"),
                ),
                reimbursement_request_count=dept_count(
                    Reimbursement.objects.filter(employee__is_deleted=False, status="On Hold"),
                ),
                todays_leave_employee_count=dept_count(
                    LeaveRequest.objects.filter(
                        employee__is_deleted=False,
                        status="approved",
                        from_date__lte=today,
                        to_date__gte=today,
                    ),
                    distinct_on="employee",
                ),
            )
        )

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


# -------------------- Attendance per department (admin)
class DepartmentAttendanceListView(generics.ListAPIView):
    serializer_class = DepartmentAttendanceSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        today = timezone.localdate()
        return (
            Department.objects
            .filter(company=self.request.user.company)
            .annotate(
                attendance_employee_count=dept_count(
                    Attendance.objects.filter(employee__is_deleted=False, date=today),
                    distinct_on="employee",
                ),
            )
            .order_by("name")
        )


# -------------------- Retrieve + Update + Delete (admin)
class DepartmentRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        return Department.objects.filter(company=self.request.user.company)

    def perform_destroy(self, instance):
        # Deleting would set employee.department = NULL and hide them everywhere
        if Employee_db.objects.filter(department=instance).exists():
            raise ValidationError(
                {"detail": "Move or remove all employees (including archived ones) "
                           "before deleting this department."}
            )
        instance.delete()


# -------------------- Employees of a department (admin)
class EmployeeByDepartmentView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request, department_id):
        try:
            department = Department.objects.get(
                pk=department_id, company=request.user.company
            )
        except Department.DoesNotExist:
            return Response({"detail": "Department not found."}, status=404)

        employees = Employee_db.objects.filter(department=department, is_deleted=False)
        serializer = EmployeeSerializer(employees, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


# -------------------- Department head (employee app)
class MyDepartmentHeadEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = getattr(request.user, "employee_db", None)

        if not employee:
            return Response({"error": "Employee record not found"}, status=404)

        department = employee.department
        if not department or not department.department_head:
            return Response({"error": "Department head not assigned"}, status=404)

        head = department.department_head
        return Response(
            {
                "department": department.name,
                "head_name": head.name,
                "email": head.email,
            },
            status=200,
        )