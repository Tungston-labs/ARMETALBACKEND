# tasks/serializers.py
from rest_framework import serializers
from .models import DailyTask
from employee.models import Employee_db

class DailyTaskSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(source='created', format='%Y-%m-%d %H:%M', read_only=True)
    class Meta:
        model = DailyTask
        fields = '__all__'
        read_only_fields = ['employee', 'created_at', 'upadted_at']

class EmployeeMiniSerializer(serializers.ModelSerializer):
    profile_pic = serializers.SerializerMethodField()

    class Meta:
        model = Employee_db
        fields = ["employee_id", "name", "profile_pic","id"]

    def get_profile_pic(self, obj):
        request = self.context.get('request')  # important
        if obj.profile_pic:                     # check if file exists
            if request:
                return request.build_absolute_uri(obj.profile_pic.url)
            else:
                return obj.profile_pic.url     # fallback to relative URL
        return None
