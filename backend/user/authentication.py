from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class CompanyJWTAuthentication(JWTAuthentication):

    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        # User disabled
        if not user.is_active:
            raise AuthenticationFailed(
                "Your account has been disabled."
            )

        company = None

        # HR Admin / Company Admin
        if user.company:
            company = user.company

        # Employee
        elif hasattr(user, "employee_db"):
            employee = user.employee_db

            if (
                employee and
                employee.department and
                employee.department.company
            ):
                company = employee.department.company

        # Company frozen
        if company and not company.is_active:
            raise AuthenticationFailed(
                "Your company subscription has expired."
            )

        return user