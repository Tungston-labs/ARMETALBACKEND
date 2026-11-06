from rest_framework import serializers
from .models import Department
from hr.employee.models import Employee_db


class DepartmentMiniSerializer(serializers.ModelSerializer):
    total_employee_count = serializers.IntegerField(read_only=True)
    swiped_employee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "total_employee_count",
            "swiped_employee_count",
        ]


class DepartmentAttendanceSerializer(serializers.ModelSerializer):
    attendance_employee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = ["id", "name", "attendance_employee_count"]


class DepartmentHeadSerializer(serializers.ModelSerializer):
    """Only the fields needed to show a department head (no passport/Aadhaar/etc.)."""
    profile_pic = serializers.SerializerMethodField()

    class Meta:
        model = Employee_db
        fields = ["id", "name", "email", "employee_id", "designation", "profile_pic"]

    def get_profile_pic(self, obj):
        if not obj.profile_pic:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.profile_pic.url) if request else obj.profile_pic.url


class DepartmentSerializer(serializers.ModelSerializer):
    department_head = DepartmentHeadSerializer(read_only=True)
    department_head_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee_db.objects.filter(is_deleted=False),
        source="department_head",
        write_only=True,
        required=False,
        allow_null=True,
    )

    employee_count = serializers.IntegerField(read_only=True)
    reimbursement_request_count = serializers.IntegerField(read_only=True)
    attendance_employee_count = serializers.IntegerField(read_only=True)
    leave_request_count = serializers.IntegerField(read_only=True)
    todays_leave_employee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = "__all__"
        read_only_fields = ["company"]

    def _company(self):
        request = self.context.get("request")
        return getattr(request.user, "company", None) if request else None

    def validate_department_code(self, value):
        company = self._company()
        if not company:
            raise serializers.ValidationError("No company is associated with this user.")

        qs = Department.objects.filter(company=company, department_code__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                "This department code is already used in your company."
            )
        return value

    def validate_department_head_id(self, head):
        # head can be None when the client clears the department head
        if head is None:
            return head

        company = self._company()
        if (
            not company
            or head.department is None
            or head.department.company_id != company.id
        ):
            raise serializers.ValidationError("This employee does not belong to your company.")
        return head