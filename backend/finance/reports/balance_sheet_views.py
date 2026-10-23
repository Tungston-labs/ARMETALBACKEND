
#balance sheet

from datetime import date

from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .balance_sheet import calculate_balance_sheet


def get_user_company_id(user):
    """
    Resolve the company belonging to a non-superadmin user.

    Adjust this helper if your user-to-company relationship uses
    a different field or related name.
    """
    company_id = getattr(user, "company_id", None)

    if company_id:
        return company_id

    employee = getattr(user, "employee", None)
    if employee is not None:
        return getattr(employee, "company_id", None)

    return None


def is_superadmin(user):
    return bool(
        getattr(user, "is_super_admin", False)
        or getattr(user, "is_superadmin", False)
    )


class BalanceSheetView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        raw_date = request.query_params.get("as_of_date")

        if raw_date:
            as_of_date = parse_date(raw_date)

            if as_of_date is None:
                return Response(
                    {
                        "detail": (
                            "Invalid as_of_date. "
                            "Use YYYY-MM-DD, for example 2026-10-23."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            as_of_date = date.today()

        if is_superadmin(request.user):
            company_pk = request.query_params.get("company_pk")

            if not company_pk:
                return Response(
                    {
                        "detail": (
                            "company_pk is required for a superadmin."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                company_pk = int(company_pk)
                if company_pk <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                return Response(
                    {"detail": "company_pk must be a positive integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            company_pk = get_user_company_id(request.user)

            if not company_pk:
                return Response(
                    {
                        "detail": (
                            "No company is associated with this user. "
                            "Please check the user-company relationship."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            report = calculate_balance_sheet(
                company_id=company_pk,
                as_of_date=as_of_date,
            )
        except Exception:
            # Unexpected errors should be logged server-side.
            # Avoid exposing database details to API clients.
            import logging

            logging.getLogger(__name__).exception(
                "Failed to generate balance sheet for company %s",
                company_pk,
            )
            return Response(
                {"detail": "Unable to generate the balance sheet."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(report, status=status.HTTP_200_OK)
