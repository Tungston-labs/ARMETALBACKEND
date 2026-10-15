
from datetime import date, timedelta
from decimal import Decimal

from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# Adjust this import if your Bill model lives in another module.
from finance.bill.models import Bill


ZERO = Decimal("0.00")

VALID_STATUSES = {
    "paid",
    "unpaid",
    "partially_paid",
    "overdue",
}


class AccountsPayableView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        user = request.user

        # --------------------------------------------------
        # 1. Company isolation
        # --------------------------------------------------
        if not getattr(user, "company_id", None):
            return Response(
                {"detail": "User is not associated with a company."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = (
            Bill.objects
            .filter(company_id=user.company_id)
            .select_related("vendor")
        )

        # --------------------------------------------------
        # 2. Validate date range
        # Dates refer to bill_date.
        # --------------------------------------------------
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
            queryset = queryset.filter(bill_date__gte=date_from)

        if date_to:
            queryset = queryset.filter(bill_date__lte=date_to)

        # --------------------------------------------------
        # 3. Dashboard totals
        # Calculate before search, vendor, status, pagination.
        # --------------------------------------------------
        total_payable = ZERO
        not_yet_due = ZERO
        overdue_to_vendors = ZERO
        due_in_next_14_days = ZERO
        overdue_vendor_ids = set()

        upcoming_limit = today + timedelta(days=14)

        for bill in queryset.iterator():
            total_amount = Decimal(bill.total_amount or ZERO)
            amount_paid = Decimal(bill.amount_paid or ZERO)

            outstanding = max(total_amount - amount_paid, ZERO)

            if outstanding <= ZERO:
                continue

            total_payable += outstanding
            due_date = bill.due_date

            if due_date is None or due_date >= today:
                not_yet_due += outstanding

            if due_date and due_date < today:
                overdue_to_vendors += outstanding

                if bill.vendor_id:
                    overdue_vendor_ids.add(bill.vendor_id)

            if (
                due_date
                and today <= due_date <= upcoming_limit
            ):
                due_in_next_14_days += outstanding

        dashboard = {
            "total_payable": str(total_payable),
            "not_yet_due": str(not_yet_due),
            "overdue_to_vendors": str(overdue_to_vendors),
            "due_in_next_14_days": str(due_in_next_14_days),
            "vendors_overdue_count": len(overdue_vendor_ids),
        }

        # --------------------------------------------------
        # 4. Search by bill number or vendor name
        # --------------------------------------------------
        search = request.query_params.get("search", "").strip()

        if search:
            queryset = queryset.filter(
                Q(bill_number__icontains=search)
                | Q(vendor__name__icontains=search)
                | Q(bill_to_name__icontains=search)
            )

        # --------------------------------------------------
        # 5. Filter by vendor
        # --------------------------------------------------
        vendor_id = request.query_params.get("vendor_id")

        if vendor_id:
            if not vendor_id.isdigit():
                return Response(
                    {"detail": "vendor_id must be a valid integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = queryset.filter(vendor_id=vendor_id)

        # --------------------------------------------------
        # 6. Validate status filter
        # --------------------------------------------------
        requested_status = request.query_params.get(
            "status", ""
        ).strip().lower()

        if requested_status and requested_status not in VALID_STATUSES:
            return Response(
                {
                    "detail": (
                        "Invalid status. Choose paid, unpaid, "
                        "partially_paid, or overdue."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------
        # 7. Build results and calculate status
        # --------------------------------------------------
        results = []

        for bill in queryset.order_by("-bill_date", "-id").iterator():
            amount = Decimal(bill.total_amount or ZERO)
            paid_amount = Decimal(bill.amount_paid or ZERO)
            outstanding = max(amount - paid_amount, ZERO)

            if outstanding <= ZERO:
                calculated_status = "paid"
            elif bill.due_date and bill.due_date < today:
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

            vendor_name = (
                getattr(bill.vendor, "name", None)
                if bill.vendor_id else None
            ) or bill.bill_to_name or ""

            results.append({
                "id": bill.id,
                "bill_number": bill.bill_number,
                "vendor_id": bill.vendor_id,
                "vendor_name": vendor_name,
                "bill_date": (
                    bill.bill_date.isoformat()
                    if bill.bill_date else None
                ),
                "due_date": (
                    bill.due_date.isoformat()
                    if bill.due_date else None
                ),
                "amount": str(amount),
                "paid_amount": str(paid_amount),
                "outstanding_amount": str(outstanding),
                "status": calculated_status,
            })

        # --------------------------------------------------
        # 8. Pagination
        # --------------------------------------------------
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
                {
                    "detail": (
                        "page and page_size must be positive integers."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        paginator = Paginator(results, page_size)

        try:
            page_obj = paginator.page(page_number)
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
