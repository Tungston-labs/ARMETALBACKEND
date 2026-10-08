from decimal import Decimal

from django.db.models import Q, Sum
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ChartOfAccount
from .serializers import ChartOfAccountSerializer


class ChartOfAccountListCreateView(ListCreateAPIView):

    serializer_class = ChartOfAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        user = self.request.user

        queryset = (
            ChartOfAccount.objects
            .filter(company=user.company)
            .select_related(
                "parent_account",
                "company",
                "created_by",
            )
        )

        # Search by account name
        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(account_name__icontains=search)
                |
                Q(account_code__icontains=search)
            )

        # Filter by account type
        account_type = self.request.query_params.get(
            "account_type"
        )

        if account_type:
            queryset = queryset.filter(
                account_type=account_type
            )

        # Filter by status
        status_value = self.request.query_params.get(
            "status"
        )

        if status_value:
            queryset = queryset.filter(
                status=status_value
            )

        return queryset

    def list(self, request, *args, **kwargs):

        queryset = self.filter_queryset(
            self.get_queryset()
        )

        serializer = self.get_serializer(
            queryset,
            many=True
        )

        grouped_accounts = {
            "asset": [],
            "liability": [],
            "equity": [],
            "revenue": [],
            "expense": [],
        }

        totals = {
            "asset": Decimal("0.00"),
            "liability": Decimal("0.00"),
            "equity": Decimal("0.00"),
            "revenue": Decimal("0.00"),
            "expense": Decimal("0.00"),
        }

        for account_data in serializer.data:

            account_type = account_data["account_type"]

            if account_type in grouped_accounts:

                grouped_accounts[
                    account_type
                ].append(account_data)

                totals[account_type] += Decimal(
                    str(account_data["balance"])
                )

        return Response({
            "count": queryset.count(),

            "totals": {
                "asset": str(totals["asset"]),
                "liability": str(totals["liability"]),
                "equity": str(totals["equity"]),
                "revenue": str(totals["revenue"]),
                "expense": str(totals["expense"]),
            },

            "sections": {
                "asset": grouped_accounts["asset"],
                "liability": grouped_accounts["liability"],
                "equity": grouped_accounts["equity"],
                "revenue": grouped_accounts["revenue"],
                "expense": grouped_accounts["expense"],
            }
        })

    def perform_create(self, serializer):

        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user
        )



from django.db.models import Count
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import models
from .models import ChartOfAccount


class ChartOfAccountKPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        company = request.user.company

        queryset = ChartOfAccount.objects.filter(
            company=company
        )

        kpis = queryset.aggregate(
            total_accounts=Count("id"),

            active_accounts=Count(
                "id",
                filter=models.Q(status="active")
            ),

            asset_accounts=Count(
                "id",
                filter=models.Q(account_type="asset")
            ),

            liability_accounts=Count(
                "id",
                filter=models.Q(account_type="liability")
            ),

            equity_accounts=Count(
                "id",
                filter=models.Q(account_type="equity")
            ),
        )

        return Response(
            {
                "total_accounts": kpis["total_accounts"],
                "active_accounts": kpis["active_accounts"],
                "asset_accounts": kpis["asset_accounts"],
                "liability_accounts": kpis["liability_accounts"],
                "equity_accounts": kpis["equity_accounts"],
            },
            status=status.HTTP_200_OK
        )