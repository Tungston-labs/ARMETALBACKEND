# users/permissions.py

from rest_framework import permissions

class IsHRAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_hr_admin or request.user.is_hr
        )


class IsEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_employee


class IsHRorIsEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_hr_admin or request.user.is_employee
        )
class IsCompanyActive(permissions.BasePermission):
    """
    Blocks API access if user account is inactive.
    Used globally.
    """
    message = "Your company subscription is inactive. Please contact admin."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if not user.is_active:
            return False

        return True

from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):

    def has_permission(self, request, view):

        return (
            request.user.is_authenticated
            and request.user.is_superadmin
        )