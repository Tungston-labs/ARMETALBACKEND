from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

from django.db import IntegrityError
from django.core.exceptions import ValidationError

import traceback


def custom_exception_handler(exc, context):

    # Let DRF handle its normal exceptions first
    response = exception_handler(exc, context)

    if response is not None:
        return response

    # =====================================================
    # DATABASE ERRORS
    # =====================================================

    if isinstance(exc, IntegrityError):

        error_message = str(exc).lower()

        print("\n========== INTEGRITY ERROR ==========")
        print(error_message)
        print("=====================================\n")

        if "email" in error_message:
            message = {
                "email": ["Email already exists."]
            }

        elif "employee_id" in error_message:
            message = {
                "employee_id": ["Employee ID already exists."]
            }

        elif "employee_code" in error_message:
            message = {
                "employee_code": ["Employee code already exists."]
            }

        elif "phno" in error_message:
            message = {
                "phno": ["Phone number already exists."]
            }

        elif "aadar_number" in error_message:
            message = {
                "aadar_number": ["Aadhaar number already exists."]
            }

        elif "iqama_number" in error_message:
            message = {
                "iqama_number": ["Iqama number already exists."]
            }

        else:
            message = {
                "detail": "Database integrity error.",
                "error": error_message
            }

        return Response(
            message,
            status=status.HTTP_400_BAD_REQUEST
        )

    # =====================================================
    # DJANGO VALIDATION
    # =====================================================

    if isinstance(exc, ValidationError):

        print("\n========== VALIDATION ERROR ==========")
        print(str(exc))
        print("======================================\n")

        return Response(
            {
                "detail": str(exc)
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # =====================================================
    # UNKNOWN ERRORS
    # =====================================================

    print("\n========== UNKNOWN SERVER ERROR ==========")
    print("Exception type:", type(exc))
    print("Exception:", repr(exc))
    traceback.print_exc()
    print("==========================================\n")

    return Response(
        {
            "detail": str(exc)
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )