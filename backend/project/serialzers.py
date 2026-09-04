from datetime import timedelta
import calendar

from django.conf import settings
from django.db.models import Sum
from rest_framework import serializers

from .models import Project
from employee.models import Employee_db
from attendance.models import Attendance
from attendance.serializers import AttendanceSessionSerializer


# ============================================================
# Employee Serializer
# ============================================================

class EmployeeSerializer(serializers.ModelSerializer):

    department_name = serializers.CharField(
        source="department.name",
        read_only=True
    )

    profile_pic = serializers.SerializerMethodField()

    is_lead = serializers.SerializerMethodField()

    class Meta:
        model = Employee_db

        fields = [
            "id",
            "name",
            "employee_id",
            "email",
            "designation",
            "department",
            "department_name",
            "profile_pic",
            "joining_date",
            "gender",
            "is_lead",
        ]

    def get_profile_pic(self, obj):

        request = self.context.get("request")

        if not obj.profile_pic:
            return None

        if request:
            return request.build_absolute_uri(
                obj.profile_pic.url
            )

        return f"{settings.MEDIA_URL}{obj.profile_pic.url}"

    def get_is_lead(self, obj):

        project = self.context.get("project")

        if not project:
            return False

        return project.team_leads.filter(
            id=obj.id
        ).exists()


# ============================================================
# Project Base Serializer
# ============================================================

class ProjectBaseSerializer(serializers.ModelSerializer):

    latitude = serializers.FloatField(
        required=False,
        allow_null=True
    )

    longitude = serializers.FloatField(
        required=False,
        allow_null=True
    )

    class Meta:
        model = Project

        fields = [
            "id",
            "name",
            "punch_type",
            "latitude",
            "longitude",
            "company",
            "employees",
            "status",
            "priority",
            "start_date",
            "team_leads"
        ]

        read_only_fields = [
            "company",
        ]


# ============================================================
# Project Serializer
# Used for Create / Update
# ============================================================

class ProjectSerializer(serializers.ModelSerializer):

    employees = serializers.PrimaryKeyRelatedField(
        queryset=Employee_db.objects.all(),
        many=True,
        required=False
    )

    team_leads = serializers.PrimaryKeyRelatedField(
        queryset=Employee_db.objects.all(),
        many=True,
        required=False
    )

    company = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "punch_type",
            "latitude",
            "longitude",
            "company",
            "employees",
            "team_leads",
            "status",
            "priority",
            "start_date",
        ]

    def validate(self, attrs):
        employees = attrs.get("employees", [])
        team_leads = attrs.get("team_leads", [])

        employee_ids = {employee.id for employee in employees}
        team_lead_ids = {employee.id for employee in team_leads}

        # Team leads must be project employees
        if not team_lead_ids.issubset(employee_ids):
            raise serializers.ValidationError({
                "team_leads": "All team leads must also be assigned to the project."
            })

        return attrs

    def create(self, validated_data):
        employees = validated_data.pop("employees", [])
        team_leads = validated_data.pop("team_leads", [])

        project = Project.objects.create(**validated_data)

        if employees:
            project.employees.set(employees)

        if team_leads:
            project.team_leads.set(team_leads)

        return project

    def update(self, instance, validated_data):
        employees = validated_data.pop("employees", None)
        team_leads = validated_data.pop("team_leads", None)

        instance = super().update(instance, validated_data)

        if employees is not None:
            instance.employees.set(employees)

        if team_leads is not None:
            instance.team_leads.set(team_leads)

        return instance

# ============================================================
# Project Read Serializer
# Used for GET Project List / Details
# ============================================================

class ProjectReadSerializer(ProjectBaseSerializer):

    employees = serializers.SerializerMethodField()

    company = serializers.StringRelatedField(
        read_only=True
    )

    def get_employees(self, obj):
        request = self.context.get("request")

        return EmployeeSerializer(
                obj.employees.all(),
                many=True,
                context={
                    "request": request,
                    "project": obj,
                }
            ).data


# ============================================================
# Project Write Serializer
# Used when API specifically requires a write serializer
# ============================================================

class ProjectWriteSerializer(ProjectBaseSerializer):

    employees = serializers.PrimaryKeyRelatedField(
        queryset=Employee_db.objects.all(),
        many=True,
        required=False
    )

    team_leads = serializers.PrimaryKeyRelatedField(
        queryset=Employee_db.objects.all(),
        many=True,
        required=False
    )

    # Company should not be sent from frontend
    company = serializers.StringRelatedField(
        read_only=True
    )

    def validate(self, attrs):
        employees = attrs.get("employees")
        team_leads = attrs.get("team_leads")

        # Only validate when both are provided
        if employees is not None and team_leads is not None:

            employee_ids = {
                employee.id for employee in employees
            }

            team_lead_ids = {
                employee.id for employee in team_leads
            }

            if not team_lead_ids.issubset(employee_ids):
                raise serializers.ValidationError({
                    "team_leads":
                        "All team leads must also be assigned to the project."
                })

        return attrs

    def create(self, validated_data):

        employees = validated_data.pop("employees", [])
        team_leads = validated_data.pop("team_leads", [])

        project = Project.objects.create(
            **validated_data
        )

        if employees:
            project.employees.set(employees)

        if team_leads:
            project.team_leads.set(team_leads)

        return project

    def update(self, instance, validated_data):

        employees = validated_data.pop(
            "employees",
            None
        )

        team_leads = validated_data.pop(
            "team_leads",
            None
        )

        # Update normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Update employees
        if employees is not None:
            instance.employees.set(employees)

        # Update team leads
        if team_leads is not None:
            instance.team_leads.set(team_leads)

        return instance


# ============================================================
# Employee Attendance Detail Serializer
# ============================================================

class EmployeeAttendanceDetailSerializer(serializers.ModelSerializer):

    employee = serializers.SerializerMethodField()

    sessions = AttendanceSessionSerializer(
        many=True,
        read_only=True
    )

    total_hours_formatted = serializers.SerializerMethodField()
    weekly_hours_formatted = serializers.SerializerMethodField()
    monthly_hours_formatted = serializers.SerializerMethodField()
    total_working_hours = serializers.SerializerMethodField()
    locations = serializers.SerializerMethodField()

    class Meta:
        model = Attendance

        fields = [
            "id",
            "date",
            "total_hours",
            "total_hours_formatted",
            "weekly_hours_formatted",
            "monthly_hours_formatted",
            "total_working_hours",
            "locations",
            "remark",
            "employee",
            "sessions",
        ]

    # --------------------------------------------------------
    # Employee
    # --------------------------------------------------------

    def get_employee(self, obj):
        request = self.context.get("request")

        return EmployeeSerializer(
            obj.employee,
            context={
                "request": request
            }
        ).data

    # --------------------------------------------------------
    # Total Hours
    # --------------------------------------------------------

    def get_total_hours_formatted(self, obj):
        return self.format_hours(
            obj.total_hours
        )

    # --------------------------------------------------------
    # Weekly Hours
    # --------------------------------------------------------

    def get_weekly_hours_formatted(self, obj):

        week_start = (
            obj.date -
            timedelta(days=obj.date.weekday())
        )

        week_end = (
            week_start +
            timedelta(days=6)
        )

        total = (
            Attendance.objects
            .filter(
                employee=obj.employee,
                date__range=[
                    week_start,
                    week_end
                ]
            )
            .aggregate(
                total=Sum("total_hours")
            )
            ["total"]
            or 0
        )

        return self.format_hours(total)

    # --------------------------------------------------------
    # Monthly Hours
    # --------------------------------------------------------

    def get_monthly_hours_formatted(self, obj):

        month_start = obj.date.replace(
            day=1
        )

        last_day = calendar.monthrange(
            month_start.year,
            month_start.month
        )[1]

        month_end = month_start.replace(
            day=last_day
        )

        total = (
            Attendance.objects
            .filter(
                employee=obj.employee,
                date__range=[
                    month_start,
                    month_end
                ]
            )
            .aggregate(
                total=Sum("total_hours")
            )
            ["total"]
            or 0
        )

        return self.format_hours(total)

    # --------------------------------------------------------
    # Total Working Hours
    # --------------------------------------------------------

    def get_total_working_hours(self, obj):

        from holidays.models import PublicHoliday

        month_start = obj.date.replace(
            day=1
        )

        last_day = calendar.monthrange(
            month_start.year,
            month_start.month
        )[1]

        month_end = month_start.replace(
            day=last_day
        )

        all_days = [
            month_start + timedelta(days=i)
            for i in range(
                (month_end - month_start).days + 1
            )
        ]

        sundays = {
            day
            for day in all_days
            if day.weekday() == 6
        }

        holidays = set(
            PublicHoliday.objects
            .filter(
                company=obj.employee.department.company,
                date__range=(
                    month_start,
                    month_end
                )
            )
            .values_list(
                "date",
                flat=True
            )
        )

        working_days = [
            day
            for day in all_days
            if day not in sundays
            and day not in holidays
        ]

        return len(working_days) * 8

    # --------------------------------------------------------
    # Locations
    # --------------------------------------------------------

    def get_locations(self, obj):
        return obj.locations or []

    # --------------------------------------------------------
    # Format Hours
    # --------------------------------------------------------

    @staticmethod
    def format_hours(hours):

        if not hours:
            return "00:00"

        hours = float(hours)

        h = int(hours)

        m = int(
            round(
                (hours - h) * 60
            )
        )

        if m == 60:
            h += 1
            m = 0

        return f"{h:02d}:{m:02d}"