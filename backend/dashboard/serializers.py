from rest_framework import serializers
from datetime import date
from employee.models import Employee_db


class ContractExpirySerializer(serializers.ModelSerializer):
    days_left = serializers.SerializerMethodField()

    class Meta:
        model = Employee_db
        fields = ["name", "employee_id", "contract_expiry_date", "days_left"]

    def get_days_left(self, obj):
        if obj.contract_expiry_date:
            return (obj.contract_expiry_date - date.today()).days
        return None
