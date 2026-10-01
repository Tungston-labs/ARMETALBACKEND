from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import VendorLedger
from .serializers import (
    VendorLedgerCreateSerializer,
    VendorLedgerListSerializer,VendorLedgerCustomerSerializer,
)
from decimal import Decimal

from django.db.models import Q, Sum
from rest_framework.response import Response

from finance.vendor.models import Vendor

class VendorLedgerListCreateView(
    generics.ListCreateAPIView
):
    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):
        queryset = (
            VendorLedger.objects
            .filter(
                company=self.request.user.company
            )
            .select_related(
                "vendor",
                "bill",
                "purchase_order",
                "payment",
                "created_by",
            )
        )

        vendor = self.request.query_params.get(
            "vendor"
        )

        transaction_type = (
            self.request.query_params.get(
                "transaction_type"
            )
        )

        status = self.request.query_params.get(
            "status"
        )

        search = self.request.query_params.get(
            "search"
        )

        date_from = self.request.query_params.get(
            "date_from"
        )

        date_to = self.request.query_params.get(
            "date_to"
        )

        if vendor:
            queryset = queryset.filter(
                vendor_id=vendor
            )

        if transaction_type:
            queryset = queryset.filter(
                transaction_type=transaction_type
            )

        if status:
            queryset = queryset.filter(
                vendor__client_status=status
            )

        if date_from:
            queryset = queryset.filter(
                entry_date__gte=date_from
            )

        if date_to:
            queryset = queryset.filter(
                entry_date__lte=date_to
            )

        if search:
            queryset = queryset.filter(
                Q(vendor__vendor_id__icontains=search)
                | Q(vendor__name__icontains=search)
                | Q(reference_number__icontains=search)
                | Q(description__icontains=search)
            )

        return queryset.order_by(
            "-entry_date",
            "-id",
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VendorLedgerCreateSerializer

        return VendorLedgerListSerializer
    

class VendorLedgerDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):
        return (
            VendorLedger.objects
            .filter(
                company=self.request.user.company
            )
            .select_related(
                "vendor",
                "bill",
                "purchase_order",
                "payment",
                "created_by",
            )
        )

    def get_serializer_class(self):
        if self.request.method in [
            "PUT",
            "PATCH",
        ]:
            return VendorLedgerCreateSerializer

        return VendorLedgerListSerializer
    


class VendorLedgerCustomerView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorLedgerCustomerSerializer

    def get_vendor(self):
        vendor_id = self.kwargs["vendor_id"]

        return Vendor.objects.get(
            id=vendor_id,
            company=self.request.user.company,
        )

    def get_queryset(self):
        vendor = self.get_vendor()

        queryset = (
            VendorLedger.objects
            .filter(
                company=self.request.user.company,
                vendor=vendor,
            )
            .select_related("vendor")
            .order_by("entry_date", "id")
        )

        transaction_type = self.request.query_params.get(
            "type"
        )

        search = self.request.query_params.get(
            "search"
        )

        date_from = self.request.query_params.get(
            "date_from"
        )

        date_to = self.request.query_params.get(
            "date_to"
        )

        if transaction_type:
            queryset = queryset.filter(
                transaction_type=transaction_type
            )

        if search:
            queryset = queryset.filter(
                Q(reference_number__icontains=search)
                | Q(description__icontains=search)
                | Q(transaction_type__icontains=search)
            )

        if date_from:
            queryset = queryset.filter(
                entry_date__gte=date_from
            )

        if date_to:
            queryset = queryset.filter(
                entry_date__lte=date_to
            )

        return queryset

    def list(self, request, *args, **kwargs):
        vendor = self.get_vendor()

        queryset = self.get_queryset()

        # --------------------------------------------------
        # Calculate running balance
        # --------------------------------------------------

        running_balance = Decimal("0.00")

        running_balances = {}

        for entry in queryset:
            running_balance += (
                entry.debit_amount
                - entry.credit_amount
            )

            running_balances[entry.id] = running_balance

        # --------------------------------------------------
        # Cards
        # --------------------------------------------------

        total_opening_balance = (
            queryset
            .filter(
                transaction_type="opening_balance"
            )
            .aggregate(
                total=Sum("debit_amount")
            )["total"]
            or Decimal("0.00")
        )

        total_billed = (
            queryset
            .filter(
                transaction_type="bill"
            )
            .aggregate(
                total=Sum("debit_amount")
            )["total"]
            or Decimal("0.00")
        )

        total_paid = (
            queryset
            .filter(
                transaction_type="payment"
            )
            .aggregate(
                total=Sum("credit_amount")
            )["total"]
            or Decimal("0.00")
        )

        total_debit_note = (
            queryset
            .filter(
                transaction_type="debit_note"
            )
            .aggregate(
                total=Sum("debit_amount")
            )["total"]
            or Decimal("0.00")
        )

        total_paid_and_debit_note = (
            total_paid + total_debit_note
        )

        total_debit = (
            queryset.aggregate(
                total=Sum("debit_amount")
            )["total"]
            or Decimal("0.00")
        )

        total_credit = (
            queryset.aggregate(
                total=Sum("credit_amount")
            )["total"]
            or Decimal("0.00")
        )

        outstanding_payable = (
            total_debit - total_credit
        )

        total_transactions = queryset.count()

        # --------------------------------------------------
        # Serialize
        # --------------------------------------------------

        serializer = self.get_serializer(
            queryset,
            many=True,
            context={
                "request": request,
                "running_balances": running_balances,
            },
        )

        return Response({
            "vendor": {
                "id": vendor.id,
                "vendor_id": vendor.vendor_id,
                "name": vendor.name,
            },
            "cards": {
                "total_opening_balance": total_opening_balance,
                "total_billed": total_billed,
                "total_paid_and_debit_note": (
                    total_paid_and_debit_note
                ),
                "outstanding_payable": outstanding_payable,
                "total_transactions": total_transactions,
            },
            "filters": {
                "type": request.query_params.get("type"),
                "search": request.query_params.get("search"),
                "date_from": request.query_params.get("date_from"),
                "date_to": request.query_params.get("date_to"),
            },
            "data": serializer.data,
        })
    
from decimal import Decimal

from django.db.models import (
    Q,
    Sum,
    Max,
)

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from finance.vendor.models import Vendor
from .models import VendorLedger
from .serializers import VendorLedgerSummarySerializer


class VendorLedgerSummaryView(generics.ListAPIView):

    permission_classes = [IsAuthenticated]
    serializer_class = VendorLedgerSummarySerializer

    def get_queryset(self):
        company = self.request.user.company

        queryset = Vendor.objects.filter(
            company=company,
        )

        search = self.request.query_params.get("search")
        status = self.request.query_params.get("status")
        transaction_type = self.request.query_params.get(
            "transaction_type"
        )

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(vendor_id__icontains=search)
            )

        # Vendor status filter is applied later because
        # payable status is calculated from ledger/bills.

        return queryset.order_by("name")

    def get_vendor_ledger(self, vendor):

        queryset = VendorLedger.objects.filter(
            company=self.request.user.company,
            vendor=vendor,
        )

        date_from = self.request.query_params.get(
            "date_from"
        )

        date_to = self.request.query_params.get(
            "date_to"
        )

        transaction_type = (
            self.request.query_params.get(
                "transaction_type"
            )
        )

        if date_from:
            queryset = queryset.filter(
                entry_date__gte=date_from
            )

        if date_to:
            queryset = queryset.filter(
                entry_date__lte=date_to
            )

        if transaction_type:
            queryset = queryset.filter(
                transaction_type=transaction_type
            )

        return queryset

    def get_vendor_data(self, vendor):

        queryset = self.get_vendor_ledger(vendor)

        zero = Decimal("0.00")

        opening_balance = (
            queryset
            .filter(
                transaction_type="opening_balance"
            )
            .aggregate(
                total=Sum("debit_amount")
            )["total"]
            or zero
        )

        total_billed = (
            queryset
            .filter(
                transaction_type="bill"
            )
            .aggregate(
                total=Sum("debit_amount")
            )["total"]
            or zero
        )

        total_paid = (
            queryset
            .filter(
                transaction_type="payment"
            )
            .aggregate(
                total=Sum("credit_amount")
            )["total"]
            or zero
        )

        total_debit_note = (
            queryset
            .filter(
                transaction_type="debit_note"
            )
            .aggregate(
                total=Sum("debit_amount")
            )["total"]
            or zero
        )

        total_credit_note = (
            queryset
            .filter(
                transaction_type="credit_note"
            )
            .aggregate(
                total=Sum("credit_amount")
            )["total"]
            or zero
        )

        total_paid_and_debited = (
            total_paid + total_debit_note
        )

        total_debit = (
            queryset.aggregate(
                total=Sum("debit_amount")
            )["total"]
            or zero
        )

        total_credit = (
            queryset.aggregate(
                total=Sum("credit_amount")
            )["total"]
            or zero
        )

        closing_payable = (
            total_debit - total_credit
        )

        # Latest bill due date
        latest_bill = (
            queryset
            .filter(
                transaction_type="bill",
                bill__isnull=False,
            )
            .select_related("bill")
            .order_by(
                "-bill__due_date",
                "-entry_date",
                "-id",
            )
            .first()
        )

        due_date = None

        if latest_bill and latest_bill.bill:
            due_date = latest_bill.bill.due_date

        # Determine account status
        account_status = self.get_account_status(
            vendor=vendor,
            closing_payable=closing_payable,
            due_date=due_date,
        )

        return {
            "vendor_id": vendor.id,
            "vendor_code": vendor.vendor_id,
            "vendor_name": vendor.name,
            "opening_balance": opening_balance,
            "total_billed": total_billed,
            "total_paid_and_debited": (
                total_paid_and_debited
            ),
            "closing_payable": closing_payable,
            "due_date": due_date,
            "status": account_status,
        }

    def get_account_status(
        self,
        vendor,
        closing_payable,
        due_date,
    ):

        from django.utils import timezone

        if closing_payable <= Decimal("0.00"):
            return "cleared"

        if due_date:
            today = timezone.localdate()

            if due_date < today:
                return "overdue"

        return "watch"

    def list(self, request, *args, **kwargs):

        vendors = self.get_queryset()

        data = []

        for vendor in vendors:

            vendor_data = self.get_vendor_data(
                vendor
            )

            requested_status = (
                request.query_params.get("status")
            )

            if (
                requested_status
                and vendor_data["status"]
                != requested_status
            ):
                continue

            data.append(vendor_data)

        serializer = self.get_serializer(
            data,
            many=True,
        )

        # --------------------------------------------------
        # Cards
        # --------------------------------------------------

        zero = Decimal("0.00")

        total_vendors = len(data)

        total_billed = sum(
            (
                item["total_billed"]
                for item in data
            ),
            zero,
        )

        total_paid_and_debited = sum(
            (
                item["total_paid_and_debited"]
                for item in data
            ),
            zero,
        )

        total_payable = sum(
            (
                item["closing_payable"]
                for item in data
            ),
            zero,
        )

        overdue_accounts = sum(
            1
            for item in data
            if item["status"] == "overdue"
        )

        return Response({

            "cards": {
                "total_vendors": total_vendors,

                "total_billed": total_billed,

                "total_paid_and_debited": (
                    total_paid_and_debited
                ),

                "total_payable": total_payable,

                "overdue_accounts": overdue_accounts,
            },

            "filters": {
                "search": request.query_params.get(
                    "search"
                ),

                "transaction_type": (
                    request.query_params.get(
                        "transaction_type"
                    )
                ),

                "status": request.query_params.get(
                    "status"
                ),

                "date_from": request.query_params.get(
                    "date_from"
                ),

                "date_to": request.query_params.get(
                    "date_to"
                ),
            },

            "data": serializer.data,
        })