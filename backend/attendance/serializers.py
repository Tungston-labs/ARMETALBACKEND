# attendance/serializers.py
from rest_framework import serializers
from .models import Attendance, AttendanceSession
from employee.models import Employee_db
# serializers.py
from rest_framework import serializers
from .models import Attendance, AttendanceSession
from datetime import time,datetime
from rest_framework import serializers
from .models import Attendance, AttendanceSession,AttendanceCorrectionRequest
from .utils.timezone_utils import get_company_timezone,convert_to_company_timezone,safe_parse_datetime,ensure_timezone
import pytz
from django.db.models import Sum
from datetime import timedelta,date
from decimal import Decimal, ROUND_HALF_UP

class AttendanceSessionSerializer(serializers.ModelSerializer):
    time_in = serializers.SerializerMethodField()
    time_out = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSession
        fields = ['id', 'time_in', 'time_out', 'duration', 'note','punch_in_latitude',
            'punch_in_longitude',
            'punch_in_location',
            'punch_out_latitude',
            'punch_out_longitude',
            'punch_out_location',]

    def get_time_in(self, obj):
        return self._safe_convert(obj.time_in, obj)

    def get_time_out(self, obj):
        return self._safe_convert(obj.time_out, obj)

    def get_duration(self, obj):
        """Get session duration in hours"""
        return obj.get_duration()

    def _safe_convert(self, dt, obj):
        """Safely convert datetime to company timezone string"""
        if dt is None:
            return None
            
        try:
            # Handle time objects
            if isinstance(dt, time):
                # Combine with attendance date
                dt = datetime.combine(obj.attendance.date, dt)
            
            # Ensure it's a datetime object
            if not isinstance(dt, datetime):
                return None
                
            # Convert to company timezone
            return convert_to_company_timezone(dt, obj.attendance.employee)
            
        except Exception as e:
            # Fallback to UTC string
            if isinstance(dt, datetime):
                if dt.tzinfo is None:
                    dt = pytz.UTC.localize(dt)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            return None


from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, time
import pytz
from employee.models import Employee_db

IST = pytz.timezone("Asia/Kolkata")

# serializers.py
from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, time
import pytz
from .models import  Attendance, AttendanceSession

IST = pytz.timezone("Asia/Kolkata")


class AttendanceSerializer(serializers.ModelSerializer):
    employee = serializers.IntegerField(source="id", read_only=True)
    employee_name = serializers.CharField(source="name", read_only=True)
    profile_pic = serializers.ImageField(read_only=True)
    employee_code = serializers.CharField(read_only=True)
    attendance_id = serializers.IntegerField(read_only=True)  # comes from queryset annotation

    total_hours = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    total_hours_formatted = serializers.SerializerMethodField()
    attendance_today = serializers.BooleanField(read_only=True)
    date = serializers.DateField(read_only=True)

    first_swipe_in = serializers.SerializerMethodField()
    last_swipe_out = serializers.SerializerMethodField()
    attendance_type = serializers.CharField(
        read_only=True,
        allow_null=True
    )

    attendance_status = serializers.CharField(
        read_only=True
    )

    class Meta:
        model = Employee_db
        fields = [
            "employee",
            "employee_name",
            "employee_id",
            "employee_code",
            "profile_pic",
            "date",
            "first_swipe_in",
            "last_swipe_out",
            "total_hours",
            "total_hours_formatted",
            "attendance_today",
            "attendance_id",
            "attendance_status",
            "attendance_type",
        ]

    # ---------- format total_hours ----------
    def get_total_hours_formatted(self, obj):

        total_hours = Decimal(str(obj.total_hours or 0))

        hours = int(total_hours)

        minutes = int(
            ((total_hours - Decimal(hours)) * Decimal("60"))
            .quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP
            )
        )

        if minutes == 60:
            hours += 1
            minutes = 0

        return f"{hours:02d}:{minutes:02d}"

    # ---------- convert time to IST AM/PM ----------
    def _to_ist(self, value, attendance_date=None):
        if not value:
            return None

        # If TIME → combine with date
        if isinstance(value, time):
            if attendance_date is None:
                return value.strftime("%H:%M")
            value = datetime.combine(attendance_date, value)

        if timezone.is_naive(value):
            value = timezone.make_aware(value, pytz.UTC)

        value = value.astimezone(IST)
        return value.strftime("%I:%M %p")

    # ---------- first swipe in ----------
    def get_first_swipe_in(self, obj):
        if hasattr(obj, "first_swipe_in") and obj.first_swipe_in:
            return self._to_ist(obj.first_swipe_in, getattr(obj, "date", None))

        # fallback: fetch from attendance sessions if annotation missing
        if getattr(obj, "attendance_id", None):
            try:
                attendance = Attendance.objects.get(id=obj.attendance_id)
                session = attendance.sessions.order_by("time_in").first()
                return self._to_ist(session.time_in, attendance.date) if session else None
            except Attendance.DoesNotExist:
                return None
        return None

    # ---------- last swipe out ----------
    def get_last_swipe_out(self, obj):
        if hasattr(obj, "last_swipe_out") and obj.last_swipe_out:
            return self._to_ist(obj.last_swipe_out, getattr(obj, "date", None))

        # fallback: fetch from attendance sessions if annotation missing
        if getattr(obj, "attendance_id", None):
            try:
                attendance = Attendance.objects.get(id=obj.attendance_id)
                session = attendance.sessions.order_by("-time_out").first()
                return self._to_ist(session.time_out, attendance.date) if session else None
            except Attendance.DoesNotExist:
                return None
        return None

from rest_framework import serializers
from employee.models import Employee_db


class AttendanceEmployeeRowSerializer(serializers.ModelSerializer):
    first_punch_in = serializers.TimeField(read_only=True)
    has_swipe_today = serializers.BooleanField(read_only=True)

    class Meta:
        model = Employee_db
        fields = [
            "id",
            "employee_id",
            "name",
            "profile_pic",
            "first_punch_in",
            "has_swipe_today",
        ]


class EmployeeInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee_db
        fields = ['id', 'name', 'email', 'employee_id', 'profile_pic', 'department', 'designation','address','dob','gender']
        depth = 1  # if department/designation are foreign keys
class AttendanceDetailSerializer(serializers.ModelSerializer):
    sessions = AttendanceSessionSerializer(many=True, read_only=True)
    employee = EmployeeInfoSerializer(read_only=True)
    total_hours_formatted = serializers.SerializerMethodField()
    weekly_hours_formatted = serializers.SerializerMethodField()
    monthly_hours_formatted = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            'id', 'date', 'total_hours', 'total_hours_formatted',
            'weekly_hours_formatted', 'monthly_hours_formatted',
            'remark', 'employee', 'sessions'
        ]

    # ---------- format helpers ----------
    def format_hours(self, hours):
        """Convert decimal hours → HH:MM"""
        if hours is None:
            return "00:00"

        h = int(hours)
        m = int(round((float(hours) - h) * 60))
        return f"{h:02d}:{m:02d}"

    # ---------- total ----------
    def get_total_hours_formatted(self, obj):
        return self.format_hours(obj.total_hours)

    # ---------- week ----------
    def get_weekly_hours_formatted(self, obj):
        day = obj.date.day
        month_start = obj.date.replace(day=1)

        # week blocks: 1-7, 8-14, 15-21, 22-28, 29-end
        week_start_day = ((day - 1) // 7) * 7 + 1
        week_start = month_start.replace(day=week_start_day)

        # last day of month
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1, day=1)

        month_end_day = (next_month - timedelta(days=1)).day
        week_end_day = min(week_start_day + 6, month_end_day)
        week_end = month_start.replace(day=week_end_day)

        total = Attendance.objects.filter(
            employee=obj.employee,
            date__range=[week_start, week_end]
        ).aggregate(total=Sum('total_hours'))['total']

        return self.format_hours(total)

    # ---------- month ----------
    def get_monthly_hours_formatted(self, obj):
        month_start = obj.date.replace(day=1)

        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1, day=1)

        month_end = next_month - timedelta(days=1)

        total = Attendance.objects.filter(
            employee=obj.employee,
            date__range=[month_start, month_end]
        ).aggregate(total=Sum('total_hours'))['total']

        return self.format_hours(total)




class AttendanceLocationSerializer(serializers.Serializer):
    location = serializers.CharField()
    timestamp = serializers.DateTimeField(required=False)

# attendance/serializers.py
from rest_framework import serializers
from .models import HourlyLocationLog

# serializers.py
class HourlyLocationLogSerializer(serializers.ModelSerializer):
    captured_at = serializers.DateTimeField(required=False, write_only=True)

    class Meta:
        model = HourlyLocationLog
        fields = ['employee', 'latitude', 'longitude', 'location_name', 'logged_at', 'captured_at']
        extra_kwargs = {
            'logged_at': {'required': False},
        }

    def create(self, validated_data):
        captured_at = validated_data.pop('captured_at', None)
        if captured_at and 'logged_at' not in validated_data:
            validated_data['logged_at'] = captured_at
        return super().create(validated_data)




class DailyAttendanceSerializer(serializers.Serializer):

    date = serializers.DateField()

    status = serializers.CharField()

    total_hours = serializers.FloatField()

    first_punch_in = serializers.CharField(
        allow_null=True,
        required=False
    )

    last_punch_out = serializers.CharField(
        allow_null=True,
        required=False
    )

    attendance_type = serializers.CharField(
        allow_null=True,
        required=False
    )

    remark = serializers.CharField(
        allow_null=True,
        required=False
    )

    updated_by = serializers.CharField(
        allow_null=True,
        required=False
    )

    updated_by_role = serializers.CharField(
        allow_null=True,
        required=False
    )

    updated_at = serializers.CharField(
        allow_null=True,
        required=False
    )


class EmployeeAttendanceSummarySerializer(serializers.Serializer):

    employee_id = serializers.CharField()

    employee_name = serializers.CharField()

    department = serializers.CharField(
        allow_null=True,
        required=False
    )

    working_days = serializers.FloatField()

    present_days = serializers.FloatField()

    absent_days = serializers.FloatField()

    lop_days = serializers.FloatField()

    daily_records = DailyAttendanceSerializer(
        many=True
    )



class AttendanceCorrectionRequestSerializer(
    serializers.ModelSerializer
):

    employee_name = serializers.CharField(
        source="employee.name",
        read_only=True
    )

    employee_id = serializers.CharField(
        source="employee.employee_id",
        read_only=True
    )

    class Meta:
        model = AttendanceCorrectionRequest

        fields = [
            "id",
            "employee",
            "employee_name",
            "employee_id",
            "date",
            "request_type",
            "reason",
            "status",
            "admin_reason",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "employee",
            "status",
            "admin_reason",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):

        request = self.context["request"]

        employee = getattr(
            request.user,
            "employee_profile",
            None
        )

        if not employee:
            raise serializers.ValidationError({
                "employee": "Employee profile not found."
            })

        date = attrs.get("date")

        if AttendanceCorrectionRequest.objects.filter(
            employee=employee,
            date=date
        ).exists():

            raise serializers.ValidationError({
                "date": (
                    "You have already submitted an attendance "
                    "correction request for this date."
                )
            })

        return attrs
    

class MissingPunchStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = AttendanceCorrectionRequest
        fields = [
            "id",
            "status",
            "admin_reason",
        ]

    def validate_status(self, value):

        if value not in ["approved", "rejected"]:
            raise serializers.ValidationError(
                "Status must be either approved or rejected."
            )

        return value
    

from rest_framework import serializers
from attendance.models import Attendance

from rest_framework import serializers
from attendance.models import Attendance

from rest_framework import serializers

from attendance.models import Attendance


class AttendanceManualUpdateSerializer(
    serializers.ModelSerializer
):

    employee = serializers.IntegerField(
        source="employee.id",
        read_only=True
    )

    updated_by = serializers.SerializerMethodField()

    updated_by_role = serializers.SerializerMethodField()

    class Meta:

        model = Attendance

        fields = [
            "id",
            "employee",
            "date",
            "attendance_type",
            "remark",
            "total_hours",
            "updated_by",
            "updated_by_role",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "employee",
            "total_hours",
            "updated_by",
            "updated_by_role",
            "created_at",
            "updated_at",
        ]

    # ==================================================
    # UPDATED BY
    # ==================================================

    def get_updated_by(self, obj):

        if not obj.updated_by:
            return None

        user = obj.updated_by

        return (
            getattr(user, "company_name", None)
            or getattr(user, "username", None)
            or getattr(user, "email", None)
            or getattr(user, "name", None)
            or str(user)
        )

    # ==================================================
    # UPDATED BY ROLE
    # ==================================================

    def get_updated_by_role(self, obj):

        if not obj.updated_by:
            return None

        user = obj.updated_by

        if getattr(user, "is_superadmin", False):
            return "Super Admin"

        if getattr(user, "is_hr_admin", False):
            return "HR Admin"

        if getattr(user, "is_hr", False):
            return "HR"

        return "User"