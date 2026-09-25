from decimal import Decimal
from django.shortcuts import render
from django.db.models import Count, Sum, Q
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import (
    DjangoFilterBackend
)

from rest_framework.filters import (
    SearchFilter,
    OrderingFilter
)

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
    OpenApiParameter
)

from user.permissions import (
    IsHRAdmin,
    IsCompanyActive
)

from finance.quotation.models import Quotation
from finance.quotation.serializers import QuotationSerializer, QuotationListSerializer
from finance.payment.models import Payment
from finance.payment.serializers import PaymentListSerializer
from finance.credit_note.models import CreditNote
from finance.credit_note.serializers import CreditNoteSerializer, CreditNoteListSerializer
from finance.invoice.models import Invoice
from finance.ledger.models import CustomerLedger
from finance.ledger.serializers import CustomerLedgerSerializer
from finance.ledger.services import recalculate_customer_ledger

from .models import (
    Customer,
    CustomerDocument
)

from .serializers import (
    CustomerSerializer,
    CustomerDocumentSerializer,
    CustomerDocumentUploadSerializer,
    CustomerHeaderSerializer,
    CustomerOverviewSerializer,
    CustomerQuotationsKPISerializer,
    CustomerPaymentsKPISerializer,
    CustomerCreditNotesKPISerializer,
    CustomerLedgerKPISerializer,
)


class CustomerViewSet(viewsets.ModelViewSet):

    serializer_class = CustomerSerializer

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
        "client_status",
    ]

    search_fields = [
        "customer_id",
        "customer_name",
        "company_name",
        "cr_number",
        "vat_number",
        "admin_email",
        "financial_email",
        "technical_email",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "customer_name",
        "customer_id",
    ]

    ordering = [
        "-created_at"
    ]

    def get_queryset(self):

        user = self.request.user

        if not user.is_authenticated:
            return Customer.objects.none()

        if not user.company:
            return Customer.objects.none()

        return (
            Customer.objects
            .filter(company=user.company)
            .select_related(
                "company",
                "created_by"
            )
            .prefetch_related(
                "documents"
            )
        )

    def get_object(self):
        if self.action in ["overview", "upload_document", "delete_document", "quotations", "payments", "credit_notes", "credit_notes_alt", "ledger"]:
            queryset = self.get_queryset()
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
            from django.shortcuts import get_object_or_404
            obj = get_object_or_404(queryset, **filter_kwargs)
            self.check_object_permissions(self.request, obj)
            return obj
        return super().get_object()

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    def create(
        self,
        request,
        *args,
        **kwargs
    ):

        serializer = self.get_serializer(
            data=request.data
        )

        if not serializer.is_valid():

            return Response(
                {
                    "message": "Customer creation failed.",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        customer = serializer.save(
            company=request.user.company,
            created_by=request.user
        )

        # ---------------------------------------------
        # MULTIPLE DOCUMENTS
        # ---------------------------------------------

        documents = request.FILES.getlist(
            "documents"
        )

        document_objects = []

        for file in documents:

            document_objects.append(
                CustomerDocument(
                    customer=customer,
                    document=file,
                    document_name=file.name
                )
            )

        if document_objects:

            CustomerDocument.objects.bulk_create(
                document_objects
            )

        serializer = self.get_serializer(
            customer
        )

        return Response(
            {
                "message": "Customer created successfully.",
                "data": serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    # ---------------------------------------------------------
    # LIST
    # ---------------------------------------------------------

    def list(
        self,
        request,
        *args,
        **kwargs
    ):

        queryset = self.filter_queryset(
            self.get_queryset()
        )

        page = self.paginate_queryset(
            queryset
        )

        if page is not None:

            serializer = self.get_serializer(
                page,
                many=True
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = self.get_serializer(
            queryset,
            many=True
        )

        return Response(
            {
                "message": "Customers retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # RETRIEVE
    # ---------------------------------------------------------

    def retrieve(
        self,
        request,
        *args,
        **kwargs
    ):

        instance = self.get_object()

        serializer = self.get_serializer(
            instance
        )

        return Response(
            {
                "message": "Customer retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # UPDATE / PATCH
    # ---------------------------------------------------------

    def update(
        self,
        request,
        *args,
        **kwargs
    ):

        partial = kwargs.pop(
            "partial",
            False
        )

        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial
        )

        if not serializer.is_valid():

            return Response(
                {
                    "message": "Customer update failed.",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        customer = serializer.save()

        # ---------------------------------------------
        # ADD NEW DOCUMENTS
        # ---------------------------------------------

        documents = request.FILES.getlist(
            "documents"
        )

        document_objects = []

        for file in documents:

            document_objects.append(
                CustomerDocument(
                    customer=customer,
                    document=file,
                    document_name=file.name
                )
            )

        if document_objects:

            CustomerDocument.objects.bulk_create(
                document_objects
            )

        serializer = self.get_serializer(
            customer
        )

        return Response(
            {
                "message": "Customer updated successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    def destroy(
        self,
        request,
        *args,
        **kwargs
    ):

        instance = self.get_object()

        customer_name = instance.customer_name

        instance.delete()

        return Response(
            {
                "message": (
                    f"Customer '{customer_name}' "
                    "deleted successfully."
                )
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    @action(
        detail=False,
        methods=["get"],
        url_path="summary"
    )
    def summary(
        self,
        request
    ):

        queryset = self.get_queryset()

        total_customers = queryset.count()

        active_customers = queryset.filter(
            client_status="active"
        ).count()

        inactive_customers = queryset.filter(
            client_status="inactive"
        ).count()

        # ---------------------------------------------
        # NEW CUSTOMERS THIS MONTH
        # ---------------------------------------------

        today = timezone.localdate()

        new_customers_this_month = queryset.filter(
            created_at__year=today.year,
            created_at__month=today.month
        ).count()

        # ---------------------------------------------
        # PAYMENT RECEIVED
        # ---------------------------------------------

        payment_received = 0

        return Response(
            {
                "message": (
                    "Customer summary retrieved "
                    "successfully."
                ),
                "data": {
                    "total_customers": total_customers,
                    "active_customers": active_customers,
                    "new_customers_this_month": (
                        new_customers_this_month
                    ),
                    "inactive_customers": (
                        inactive_customers
                    ),
                    "payment_received": payment_received,
                }
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # INDIVIDUAL CUSTOMER OVERVIEW
    # ---------------------------------------------------------

    @extend_schema(
        summary="Get Individual Customer Overview",
        description="Retrieves overview details for a specific customer including header data, company info, contact info, business/financial details, and uploaded documents.",
        responses={
            200: OpenApiResponse(
                description="Customer Overview Data",
                response=CustomerOverviewSerializer
            )
        }
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="overview"
    )
    def overview(
        self,
        request,
        pk=None
    ):
        instance = self.get_object()
        serializer = CustomerOverviewSerializer(instance)

        return Response(
            {
                "message": "Customer overview retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # UPLOAD DOCUMENT TO CUSTOMER
    # ---------------------------------------------------------

    @extend_schema(
        summary="Upload Document to Individual Customer",
        description="Uploads one or multiple documents for the specified customer overview page.",
        request={
            "multipart/form-data": CustomerDocumentUploadSerializer
        },
        responses={
            201: OpenApiResponse(
                description="Uploaded document details",
                response=CustomerDocumentSerializer(many=True)
            ),
            400: OpenApiResponse(
                description="Bad Request - No document file provided"
            )
        }
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="upload_document"
    )
    def upload_document(
        self,
        request,
        pk=None
    ):
        customer = self.get_object()

        documents = request.FILES.getlist("documents") or request.FILES.getlist("document")
        if not documents and "document" in request.FILES:
            documents = [request.FILES["document"]]

        if not documents:
            return Response(
                {
                    "message": "Upload failed. No document files provided.",
                    "errors": {"documents": ["This field is required."]}
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        document_objects = []
        doc_name_input = request.data.get("document_name", "")

        for file in documents:
            document_objects.append(
                CustomerDocument(
                    customer=customer,
                    document=file,
                    document_name=doc_name_input or file.name
                )
            )

        CustomerDocument.objects.bulk_create(document_objects)

        updated_documents = CustomerDocument.objects.filter(customer=customer)
        doc_serializer = CustomerDocumentSerializer(
            updated_documents,
            many=True
        )

        return Response(
            {
                "message": "Document(s) uploaded successfully.",
                "documents": doc_serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    # ---------------------------------------------------------
    # DELETE DOCUMENT FROM CUSTOMER
    # ---------------------------------------------------------

    @extend_schema(
        summary="Delete Document from Individual Customer",
        description="Deletes a customer document by document ID (passed as URL path component /delete_document/<doc_id>/ or query parameter ?document_id=<doc_id>).",
        parameters=[
            OpenApiParameter("document_id", int, description="ID of the document to delete", required=False),
        ],
        responses={
            200: OpenApiResponse(
                description="Document deleted successfully.",
                response=CustomerDocumentSerializer(many=True)
            ),
            400: OpenApiResponse(description="Bad Request - Missing document_id"),
            404: OpenApiResponse(description="Document or Customer not found")
        }
    )
    @action(
        detail=True,
        methods=["delete", "post"],
        url_path=r"delete_document(?:/(?P<doc_id>\d+))?"
    )
    def delete_document(
        self,
        request,
        pk=None,
        doc_id=None
    ):
        customer = self.get_object()

        target_doc_id = (
            doc_id or
            request.query_params.get("document_id") or
            request.data.get("document_id") or
            request.data.get("doc_id")
        )

        if not target_doc_id:
            return Response(
                {
                    "message": "Delete failed. document_id is required.",
                    "errors": {"document_id": ["This field or URL parameter is required."]}
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        document = CustomerDocument.objects.filter(
            id=target_doc_id,
            customer=customer
        ).first()

        if not document:
            return Response(
                {
                    "message": "Document not found for this customer.",
                    "errors": {"document_id": ["Invalid document ID for this customer."]}
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if document.document:
            document.document.delete(save=False)
        document.delete()

        remaining_documents = CustomerDocument.objects.filter(customer=customer)
        doc_serializer = CustomerDocumentSerializer(
            remaining_documents,
            many=True
        )

        return Response(
            {
                "message": "Document deleted successfully.",
                "documents": doc_serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # INDIVIDUAL CUSTOMER QUOTATIONS
    # ---------------------------------------------------------

    @extend_schema(
        summary="Get Individual Customer Quotations",
        description="Retrieves header info, KPI statistics summary (total quotations, total amount, negotiation amount, approved, rejected, pending quotes) and a paginated list of quotations for a specific customer.",
        parameters=[
            OpenApiParameter("search", str, description="Search term across quote_number, bill_to_name, notes"),
            OpenApiParameter("status", str, description="Filter by status (pending, approved, rejected, converted)"),
            OpenApiParameter("from_date", str, description="Filter from issue date (YYYY-MM-DD)"),
            OpenApiParameter("to_date", str, description="Filter to issue date (YYYY-MM-DD)"),
            OpenApiParameter("start_date", str, description="Alias for from_date (YYYY-MM-DD)"),
            OpenApiParameter("end_date", str, description="Alias for to_date (YYYY-MM-DD)"),
            OpenApiParameter("issue_date", str, description="Filter by exact issue date (YYYY-MM-DD)"),
            OpenApiParameter("valid_till", str, description="Filter by valid till date (YYYY-MM-DD)"),
            OpenApiParameter("ordering", str, description="Field to order by (e.g. -created_at, quote_amount)"),
            OpenApiParameter("full", str, description="Pass 'true' to include nested line items and conversions"),
        ],
        responses={
            200: OpenApiResponse(
                description="Customer Quotations and KPI metrics"
            )
        }
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="quotations"
    )
    def quotations(
        self,
        request,
        pk=None
    ):
        customer = self.get_object()
        header_data = CustomerHeaderSerializer(customer).data

        quotations_qs = Quotation.objects.filter(
            customer=customer,
            company=request.user.company
        )

        # Date range filtration
        from_date = request.query_params.get("from_date") or request.query_params.get("start_date")
        to_date = request.query_params.get("to_date") or request.query_params.get("end_date")

        if from_date:
            quotations_qs = quotations_qs.filter(issue_date__gte=from_date)
        if to_date:
            quotations_qs = quotations_qs.filter(issue_date__lte=to_date)

        issue_date_param = request.query_params.get("issue_date")
        if issue_date_param:
            quotations_qs = quotations_qs.filter(issue_date=issue_date_param)

        valid_till_param = request.query_params.get("valid_till")
        if valid_till_param:
            quotations_qs = quotations_qs.filter(valid_till=valid_till_param)

        status_param = request.query_params.get("status")
        if status_param:
            quotations_qs = quotations_qs.filter(status=status_param)

        search_query = request.query_params.get("search", "").strip()
        if search_query:
            quotations_qs = quotations_qs.filter(
                Q(quote_number__icontains=search_query) |
                Q(bill_to_name__icontains=search_query) |
                Q(notes__icontains=search_query)
            )

        # KPI Metrics for filtered customer quotations
        kpi_stats = quotations_qs.aggregate(
            total_value=Coalesce(Sum("quote_amount"), Decimal("0.00")),
            total_negotiation=Coalesce(Sum("negotiation_amount"), Decimal("0.00"))
        )

        total_quotations = quotations_qs.count()
        approved_quotes = quotations_qs.filter(status="approved").count()
        rejected_quotes = quotations_qs.filter(status="rejected").count()
        pending_quotes = quotations_qs.filter(status="pending").count()

        kpi_cards = {
            "total_quotations": total_quotations,
            "total_amount": kpi_stats["total_value"],
            "negotiation_amount": kpi_stats["total_negotiation"],
            "rejected_quotations": rejected_quotes,
            "approved_quotations": approved_quotes,
            "pending_quotations": pending_quotes,
        }

        ordering_param = request.query_params.get("ordering", "-created_at")
        allowed_ordering = [
            "quote_number", "-quote_number",
            "issue_date", "-issue_date",
            "valid_till", "-valid_till",
            "quote_amount", "-quote_amount",
            "negotiation_amount", "-negotiation_amount",
            "created_at", "-created_at",
            "status", "-status",
        ]
        if ordering_param in allowed_ordering:
            quotations_qs = quotations_qs.order_by(ordering_param)
        else:
            quotations_qs = quotations_qs.order_by("-created_at")

        serializer_cls = QuotationSerializer if request.query_params.get("full") == "true" else QuotationListSerializer

        page = self.paginate_queryset(quotations_qs)
        if page is not None:
            serializer = serializer_cls(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["message"] = "Customer quotations retrieved successfully."
            response.data["customer_header"] = header_data
            response.data["kpi_cards"] = kpi_cards
            return response

        serializer = serializer_cls(quotations_qs, many=True)
        return Response(
            {
                "message": "Customer quotations retrieved successfully.",
                "customer_header": header_data,
                "kpi_cards": kpi_cards,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # INDIVIDUAL CUSTOMER PAYMENTS
    # ---------------------------------------------------------

    @extend_schema(
        summary="Get Individual Customer Payments",
        description="Retrieves header info, KPI statistics summary (total payments received, this month collections, pending payments, overdue amount) and a paginated list of payments for a specific customer.",
        parameters=[
            OpenApiParameter("search", str, description="Search term across receipt_number, invoice_number, reference_number, notes"),
            OpenApiParameter("payment_method", str, description="Filter by payment method (bank_transfer, cheque, online_payment, cash)"),
            OpenApiParameter("status", str, description="Filter by status (completed, pending, cancelled)"),
            OpenApiParameter("from_date", str, description="Filter from payment date (YYYY-MM-DD)"),
            OpenApiParameter("to_date", str, description="Filter to payment date (YYYY-MM-DD)"),
            OpenApiParameter("start_date", str, description="Alias for from_date (YYYY-MM-DD)"),
            OpenApiParameter("end_date", str, description="Alias for to_date (YYYY-MM-DD)"),
            OpenApiParameter("ordering", str, description="Field to order by (e.g. -payment_date, amount_received)"),
        ],
        responses={
            200: OpenApiResponse(
                description="Customer Payments and KPI metrics"
            )
        }
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="payments"
    )
    def payments(
        self,
        request,
        pk=None
    ):
        customer = self.get_object()
        header_data = CustomerHeaderSerializer(customer).data
        company = request.user.company
        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        payments_qs = Payment.objects.filter(
            customer=customer,
            company=company
        ).select_related("company", "customer", "invoice", "created_by")

        # Date range filtration
        from_date = request.query_params.get("from_date") or request.query_params.get("start_date")
        to_date = request.query_params.get("to_date") or request.query_params.get("end_date")

        if from_date:
            payments_qs = payments_qs.filter(payment_date__gte=from_date)
        if to_date:
            payments_qs = payments_qs.filter(payment_date__lte=to_date)

        search_query = request.query_params.get("search", "").strip()
        if search_query:
            payments_qs = payments_qs.filter(
                Q(receipt_number__icontains=search_query) |
                Q(invoice__invoice_number__icontains=search_query) |
                Q(reference_number__icontains=search_query) |
                Q(notes__icontains=search_query)
            )

        method_param = request.query_params.get("payment_method")
        if method_param:
            payments_qs = payments_qs.filter(payment_method=method_param)

        status_param = request.query_params.get("status")
        if status_param:
            payments_qs = payments_qs.filter(status=status_param)

        # 1. Total payments received (completed payments in filtered set)
        total_payments_received = payments_qs.filter(
            status="completed"
        ).aggregate(
            total=Coalesce(Sum("amount_received"), Decimal("0.00"))
        )["total"]

        # 2. Collections in period / this month
        if from_date or to_date:
            this_month_collections = total_payments_received
        else:
            this_month_collections = payments_qs.filter(
                status="completed",
                payment_date__gte=start_of_month
            ).aggregate(
                total=Coalesce(Sum("amount_received"), Decimal("0.00"))
            )["total"]

        # 3. Pending & Overdue amounts on invoices of this customer
        customer_invoices = Invoice.objects.filter(
            customer=customer,
            company=company
        ).exclude(payment_status="paid")

        if from_date:
            customer_invoices = customer_invoices.filter(invoice_date__gte=from_date)
        if to_date:
            customer_invoices = customer_invoices.filter(invoice_date__lte=to_date)

        pending_payments = Decimal("0.00")
        overdue_amount = Decimal("0.00")

        for inv in customer_invoices:
            rem = inv.total_amount - inv.amount_paid
            if rem > Decimal("0.00"):
                pending_payments += rem
                if inv.due_date and inv.due_date < today:
                    overdue_amount += rem

        kpi_cards = {
            "total_payments_received": total_payments_received,
            "this_month_collections": this_month_collections,
            "pending_payments": pending_payments,
            "overdue_amount": overdue_amount,
        }

        ordering_param = request.query_params.get("ordering", "-created_at")
        allowed_ordering = [
            "receipt_number", "-receipt_number",
            "payment_date", "-payment_date",
            "amount_received", "-amount_received",
            "created_at", "-created_at",
            "status", "-status",
        ]
        if ordering_param in allowed_ordering:
            payments_qs = payments_qs.order_by(ordering_param)
        else:
            payments_qs = payments_qs.order_by("-created_at")

        page = self.paginate_queryset(payments_qs)
        if page is not None:
            serializer = PaymentListSerializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["message"] = "Customer payments retrieved successfully."
            response.data["customer_header"] = header_data
            response.data["kpi_cards"] = kpi_cards
            return response

        serializer = PaymentListSerializer(payments_qs, many=True)
        return Response(
            {
                "message": "Customer payments retrieved successfully.",
                "customer_header": header_data,
                "kpi_cards": kpi_cards,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # INDIVIDUAL CUSTOMER CREDIT NOTES
    # ---------------------------------------------------------

    @extend_schema(
        summary="Get Individual Customer Credit Notes",
        description="Retrieves header info, KPI statistics summary (total credit notes, total credit value, this month credit value, open credit notes) and a paginated list of credit notes for a specific customer.",
        parameters=[
            OpenApiParameter("search", str, description="Search term across cn_number, invoice_ref, reason, notes"),
            OpenApiParameter("status", str, description="Filter by status (open, partially_applied, closed, cancelled, draft)"),
            OpenApiParameter("reason", str, description="Filter by reason (sales_return, price_adjustment, damaged_goods, etc.)"),
            OpenApiParameter("from_date", str, description="Filter from issue date (YYYY-MM-DD)"),
            OpenApiParameter("to_date", str, description="Filter to issue date (YYYY-MM-DD)"),
            OpenApiParameter("start_date", str, description="Alias for from_date (YYYY-MM-DD)"),
            OpenApiParameter("end_date", str, description="Alias for to_date (YYYY-MM-DD)"),
            OpenApiParameter("ordering", str, description="Field to order by (e.g. -issue_date, credit_amount)"),
            OpenApiParameter("full", str, description="Pass 'true' to include nested items"),
        ],
        responses={
            200: OpenApiResponse(
                description="Customer Credit Notes and KPI metrics"
            )
        }
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="credit_notes"
    )
    def credit_notes(
        self,
        request,
        pk=None
    ):
        return self._get_customer_credit_notes(request)

    @action(
        detail=True,
        methods=["get"],
        url_path="credit-notes"
    )
    def credit_notes_alt(
        self,
        request,
        pk=None
    ):
        return self._get_customer_credit_notes(request)

    def _get_customer_credit_notes(self, request):
        customer = self.get_object()
        header_data = CustomerHeaderSerializer(customer).data
        company = request.user.company
        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        cn_qs = CreditNote.objects.filter(
            customer=customer,
            company=company
        ).select_related("company", "customer", "created_by")

        # Date range filtration
        from_date = request.query_params.get("from_date") or request.query_params.get("start_date")
        to_date = request.query_params.get("to_date") or request.query_params.get("end_date")

        if from_date:
            cn_qs = cn_qs.filter(issue_date__gte=from_date)
        if to_date:
            cn_qs = cn_qs.filter(issue_date__lte=to_date)

        # Search filter
        search_query = request.query_params.get("search", "").strip()
        if search_query:
            cn_qs = cn_qs.filter(
                Q(cn_number__icontains=search_query) |
                Q(invoice_ref__icontains=search_query) |
                Q(reason__icontains=search_query) |
                Q(notes__icontains=search_query)
            )

        status_param = request.query_params.get("status")
        if status_param:
            cn_qs = cn_qs.filter(status=status_param)

        reason_param = request.query_params.get("reason")
        if reason_param:
            cn_qs = cn_qs.filter(reason=reason_param)

        # KPI Metrics for filtered customer credit notes
        total_credit_notes = cn_qs.count()
        total_credit_value = cn_qs.aggregate(
            total=Coalesce(Sum("credit_amount"), Decimal("0.00"))
        )["total"]

        if from_date or to_date:
            this_month_value = total_credit_value
        else:
            this_month_value = cn_qs.filter(
                issue_date__gte=start_of_month
            ).aggregate(
                total=Coalesce(Sum("credit_amount"), Decimal("0.00"))
            )["total"]

        open_credit_notes = cn_qs.filter(status="open").count()

        kpi_cards = {
            "total_credit_notes": total_credit_notes,
            "total_credit_value": total_credit_value,
            "this_month": this_month_value,
            "open_credit_notes": open_credit_notes,
        }

        ordering_param = request.query_params.get("ordering", "-created_at")
        allowed_ordering = [
            "cn_number", "-cn_number",
            "issue_date", "-issue_date",
            "credit_amount", "-credit_amount",
            "applied_amount", "-applied_amount",
            "created_at", "-created_at",
            "status", "-status",
        ]
        if ordering_param in allowed_ordering:
            cn_qs = cn_qs.order_by(ordering_param)
        else:
            cn_qs = cn_qs.order_by("-created_at")

        serializer_cls = CreditNoteSerializer if request.query_params.get("full") == "true" else CreditNoteListSerializer

        page = self.paginate_queryset(cn_qs)
        if page is not None:
            serializer = serializer_cls(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["message"] = "Customer credit notes retrieved successfully."
            response.data["customer_header"] = header_data
            response.data["kpi_cards"] = kpi_cards
            return response

        serializer = serializer_cls(cn_qs, many=True)
        return Response(
            {
                "message": "Customer credit notes retrieved successfully.",
                "customer_header": header_data,
                "kpi_cards": kpi_cards,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # INDIVIDUAL CUSTOMER LEDGER
    # ---------------------------------------------------------

    @extend_schema(
        summary="Get Individual Customer Ledger Report",
        description="Retrieves header info, ledger KPI statistics summary (opening balance, total invoices/debit, total payments/credit, credit notes, closing balance) and a paginated list of ledger transactions for a specific customer.",
        parameters=[
            OpenApiParameter("search", str, description="Search term across reference_number, description, invoice number"),
            OpenApiParameter("transaction_type", str, description="Filter by transaction_type (invoice, payment, credit_note, opening_balance, adjustment)"),
            OpenApiParameter("from_date", str, description="Filter from transaction date (YYYY-MM-DD)"),
            OpenApiParameter("to_date", str, description="Filter to transaction date (YYYY-MM-DD)"),
            OpenApiParameter("start_date", str, description="Alias for from_date (YYYY-MM-DD)"),
            OpenApiParameter("end_date", str, description="Alias for to_date (YYYY-MM-DD)"),
            OpenApiParameter("ordering", str, description="Field to order by (e.g. transaction_date, -transaction_date)"),
            OpenApiParameter("full", str, description="Pass 'true' to include full relational objects"),
        ],
        responses={
            200: OpenApiResponse(
                description="Customer Ledger Report and KPI metrics"
            )
        }
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="ledger"
    )
    def ledger(
        self,
        request,
        pk=None
    ):
        customer = self.get_object()
        header_data = CustomerHeaderSerializer(customer).data
        company = request.user.company

        # Recalculate customer ledger running balances to ensure data accuracy
        recalculate_customer_ledger(
            customer_id=customer.id,
            company_id=company.id
        )

        ledger_qs = CustomerLedger.objects.filter(
            customer=customer,
            company=company
        ).select_related("company", "customer", "invoice", "payment", "created_by")

        from_date = request.query_params.get("from_date") or request.query_params.get("start_date")
        to_date = request.query_params.get("to_date") or request.query_params.get("end_date")

        initial_opening_balance = customer.opening_balance or Decimal("0.00")
        if from_date:
            prior_entries = CustomerLedger.objects.filter(
                customer=customer,
                company=company,
                transaction_date__lt=from_date
            ).aggregate(
                prior_debit=Coalesce(Sum("debit"), Decimal("0.00")),
                prior_credit=Coalesce(Sum("credit"), Decimal("0.00"))
            )
            opening_balance = initial_opening_balance + prior_entries["prior_debit"] - prior_entries["prior_credit"]
            ledger_qs = ledger_qs.filter(transaction_date__gte=from_date)
        else:
            opening_balance = initial_opening_balance

        if to_date:
            ledger_qs = ledger_qs.filter(transaction_date__lte=to_date)

        transaction_type = request.query_params.get("transaction_type")
        if transaction_type:
            ledger_qs = ledger_qs.filter(transaction_type=transaction_type)

        search_query = request.query_params.get("search", "").strip()
        if search_query:
            ledger_qs = ledger_qs.filter(
                Q(reference_number__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(invoice__invoice_number__icontains=search_query) |
                Q(payment__receipt_number__icontains=search_query)
            )

        # KPI Metrics
        debit_credit_stats = ledger_qs.aggregate(
            total_debit=Coalesce(Sum("debit"), Decimal("0.00")),
            total_credit=Coalesce(Sum("credit"), Decimal("0.00")),
            credit_notes=Coalesce(Sum("credit", filter=Q(transaction_type="credit_note")), Decimal("0.00"))
        )
        total_invoices = debit_credit_stats["total_debit"]
        total_payments = debit_credit_stats["total_credit"]
        cn_amount = debit_credit_stats["credit_notes"]
        closing_balance = opening_balance + total_invoices - total_payments

        kpi_cards = {
            "opening_balance": opening_balance,
            "total_invoices": total_invoices,
            "total_payments": total_payments,
            "credit_notes": cn_amount,
            "closing_balance": closing_balance,
            "outstanding": closing_balance,
        }

        # Search filter
        search_query = request.query_params.get("search", "").strip()
        if search_query:
            ledger_qs = ledger_qs.filter(
                Q(reference_number__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        # Transaction type filter
        type_param = request.query_params.get("transaction_type") or request.query_params.get("type")
        if type_param:
            ledger_qs = ledger_qs.filter(transaction_type=type_param)

        # Date range filters
        from_date = request.query_params.get("from_date")
        if from_date:
            ledger_qs = ledger_qs.filter(transaction_date__gte=from_date)

        to_date = request.query_params.get("to_date")
        if to_date:
            ledger_qs = ledger_qs.filter(transaction_date__lte=to_date)

        # Ordering
        ordering_param = request.query_params.get("ordering", "-transaction_date")
        allowed_ordering = [
            "transaction_date", "-transaction_date",
            "created_at", "-created_at",
            "reference_number", "-reference_number",
            "debit", "-debit",
            "credit", "-credit",
            "balance", "-balance",
        ]
        if ordering_param in allowed_ordering:
            ledger_qs = ledger_qs.order_by(ordering_param, "-id")
        else:
            ledger_qs = ledger_qs.order_by("-transaction_date", "-id")

        page = self.paginate_queryset(ledger_qs)
        if page is not None:
            serializer = CustomerLedgerSerializer(page, many=True, context={"request": request})
            response = self.get_paginated_response(serializer.data)
            response.data["message"] = "Customer ledger retrieved successfully."
            response.data["customer_header"] = header_data
            response.data["kpi_cards"] = kpi_cards
            return response

        serializer = CustomerLedgerSerializer(ledger_qs, many=True, context={"request": request})
        return Response(
            {
                "message": "Customer ledger retrieved successfully.",
                "customer_header": header_data,
                "kpi_cards": kpi_cards,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK
        )