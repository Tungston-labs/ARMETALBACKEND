from rest_framework import serializers
from .models import Department
from employee.models import Employee_db
from employee.serializers import EmployeeSerializer


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



class DepartmentSerializer(serializers.ModelSerializer):
    department_head = EmployeeSerializer(read_only=True)
    department_head_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee_db.objects.filter(is_deleted=False),
        source='department_head',
        write_only=True,
        required=False
    )

    employee_count = serializers.IntegerField(read_only=True)
    reimbursement_request_count = serializers.IntegerField(read_only=True)
    attendance_employee_count = serializers.IntegerField(read_only=True)
    leave_request_count = serializers.IntegerField(read_only=True)
    todays_leave_employee_count = serializers.IntegerField(read_only=True)  

    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ['company']


