from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class CompanyJWTAuthentication(JWTAuthentication):

    def get_raw_token(self, header):
        parts = header.split()
        if len(parts) == 0:
            return None

        if len(parts) == 1:
            # Accepts raw token even if 'Bearer ' prefix was omitted in Swagger UI or client
            return parts[0]

        if len(parts) == 2:
            return parts[1]

        return super().get_raw_token(header)

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