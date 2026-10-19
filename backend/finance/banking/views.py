
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import BankAccount, BankTransaction, LoanAccount
from .serializers import (
    BankAccountSerializer,
    BankTransactionSerializer,
    LoanAccountSerializer,
)

ZERO = Decimal("0.00")


class BankingPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class BankingBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = BankingPagination

    date_field = "created_at__date"
    search_fields = ()
    status_field = "status"
    type_field = None
    bank_account_filter_field = None

    def company_id(self):
        company_id = getattr(self.request.user, "company_id", None)
        if not company_id:
            raise ValidationError({
                "detail": "Your user account is not linked to a company."
            })
        return company_id

    def date_range(self):
        params = self.request.query_params
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        start = parse_date(date_from) if date_from else None
        end = parse_date(date_to) if date_to else None

        if date_from and start is None:
            raise ValidationError({
                "date_from": "Use YYYY-MM-DD format."
            })
        if date_to and end is None:
            raise ValidationError({
                "date_to": "Use YYYY-MM-DD format."
            })
        if start and end and start > end:
            raise ValidationError({
                "date_to": "Must be on or after date_from."
            })
        return start, end

    def filter_dates(self, queryset, field, start, end):
        if start:
            queryset = queryset.filter(**{f"{field}__gte": start})
        if end:
            queryset = queryset.filter(**{f"{field}__lte": end})
        return queryset

    def get_queryset(self):
        queryset = self.company_queryset()
        start, end = self.date_range()
        queryset = self.filter_dates(
            queryset, self.date_field, start, end
        )

        params = self.request.query_params
        search = params.get("search", "").strip()

        if search and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": search})
            queryset = queryset.filter(query)

        status_value = params.get("status")
        if status_value and self.status_field:
            queryset = queryset.filter(
                **{self.status_field: status_value}
            )

        type_value = params.get("type")
        if type_value and self.type_field:
            queryset = queryset.filter(
                **{self.type_field: type_value}
            )

        bank_account_id = params.get("bank_account_id")
        if bank_account_id:
            if not bank_account_id.isdigit():
                raise ValidationError({
                    "bank_account_id": "Must be a positive integer."
                })
            queryset = queryset.filter(
                **{
                    self.bank_account_filter_field:
                        int(bank_account_id)
                }
            )

        return self.apply_extra_filters(queryset)

    def apply_extra_filters(self, queryset):
        return queryset

    def company_queryset(self):
        raise NotImplementedError

    def dashboard(self):
        company_id = self.company_id()
        start, end = self.date_range()
        today = timezone.localdate()

        accounts = BankAccount.objects.filter(company_id=company_id)
        loans = LoanAccount.objects.filter(
            bank_account__company_id=company_id
        )
        transactions = BankTransaction.objects.filter(
            company_id=company_id
        )

        # Apply a selected date range to accounts and loans.
        if start:
            accounts = accounts.filter(created_at__date__gte=start)
            loans = loans.filter(start_date__gte=start)
        if end:
            accounts = accounts.filter(created_at__date__lte=end)
            loans = loans.filter(start_date__lte=end)

        # Money-in and money-out default to the current month.
        transaction_start = start or today.replace(day=1)
        transaction_end = end or today
        transactions = transactions.filter(
            transaction_date__gte=transaction_start,
            transaction_date__lte=transaction_end,
        )

        return {
            "total_bank_accounts": accounts.count(),
            "total_loan_accounts": loans.count(),
            "money_in": (
                transactions.aggregate(total=Sum("money_in"))["total"]
                or ZERO
            ),
            "money_out": (
                transactions.aggregate(total=Sum("money_out"))["total"]
                or ZERO
            ),
            "loan_still_owed": (
                loans.aggregate(
                    total=Sum("outstanding_balance")
                )["total"] or ZERO
            ),
            "date_from": start or transaction_start,
            "date_to": end or transaction_end,
        }

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["dashboard"] = self.dashboard()
            return response

        return Response({
            "dashboard": self.dashboard(),
            "results": self.get_serializer(
                queryset, many=True
            ).data,
        })


class BankAccountViewSet(BankingBaseViewSet):
    serializer_class = BankAccountSerializer
    date_field = "created_at__date"
    search_fields = (
        "bank_name",
        "account_holder_name",
        "account_number",
        "iban",
        "branch",
    )
    status_field = "status"
    type_field = "bank_type"
    bank_account_filter_field = "id"

    def company_queryset(self):
        return BankAccount.objects.filter(
            company_id=self.company_id()
        )

    def apply_extra_filters(self, queryset):
        account_type = self.request.query_params.get("account_type")
        if account_type:
            queryset = queryset.filter(account_type=account_type)
        return queryset

    def perform_create(self, serializer):
        serializer.save(company_id=self.company_id())

    def perform_update(self, serializer):
        serializer.save(company_id=self.company_id())


class BankTransactionViewSet(BankingBaseViewSet):
    serializer_class = BankTransactionSerializer
    date_field = "transaction_date"
    search_fields = (
        "reference_number",
        "bank_account__bank_name",
        "description",
    )
    status_field = "status"
    type_field = "transaction_type"
    bank_account_filter_field = "bank_account_id"

    def company_queryset(self):
        return BankTransaction.objects.filter(
            company_id=self.company_id()
        ).select_related("bank_account")

    def perform_create(self, serializer):
        serializer.save(company_id=self.company_id())

    def perform_update(self, serializer):
        serializer.save(company_id=self.company_id())


class LoanAccountViewSet(BankingBaseViewSet):
    serializer_class = LoanAccountSerializer
    date_field = "start_date"
    search_fields = (
        "bank_account__bank_name",
        "bank_account__account_number",
        "loan_account_number",
    )
    status_field = "bank_account__status"
    type_field = "loan_type"
    bank_account_filter_field = "bank_account_id"

    def company_queryset(self):
        return LoanAccount.objects.filter(
            bank_account__company_id=self.company_id()
        ).select_related("bank_account")

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()
