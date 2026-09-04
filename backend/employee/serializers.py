from rest_framework import serializers
from user.models import User
from .models import ScheduleReminder
from django.db.models import Sum
from datetime import datetime
import random
import string
from .models import (
    Employee_db, EmpBankPaymentModel, EmpDocument, TempUpload
)
from departments.models import Department
from attendance.models import Attendance
from task.models import DailyTask
from leave.models import LeaveRequest,EmployeeLeaveBalance
from datetime import date, timedelta
from calendar import monthrange
from decimal import Decimal
from django.db import transaction, IntegrityError
def generate_password():
    return 'EMP' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
class SafeDateField(serializers.DateField):
    def to_representation(self, value):
        if isinstance(value, datetime):
            return value.date().isoformat()
        return super().to_representation(value)

class EmployeeSerializer(serializers.ModelSerializer):
    company = serializers.SerializerMethodField(read_only=True)

    dob = SafeDateField(required=False)
    joining_date = SafeDateField(required=False)
    visa_expiry_date = SafeDateField(required=False)

    iqama_number = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        validators=[]
    )

    aadar_number = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        validators=[]
    )

    insurance_number = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    employee_id = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[]
    )

    employee_code = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        validators=[]
    )

    email = serializers.EmailField(
        validators=[]
    )

    phno = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        validators=[]
    )

    passport_number = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        validators=[]
    )

    department_id = serializers.PrimaryKeyRelatedField(
        source='department',
        queryset=Department.objects.all(),
        write_only=True
    )

    department = serializers.CharField(
        source='department.name',
        read_only=True
    )

    is_head = serializers.SerializerMethodField(read_only=True)

    casual_leave = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        default=0,
    )

    sick_leave = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        default=0,
    )

    earned_leave = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        default=0,
    )

    maternity_leave = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        default=0,
    )

    other_leave = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        default=0,
    )

    class Meta:
        model = Employee_db
        exclude = ['user', 'password']

    def get_is_head(self, obj):
        return (
            obj.department
            and obj.department.department_head == obj
        )

    def get_company(self, obj):
        company = obj.department.company if obj.department else None
        if not company:
            return None

        return {
            "id": company.id,
            "name": company.name,
            "country": company.country,
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)

        balances = {
            balance.leave_type: balance.total_leave
            for balance in EmployeeLeaveBalance.objects.filter(
                employee=instance
            )
        }

        data["casual_leave"] = balances.get("casual", 0)
        data["sick_leave"] = balances.get("sick", 0)
        data["earned_leave"] = balances.get("earned", 0)
        data["maternity_leave"] = balances.get("maternity", 0)
        data["other_leave"] = balances.get("others", 0)

        return data

        # =====================================================
    # EMAIL VALIDATION
    # =====================================================

    def validate(self, data):

        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError({
                "detail": "Authentication is required."
            })

        company = getattr(request.user, "company", None)

        if not company:
            raise serializers.ValidationError({
                "company": "No company is associated with this user."
            })

        errors = {}

        # =====================================================
        # VALUES
        # =====================================================

        email = data.get("email")
        phno = data.get("phno")
        employee_id = data.get("employee_id")
        employee_code = data.get("employee_code")
        iqama_number = data.get("iqama_number")
        aadar_number = data.get("aadar_number")
        passport_number = data.get("passport_number")

        # Employee ID is automatically generated from email
        # inside Employee_db.save() if not provided.
        effective_employee_id = employee_id or email

        # =====================================================
        # EMAIL
        # =====================================================

        if email:

            employee_email_exists = Employee_db.objects.filter(
                email__iexact=email
            )

            user_email_exists = User.objects.filter(
                email__iexact=email
            )

            if self.instance:
                employee_email_exists = employee_email_exists.exclude(
                    pk=self.instance.pk
                )

                if self.instance.user_id:
                    user_email_exists = user_email_exists.exclude(
                        pk=self.instance.user_id
                    )

            if employee_email_exists.exists() or user_email_exists.exists():

                errors["email"] = "An employee with this email already exists."

        # =====================================================
        # PHONE
        # =====================================================

        if phno:

            qs = Employee_db.objects.filter(phno=phno)

            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                errors["phno"] = "This phone number is already registered."

        # =====================================================
        # EMPLOYEE ID
        # =====================================================

        if effective_employee_id:

            employee_id_exists = Employee_db.objects.filter(
                employee_id=effective_employee_id
            )

            user_username_exists = User.objects.filter(
                username=effective_employee_id
            )

            if self.instance:
                employee_id_exists = employee_id_exists.exclude(
                    pk=self.instance.pk
                )

                if self.instance.user_id:
                    user_username_exists = user_username_exists.exclude(
                        pk=self.instance.user_id
                    )

            if (
                employee_id_exists.exists()
                or user_username_exists.exists()
            ):
                errors["employee_id"] = (
                    "This employee ID is already in use."
                )

        # =====================================================
        # EMPLOYEE CODE
        # =====================================================

        if employee_code:

            qs = Employee_db.objects.filter(
                employee_code=employee_code
            )

            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                errors["employee_code"] = (
                    "This employee code is already in use."
                )

        # =====================================================
        # IQAMA
        # =====================================================

        if iqama_number:

            qs = Employee_db.objects.filter(
                iqama_number=iqama_number
            )

            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                errors["iqama_number"] = (
                    "This Iqama number is already registered."
                )

        # =====================================================
        # AADHAAR
        # =====================================================

        if aadar_number:

            qs = Employee_db.objects.filter(
                aadar_number=aadar_number
            )

            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                errors["aadar_number"] = (
                    "This Aadhaar number is already registered."
                )

        # =====================================================
        # PASSPORT
        # =====================================================

        if passport_number:

            qs = Employee_db.objects.filter(
                passport_number=passport_number
            )

            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                errors["passport_number"] = (
                    "This passport number is already registered."
                )

        # =====================================================
        # COUNTRY-SPECIFIC VALIDATION
        # =====================================================

        country = company.country

        if country == "IN":

            if not aadar_number:
                errors["aadar_number"] = (
                    "Aadhaar number is required for India."
                )

        elif country == "AE":

            if not iqama_number:
                errors["iqama_number"] = (
                    "Emirates ID is required for UAE."
                )

            if not data.get("visa_expiry_date"):
                errors["visa_expiry_date"] = (
                    "Visa expiry date is required."
                )

            if not data.get("insurance_number"):
                errors["insurance_number"] = (
                    "Insurance number is required for UAE."
                )

        else:

            if not passport_number:
                errors["passport_number"] = (
                    "Passport number is required for this country."
                )

            if not data.get("visa_expiry_date"):
                errors["visa_expiry_date"] = (
                    "Visa expiry date is required."
                )

            if not data.get("insurance_number"):
                errors["insurance_number"] = (
                    "Insurance number is required for this country."
                )

        # =====================================================
        # RETURN ALL VALIDATION ERRORS
        # =====================================================

        if errors:
            raise serializers.ValidationError(errors)

        return data





    def create(self, validated_data):

        casual_leave = validated_data.pop("casual_leave", 0)
        sick_leave = validated_data.pop("sick_leave", 0)
        earned_leave = validated_data.pop("earned_leave", 0)
        maternity_leave = validated_data.pop("maternity_leave", 0)
        other_leave = validated_data.pop("other_leave", 0)

        try:
            with transaction.atomic():

                # 1. CREATE EMPLOYEE FIRST
                employee = Employee_db.objects.create(
                    **validated_data
                )

                # 2. GENERATE PASSWORD
                password = generate_password()

                # 3. CREATE USER AFTER EMPLOYEE
                user = User.objects.create_user(
                    username=employee.employee_id,
                    email=employee.email,
                    password=password,
                    is_employee=True,
                    is_hr=employee.role == "hr",
                    company=(
                        employee.department.company
                        if employee.department
                        else None
                    )
                )

                # 4. LINK USER TO EMPLOYEE
                employee.user = user
                employee.password = password

                employee.save(
                    update_fields=["user", "password"]
                )

                # 5. CREATE LEAVE BALANCES
                leave_data = [
                    ("casual", casual_leave),
                    ("sick", sick_leave),
                    ("earned", earned_leave),
                    ("maternity", maternity_leave),
                    ("others", other_leave),
                ]

                total_leave = Decimal("0")

                for leave_type, total in leave_data:

                    total = Decimal(str(total or 0))

                    EmployeeLeaveBalance.objects.create(
                        employee=employee,
                        leave_type=leave_type,
                        total_leave=total,
                        used_leave=0,
                        remaining_leave=total
                    )

                    total_leave += total

                # 6. UPDATE TOTAL LEAVE
                employee.total_leave = total_leave

                employee.save(
                    update_fields=["total_leave"]
                )

                return employee

        except IntegrityError as e:
            raise serializers.ValidationError({
                "detail": (
                    "Unable to create employee. "
                    "One or more details already exist."
                )
            })

    def update(self, instance, validated_data):

        casual_leave = validated_data.pop("casual_leave", None)
        sick_leave = validated_data.pop("sick_leave", None)
        earned_leave = validated_data.pop("earned_leave", None)
        maternity_leave = validated_data.pop("maternity_leave", None)
        other_leave = validated_data.pop("other_leave", None)

        # Keep old role before updating
        old_role = instance.role

        employee_id = validated_data.get(
            "employee_id",
            instance.employee_id
        )

        # Update employee fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.employee_id = employee_id
        instance.save()

        # =====================================================
        # UPDATE USER is_hr WHEN EMPLOYEE ROLE CHANGES
        # =====================================================

        if instance.user:
            new_is_hr = instance.role == "hr"

            if instance.user.is_hr != new_is_hr:
                instance.user.is_hr = new_is_hr
                instance.user.save(update_fields=["is_hr"])

        # =====================================================
        # UPDATE LEAVE BALANCES
        # =====================================================

        leave_updates = {
            "casual": casual_leave,
            "sick": sick_leave,
            "earned": earned_leave,
            "maternity": maternity_leave,
            "others": other_leave,
        }

        total_leave = Decimal("0")

        for leave_type, leave_total in leave_updates.items():

            balance, created = EmployeeLeaveBalance.objects.get_or_create(
                employee=instance,
                leave_type=leave_type,
                defaults={
                    "total_leave": leave_total or 0,
                    "used_leave": 0,
                    "remaining_leave": leave_total or 0,
                }
            )

            if leave_total is not None:

                leave_total = Decimal(str(leave_total))

                balance.total_leave = leave_total

                balance.remaining_leave = (
                    leave_total - balance.used_leave
                )

                if balance.remaining_leave < 0:
                    balance.remaining_leave = 0

                balance.save()

            total_leave += balance.total_leave

        # Update total leave
        instance.total_leave = total_leave
        instance.save(update_fields=["total_leave"])

        return instance



class EmpBankPaymentSerializer(serializers.ModelSerializer):
    employee = EmployeeSerializer(read_only=True)
    class Meta:
        model = EmpBankPaymentModel
        fields = '__all__'
        read_only_fields = ['employee']



class TempUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = TempUpload
        fields = ['id', 'file']

class EmpDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmpDocument
        fields = [
            "employee",
            'passport_image1_url',
            'passport_image2_url',
            'insurance_image_url',
            'work_permit_urls',
            'contract_urls',
            'certificate_urls'
        ]
        read_only_fields = ['employee']





class DepartmentForProfileSerializer(serializers.ModelSerializer):
    head = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['name', 'head']

    def get_head(self, obj):
        return obj.department_head.name if obj.department_head else None




class EmployeeProfileSerializer(serializers.ModelSerializer):
    department = DepartmentForProfileSerializer()
    company_logo = serializers.SerializerMethodField()

    class Meta:
        model = Employee_db
        exclude = ['password']

    def get_company_logo(self, obj):
        company = obj.user.company
        if company and company.logo:
            request = self.context.get("request")
            return request.build_absolute_uri(company.logo.url) if request else company.logo.url
        return None





class EmployeeDocumentSummarySerializer(serializers.ModelSerializer):
    healthcard_number = serializers.CharField(source='insurance_number', allow_null=True)
    work_permit_urls = serializers.SerializerMethodField()
    contract_urls = serializers.SerializerMethodField()
    passport_number = serializers.CharField(allow_null=True)
    iqama_number = serializers.CharField(allow_null=True)
    aadar_number = serializers.CharField(allow_null=True)
    visa_expiry_date = serializers.DateField(allow_null=True)
    contract_expiry_date = serializers.DateField(allow_null=True)
    insurance_image_url = serializers.SerializerMethodField()
    id_card_image_url = serializers.SerializerMethodField()
    employee_id = serializers.IntegerField(source='id')


    class Meta:
        model = Employee_db
        fields = [
            'employee_id',
            'name',
            'healthcard_number',
            'passport_number',
            'iqama_number',
            'aadar_number',
            'contract_expiry_date',
            'visa_expiry_date',
            'work_permit_urls',
            'contract_urls',
            'insurance_image_url',
            'id_card_image_url',
        ]

    def get_work_permit_urls(self, obj):
        return getattr(getattr(obj, 'documents', None), 'work_permit_urls', [])

    def get_contract_urls(self, obj):
        return getattr(getattr(obj, 'documents', None), 'contract_urls', [])

    def get_insurance_image_url(self, obj):
        return getattr(getattr(obj, 'documents', None), 'insurance_image_url', None)

    def get_id_card_image_url(self, obj):
        if obj.idcard:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.idcard.url) if request else obj.idcard.url
        return None

from rest_framework import serializers
from datetime import date, timedelta
from calendar import day_name

from employee.models import Employee_db
from attendance.models import Attendance
from task.models import DailyTask
from leave.models import LeaveRequest


class EmployeeDashboardSerializer(serializers.ModelSerializer):
    profile_pic = serializers.SerializerMethodField()
    department = serializers.CharField(source="department.name", read_only=True)
    contract = serializers.SerializerMethodField()
    salary = serializers.SerializerMethodField()
    pending_leave = serializers.SerializerMethodField()
    leave_taken = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()
    attendance_graph = serializers.SerializerMethodField()
    task_graph = serializers.SerializerMethodField()
    aadar_number = serializers.SerializerMethodField()
    iqama_number = serializers.SerializerMethodField()
    pan_number = serializers.SerializerMethodField()
    account_number = serializers.SerializerMethodField()
    passport_number = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()


    class Meta:
        model = Employee_db
        fields = [
            "id",
            "profile_pic",
            "name",
            "address",
            "phno",
            "email",
            "employee_id",
            "designation",
            "joining_date",
            "dob",                             
            "aadar_number",                    
            "iqama_number",                     
            "pan_number",                     
            "account_number",                   
            "passport_number",                  
            "department",
            "role",
            "salary",
            "contract",
            "visa_expiry_date",
            "leave_taken",
            "pending_leave",
            "projects",
            "attendance_graph",
            "task_graph",
            "is_active",
        ]

    # -------------------------
    #  FULL PROFILE PIC URL
    # -------------------------
    def get_profile_pic(self, obj):
        request = self.context.get("request")
        if obj.profile_pic:
            return request.build_absolute_uri(obj.profile_pic.url)
        return None

    # -------------------------
    #  BANK DETAILS
    # -------------------------
    def get_salary(self, obj):
        if hasattr(obj, "bank_details") and obj.bank_details:
            return float(obj.bank_details.basic_salary)
        return None

    def get_account_number(self, obj):
        if hasattr(obj, "bank_details") and obj.bank_details:
            return obj.bank_details.account_number
        return None

    def get_pan_number(self, obj):
        if hasattr(obj, "bank_details") and obj.bank_details:
            return obj.bank_details.pan_number
        return None

    # -------------------------
    #  PERSONAL FIELDS
    # -------------------------
    def get_aadar_number(self, obj):
        return obj.aadar_number

    def get_iqama_number(self, obj):
        return obj.iqama_number

    def get_passport_number(self, obj):
        return obj.passport_number

    # -------------------------
    #  CONTRACT
    # -------------------------
    def get_contract(self, obj):
        return obj.contract_expiry_date

    # -------------------------
    #  LEAVES
    # -------------------------
    def get_leave_taken(self, obj):
        approved = LeaveRequest.objects.filter(employee=obj, status="approved")
        taken = sum([leave.calculate_leave_days() for leave in approved])
        return float(taken)

    def get_pending_leave(self, obj):
        return float(obj.total_leave or 0)

    # -------------------------
    #  PROJECTS
    # -------------------------
    def get_projects(self, obj):
        projects = obj.projects.all()

        ongoing_count = projects.filter(status="in_progress").count()
        completed_count = projects.filter(status="completed").count()

        return {
            "ongoing_count": ongoing_count,
            "completed_count": completed_count
        }



    # -------------------------
    #  ATTENDANCE GRAPH
    # -------------------------
    def get_attendance_graph(self, obj):
        today = date.today()
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)

        graph = {day: 0 for day in day_name}

        attendance = Attendance.objects.filter(
            employee=obj,
            date__range=[start_week, end_week]
        )

        for att in attendance:
            weekday = day_name[att.date.weekday()]
            graph[weekday] += float(att.total_hours or 0)

        return graph

    # -------------------------
    #  TASK GRAPH
    # -------------------------
    def get_task_graph(self, obj):
        today = date.today()
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)

        graph = {day: 0 for day in day_name}

        tasks = DailyTask.objects.filter(
            employee=obj,
            created_at__date__range=[start_week, end_week]
        )

        for task in tasks:
            weekday = day_name[task.created_at.weekday()]
            graph[weekday] += float(task.time_taken or 0)

        return graph
    
    #------------------ IS ACTIVE STATUS ------------------------------------
    
    def get_is_active(self, obj):
        today = date.today()

        attendance = Attendance.objects.filter(employee=obj, date=today).first()
        if not attendance:
            return False

        # Employee is active if any session has punch in but no punch-out
        return attendance.sessions.filter(time_in__isnull=False, time_out__isnull=True).exists()





class ScheduleReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleReminder
        fields = '__all__'
        read_only_fields = ('employee', 'created_at', 'notified')


# serializers.py

from rest_framework import serializers
from decimal import Decimal
from .models import SalaryIncrement,EmpBankPaymentModel


class SalaryIncrementSerializer(serializers.ModelSerializer):

    class Meta:
        model = SalaryIncrement
        fields = "__all__"
        read_only_fields = ["total_salary"]

    def create(self, validated_data):
        employee = validated_data["employee"]
        increment_amount = Decimal(validated_data["increment_amount"])

        # Get last increment
        last_increment = SalaryIncrement.objects.filter(
            employee=employee
        ).order_by("-date").first()

        if last_increment:
            base_salary = last_increment.total_salary
        else:
            # First increment → take from bank model
            bank = EmpBankPaymentModel.objects.get(employee=employee)
            base_salary = bank.basic_salary

        total_salary = base_salary + increment_amount

        validated_data["total_salary"] = total_salary

        return super().create(validated_data)
    



class DeletedEmployeeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(
        source="department.name",
        read_only=True
    )
    exit_date = serializers.DateTimeField(
        source="deleted_at",
        read_only=True
    )

    class Meta:
        model = Employee_db
        fields = [
             "id",   
            "name",
            "employee_id",
            "employee_code",
            "email",
            "department_name",
            "exit_date",
        ]
