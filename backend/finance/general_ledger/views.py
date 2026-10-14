# finance/general_ledger/views.py

from decimal import Decimal

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Sum, Count, DecimalField, Value
from django.db.models.functions import Coalesce

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from finance.journal.models import JournalEntryLine


class GeneralLedgerView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Assumes the logged-in user has a company ForeignKey.
        company_id = getattr(user, "company_id", None)

        if not company_id:
            return Response(
                {"detail": "Company is not associated with this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only posted journal entries belonging to this company.
        queryset = JournalEntryLine.objects.filter(
            journal_entry__company_id=company_id,
            journal_entry__status="posted",
        ).select_related(
            "journal_entry",
            "account",
        )

        # Date filters: YYYY-MM-DD
        
       
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if date_from:
            queryset = queryset.filter(
                journal_entry__entry_date__gte=date_from
            )

        if date_to:
            queryset = queryset.filter(
                journal_entry__entry_date__lte=date_to
            )


        # Account filter
        account_id = request.query_params.get("account_id")
        if account_id:
            queryset = queryset.filter(account_id=account_id)

        # Source filter
        source = request.query_params.get("source")
        if source:
            queryset = queryset.filter(
                journal_entry__source_module__iexact=source
            )

        # Account type filter: asset, liability, equity, revenue, expense
        account_type = request.query_params.get("type")
        if account_type:
            queryset = queryset.filter(
                account__account_type__iexact=account_type
            )

        # Search
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(journal_entry__reference_number__icontains=search)
                | Q(account__account_name__icontains=search)
                | Q(account__account_code__icontains=search)
                | Q(description__icontains=search)
                | Q(journal_entry__description__icontains=search)
                | Q(journal_entry__source_module__icontains=search)
            )

        # Calculate dashboard totals BEFORE pagination.
        totals = queryset.aggregate(
            total_lines=Count("id"),
            asset_lines=Count(
                "id",
                filter=Q(account__account_type="asset"),
            ),
            liability_lines=Count(
                "id",
                filter=Q(account__account_type="liability"),
            ),
            equity_lines=Count(
                "id",
                filter=Q(account__account_type="equity"),
            ),
            income_lines=Count(
                "id",
                filter=Q(account__account_type="revenue"),
            ),
            expense_lines=Count(
                "id",
                filter=Q(account__account_type="expense"),
            ),
            total_debit=Coalesce(
                Sum("debit_amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(
                    max_digits=15,
                    decimal_places=2,
                ),
            ),
            total_credit=Coalesce(
                Sum("credit_amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(
                    max_digits=15,
                    decimal_places=2,
                ),
            ),
        )

        total_debit = totals["total_debit"]
        total_credit = totals["total_credit"]

        dashboard = {
            "total_lines": totals["total_lines"],
            "asset_lines": totals["asset_lines"],
            "liability_lines": totals["liability_lines"],
            "equity_lines": totals["equity_lines"],
            "income_lines": totals["income_lines"],
            "expense_lines": totals["expense_lines"],
            "total_debit": str(total_debit),
            "total_credit": str(total_credit),
            "difference": str(total_debit - total_credit),
            "balance_status": (
                "balanced"
                if total_debit == total_credit
                else "not_balanced"
            ),
        }

        # Newest entries first.
        queryset = queryset.order_by(
            "-journal_entry__entry_date",
            "-id",
        )

        # Pagination
        try:
            page_number = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))

            if page_number < 1 or page_size < 1:
                raise ValueError

            # Prevent excessively large page requests.
            page_size = min(page_size, 100)

        except (ValueError, TypeError):
            return Response(
                {"detail": "page and page_size must be positive integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paginator = Paginator(queryset, page_size)

        try:
            page = paginator.page(page_number)
        except (EmptyPage, PageNotAnInteger):
            return Response(
                {"detail": "Invalid page number."},
                status=status.HTTP_404_NOT_FOUND,
            )

        results = []

        for line in page.object_list:
            entry = line.journal_entry
            account = line.account

            results.append({
                "id": line.id,
                "date": (
                    entry.entry_date.isoformat()
                    if entry.entry_date
                    else None
                ),
                # Change reference_number if your model uses another
                # field for the journal number.
                "journal_number": entry.reference_number,
                "account_id": account.id,
                "account_code": account.account_code,
                "account_name": account.account_name,
                "account": (
                    f"{account.account_code} - {account.account_name}"
                ),
                "type": account.account_type,
                "description": (
                    line.description or entry.description or ""
                ),
                "source": entry.source_module or entry.source or "",
                "debit_amount": str(line.debit_amount),
                "credit_amount": str(line.credit_amount),
            })

        return Response({
            "dashboard": dashboard,
            "pagination": {
                "count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page.number,
                "page_size": page_size,
                "next_page": (
                    page.next_page_number() if page.has_next() else None
                ),
                "previous_page": (
                    page.previous_page_number()
                    if page.has_previous()
                    else None
                ),
            },
            "results": results,
        })