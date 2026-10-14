
from datetime import date, timedelta
from decimal import Decimal

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.invoice.models import Invoice


ZERO = Decimal("0.00")


class AccountsReceivableView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = date.today()

        # ----------------------------------------------------
        # 1. Company isolation
        # ----------------------------------------------------
        queryset = Invoice.objects.filter(
            company_id=user.company_id
        ).select_related("customer")

        # ----------------------------------------------------
        # 2. Validate and apply invoice date range
        # ----------------------------------------------------
        date_from_raw = request.query_params.get("date_from")
        date_to_raw = request.query_params.get("date_to")

        date_from = None
        date_to = None

        if date_from_raw:
            date_from = parse_date(date_from_raw)
            if not date_from:
                return Response(
                    {"detail": "Invalid date_from. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if date_to_raw:
            date_to = parse_date(date_to_raw)
            if not date_to:
                return Response(
                    {"detail": "Invalid date_to. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if date_from and date_to and date_from > date_to:
            return Response(
                {"detail": "date_from cannot be after date_to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if date_from:
            queryset = queryset.filter(invoice_date__gte=date_from)

        if date_to:
            queryset = queryset.filter(invoice_date__lte=date_to)

        # Keep this date-filtered queryset for dashboard calculations.
        dashboard_invoices = list(queryset)

        # ----------------------------------------------------
        # 3. Dashboard calculations
        # ----------------------------------------------------
        total_receivable = ZERO
        not_yet_due = ZERO
        overdue_amount = ZERO
        over_60_days_late = ZERO
        overdue_customer_ids = set()

        for invoice in dashboard_invoices:
            outstanding = max(
                Decimal(invoice.total_amount or ZERO)
                - Decimal(invoice.amount_paid or ZERO),
                ZERO,
            )

            if outstanding <= ZERO:
                continue

            total_receivable += outstanding

            if invoice.due_date and invoice.due_date < today:
                overdue_amount += outstanding
                overdue_customer_ids.add(invoice.customer_id)

                if invoice.due_date < today - timedelta(days=60):
                    over_60_days_late += outstanding
            else:
                not_yet_due += outstanding

        dashboard = {
            "total_receivable": str(total_receivable),
            "not_yet_due": str(not_yet_due),
            "overdue_amount": str(overdue_amount),
            "over_60_days_late": str(over_60_days_late),
            "overdue_customers": len(overdue_customer_ids),
        }

        # ----------------------------------------------------
        # 4. Search
        # ----------------------------------------------------
        search = request.query_params.get("search", "").strip()

        # Search by invoice number or customer name
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search)
                | Q(customer__customer_name__icontains=search)
            )

        # ----------------------------------------------------
        # 5. Filter by customer
        # ----------------------------------------------------
        customer_id = request.query_params.get("customer_id")

        if customer_id:
            if not customer_id.isdigit():
                return Response(
                    {"detail": "customer_id must be a valid integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = queryset.filter(customer_id=customer_id)

        # ----------------------------------------------------
        # 6. Filter by calculated status
        # ----------------------------------------------------
        requested_status = request.query_params.get("status", "").lower()

        valid_statuses = {
            "paid",
            "unpaid",
            "partially_paid",
            "overdue",
        }

        if requested_status and requested_status not in valid_statuses:
            return Response(
                {
                    "detail": (
                        "Invalid status. Choose paid, unpaid, "
                        "partially_paid, or overdue."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # 7. Prepare table results
        # ----------------------------------------------------
        invoices = []

        for invoice in queryset.order_by("-invoice_date", "-id"):
            amount = Decimal(invoice.total_amount or ZERO)
            paid_amount = Decimal(invoice.amount_paid or ZERO)
            outstanding = max(amount - paid_amount, ZERO)

            if outstanding <= ZERO:
                calculated_status = "paid"
            elif invoice.due_date and invoice.due_date < today:
                calculated_status = "overdue"
            elif paid_amount > ZERO:
                calculated_status = "partially_paid"
            else:
                calculated_status = "unpaid"

            if (
                requested_status
                and calculated_status != requested_status
            ):
                continue

            customer_name = (
                getattr(invoice.customer, "name", None)
                or str(invoice.customer)
            )

            invoices.append({
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer_id": invoice.customer_id,
                "customer_name": customer_name,
                "invoice_date": (
                    invoice.invoice_date.isoformat()
                    if invoice.invoice_date else None
                ),
                "due_date": (
                    invoice.due_date.isoformat()
                    if invoice.due_date else None
                ),
                "amount": str(amount),
                "paid_amount": str(paid_amount),
                "outstanding_amount": str(outstanding),
                "status": calculated_status,
            })

        # ----------------------------------------------------
        # 8. Pagination
        # ----------------------------------------------------
        try:
            page_number = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 10))

            if page_number < 1 or page_size < 1:
                raise ValueError

            if page_size > 100:
                return Response(
                    {"detail": "page_size cannot exceed 100."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except (TypeError, ValueError):
            return Response(
                {"detail": "page and page_size must be positive integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paginator = Paginator(invoices, page_size)

        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            return Response(
                {"detail": "Invalid page number."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except EmptyPage:
            return Response(
                {"detail": "Page does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "dashboard": dashboard,
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
            "results": list(page_obj.object_list),
        })
