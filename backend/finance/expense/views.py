
from datetime import date

from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.db.models import DecimalField
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Expense
from .serializers import ExpenseSerializer


class ExpensePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ExpensePagination

    def get_queryset(self):
        company_id = getattr(self.request.user, "company_id", None)

        if not company_id:
            return Expense.objects.none()

        queryset = Expense.objects.filter(
            company_id=company_id
        ).select_related("paid_from_account")

        params = self.request.query_params

        # Date range filters
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        start_date = None
        end_date = None

        if date_from:
            start_date = date.fromisoformat(date_from) if self._valid_date(date_from) else None
            if start_date is None:
                raise ValidationError({
                    "date_from": "Enter a valid date in YYYY-MM-DD format."
                })

        if date_to:
            end_date = date.fromisoformat(date_to) if self._valid_date(date_to) else None
            if end_date is None:
                raise ValidationError({
                    "date_to": "Enter a valid date in YYYY-MM-DD format."
                })

        if start_date and end_date and start_date > end_date:
            raise ValidationError({
                "date_to": "End date must be on or after the start date."
            })

        if start_date:
            queryset = queryset.filter(expense_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(expense_date__lte=end_date)

        # Category and status filters
        category = params.get("category")
        if category:
            queryset = queryset.filter(category=category)

        expense_status = params.get("status")
        if expense_status:
            queryset = queryset.filter(status=expense_status)

        # Payment method filter
        paid_method = params.get("paid_method")
        if paid_method:
            queryset = queryset.filter(paid_method=paid_method)

        # Search
        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(expense_id__icontains=search)
                | Q(paid_to__icontains=search)
                | Q(description__icontains=search)
                | Q(category__icontains=search)
                | Q(paid_from_account__bank_name__icontains=search)
            )

        return queryset.order_by("-expense_date", "-id")

    @staticmethod
    def _valid_date(value):
        try:
            date.fromisoformat(value)
            return True
        except (TypeError, ValueError):
            return False

    def get_dashboard(self):
        company_id = getattr(self.request.user, "company_id", None)

        if not company_id:
            return {
                "total_expense": "0.00",
                "this_month_expense": "0.00",
                "already_paid": "0.00",
                "still_pay": "0.00",
                "biggest_cost": None,
            }

        params = self.request.query_params
        expenses = Expense.objects.filter(company_id=company_id)

        # Dashboard date range follows date_from/date_to.
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        if date_from and self._valid_date(date_from):
            expenses = expenses.filter(
                expense_date__gte=date.fromisoformat(date_from)
            )

        if date_to and self._valid_date(date_to):
            expenses = expenses.filter(
                expense_date__lte=date.fromisoformat(date_to)
            )

        def total(queryset):
            return queryset.aggregate(
                total=Coalesce(
                    Sum("amount"),
                    0,
                    output_field=DecimalField(
                        max_digits=14,
                        decimal_places=2,
                    ),
                )
            )["total"]

        today = timezone.localdate()
        month_expenses = Expense.objects.filter(
            company_id=company_id,
            expense_date__year=today.year,
            expense_date__month=today.month,
        )

        category_totals = (
            expenses.values("category")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )

        biggest = category_totals.first()

        return {
            "total_expense": str(total(expenses)),
            "this_month_expense": str(total(month_expenses)),
            "already_paid": str(
                total(expenses.filter(status="paid"))
            ),
            "still_pay": str(
                total(expenses.filter(status="unpaid"))
            ),
            "biggest_cost": (
                {
                    "category": biggest["category"],
                    "category_label": dict(
                        Expense.CATEGORY_CHOICES
                    ).get(biggest["category"], biggest["category"]),
                    "amount": str(biggest["total"] or 0),
                }
                if biggest
                else None
            ),
        }

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data["dashboard"] = self.get_dashboard()
        return response

    def perform_create(self, serializer):
        company_id = getattr(self.request.user, "company_id", None)
        if not company_id:
            raise ValidationError({
                "company": "Your user account is not linked to a company."
            })

        serializer.save(company_id=company_id)

    def perform_update(self, serializer):
        company_id = getattr(self.request.user, "company_id", None)
        if not company_id:
            raise ValidationError({
                "company": "Your user account is not linked to a company."
            })

        serializer.save(company_id=company_id)
