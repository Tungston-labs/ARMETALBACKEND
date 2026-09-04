from django.shortcuts import render
from .models import DailyTask
from .serializers import DailyTaskSerializer
from user.permissions import IsEmployee, IsHRAdmin  
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from django.utils.timezone import now
from decimal import Decimal, InvalidOperation
from django.db.models import Sum
from django.utils import timezone
from rest_framework import generics, permissions, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from departments.models import Department
from .serializers import EmployeeMiniSerializer
from employee.models import Employee_db
from rest_framework.response import Response

class EmployeeDailyTaskCreateListView(generics.ListCreateAPIView):
    serializer_class = DailyTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee]

    def get_queryset(self):
        employee = self.request.user.employee_db
        queryset = DailyTask.objects.filter(employee=employee)

        date_str = self.request.query_params.get('date')
        if date_str:
            from django.utils.dateparse import parse_date
            date = parse_date(date_str)
            if date:
                queryset = queryset.filter(created_at__date=date)  
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        employee = self.request.user.employee_db
        today = timezone.localdate()  

        # Aggregate today's total hours based on created_at
        agg = DailyTask.objects.filter(
            employee=employee,
            created_at__date=today
        ).aggregate(total=Sum("time_taken"))

        existing_hours = agg["total"] or Decimal("0")

        # Make sure we handle decimals safely
        try:
            new_hours = Decimal(str(serializer.validated_data.get("time_taken", 0)))
        except (InvalidOperation, TypeError):
            raise serializers.ValidationError({"time_taken": ["Invalid time value"]})

        total_hours = existing_hours + new_hours

        if total_hours > Decimal("24"):
            raise serializers.ValidationError({
                "time_taken": [
                    f"Daily total cannot exceed 24 hours. You already logged {existing_hours} hours today."
                ]
            })

        serializer.save(employee=employee)




#  Employee: Retrieve/Update/Delete Own Task
class EmployeeDailyTaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DailyTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee]

    def get_queryset(self):
        return DailyTask.objects.filter(employee=self.request.user.employee_db)

#  HR Admin: List All Tasks
class HRDailyTaskListView(generics.ListAPIView):
    queryset = DailyTask.objects.all()
    serializer_class = DailyTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]



class EmployeeByDepartmentView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request, department_id):
        # Validate department belongs to the same company
        try:
            department = Department.objects.get(
                pk=department_id, 
                company=request.user.company
            )
        except Department.DoesNotExist:
            return Response({"detail": "Department not found."}, status=404)

        employees = Employee_db.objects.filter(
            department=department,
            is_deleted=False
        )

        # Pass request in context so profile_pic URLs are correct
        serializer = EmployeeMiniSerializer(employees, many=True, context={'request': request})
        return Response(serializer.data)

# HR:list daily task of particular employee with id
from datetime import datetime


class HRDailyTaskByEmployeeView(generics.ListAPIView):
    serializer_class = DailyTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        employee_id = self.kwargs['employee_id']
        queryset = DailyTask.objects.filter(employee__id=employee_id)

        # Optional date filter: ?date=2025-06-16
        date_str = self.request.query_params.get('date')
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                queryset = queryset.filter(created_at__date=date_obj)
            except ValueError:
                pass  # Optionally raise a validation error

        return queryset.order_by('-created_at')


