
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.accounting.models import ChartOfAccount
from finance.journal.models import JournalEntryLine


ZERO = Decimal("0.00")
MONEY_FIELD = DecimalField(max_digits=18, decimal_places=2)

TYPE_ORDER = [
    ("asset", "Assets"),
    ("liability", "Liabilities"),
    ("revenue", "Income"),
    ("equity", "Equity"),
    ("expense", "Expenses"),
]


def money(value):
    return str(Decimal(value or ZERO).quantize(Decimal("0.01")))


def get_report_dates(request):
    today = timezone.localdate()
    default_start = date(today.year, 1, 1)

    raw_from = request.query_params.get("date_from")
    raw_to = request.query_params.get("date_to")

    try:
        date_from = (
            date.fromisoformat(raw_from) if raw_from else default_start
        )
        date_to = (
            date.fromisoformat(raw_to) if raw_to else today
        )
    except ValueError:
        raise ValidationError({
            "date": "Use valid dates in YYYY-MM-DD format."
        })

    if date_from > date_to:
        raise ValidationError({
            "date_to": "End date must be on or after the start date."
        })

    return date_from, date_to


def get_trial_balance_rows(company_id, date_from, date_to, params):
    # Only posted journal entries from the requested company and period.
    posted_period = Q(
        journal_entry_lines__journal_entry__company_id=company_id,
        journal_entry_lines__journal_entry__status="posted",
        journal_entry_lines__journal_entry__entry_date__gte=date_from,
        journal_entry_lines__journal_entry__entry_date__lte=date_to,
    )

    accounts = ChartOfAccount.objects.filter(
        company_id=company_id,
        status="active",
    ).annotate(
        period_debit=Coalesce(
            Sum(
                "journal_entry_lines__debit_amount",
                filter=posted_period,
            ),
            Value(ZERO),
            output_field=MONEY_FIELD,
        ),
        period_credit=Coalesce(
            Sum(
                "journal_entry_lines__credit_amount",
                filter=posted_period,
            ),
            Value(ZERO),
            output_field=MONEY_FIELD,
        ),
    )

    search = params.get("search", "").strip()
    account_type = params.get("type", "").strip().lower()

    if search:
        accounts = accounts.filter(
            Q(account_code__icontains=search)
            | Q(account_name__icontains=search)
        )

    valid_types = {value for value, _ in TYPE_ORDER}

    if account_type:
        if account_type not in valid_types:
            raise ValidationError({
                "type": (
                    "Invalid account type. Use asset, liability, "
                    "revenue, equity, or expense."
                )
            })
        accounts = accounts.filter(account_type=account_type)

    accounts = accounts.order_by("account_code")

    rows = []

    for account in accounts:
        opening_debit = (
            account.opening_balance
            if account.opening_balance_type == "debit"
            else ZERO
        )
        opening_credit = (
            account.opening_balance
            if account.opening_balance_type == "credit"
            else ZERO
        )

        gross_debit = opening_debit + account.period_debit
        gross_credit = opening_credit + account.period_credit

        net = gross_debit - gross_credit
        debit_balance = max(net, ZERO)
        credit_balance = max(-net, ZERO)

        rows.append({
            "account_id": account.id,
            "account_code": account.account_code,
            "account_name": account.account_name,
            "account_type": account.account_type,
            "account_type_label": dict(TYPE_ORDER)[account.account_type],
            "category": account.category,
            "debit_amount": debit_balance,
            "credit_amount": credit_balance,
        })

    return rows


def calculate_totals(rows):
    totals = {
        "total_debit": ZERO,
        "total_credit": ZERO,
        "asset": ZERO,
        "liability": ZERO,
        "revenue": ZERO,
        "equity": ZERO,
        "expense": ZERO,
    }

    for row in rows:
        debit = row["debit_amount"]
        credit = row["credit_amount"]

        totals["total_debit"] += debit
        totals["total_credit"] += credit

        account_type = row["account_type"]

        # Natural balance: debit for assets/expenses,
        # credit for liabilities/equity/revenue.
        if account_type in ("asset", "expense"):
            totals[account_type] += debit - credit
        else:
            totals[account_type] += credit - debit

    totals["difference"] = abs(
        totals["total_debit"] - totals["total_credit"]
    )

    totals["is_balanced"] = totals["difference"] == ZERO

    return totals


def serialize_totals(totals):
    result = {
        "total_debit": money(totals["total_debit"]),
        "total_credit": money(totals["total_credit"]),
        "difference": money(totals["difference"]),
        "is_balanced": totals["is_balanced"],
        "balance_status": (
            "Balanced" if totals["is_balanced"] else "Not Balanced"
        ),
    }

    for key in ("asset", "liability", "revenue", "equity", "expense"):
        result[f"total_{key}"] = money(totals[key])

    # Frontend-friendly alias.
    result["total_income"] = money(totals["revenue"])

    return result


class TrialBalanceDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = getattr(request.user, "company_id", None)

        if not company_id:
            raise ValidationError({
                "company": "Your user account is not linked to a company."
            })

        date_from, date_to = get_report_dates(request)

        # Dashboard totals are based on ALL active accounts,
        # not the list's search/type filters.
        rows = get_trial_balance_rows(
            company_id,
            date_from,
            date_to,
            {},
        )
        totals = calculate_totals(rows)

        return Response({
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            **serialize_totals(totals),
        })




class TrialBalanceListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = getattr(request.user, "company_id", None)

        if not company_id:
            return Response(
                {"detail": "User is not associated with a company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Pass the full request object
            date_from, date_to = get_report_dates(request)

            # Fetch all matching accounts without pagination
            rows = get_trial_balance_rows(
                company_id=company_id,
                date_from=date_from,
                date_to=date_to,
                params=request.query_params,
            )

        except ValidationError as exc:
            return Response(
                exc.detail,
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calculate totals across all matching accounts
        totals = calculate_totals(rows)
        summary = serialize_totals(totals)

        groups = []
        selected_type = request.query_params.get("type", "").strip().lower()

        # TYPE_ORDER is a list of tuples, so iterate directly
        for account_type, label in TYPE_ORDER:

            if selected_type and selected_type != account_type:
                continue

            category_accounts = [
                row for row in rows
                if row["account_type"] == account_type
            ]

            category_debit = sum(
                (row["debit_amount"] for row in category_accounts),
                ZERO,
            )
            category_credit = sum(
                (row["credit_amount"] for row in category_accounts),
                ZERO,
            )

            groups.append({
                "type": account_type,
                "label": label,
                "total_debit": money(category_debit),
                "total_credit": money(category_credit),
                "accounts": [
                    {
                        **account,
                        "debit_amount": money(account["debit_amount"]),
                        "credit_amount": money(account["credit_amount"]),
                    }
                    for account in category_accounts
                ],
            })

        return Response({
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "groups": groups,
            "grand_total_debit": summary["total_debit"],
            "grand_total_credit": summary["total_credit"],
            "difference": summary["difference"],
            "is_balanced": summary["is_balanced"],
            "balance_status": summary["balance_status"],
        })
