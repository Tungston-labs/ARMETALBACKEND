import calendar
from datetime import datetime, timedelta

from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Count, Q

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


# ============================================================
#  Company-scoping helpers
# ============================================================

def company_projects(user):
    """Only projects that belong to the user's company."""
    return Project.objects.filter(company=user.company)


def company_employees(user):
    """Only (non-deleted) employees that belong to the user's company."""
    return Employee_db.objects.filter(
        department__company=user.company,
        is_deleted=False,
    )


def ensure_employees_in_company(user, employee_ids):
    """
    Raise a 400 if any id is not an employee of the user's company.
    Prevents attaching another company's employees to a project.
    """
    ids = {getattr(e, "id", e) for e in (employee_ids or [])}
    if not ids:
        return
    found = set(
        company_employees(user)
        .filter(id__in=ids)
        .values_list("id", flat=True)
    )
    # compare as strings so "5" and 5 both work
    if {str(i) for i in ids} != {str(i) for i in found}:
        raise ValidationError(
            {"employees": "One or more employees do not belong to your company."}
        )


# ============================================================
#  Project List/Create
# ============================================================

class ProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        queryset = company_projects(self.request.user).prefetch_related('employees')

        # ?status=in_progress | completed | on_hold | cancelled
        project_status = self.request.query_params.get('status')
        if project_status:
            queryset = queryset.filter(status=project_status)

        # ?date=2026-08  (year-month)
        date = self.request.query_params.get('date')
        if date:
            year, month = date.split("-")[:2]
            queryset = queryset.filter(
                created_at__year=int(year),
                created_at__month=int(month)
            )

        # ?start_date=2026-08-01&end_date=2026-08-31
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)

        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        ensure_employees_in_company(user, serializer.validated_data.get("employees"))
        ensure_employees_in_company(user, serializer.validated_data.get("team_leads"))
        serializer.save(company=user.company)


# ============================================================
#  Project Retrieve/Update/Delete
# ============================================================
class ProjectRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Other companies' projects -> 404
        return company_projects(self.request.user).prefetch_related(
            'employees',
            'team_leads'
        )

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProjectWriteSerializer
        return ProjectReadSerializer

    def perform_update(self, serializer):
        # PUT path
        user = self.request.user
        ensure_employees_in_company(user, serializer.validated_data.get("employees"))
        ensure_employees_in_company(user, serializer.validated_data.get("team_leads"))
        serializer.save()

    def patch(self, request, *args, **kwargs):

        project = self.get_object()  # already company-scoped

        data = request.data.copy()

        # Convert "" -> None for latitude & longitude
        if data.get("latitude") in ["", None]:
            data["latitude"] = None

        if data.get("longitude") in ["", None]:
            data["longitude"] = None

        employee_ids = data.pop("employees", None)
        team_lead_ids = data.pop("team_leads", None)

        # -----------------------------------------
        # Validate everything BEFORE writing anything
        # -----------------------------------------
        ensure_employees_in_company(request.user, employee_ids)
        ensure_employees_in_company(request.user, team_lead_ids)

        if team_lead_ids is not None:
            current_employee_ids = set(
                project.employees.values_list("id", flat=True)
            )
            if employee_ids is not None:
                current_employee_ids |= {int(i) for i in employee_ids}

            invalid_team_leads = {int(i) for i in team_lead_ids} - current_employee_ids

            if invalid_team_leads:
                return Response(
                    {"team_leads": "All team leads must also be assigned to the project."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = self.get_serializer(project, data=data, partial=True)
        serializer.is_valid(raise_exception=True)

        # -----------------------------------------
        # Apply changes
        # -----------------------------------------
        if employee_ids is not None:
            for emp_id in employee_ids:
                project.employees.add(emp_id)

        if team_lead_ids is not None:
            for emp_id in team_lead_ids:
                project.team_leads.add(emp_id)

        serializer.save()

        read_serializer = ProjectReadSerializer(
            project,
            context={"request": request}
        )
        return Response(read_serializer.data)


# ============================================================
#  Employees Not In Project
# ============================================================
class EmployeesNotInProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        if not getattr(request.user, "company", None):
            return Response(
                {"detail": "User has no company assigned"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 404 (not 403) so other companies can't even tell the project exists
        project = get_object_or_404(company_projects(request.user), id=project_id)

        employees_not_in_project = company_employees(request.user).exclude(
            id__in=project.employees.values_list("id", flat=True)
        )

        serializer = EmployeeSerializer(
            employees_not_in_project, many=True, context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================
#  Remove Employee From Project
# ============================================================
class RemoveEmployeeFromProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, project_id, employee_id):

        project = get_object_or_404(company_projects(request.user), pk=project_id)

        # Archived employees can still be removed from a project
        employee = get_object_or_404(
            Employee_db,
            pk=employee_id,
            department__company=request.user.company,
        )

        project.employees.remove(employee)
        project.team_leads.remove(employee)

        return Response(
            {'detail': f'Employee {employee.name} removed from project {project.name}.'},
            status=status.HTTP_200_OK
        )


# ============================================================
#  Employee Attendance Detail
# ============================================================

class EmployeeAttendanceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        employee = get_object_or_404(
            Employee_db,
            id=employee_id,
            department__company=request.user.company,
        )

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

        # Total working hours
        all_days = [month_start + timedelta(days=i) for i in range((month_end - month_start).days + 1)]
        holidays = set(
            PublicHoliday.objects.filter(
                company=request.user.company,
                date__range=(month_start, month_end)
            ).values_list('date', flat=True)
        )

        working_days = [d for d in all_days if d.weekday() != 6 and d not in holidays]
        total_working_hours = len(working_days) * 8

        def format_hours(hours):
            if not hours:
                return "00:00"
            h = int(hours)
            m = int(round((hours - h) * 60))
            return f"{h:02d}:{m:02d}"

        if attendance:
            serializer = EmployeeAttendanceDetailSerializer(attendance, context={'request': request})
            data = serializer.data
        else:
            emp_serializer = EmployeeSerializer(employee, context={'request': request})
            data = {
                "employee": emp_serializer.data,
                "detail": f"No attendance recorded on {selected_date}.",
                "total_hours_formatted": "00:00",
                "locations": []
            }

        data["weekly_hours_formatted"] = format_hours(total_week)
        data["monthly_hours_formatted"] = format_hours(total_month)
        data["total_working_hours"] = total_working_hours

        return Response(data, status=200)


# ============================================================
#  Employee's own project (employee app)
# ============================================================
class EmployeeProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = getattr(request.user, "employee_profile", getattr(request.user, "employee_db", None))
        if not employee:
            return Response({"error": "Employee record not found"}, status=404)

        company = getattr(request.user, "company", None)
        if not company and employee.department:
            company = employee.department.company

        project_qs = Project.objects.filter(employees=employee)
        if company:
            project_qs = project_qs.filter(company=company)
        project = project_qs.first()

        if not project:
            return Response({"project": None})

        return Response({
            "id": project.id,
            "name": project.name,
            "punch_type": project.punch_type,
            "latitude": project.latitude,
            "longitude": project.longitude
        })


# ============================================================
#  Project counts
# ============================================================
class ProjectCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = company_projects(request.user).aggregate(
            total_projects=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            in_progress=Count("id", filter=Q(status="in_progress")),
            pending=Count("id", filter=Q(status="on_hold")),
            high_priority=Count("id", filter=Q(priority="high")),
        )
        return Response(data)