from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model

User = get_user_model()
from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    username_field = User.USERNAME_FIELD  # usually 'username' or 'email'

    @classmethod
    def get_token(cls, user):

        token = super().get_token(user)

        # =====================================================
        # USER ROLES IN JWT
        # =====================================================

        token['is_superadmin'] = user.is_superadmin
        token['is_hr_admin'] = user.is_hr_admin
        token['is_employee'] = user.is_employee
        token['is_hr'] = user.is_hr

        return token

    def validate(self, attrs):

        username = attrs.get("username")
        password = attrs.get("password")

        request = self.context['request']

        fcm_token = request.data.get("fcm_token")

        # =====================================================
        # AUTHENTICATE USER
        # =====================================================

        user = authenticate(
            username=username,
            password=password
        )

        if user is None:
            raise serializers.ValidationError(
                "Invalid username or password"
            )

        # =====================================================
        # CHECK USER ACTIVE
        # =====================================================

        if not user.is_active:
            raise serializers.ValidationError(
                "Your account has been disabled."
            )

        # =====================================================
        # FIND COMPANY
        # =====================================================

        company = None
        employee = None

        # -----------------------------------------------------
        # COMPANY / HR ADMIN
        # -----------------------------------------------------

        if user.company:
            company = user.company

        # -----------------------------------------------------
        # EMPLOYEE / HR
        # -----------------------------------------------------

        elif hasattr(user, "employee_profile"):

            employee = user.employee_profile

            if (
                employee
                and employee.department
                and employee.department.company
            ):
                company = employee.department.company

        # =====================================================
        # CHECK COMPANY SUBSCRIPTION
        # =====================================================

        if company and not company.is_active:
            raise serializers.ValidationError(
                "Your company's subscription has expired."
            )

        # =====================================================
        # UPDATE FCM TOKEN
        # =====================================================

        if fcm_token:

            user.fcm_token = fcm_token

            user.save(
                update_fields=["fcm_token"]
            )

        # =====================================================
        # GENERATE JWT
        # =====================================================

        data = super().validate(attrs)

        # =====================================================
        # FIND COMPANY AND EMPLOYEE
        # =====================================================

        company = None
        employee = None

        # Always check employee profile first
        if hasattr(user, "employee_profile"):
            employee = user.employee_profile

        # Company/Admin users have company directly
        if user.company:
            company = user.company

        # Employee users may get company through department
        elif (
            employee
            and employee.department
            and employee.department.company
        ):
            company = employee.department.company


        # =====================================================
        # CHECK COMPANY SUBSCRIPTION
        # =====================================================

        if company and not company.is_active:
            raise serializers.ValidationError(
                "Your company's subscription has expired."
            )


        # =====================================================
        # COMPANY MODULES
        # =====================================================

        company_modules = company.modules if company else {}


        # =====================================================
        # DISPLAY NAME
        # =====================================================

        if employee and user.is_employee:
            # HR employee or normal employee
            display_name = employee.name

        elif company:
            # Company Admin / HR Admin
            display_name = company.name

        else:
            display_name = user.username


        # =====================================================
        # USER RESPONSE
        # =====================================================

        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,

            'name': display_name,

            'is_superadmin': user.is_superadmin,
            'is_hr_admin': user.is_hr_admin,
            'is_employee': user.is_employee,
            'is_hr': user.is_hr,

            'company_modules': company_modules,

            'fcm_token': user.fcm_token,

            'company': {
                'id': company.id if company else None,
                'name': company.name if company else None,
                'location': company.location if company else None,
                'country': company.country if company else None,
                'logo': (
                    request.build_absolute_uri(company.logo.url)
                    if company and company.logo
                    else None
                )
            }
        }

        return data


from rest_framework import serializers
from .models import OTP, User

class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data
