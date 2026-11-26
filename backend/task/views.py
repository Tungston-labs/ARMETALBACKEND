from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, permissions, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from departments.models import Department
from employee.models import Employee_db
from user.permissions import IsEmployee, IsHRAdmin

from .models import DailyTask
from .serializers import DailyTaskSerializer, EmployeeMiniSerializer


def get_employee(user):
    """Return the Employee_db row linked to this user, or raise 403."""
    try:
        return Employee_db.objects.get(user=user, is_deleted=False)
    except Employee_db.DoesNotExist:
        raise PermissionDenied("No employee profile is linked to this account.")


class EmployeeDailyTaskCreateListView(generics.ListCreateAPIView):
    serializer_class = DailyTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee]

    def get_queryset(self):
        employee = get_employee(self.request.user)
        queryset = DailyTask.objects.filter(employee=employee)

        date_str = self.request.query_params.get('date')
        if date_str:
            date = parse_date(date_str)
            if date:
                queryset = queryset.filter(created_at__date=date)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        employee = get_employee(self.request.user)
        today = timezone.localdate()

        agg = DailyTask.objects.filter(
            employee=employee,
            created_at__date=today,
        ).aggregate(total=Sum("time_taken"))

        existing_hours = agg["total"] or Decimal("0")

        try:
            new_hours = Decimal(str(serializer.validated_data.get("time_taken", 0)))
        except (InvalidOperation, TypeError):
            raise serializers.ValidationError({"time_taken": ["Invalid time value"]})

        if existing_hours + new_hours > Decimal("24"):
            raise serializers.ValidationError({
                "time_taken": [
                    f"Daily total cannot exceed 24 hours. You already logged {existing_hours} hours today."
                ]
            })

        serializer.save(employee=employee)


# Employee: Retrieve/Update/Delete own task
class EmployeeDailyTaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DailyTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee]

    def get_queryset(self):
        return DailyTask.objects.filter(employee=get_employee(self.request.user))


# HR Admin: list all tasks
class HRDailyTaskListView(generics.ListAPIView):
    serializer_class = DailyTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        company = self.request.user.company
        if not company:
            return DailyTask.objects.none()
        return DailyTask.objects.filter(employee__department__company=company)


class EmployeeByDepartmentView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request, department_id):
        try:
            department = Department.objects.get(
                pk=department_id,
                company=request.user.company,
            )
        except Department.DoesNotExist:
            return Response({"detail": "Department not found."}, status=404)

        employees = Employee_db.objects.filter(
            department=department,
            is_deleted=False,
        )

        serializer = EmployeeMiniSerializer(
            employees, many=True, context={'request': request}
        )
        return Response(serializer.data)


# HR: list daily tasks of a particular employee
class HRDailyTaskByEmployeeView(generics.ListAPIView):
    serializer_class = DailyTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        employee_id = self.kwargs['employee_id']
        queryset = DailyTask.objects.filter(
            employee__id=employee_id,
            employee__department__company=self.request.user.company,
        )

        # Optional date filter: ?date=2025-06-16
        date_str = self.request.query_params.get('date')
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                queryset = queryset.filter(created_at__date=date_obj)
            except ValueError:
                pass

        return queryset.order_by('-created_at')