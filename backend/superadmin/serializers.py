from rest_framework import serializers
from .models import Company,CompanySubscription,SubscriptionPlan
from user.models import User
from calendar import month_name
from rest_framework import serializers
from django.core.mail import send_mail
from django.conf import settings
from datetime import date, timedelta
import calendar
from django.utils.timezone import now
from django.conf import settings
from django.core.mail import send_mail
import json
from decimal import Decimal
from finance.models import FinanceCategory
from employee.models import Employee_db


COUNTRY_CURRENCY = {
    "IN": "INR",
    "AE": "AED",
    "US": "USD",
    "SG": "SGD",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "JP": "JPY",
    "CN": "CNY",
    "AU": "AUD",
    "CA": "CAD",
}


def get_currency_for_country(country):
    return COUNTRY_CURRENCY.get(country, "INR")



class CompanyCreateSerializer(serializers.ModelSerializer):
    number_of_employees = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    plan_name = serializers.CharField(
        source="plan.name",
        read_only=True
    )

    class Meta:
        model = Company
        fields = [
            "id",
            "company_id",
            "name",
            "address",
            "location",
            "contact_number",
            "country",
            "currency",
            "logo",
            "email",
            "modules",
            "latitude",
            "longitude",
            "number_of_employees",
            "default_password",
            "created_at",
            "updated_at",
            "amount_per_employee",
            "initial_payment",
            "basic_salary_percent",
            "house_allowance_percent",
            "transport_allowance_percent",
            "special_allowance_percent",
            "working_hours_per_day",
            "half_day_hours",
            "is_active",
            "plan",
            "plan_name",
        ]

        read_only_fields = [
            "id",
            "company_id",
            "number_of_employees",
            "default_password",
            "created_at",
            "updated_at",
        ]

        extra_kwargs = {
            "modules": {"required": True},
            "amount_per_employee": {"required": False},
            "initial_payment": {"required": False},
            "plan": {"required": False},
        }
    def validate(self, attrs):

        # ---------------------------------------------------------
        # PLAN / AMOUNT PER EMPLOYEE
        # ---------------------------------------------------------

        plan = attrs.get("plan", getattr(self.instance, "plan", None))

        ape = self.initial_data.get("amount_per_employee")
        ip = self.initial_data.get("initial_payment")

        # If a plan is selected, amount_per_employee is optional.
        # The plan pricing will be used.
        if plan:
            if ape not in [None, ""]:
                try:
                    attrs["amount_per_employee"] = Decimal(ape)
                except Exception:
                    raise serializers.ValidationError({
                        "amount_per_employee": "Enter a valid amount."
                    })

        else:
            # No plan → amount per employee is required
            if self.instance:
                current_amount = self.instance.amount_per_employee

                if ape in [None, ""]:
                    if not current_amount or current_amount <= 0:
                        raise serializers.ValidationError({
                            "amount_per_employee":
                                "Amount per employee is required when no plan is selected."
                        })
            else:
                if ape in [None, ""]:
                    raise serializers.ValidationError({
                        "amount_per_employee":
                            "Amount per employee is required when no plan is selected."
                    })

            if ape not in [None, ""]:
                try:
                    amount = Decimal(ape)

                    if amount <= 0:
                        raise serializers.ValidationError({
                            "amount_per_employee":
                                "Enter a valid amount greater than 0."
                        })

                    attrs["amount_per_employee"] = amount

                except serializers.ValidationError:
                    raise

                except Exception:
                    raise serializers.ValidationError({
                        "amount_per_employee": "Enter a valid amount."
                    })

        # ---------------------------------------------------------
        # INITIAL PAYMENT
        # ---------------------------------------------------------

        if ip not in [None, ""]:
            attrs["initial_payment"] = Decimal(ip)

        # ---------------------------------------------------------
        # SALARY PERCENTAGE VALIDATION
        # ---------------------------------------------------------

        basic = attrs.get("basic_salary_percent", 0)
        hra = attrs.get("house_allowance_percent", 0)
        transport = attrs.get("transport_allowance_percent", 0)
        special = attrs.get("special_allowance_percent", 0)

        total_percent = basic + hra + transport + special

        if total_percent > 100:
            raise serializers.ValidationError(
                "Total salary percentage cannot exceed 100%."
            )

        # ---------------------------------------------------------
        # WORKING HOURS VALIDATION
        # ---------------------------------------------------------

        working_hours = attrs.get("working_hours_per_day")
        half_day_hours = attrs.get("half_day_hours")

        if working_hours and half_day_hours:
            if half_day_hours >= working_hours:
                raise serializers.ValidationError(
                    "Half day hours must be less than working hours per day."
                )

        return attrs

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------
    def create(self, validated_data):

        modules = self.initial_data.get("modules")

        if isinstance(modules, str):
            validated_data["modules"] = json.loads(modules)

        company = Company.objects.create(**validated_data)

        # -------------------------------------------------
        # Create HR Admin User
        # -------------------------------------------------
        User.objects.create_user(
            username=company.company_id,
            email=company.email,
            password=company.default_password,
            is_hr_admin=True,
            company=company,
        )

        # -------------------------------------------------
        # Create Default Finance Categories
        # -------------------------------------------------
        company_modules = company.modules or {}

        finance_enabled = (
            company_modules.get("finance") is True
            or company_modules.get("finance") == "true"
        )

        if finance_enabled:

            default_categories = [
                {
                    "name": "salary",
                    "payment_type": "OUT"
                },
                {
                    "name": "reimbursement",
                    "payment_type": "OUT"
                },
            ]

            for category in default_categories:

                FinanceCategory.objects.get_or_create(
                    company=company,
                    name=category["name"],
                    payment_type=category["payment_type"]
                )

        # -------------------------------------------------
        # Create Default Mock Reimbursement Data (HR Module)
        # -------------------------------------------------
        try:
            from departments.models import Department
            from employee.models import Employee_db
            from reimbursement.models import Reimbursement
            from datetime import date

            # 1. Create a default department
            dept = Department.objects.create(
                company=company,
                name="HR Department"
            )

            # 2. Create a mock employee
            emp = Employee_db.objects.create(
                name="Jane Doe",
                email=f"jane.doe.{company.company_id}@example.com",
                address="Dubai, UAE",
                dob=date(1995, 5, 15),
                gender="Female",
                designation="Senior HR Executive",
                department=dept,
                employment_type="Full-time",
            )

            # 3. Create mock reimbursements
            Reimbursement.objects.create(
                employee=emp,
                expense_category="TRAVEL",
                date=date.today(),
                amount=250.00,
                note="Travel allowance for client meeting",
                status="On Hold"
            )
            Reimbursement.objects.create(
                employee=emp,
                expense_category="MEALS",
                date=date.today(),
                amount=75.50,
                note="Client dinner meal reimbursement",
                status="In Verification"
            )
            Reimbursement.objects.create(
                employee=emp,
                expense_category="BILLS",
                date=date.today(),
                amount=120.00,
                note="Office internet connectivity bill",
                status="Approve"
            )

        except Exception as ex:
            print("Error creating default mock reimbursement data:", str(ex))

        # -------------------------------------------------
        # Send Mail
        # -------------------------------------------------
        try:
            send_mail(
                subject="Welcome to Rekory - Company Credentials",
                message=f"""
    Hi {company.name},

    Your company account has been successfully created.

    Login credentials:
    Username: {company.company_id}
    Password: {company.default_password}

    Regards,
    Rekory Team
    """,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[company.email],
                fail_silently=True,
            )

        except Exception:
            pass

        return company


    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------
    def update(self, instance, validated_data):

        modules = self.initial_data.get("modules")
        if isinstance(modules, str):
            validated_data["modules"] = json.loads(modules)

        old_email = instance.email
        new_email = validated_data.get("email", old_email)

        instance = super().update(instance, validated_data)

        # sync HR admin email
        if new_email != old_email:
            hr_user = User.objects.filter(company=instance, is_hr_admin=True).first()
            if hr_user:
                hr_user.email = new_email
                hr_user.save()

        return instance

    def get_number_of_employees(self, obj):
        return Employee_db.objects.filter(
            department__company=obj,
            is_deleted=False
        ).count()

    def get_currency(self, obj):
        return get_currency_for_country(obj.country)

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------
    def validate_modules(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Modules must be a dictionary")
        return value



 
class CompanySubscriptionSerializer(serializers.ModelSerializer):
    month_display = serializers.SerializerMethodField()

    class Meta:
        model = CompanySubscription
        fields = [
            "id",
            "company",
            "month",
            "month_display",
            "year",
            "employee_count",
            "amount_per_employee",
            "paid_date",
            "amount",
            "currency",
            "status",
        ]

    def get_month_display(self, obj):
        return month_name[obj.month]
    
class CompanyListSerializer(serializers.ModelSerializer):
    last_paid_date = serializers.SerializerMethodField()
    next_due_date = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id',
            'company_id',
            'name',
            'logo_url',
            'address',
            'contact_number',
            'number_of_employees',
            'last_paid_date',
            'next_due_date',
        ]

    def get_logo_url(self, obj):
        request = self.context.get('request', None)
        if obj.logo and hasattr(obj.logo, 'url'):
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None

    def get_last_paid_date(self, obj):
        last_paid = obj.subscriptions.filter(status="paid").order_by('-year', '-month').first()
        if last_paid and last_paid.paid_date:
            return last_paid.paid_date.isoformat()
        return None



    def get_next_due_date(self, obj):
        today = now().date()
        billing_day = obj.created_at.day

        year, month = today.year, today.month

        # last valid day of this month
        days_in_month = calendar.monthrange(year, month)[1]
        due_day = min(billing_day, days_in_month)

        due_date = date(year, month, due_day)

        # if already passed → move to next month
        if today > due_date:
            if month == 12:
                month, year = 1, year + 1
            else:
                month += 1

            days_in_month = calendar.monthrange(year, month)[1]
            due_day = min(billing_day, days_in_month)
            due_date = date(year, month, due_day)

        return due_date.isoformat()




class CompanySelfUpdateSerializer(serializers.ModelSerializer):
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "name",
            "address",
            "location",
            "latitude",
            "longitude",
            "country",
            "currency",
            "contact_number",
            "email",
            "modules",
            "logo",
            'amount_per_employee',   
            'initial_payment', 
            "basic_salary_percent",
            "house_allowance_percent",
            "transport_allowance_percent",
            "special_allowance_percent",
            "working_hours_per_day",
            "half_day_hours",
        ]
        extra_kwargs = {
            "email": {"required": False},
            "modules": {"required": False},
        }

    def get_currency(self, obj):
        return get_currency_for_country(obj.country)


class CompanySubscriptionActionSerializer(serializers.Serializer):

    company_id = serializers.IntegerField()

    action = serializers.ChoiceField(
        choices=[
            ("freeze", "Freeze"),
            ("unfreeze", "Unfreeze"),
        ]
    )


    def validate_company_id(self, value):

        if not Company.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                "Company not found"
            )

        return value
    




class SubscriptionReminderSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()


class SubscriptionReminderSimpleSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    email = serializers.EmailField(required=False, allow_blank=False)




from rest_framework import serializers
from .models import SubscriptionPlan


from rest_framework import serializers
from .models import SubscriptionFeature, SubscriptionPlan


class SubscriptionFeatureSerializer(serializers.ModelSerializer):

    class Meta:
        model = SubscriptionFeature
        fields = "__all__"

    def validate_name(self, value):
        queryset = SubscriptionFeature.objects.filter(
            name__iexact=value
        )

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "Feature already exists."
            )

        return value
    
from rest_framework import serializers
from .models import SubscriptionPlan, SubscriptionFeature


class SubscriptionPlanSerializer(serializers.ModelSerializer):

    features = SubscriptionFeatureSerializer(
        many=True,
        read_only=True
    )

    feature_ids = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionFeature.objects.filter(
            is_active=True
        ),
        many=True,
        write_only=True,
        source="features"
    )

    feature_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "name",
            "plan_type",
            "description",
            "base_price",
            "employee_limit",
            "extra_employee_price",
            "is_active",
            "status",
            "feature_count",
            "features",
            "feature_ids",
            "created_at",
            "updated_at",
        ]

    def get_feature_count(self, obj):
        return obj.features.count()

    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"

    def validate_name(self, value):
        queryset = SubscriptionPlan.objects.filter(
            name__iexact=value
        )

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "Plan already exists."
            )

        return value

    def validate_base_price(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Base price must be greater than 0."
            )
        return value

    def validate_extra_employee_price(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Extra employee price cannot be negative."
            )
        return value
