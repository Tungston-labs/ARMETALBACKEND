from rest_framework import serializers
from .models import LeaveRequest
from employee.models import Employee_db

class EmployeeBasicSerializer(serializers.ModelSerializer):
    department = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Employee_db
        fields = '__all__'

# class LeaveRequestSerializer(serializers.ModelSerializer):
#     employee = EmployeeBasicSerializer(read_only=True)
#     department_id = serializers.SerializerMethodField()

#     class Meta:
#         model = LeaveRequest
#         fields = '__all__'  # keep everything
#         read_only_fields = ['employee']

#     def get_department_id(self, obj):
#         return obj.employee.department.id if obj.employee and obj.employee.department else None

class LeaveRequestSerializer(serializers.ModelSerializer):
    employee = EmployeeBasicSerializer(read_only=True)
    department_id = serializers.SerializerMethodField()
    leave_days = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = '__all__'
        read_only_fields = ['employee']

    def get_department_id(self, obj):
        return (
            obj.employee.department.id
            if obj.employee and obj.employee.department
            else None
        )

    def get_leave_days(self, obj):
        if not obj.from_date or not obj.to_date:
            return 0

        # Same date
        if obj.from_date == obj.to_date:

            # Same-day half-day leave
            if (
                obj.from_date_type in ['morning', 'afternoon']
                and obj.to_date_type in ['morning', 'afternoon']
            ):
                return 0.5

            # Same-day full-day leave
            return 1

        # Multiple days
        days = (obj.to_date - obj.from_date).days + 1

        # First day is half-day
        if obj.from_date_type in ['morning', 'afternoon']:
            days -= 0.5

        # Last day is half-day
        if obj.to_date_type in ['morning', 'afternoon']:
            days -= 0.5

        return days
