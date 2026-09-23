from decimal import Decimal


from django.db.models import (
    Sum,
    Q,
    F,
    DecimalField,
    Value,
)
from django.db.models.functions import Coalesce

from rest_framework.response import Response
from rest_framework import status


from django.db.models import Sum

from django_filters.rest_framework import (
    DjangoFilterBackend,
)

from rest_framework import (
    status,
    viewsets,
)

from rest_framework.decorators import action

from rest_framework.filters import (
    OrderingFilter,
    SearchFilter,
)

from rest_framework.permissions import IsAuthenticated

from rest_framework.response import Response

from finance.customer.models import Customer

from user.permissions import (
    IsCompanyActive,
    IsHRAdmin,
)

from .models import CustomerLedger

from .serializers import (
    CustomerLedgerSerializer,
    CustomerLedgerCreateSerializer,
    CustomerLedgerSummarySerializer,CustomerLedgerCustomerSummarySerializer,CustomerFinancialSummarySerializer
)
from django.utils import timezone
from finance.payment.models import Payment
from finance.invoice.models import Invoice




class CustomerLedgerViewSet(
    viewsets.ModelViewSet
):

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "customer",
        "transaction_type",
        "transaction_date",
    ]

    search_fields = [
        "reference_number",
        "description",
        "customer__customer_name",
        "customer__customer_id",
        "invoice__invoice_number",
        "payment__receipt_number",
    ]

    ordering_fields = [
        "transaction_date",
        "created_at",
        "debit",
        "credit",
        "balance",
    ]

    ordering = [
        "transaction_date",
        "id",
    ]

    # ==================================================
    # SERIALIZER
    # ==================================================

    def get_serializer_class(self):

        if self.action == "create":
            return CustomerLedgerCreateSerializer

        return CustomerLedgerSerializer

    # ==================================================
    # QUERYSET
    # ==================================================

    def get_queryset(self):

        user = self.request.user

        if (
            not user.is_authenticated
            or not getattr(
                user,
                "company",
                None,
            )
        ):
            return CustomerLedger.objects.none()

        queryset = (
            CustomerLedger.objects
            .filter(
                company=user.company,
            )
            .select_related(
                "company",
                "customer",
                "invoice",
                "payment",
                "created_by",
            )
        )

        # ----------------------------------------------
        # Customer filter
        # ----------------------------------------------

        customer_id = (
            self.request.query_params.get(
                "customer_id"
            )
        )

        # ----------------------------------------------
        # Date filters
        # ----------------------------------------------

        from_date = (
            self.request.query_params.get(
                "from_date"
            )
        )

        to_date = (
            self.request.query_params.get(
                "to_date"
            )
        )

        # ----------------------------------------------
        # Transaction type
        # ----------------------------------------------

        transaction_type = (
            self.request.query_params.get(
                "transaction_type"
            )
        )

        # ----------------------------------------------
        # Apply filters
        # ----------------------------------------------

        if customer_id:

            queryset = queryset.filter(
                customer_id=customer_id
            )

        if from_date:

            queryset = queryset.filter(
                transaction_date__gte=from_date
            )

        if to_date:

            queryset = queryset.filter(
                transaction_date__lte=to_date
            )

        if transaction_type:

            queryset = queryset.filter(
                transaction_type=transaction_type
            )

        return queryset

    # ==================================================
    # CREATE
    # ==================================================

    def create(
        self,
        request,
        *args,
        **kwargs,
    ):

        serializer = self.get_serializer(
            data=request.data,
            context={
                "request": request
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        ledger = serializer.save()

        # ----------------------------------------------
        # Return complete ledger object
        # ----------------------------------------------

        response_serializer = (
            CustomerLedgerSerializer(
                ledger,
                context={
                    "request": request
                },
            )
        )

        return Response(
            {
                "message": (
                    "Customer ledger created "
                    "successfully."
                ),
                "data": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    # ==================================================
    # CUSTOMER LEDGER
    # ==================================================

    @action(
        detail=False,
        methods=["get"],
        url_path=(
            r"customer/(?P<customer_id>[^/.]+)"
        ),
    )
    def customer_ledger(
        self,
        request,
        customer_id,
    ):

        user = request.user

        # ----------------------------------------------
        # Check customer belongs to company
        # ----------------------------------------------

        customer = (
            Customer.objects
            .filter(
                id=customer_id,
                company=user.company,
            )
            .first()
        )

        if not customer:

            return Response(
                {
                    "message": (
                        "Customer not found."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ----------------------------------------------
        # Get ledger
        # ----------------------------------------------

        queryset = (
            self.get_queryset()
            .filter(
                customer=customer,
            )
        )

        # ----------------------------------------------
        # Apply search / filters / ordering
        # ----------------------------------------------

        queryset = self.filter_queryset(
            queryset
        )

        # ----------------------------------------------
        # Pagination
        # ----------------------------------------------

        page = self.paginate_queryset(
            queryset
        )

        if page is not None:

            serializer = (
                self.get_serializer(
                    page,
                    many=True,
                )
            )

            return self.get_paginated_response(
                serializer.data
            )

        # ----------------------------------------------
        # Without pagination
        # ----------------------------------------------

        serializer = (
            self.get_serializer(
                queryset,
                many=True,
            )
        )

        return Response(
            {
                "message": (
                    "Customer ledger retrieved "
                    "successfully."
                ),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    # ==================================================
    # SUMMARY
    # ==================================================

    @action(
        detail=False,
        methods=["get"],
        url_path="summary",
    )
    def summary(
        self,
        request,
    ):

        user = request.user

        customer_id = (
            request.query_params.get(
                "customer_id"
            )
        )

        # ----------------------------------------------
        # Validate customer_id
        # ----------------------------------------------

        if not customer_id:

            return Response(
                {
                    "message": (
                        "customer_id is required."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------
        # Find customer
        # ----------------------------------------------

        customer = (
            Customer.objects
            .filter(
                id=customer_id,
                company=user.company,
            )
            .first()
        )

        if not customer:

            return Response(
                {
                    "message": (
                        "Customer not found."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ----------------------------------------------
        # Base queryset
        # ----------------------------------------------

        queryset = (
            CustomerLedger.objects
            .filter(
                company=user.company,
                customer=customer,
            )
        )

        # ----------------------------------------------
        # Date filtering
        # ----------------------------------------------

        from_date = (
            request.query_params.get(
                "from_date"
            )
        )

        to_date = (
            request.query_params.get(
                "to_date"
            )
        )

        if from_date:

            queryset = queryset.filter(
                transaction_date__gte=from_date
            )

        if to_date:

            queryset = queryset.filter(
                transaction_date__lte=to_date
            )

        # ----------------------------------------------
        # Total debit
        # ----------------------------------------------

        total_debit = (
            queryset.aggregate(
                total=Sum("debit")
            )["total"]
            or Decimal("0.00")
        )

        # ----------------------------------------------
        # Total credit
        # ----------------------------------------------

        total_credit = (
            queryset.aggregate(
                total=Sum("credit")
            )["total"]
            or Decimal("0.00")
        )

        # ----------------------------------------------
        # Closing balance
        # ----------------------------------------------

        closing_balance = (
            (
                customer.opening_balance
                or Decimal("0.00")
            )
            + total_debit
            - total_credit
        )

        # ----------------------------------------------
        # Response
        # ----------------------------------------------

        data = {
            "customer_id": customer.id,
            "customer_code": customer.customer_id,
            "customer_name": customer.customer_name,
            "opening_balance": (
                customer.opening_balance
                or Decimal("0.00")
            ),
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": closing_balance,
        }

        serializer = (
            CustomerLedgerSummarySerializer(
                data
            )
        )

        return Response(
            {
                "message": (
                    "Customer ledger summary "
                    "retrieved successfully."
                ),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
    
    @action(
        detail=False,
        methods=["get"],
        url_path="customer-summary",
    )
    def customer_summary(self, request):

        user = request.user

        # ==================================================
        # BASE CUSTOMER QUERYSET
        # ==================================================

        customers = Customer.objects.filter(
            company=user.company
        )

        # ==================================================
        # SEARCH CUSTOMER NAME
        # ==================================================

        search = request.query_params.get(
            "search"
        )

        if search:
            customers = customers.filter(
                customer_name__icontains=search
            )

        # ==================================================
        # LEDGER AGGREGATION
        # ==================================================

        customers = customers.annotate(

            total_invoice=Coalesce(
                Sum(
                    "ledger_entries__debit",
                    filter=Q(
                        ledger_entries__transaction_type="invoice"
                    ),
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(
                    max_digits=15,
                    decimal_places=2,
                ),
            ),

            total_payment=Coalesce(
                Sum(
                    "ledger_entries__credit",
                    filter=Q(
                        ledger_entries__transaction_type="payment"
                    ),
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(
                    max_digits=15,
                    decimal_places=2,
                ),
            ),

            credit_note=Coalesce(
                Sum(
                    "ledger_entries__credit",
                    filter=Q(
                        ledger_entries__transaction_type="credit_note"
                    ),
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(
                    max_digits=15,
                    decimal_places=2,
                ),
            ),
        )

        # ==================================================
        # OUTSTANDING
        # ==================================================

        customers = customers.annotate(
            outstanding=(
                F("total_invoice")
                - F("total_payment")
                - F("credit_note")
            )
        )

        # ==================================================
        # ORDERING
        # ==================================================

        customers = customers.order_by(
            "customer_name"
        )

        # ==================================================
        # PAGINATION
        # ==================================================

        page = self.paginate_queryset(
            customers
        )

        # ==================================================
        # SERIALIZE
        # ==================================================

        if page is not None:

            data = []

            for customer in page:

                data.append({
                    "customer_code": customer.customer_id,
                    "customer_name": customer.customer_name,
                    "total_invoice": customer.total_invoice,
                    "total_payment": customer.total_payment,
                    "credit_note": customer.credit_note,
                    "overdue": Decimal("0.00"),
                    "outstanding": customer.outstanding,
                })

            serializer = (
                CustomerLedgerCustomerSummarySerializer(
                    data,
                    many=True,
                )
            )

            return self.get_paginated_response(
                serializer.data
            )

        # ==================================================
        # WITHOUT PAGINATION
        # ==================================================

        data = []

        for customer in customers:

            data.append({
                "customer_code": customer.customer_id,
                "customer_name": customer.customer_name,
                "total_invoice": customer.total_invoice,
                "total_payment": customer.total_payment,
                "credit_note": customer.credit_note,
                "overdue": Decimal("0.00"),
                "outstanding": customer.outstanding,
            })

        serializer = (
            CustomerLedgerCustomerSummarySerializer(
                data,
                many=True,
            )
        )

        return Response(
            {
                "message": (
                    "Customer ledger summary "
                    "retrieved successfully."
                ),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
    
    @action(
        detail=False,
        methods=["get"],
        url_path="dashboard-summary",
    )
    def dashboard_summary(self, request):

        user = request.user
        company = user.company

        customer_id = request.query_params.get(
            "customer_id"
        )

        today = timezone.localdate()

        # -------------------------------------------------
        # Base invoice queryset
        # -------------------------------------------------

        invoice_queryset = Invoice.objects.filter(
            company=company
        )

        if customer_id:
            invoice_queryset = invoice_queryset.filter(
                customer_id=customer_id
            )

        # -------------------------------------------------
        # Total Invoice
        # -------------------------------------------------

        total_invoice = (
            invoice_queryset.aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        # -------------------------------------------------
        # Total Collection
        # -------------------------------------------------

        payment_queryset = Payment.objects.filter(
            company=company,
            status="completed",
        )

        if customer_id:
            payment_queryset = payment_queryset.filter(
                customer_id=customer_id
            )

        total_collection = (
            payment_queryset.aggregate(
                total=Sum("amount_received")
            )["total"]
            or Decimal("0.00")
        )

        # -------------------------------------------------
        # Total Credit
        # -------------------------------------------------

        credit_queryset = CustomerLedger.objects.filter(
            company=company,
            transaction_type="credit_note",
        )

        if customer_id:
            credit_queryset = credit_queryset.filter(
                customer_id=customer_id
            )

        total_credit = (
            credit_queryset.aggregate(
                total=Sum("credit")
            )["total"]
            or Decimal("0.00")
        )

        # -------------------------------------------------
        # Total Receivable
        # -------------------------------------------------
        #
        # Receivable = Invoice - Collection - Credit
        #
        # Credit notes reduce the receivable amount.
        # -------------------------------------------------

        total_receivable = (
            total_invoice
            - total_collection
            - total_credit
        )

        if total_receivable < Decimal("0.00"):
            total_receivable = Decimal("0.00")

        # -------------------------------------------------
        # Overdue Amount
        # -------------------------------------------------
        #
        # Unpaid or partially paid invoices whose
        # due date has passed.
        #
        # Outstanding = total_amount - amount_paid
        # -------------------------------------------------

        overdue_queryset = invoice_queryset.filter(
            due_date__lt=today,
            payment_status__in=[
                "unpaid",
                "partially_paid",
            ],
        )

        overdue_amount = Decimal("0.00")

        overdue_invoices = overdue_queryset.values(
            "total_amount",
            "amount_paid",
        )

        for invoice in overdue_invoices:

            invoice_total = (
                invoice["total_amount"]
                or Decimal("0.00")
            )

            invoice_paid = (
                invoice["amount_paid"]
                or Decimal("0.00")
            )

            outstanding_amount = (
                invoice_total - invoice_paid
            )

            if outstanding_amount > Decimal("0.00"):

                overdue_amount += (
                    outstanding_amount
                )

        # -------------------------------------------------
        # Prepare response
        # -------------------------------------------------

        data = {
            "total_receivable": total_receivable,
            "total_invoice": total_invoice,
            "total_collection": total_collection,
            "total_credit": total_credit,
            "overdue_amount": overdue_amount,
        }

        serializer = CustomerFinancialSummarySerializer(
            data
        )

        return Response(
            {
                "message": (
                    "Customer financial summary "
                    "retrieved successfully."
                ),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )