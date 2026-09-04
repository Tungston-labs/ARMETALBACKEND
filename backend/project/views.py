from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Sum
from django.db.models import Count, Q

from .models import Project
from employee.models import Employee_db
from attendance.models import Attendance
from holidays.models import PublicHoliday
from project.serialzers import (
    ProjectReadSerializer,
    ProjectWriteSerializer,
    EmployeeSerializer,
    ProjectSerializer,
    EmployeeAttendanceDetailSerializer
)
from datetime import timedelta
import calendar


# ============================================================
#  Project List/Create
# ============================================================

class ProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        user = self.request.user

        queryset = Project.objects.filter(
            company=user.company
        ).prefetch_related('employees')

        # ----------------------------------------------------
        # Search by project name
        # Example:
        # ?search=website
        # ----------------------------------------------------

        # ----------------------------------------------------
        # Filter by status
        # Example:
        # ?status=in_progress
        # ?status=completed
        # ?status=on_hold
        # ?status=cancelled
        # ----------------------------------------------------

        status = self.request.query_params.get('status')

        if status:
            queryset = queryset.filter(status=status)

        # ----------------------------------------------------
        # Filter by exact created date
        # Example:
        # ?date=2026-08-31
        # ----------------------------------------------------

        date = self.request.query_params.get('date')

        if date:
            year, month = date.split("-")

            queryset = queryset.filter(
                created_at__year=int(year),
                created_at__month=int(month)
            )

        # ----------------------------------------------------
        # Filter by date range
        # Example:
        # ?start_date=2026-08-01&end_date=2026-08-31
        # ----------------------------------------------------

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)

        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        return queryset

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company
        )



# ============================================================
#  Project Retrieve/Update/Delete
# ============================================================
class ProjectRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Project.objects.all().prefetch_related(
    'employees',
    'team_leads'
)
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProjectWriteSerializer
        return ProjectReadSerializer

    def patch(self, request, *args, **kwargs):

        project = self.get_object()

        data = request.data.copy()

        # Convert "" → None for latitude & longitude
        if data.get("latitude") in ["", None]:
            data["latitude"] = None

        if data.get("longitude") in ["", None]:
            data["longitude"] = None

        # -----------------------------------------
        # Add employees
        # -----------------------------------------
        employee_ids = data.pop("employees", None)

        if employee_ids is not None:
            for emp_id in employee_ids:
                project.employees.add(emp_id)

        # -----------------------------------------
        # Add team leads
        # -----------------------------------------
        team_lead_ids = data.pop("team_leads", None)

        if team_lead_ids is not None:

            # Get current project employees
            current_employee_ids = set(
                project.employees.values_list(
                    "id",
                    flat=True
                )
            )

            # Make sure all team leads are project employees
            invalid_team_leads = (
                set(team_lead_ids) - current_employee_ids
            )

            if invalid_team_leads:
                return Response(
                    {
                        "team_leads":
                            "All team leads must also be assigned to the project."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            for emp_id in team_lead_ids:
                project.team_leads.add(emp_id)

        # -----------------------------------------
        # Update other project fields
        # -----------------------------------------
        serializer = self.get_serializer(
            project,
            data=data,
            partial=True
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save()

        # -----------------------------------------
        # Return updated project
        # -----------------------------------------
        read_serializer = ProjectReadSerializer(
            project,
            context={
                "request": request
            }
        )

        return Response(
            read_serializer.data
        )


# ============================================================
#  Employees Not In Project
# ============================================================
class EmployeesNotInProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "User has no company assigned"}, status=status.HTTP_400_BAD_REQUEST)

        project = get_object_or_404(Project, id=project_id)

        if project.company != company:
            return Response({"detail": "Not authorized for this project"}, status=status.HTTP_403_FORBIDDEN)

        employees_not_in_project = (
                Employee_db.objects.filter(
                    department__company=company,
                    is_deleted=False
                )
                .exclude(id__in=project.employees.values_list("id", flat=True))
            )

        serializer = EmployeeSerializer(employees_not_in_project, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================
#  Remove Employee From Project
# ============================================================
class RemoveEmployeeFromProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, project_id, employee_id):

        project = get_object_or_404(
            Project,
            pk=project_id
        )

        employee = get_object_or_404(
            Employee_db,
            pk=employee_id
        )

        # Remove employee from project
        project.employees.remove(employee)

        # Also remove employee from team leads
        project.team_leads.remove(employee)

        return Response(
            {
                'detail':
                    f'Employee {employee.name} removed from project {project.name}.'
            },
            status=status.HTTP_200_OK
        )

# ============================================================
#  Employee Attendance Detail
# ============================================================

class EmployeeAttendanceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        employee = get_object_or_404(Employee_db, id=employee_id)

        # Date filter
        date_str = request.query_params.get('date')
        if date_str:
            try:
                selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
        else:
            selected_date = timezone.localdate()

        attendance = Attendance.objects.filter(employee=employee, date=selected_date).first()

        # Weekly/Monthly totals
        week_start = selected_date - timedelta(days=selected_date.weekday())
        week_end = week_start + timedelta(days=6)
        total_week = Attendance.objects.filter(
            employee=employee, date__range=[week_start, week_end]
        ).aggregate(total=Sum('total_hours'))['total'] or 0

        month_start = selected_date.replace(day=1)
        month_end = month_start.replace(day=calendar.monthrange(month_start.year, month_start.month)[1])
        total_month = Attendance.objects.filter(
            employee=employee, date__range=[month_start, month_end]
        ).aggregate(total=Sum('total_hours'))['total'] or 0

        # ==============================
        # Total working hours (new logic)
        # ==============================
        all_days = [month_start + timedelta(days=i) for i in range((month_end - month_start).days + 1)]
        sundays = [d for d in all_days if d.weekday() == 6]
        holidays = set(
            PublicHoliday.objects.filter(
                company=employee.department.company,
                date__range=(month_start, month_end)
            ).values_list('date', flat=True)
        )

        working_days = [d for d in all_days if d not in sundays and d not in holidays]
        total_working_hours = len(working_days) * 8

        # Helper
        def format_hours(hours):
            if not hours:
                return "00:00"
            h = int(hours)
            m = int(round((hours - h) * 60))
            return f"{h:02d}:{m:02d}"

        if attendance:
            serializer = EmployeeAttendanceDetailSerializer(attendance, context={'request': request})
            data = serializer.data
            # Ensure correct total working hours
            data["total_working_hours"] = total_working_hours
        else:
            emp_serializer = EmployeeSerializer(employee, context={'request': request})
            data = {
                "employee": emp_serializer.data,
                "detail": f"No attendance recorded on {selected_date}.",
                "total_hours_formatted": "00:00",
                "weekly_hours_formatted": format_hours(total_week),
                "monthly_hours_formatted": format_hours(total_month),
                "total_working_hours": total_working_hours,
                "locations": []
            }


        # Ensure calculations are consistent
        data["weekly_hours_formatted"] = format_hours(total_week)
        data["monthly_hours_formatted"] = format_hours(total_month)
        data["total_working_hours"] = total_working_hours

        return Response(data, status=200)


class EmployeeProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = request.user.employee_db

        project = Project.objects.filter(employees=employee).first()

        if not project:
            return Response({"project": None})

        return Response({
            "id": project.id,
            "name": project.name,
            "punch_type": project.punch_type,
            "latitude": project.latitude,
            "longitude": project.longitude
        })
        
class ProjectCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        projects = Project.objects.filter(
    company=request.user.company
   ) 

        data = projects.aggregate(
            total_projects=Count("id"),

            completed=Count(
                "id",
                filter=Q(status="completed")
            ),

            in_progress=Count(
                "id",
                filter=Q(status="in_progress")
            ),

            pending=Count(
                "id",
                filter=Q(status="on_hold")
            ),

            high_priority=Count(
                "id",
                filter=Q(priority="high")
            ),
        )

        return Response(data)