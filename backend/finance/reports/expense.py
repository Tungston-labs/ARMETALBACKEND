
# reports/expense.py

import calendar
from collections import defaultdict
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hr.reimbursement.models import Reimbursement
from user.permissions import IsCompanyActive, IsHRAdmin


ZERO = Decimal("0.00")

APPROVED_STATUSES = {"Approve"}
PENDING_APPROVAL_STATUSES = {"On Hold", "In Verification"}
REJECTED_STATUSES = {"Reject"}


def decimal_value(value):
    return value if value is not None else ZERO


def model_field_names(model):
    return {field.name for field in model._meta.get_fields()}


def first_existing_field(model, *names):
    available = model_field_names(model)
    return next((name for name in names if name in available), None)


def get_department_name(employee):
    department = getattr(employee, "department", None)

    if department is None:
        return None

    return (
        getattr(department, "name", None)
        or getattr(department, "department_name", None)
        or str(department)
    )


def get_payment_status_field():
    """
    Detect an existing payment-status field, if one is added to
    Reimbursement in the future.
    """
    return first_existing_field(
        Reimbursement,
        "payment_status",
        "reimbursement_payment_status",
    )


def get_paid_field():
    return first_existing_field(
        Reimbursement,
        "is_paid",
        "reimbursement_paid",
    )


def get_paid_date_field():
    return first_existing_field(
        Reimbursement,
        "paid_at",
        "payment_date",
        "reimbursement_paid_date",
    )


def get_claim_payment_status(claim):
    """
    Do not treat approval as proof of payment.
    """
    payment_status_field = get_payment_status_field()
    paid_field = get_paid_field()
    paid_date_field = get_paid_date_field()

    if payment_status_field:
        value = getattr(claim, payment_status_field, None)
        return str(value).lower() if value is not None else "pending"

    if paid_field:
        return "paid" if getattr(claim, paid_field, False) else "pending"

    if paid_date_field:
        return "paid" if getattr(claim, paid_date_field, None) else "pending"

    return "not_tracked"


def claim_is_paid(claim):
    return get_claim_payment_status(claim) == "paid"


class ExpenseReportView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    DEFAULT_PAGE_SIZE = 10
    MAX_PAGE_SIZE = 100

    def get(self, request):
        company_id = getattr(request.user, "company_id", None)

        if not company_id:
            return Response(
                {"detail": "Your account is not associated with a company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 1. Read and validate filters
        # -----------------------------------------------------
        try:
            date_from_value = request.query_params.get("date_from")
            date_to_value = request.query_params.get("date_to")

            date_from = (
                parse_date(date_from_value) if date_from_value else None
            )
            date_to = (
                parse_date(date_to_value) if date_to_value else None
            )

            if date_from_value and date_from is None:
                raise ValueError("date_from must use YYYY-MM-DD.")

            if date_to_value and date_to is None:
                raise ValueError("date_to must use YYYY-MM-DD.")

            chart_year = int(
                request.query_params.get(
                    "chart_year", timezone.localdate().year
                )
            )
            graph_year = int(
                request.query_params.get(
                    "graph_year", timezone.localdate().year
                )
            )

            page = int(request.query_params.get("page", 1))
            page_size = int(
                request.query_params.get(
                    "page_size", self.DEFAULT_PAGE_SIZE
                )
            )

        except (TypeError, ValueError) as exc:
            return Response(
                {"detail": str(exc) or "Invalid filter value."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if date_from and date_to and date_from > date_to:
            return Response(
                {"detail": "date_from cannot be later than date_to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if page < 1 or page_size < 1:
            return Response(
                {"detail": "page and page_size must be positive integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        page_size = min(page_size, self.MAX_PAGE_SIZE)

        department_filter = request.query_params.get("department")
        employee_filter = request.query_params.get("employee")
        category_filter = request.query_params.get("expense_category")
        expense_type_filter = request.query_params.get("expense_type")
        payment_status_filter = request.query_params.get("payment_status")
        approval_status_filter = request.query_params.get("approval_status")

        # This model currently stores reimbursements only. It has
        # no expense_type field for differentiating other expense types.
        if expense_type_filter and expense_type_filter.lower() not in {
            "reimbursement",
            "reimbursements",
        }:
            return Response(
                {
                    "detail": (
                        "Only reimbursement claims are available in the "
                        "provided model; other expense types are not tracked."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # 2. Company-scoped claims
        # Employee_db has a nullable user FK, so claims without a
        # linked user cannot be attributed to a company by this schema.
        # -----------------------------------------------------
        claims = Reimbursement.objects.filter(
            employee__user__company_id=company_id
        ).select_related(
            "employee",
            "employee__department",
            "employee__user",
        )

        # Exclude soft-deleted employees if this field exists.
        employee_fields = model_field_names(
            Reimbursement._meta.get_field("employee").remote_field.model
        )
        if "is_deleted" in employee_fields:
            claims = claims.filter(employee__is_deleted=False)

        # -----------------------------------------------------
        # 3. Apply filters
        # -----------------------------------------------------
        if date_from:
            claims = claims.filter(date__gte=date_from)

        if date_to:
            claims = claims.filter(date__lte=date_to)

        if department_filter:
            try:
                department_id = int(department_filter)
            except ValueError:
                return Response(
                    {"detail": "department must be a valid department ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            claims = claims.filter(employee__department_id=department_id)

        if employee_filter:
            try:
                employee_id = int(employee_filter)
            except ValueError:
                return Response(
                    {"detail": "employee must be a valid employee ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            claims = claims.filter(employee_id=employee_id)

        if category_filter:
            claims = claims.filter(expense_category=category_filter)

        if approval_status_filter:
            claims = claims.filter(status=approval_status_filter)

        claims = claims.order_by("-date", "-id")
        claim_list = list(claims)

        # Payment status can only be filtered if the model has a
        # corresponding payment-tracking field.
        if payment_status_filter:
            if not (
                get_payment_status_field()
                or get_paid_field()
                or get_paid_date_field()
            ):
                return Response(
                    {
                        "detail": (
                            "Payment status is not stored in the current "
                            "Reimbursement model. Add a payment-status "
                            "field or a reimbursement payment model before "
                            "using this filter."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            allowed_payment_statuses = {
                "paid", "pending", "not_tracked"
            }
            if payment_status_filter.lower() not in allowed_payment_statuses:
                return Response(
                    {
                        "detail": (
                            "payment_status must be paid or pending."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            claim_list = [
                claim for claim in claim_list
                if get_claim_payment_status(claim)
                == payment_status_filter.lower()
            ]

        # -----------------------------------------------------
        # 4. KPI cards
        # -----------------------------------------------------
        total_expense = sum(
            (decimal_value(claim.amount) for claim in claim_list),
            ZERO,
        )

        approved_claims = [
            claim for claim in claim_list
            if claim.status in APPROVED_STATUSES
        ]

        approved_expense_amount = sum(
            (decimal_value(claim.amount) for claim in approved_claims),
            ZERO,
        )

        pending_approval = sum(
            1 for claim in claim_list
            if claim.status in PENDING_APPROVAL_STATUSES
        )

        reimbursement_paid = sum(
            (
                decimal_value(claim.amount)
                for claim in claim_list
                if claim_is_paid(claim)
            ),
            ZERO,
        )

        kpis = {
            "total_expense": float(total_expense),
            "approved_expense_amount": float(approved_expense_amount),
            "pending_approval": pending_approval,
            "reimbursement_paid": float(reimbursement_paid),
            "total_expense_claim": len(claim_list),
        }

        # -----------------------------------------------------
        # 5. Table rows
        # -----------------------------------------------------
        table_rows = []

        for claim in claim_list:
            employee = claim.employee

            table_rows.append({
                "id": claim.pk,
                "date": claim.date,
                "employee_id": employee.pk,
                "employee_name": str(employee.name),
                "department_id": employee.department_id,
                "department": get_department_name(employee),
                "category": claim.expense_category,
                "amount": float(decimal_value(claim.amount)),
                "approval_status": claim.status,
                "payment_status": get_claim_payment_status(claim),
            })

        # -----------------------------------------------------
        # 6. Graph 1 - monthly expense trend
        # Independent of the table date range.
        # Uses the selected employee/department/category filters.
        # -----------------------------------------------------
        chart_claims = Reimbursement.objects.filter(
            employee__user__company_id=company_id,
            date__year=chart_year,
        ).select_related("employee")

        if "is_deleted" in employee_fields:
            chart_claims = chart_claims.filter(
                employee__is_deleted=False
            )

        if department_filter:
            chart_claims = chart_claims.filter(
                employee__department_id=int(department_filter)
            )

        if employee_filter:
            chart_claims = chart_claims.filter(
                employee_id=int(employee_filter)
            )

        if category_filter:
            chart_claims = chart_claims.filter(
                expense_category=category_filter
            )

        monthly_expenses = {month: ZERO for month in range(1, 13)}

        for item in chart_claims.values("date__month").annotate(
            total=Sum("amount")
        ):
            monthly_expenses[item["date__month"]] = decimal_value(
                item["total"]
            )

        expense_trend_graph = {
            calendar.month_name[month]: float(monthly_expenses[month])
            for month in range(1, 13)
        }

        # -----------------------------------------------------
        # 7. Graph 2 - expense vs paid reimbursement by month
        # Uses graph_year independently from chart_year.
        # -----------------------------------------------------
        graph_claims = Reimbursement.objects.filter(
            employee__user__company_id=company_id,
            date__year=graph_year,
        ).select_related("employee")

        if "is_deleted" in employee_fields:
            graph_claims = graph_claims.filter(
                employee__is_deleted=False
            )

        if department_filter:
            graph_claims = graph_claims.filter(
                employee__department_id=int(department_filter)
            )

        if employee_filter:
            graph_claims = graph_claims.filter(
                employee_id=int(employee_filter)
            )

        if category_filter:
            graph_claims = graph_claims.filter(
                expense_category=category_filter
            )

        monthly_comparison = {
            month: {
                "expense_amount": ZERO,
                "reimbursement_paid": ZERO,
            }
            for month in range(1, 13)
        }

        for claim in graph_claims:
            month = claim.date.month
            monthly_comparison[month]["expense_amount"] += (
                decimal_value(claim.amount)
            )

            if claim_is_paid(claim):
                monthly_comparison[month]["reimbursement_paid"] += (
                    decimal_value(claim.amount)
                )

        reimbursement_graph = {
            calendar.month_name[month]: {
                "expense_amount": float(
                    monthly_comparison[month]["expense_amount"]
                ),
                "reimbursement_paid": float(
                    monthly_comparison[month]["reimbursement_paid"]
                ),
            }
            for month in range(1, 13)
        }

        # -----------------------------------------------------
        # 8. Pagination
        # -----------------------------------------------------
        paginator = Paginator(table_rows, page_size)
        page_obj = paginator.get_page(page)

        results = []
        for row in page_obj.object_list:
            row = row.copy()
            row["date"] = row["date"].isoformat()
            results.append(row)

        # -----------------------------------------------------
        # 9. Response
        # -----------------------------------------------------
        return Response({
            "filters": {
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "department": department_filter,
                "employee": employee_filter,
                "expense_category": category_filter,
                "expense_type": expense_type_filter,
                "payment_status": payment_status_filter,
                "approval_status": approval_status_filter,
                "chart_year": chart_year,
                "graph_year": graph_year,
            },
            "kpis": kpis,
            "graphs": {
                "monthly_expense_trend": {
                    "year": chart_year,
                    "data": expense_trend_graph,
                },
                "expense_vs_reimbursement": {
                    "year": graph_year,
                    "data": reimbursement_graph,
                },
            },
            "pagination": {
                "count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page_obj.number,
                "page_size": page_size,
                "next_page": (
                    page_obj.next_page_number()
                    if page_obj.has_next() else None
                ),
                "previous_page": (
                    page_obj.previous_page_number()
                    if page_obj.has_previous() else None
                ),
            },
            "results": results,
        })
