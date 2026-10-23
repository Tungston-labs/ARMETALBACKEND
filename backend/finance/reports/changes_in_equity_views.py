
from datetime import date

from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .changes_in_equity import calculate_changes_in_equity
from .views import get_user_company_id, is_superadmin


class ChangesInEquityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_raw = request.query_params.get("start_date")
        end_raw = request.query_params.get("end_date")

        today = date.today()
        start_date = parse_date(start_raw) if start_raw else today.replace(day=1)
        end_date = parse_date(end_raw) if end_raw else today

        if not start_date or not end_date:
            return Response(
                {"detail": "Dates must use YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if start_date > end_date:
            return Response(
                {"detail": "start_date cannot be after end_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if is_superadmin(request.user):
            company_pk = request.query_params.get("company_pk")
            if not company_pk or not company_pk.isdigit():
                return Response(
                    {"detail": "A valid company_pk is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            company_pk = int(company_pk)
        else:
            company_pk = get_user_company_id(request.user)
            if not company_pk:
                return Response(
                    {"detail": "No company is associated with this user."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        report = calculate_changes_in_equity(
            company_id=company_pk,
            start_date=start_date,
            end_date=end_date,
        )
        return Response(report, status=status.HTTP_200_OK)
