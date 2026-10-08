import csv
from decimal import Decimal

from django.db.models import Sum, Q
from django.http import HttpResponse
from django.utils import timezone

from rest_framework import (
    viewsets,
    generics,
    filters,
    status,
)
from django.db import transaction
from rest_framework.decorators import action

from rest_framework.permissions import IsAuthenticated

from rest_framework.parsers import (
    MultiPartParser,
    FormParser,
    JSONParser,
)

from rest_framework.response import Response

from django_filters.rest_framework import (
    DjangoFilterBackend,
)
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiTypes,
)

from user.permissions import IsHRAdmin, IsCompanyActive
from shared.pagination import CustomPagination
from finance.bill.models import Bill
from .models import (
    Vendor,
    VendorBill,
    VendorPayment,
    VendorDocument,
)

from .serializers import (
    VendorSerializer,
    VendorCreateSerializer,
    VendorPaymentSerializer,
    VendorPaymentListSerializer,
    VendorPaymentKPISerializer,
)
from .filters import VendorPaymentFilter
from finance.vendorledger.services import (
    sync_vendor_opening_balance,
)
from finance.vendorledger.services import (
    sync_vendor_payment_ledger,
    sync_bill_ledger,
)

from finance.vendorledger.services import (
    delete_payment_ledger,
    sync_bill_ledger,
)
from .filters import VendorFilter
class VendorViewSet(viewsets.ModelViewSet):

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    pagination_class = CustomPagination

    parser_classes = [
        MultiPartParser,
        FormParser,
        JSONParser,
    ]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_class = VendorFilter

    filterset_fields = [
        "client_status",
        "vendor_type",
        "payment_term",
        "currency",
    ]

    search_fields = [
        "vendor_id",
        "name",
        "cr_number",
        "vat_registration_number",
        "admin_email",
        "financial_email",
        "technical_email",
        "city",
        "country",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
        "vendor_id",
        "opening_balance",
        "credit_limit",
    ]

    ordering = ["-created_at"]

    # ==================================================
    # QUERYSET
    # ==================================================

    def get_queryset(self):

        user = self.request.user

        company = getattr(
            user,
            "company",
            None,
        )

        if not company:
            return Vendor.objects.none()

        return (
            Vendor.objects
            .filter(company=company)
            .select_related(
                "company",
                "created_by",
            )
            .prefetch_related(
                "documents"
            )
        )

    # ==================================================
    # SERIALIZER
    # ==================================================

    def get_serializer_class(self):

        if self.action == "create":
            return VendorCreateSerializer

        return VendorSerializer

    # ==================================================
    # CREATE
    # ==================================================

    def create(
        self,
        request,
        *args,
        **kwargs,
    ):

        user = request.user

        company = getattr(
            user,
            "company",
            None,
        )

        if not company:

            return Response(
                {
                    "message": (
                        "User is not associated "
                        "with a company."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------
        # Get uploaded files directly
        # ------------------------------------------

        documents = request.FILES.getlist(
            "documents"
        )

        print(
            "================================="
        )
        print(
            "FILES RECEIVED:",
            request.FILES,
        )
        print(
            "DOCUMENT COUNT:",
            len(documents),
        )
        print(
            "================================="
        )

        # ------------------------------------------
        # Vendor data only
        # ------------------------------------------

        vendor_data = request.data.copy()

        # Remove documents from serializer data
        vendor_data.pop(
            "documents",
            None,
        )

        # ------------------------------------------
        # Validate vendor
        # ------------------------------------------

        serializer = VendorCreateSerializer(
            data=vendor_data,
            context=self.get_serializer_context(),
        )

        serializer.is_valid(
            raise_exception=True
        )

        # ------------------------------------------
        # Save vendor
        # ------------------------------------------

        vendor = serializer.save(
            company=company,
            created_by=user,
        )
        sync_vendor_opening_balance(
            vendor,
            created_by=user,
        )

        # ------------------------------------------
        # Save documents
        # ------------------------------------------

        saved_documents = []

        for uploaded_file in documents:

            vendor_document = VendorDocument(
                vendor=vendor,
                document_name=uploaded_file.name,
            )

            # IMPORTANT:
            # This actually sends the file
            # through Django's FileField storage.
            vendor_document.document.save(
                uploaded_file.name,
                uploaded_file,
                save=True,
            )

            saved_documents.append(
                vendor_document
            )

        # ------------------------------------------
        # Reload vendor with documents
        # ------------------------------------------

        vendor = (
            Vendor.objects
            .filter(
                company=company,
                pk=vendor.pk,
            )
            .select_related(
                "company",
                "created_by",
            )
            .prefetch_related(
                "documents"
            )
            .get()
        )

        response_serializer = VendorSerializer(
            vendor,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "message": (
                    "Vendor created successfully."
                ),
                "documents_uploaded": len(
                    saved_documents
                ),
                "data": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    # ==================================================
    # LIST
    # ==================================================

    def list(
        self,
        request,
        *args,
        **kwargs,
    ):

        queryset = self.filter_queryset(
            self.get_queryset()
        )

        page = self.paginate_queryset(
            queryset
        )

        if page is not None:

            serializer = VendorSerializer(
                page,
                many=True,
                context={
                    "request": request,
                },
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = VendorSerializer(
            queryset,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "message": (
                    "Vendors fetched successfully."
                ),
                "data": serializer.data,
            }
        )

    # ==================================================
    # RETRIEVE
    # ==================================================

    def retrieve(
        self,
        request,
        *args,
        **kwargs,
    ):

        vendor = self.get_object()

        serializer = VendorSerializer(
            vendor,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "message": (
                    "Vendor fetched successfully."
                ),
                "data": serializer.data,
            }
        )

    # ==================================================
    # UPDATE
    # ==================================================

    def update(
        self,
        request,
        *args,
        **kwargs,
    ):

        vendor = self.get_object()

        partial = kwargs.pop(
            "partial",
            False,
        )

        serializer = VendorSerializer(
            vendor,
            data=request.data,
            partial=partial,
            context={
                "request": request,
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save()
        sync_vendor_opening_balance(
        vendor,
        created_by=request.user,
    )

        return Response(
            {
                "message": (
                    "Vendor updated successfully."
                ),
                "data": serializer.data,
            }
        )

    # ==================================================
    # PARTIAL UPDATE
    # ==================================================

    def partial_update(
        self,
        request,
        *args,
        **kwargs,
    ):

        kwargs["partial"] = True

        return self.update(
            request,
            *args,
            **kwargs,
        )

    # ==================================================
    # DELETE
    # ==================================================

    def destroy(
        self,
        request,
        *args,
        **kwargs,
    ):

        vendor = self.get_object()

        vendor.delete()

        return Response(
            {
                "message": (
                    "Vendor deleted successfully."
                )
            },
            status=status.HTTP_204_NO_CONTENT,
        )

    # ==================================================
    # UPLOAD DOCUMENTS
    # ==================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="upload-documents",
        parser_classes=[
            MultiPartParser,
            FormParser,
        ],
    )
    def upload_documents(
        self,
        request,
        pk=None,
    ):

        # get_object() already applies
        # company filtering through get_queryset()
        vendor = self.get_object()

        documents = request.FILES.getlist(
            "documents"
        )

        print(
            "UPLOAD DOCUMENTS:",
            request.FILES,
        )

        print(
            "DOCUMENT COUNT:",
            len(documents),
        )

        if not documents:

            return Response(
                {
                    "message": (
                        "Please upload at least "
                        "one document."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        saved_documents = []

        for uploaded_file in documents:

            vendor_document = VendorDocument(
                vendor=vendor,
                document_name=uploaded_file.name,
            )

        return Response({
            "message": (
                "Vendor documents uploaded successfully."
            ),
            "data": VendorSerializer(
                vendor,
                context=self.get_serializer_context(),
            ).data,
        }, status=status.HTTP_201_CREATED)


# ======================================================
# VENDOR DASHBOARD
# ======================================================

class VendorDashboardView(
    generics.GenericAPIView
):

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    def get(
        self,
        request,
        *args,
        **kwargs,
    ):

        company = getattr(
            request.user,
            "company",
            None,
        )

        if not company:

            return Response(
                {
                    "message": (
                        "User is not associated "
                        "with a company."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.localdate()
        month_start = today.replace(day=1)

        vendors = Vendor.objects.filter(
            company=company
        )

        bills = VendorBill.objects.filter(
            company=company,
            vendor__company=company,
        )

        payments = VendorPayment.objects.filter(
            company=company,
            vendor__company=company,
        )

        # ------------------------------------------
        # Vendor counts
        # ------------------------------------------

        total_vendor = vendors.count()

        active_vendor = vendors.filter(
            client_status="active"
        ).count()

        inactive_vendor = vendors.filter(
            client_status="inactive"
        ).count()

        # ------------------------------------------
        # Current month payments
        # ------------------------------------------

        total_payment_this_month = (
            payments
            .filter(
                status="completed",
                payment_date__gte=month_start,
                payment_date__lte=today,
            )
            .aggregate(
                total=Sum("amount_paid")
            )["total"]
            or Decimal("0.00")
        )

        # ------------------------------------------
        # Total bills
        # ------------------------------------------

        total_bills = (
            bills
            .aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        # ------------------------------------------
        # Opening balances
        # ------------------------------------------

        total_opening_balance = (
            vendors
            .aggregate(
                total=Sum("opening_balance")
            )["total"]
            or Decimal("0.00")
        )

        # ------------------------------------------
        # Completed payments
        # ------------------------------------------

        total_payments = (
            payments
            .filter(
                status="completed"
            )
            .aggregate(
                total=Sum("amount_paid")
            )["total"]
            or Decimal("0.00")
        )

        # ------------------------------------------
        # Outstanding payable
        # ------------------------------------------

        total_payable_outstanding = (
            total_opening_balance
            + total_bills
            - total_payments
        )

        total_payable_outstanding = max(
            total_payable_outstanding,
            Decimal("0.00"),
        )

        return Response(
            {
                "message": (
                    "Vendor dashboard fetched "
                    "successfully."
                ),
                "data": {
                    "total_vendor": total_vendor,
                    "active_vendor": active_vendor,
                    "inactive_vendor": inactive_vendor,
                    "total_payment_this_month": (
                        total_payment_this_month
                    ),
                    "total_payable_outstanding": (
                        total_payable_outstanding
                    ),
                },
            }
        )


@extend_schema_view(
    list=extend_schema(
        summary="List Vendor Payments",
        description="Retrieve a paginated list of vendor payments for the authenticated user's company with search and filter support.",
        responses={200: VendorPaymentListSerializer(many=True)},
    ),
    create=extend_schema(
        summary="Record Vendor Payment",
        description="Record a new vendor payment transaction. Links to vendor and optional bill, updating bill paid status automatically.",
        request=VendorPaymentSerializer,
        responses={201: VendorPaymentSerializer},
    ),
    retrieve=extend_schema(
        summary="Retrieve Vendor Payment",
        description="Retrieve details of a specific vendor payment by ID.",
        responses={200: VendorPaymentSerializer},
    ),
    update=extend_schema(
        summary="Update Vendor Payment",
        description="Update vendor payment record details.",
        request=VendorPaymentSerializer,
        responses={200: VendorPaymentSerializer},
    ),
    partial_update=extend_schema(
        summary="Partial Update Vendor Payment",
        description="Partially update vendor payment record details.",
        request=VendorPaymentSerializer,
        responses={200: VendorPaymentSerializer},
    ),
    destroy=extend_schema(
        summary="Delete Vendor Payment",
        description="Delete a vendor payment record and update linked bill payment status.",
        responses={200: OpenApiTypes.OBJECT},
    ),
)

class VendorPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = VendorPaymentSerializer
    permission_classes = [
        IsAuthenticated,
    ]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = VendorPaymentFilter
    search_fields = [
        "receipt_number",
        "vendor__name",
        "bill__bill_number",
        "reference_number",
        "notes",
    ]
    ordering_fields = [
        "created_at",
        "payment_date",
        "amount_paid",
        "receipt_number",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not getattr(user, "company", None):
            return VendorPayment.objects.none()

        return (
            VendorPayment.objects.filter(company=user.company)
            .select_related("company", "vendor", "bill", "created_by")
        )

    def perform_create(self, serializer):

        payment = serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
        )

        sync_vendor_payment_ledger(
            payment,
            created_by=self.request.user,
        )

        if payment.bill:
            sync_bill_ledger(
                payment.bill,
                created_by=self.request.user,
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        response_serializer = self.get_serializer(serializer.instance)
        return Response(
            {
                "message": "Vendor payment recorded successfully.",
                "data": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = VendorPaymentListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = VendorPaymentListSerializer(queryset, many=True)
        return Response(
            {
                "message": "Vendor payments retrieved successfully.",
                "data": serializer.data,
            }
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(
            {
                "message": "Vendor payment retrieved successfully.",
                "data": serializer.data,
            }
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):

        payment = self.get_object()

        old_bill = payment.bill

        serializer = self.get_serializer(
            payment,
            data=request.data,
            partial=kwargs.pop("partial", False),
        )

        serializer.is_valid(
            raise_exception=True
        )

        payment = serializer.save()

        sync_vendor_payment_ledger(
            payment,
            created_by=request.user,
        )

        # Update current bill ledger
        if payment.bill:
            sync_bill_ledger(
                payment.bill,
                created_by=request.user,
            )

        # If payment was moved from one bill to another,
        # synchronize the old bill also.
        if (
            old_bill
            and old_bill.id != payment.bill_id
        ):
            old_bill.refresh_from_db()

            sync_bill_ledger(
                old_bill,
                created_by=request.user,
            )

        return Response(
            {
                "message": "Vendor payment updated successfully.",
                "data": self.get_serializer(payment).data,
            }
        )
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):

        payment = self.get_object()

        bill = payment.bill

        delete_payment_ledger(payment)

        payment.delete()

        # VendorPayment.delete() recalculates Bill payment status.
        if bill:
            bill.refresh_from_db()

            sync_bill_ledger(
                bill,
                created_by=request.user,
            )

        return Response(
            {
                "message": "Vendor payment deleted successfully."
            }
        )
    

from decimal import Decimal

from django.db.models import Sum
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Vendor
from .serializers import VendorOverviewSerializer,VendorPurchaseOrderSerializer

from finance.purchaseorder.models import PurchaseOrder


class VendorOverviewView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorOverviewSerializer
    lookup_url_kwarg = "vendor_id"
    pagination_class = CustomPagination


    def get_queryset(self):
        return Vendor.objects.filter(
            company=self.request.user.company
        )

    def retrieve(self, request, *args, **kwargs):
        vendor = self.get_object()

        purchase_orders = PurchaseOrder.objects.filter(
            company=request.user.company,
            vendor=vendor,
        )

        total_purchase_orders = purchase_orders.count()

        total_purchase_value = (
            purchase_orders.aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        pending_purchase_orders = purchase_orders.filter(
            status__in=[
                "draft",
                "pending",
                "approved",
                "ordered",
            ]
        ).count()

        received_purchase_orders = purchase_orders.filter(
            status="received"
        ).count()

        cancelled_purchase_orders = purchase_orders.filter(
            status="cancelled"
        ).count()

        bills = vendor.bills.filter(
            company=request.user.company
        )

        total_bills = bills.count()

        total_bill_amount = (
            bills.aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        total_paid = (
            bills.aggregate(
                total=Sum("amount_paid")
            )["total"]
            or Decimal("0.00")
        )

        outstanding_amount = (
            total_bill_amount - total_paid
        )

        return Response({
            "vendor": self.get_serializer(vendor).data,

            "summary": {
                "total_purchase_orders": total_purchase_orders,
                "total_purchase_value": str(total_purchase_value),

                "pending_purchase_orders": pending_purchase_orders,
                "received_purchase_orders": received_purchase_orders,
                "cancelled_purchase_orders": cancelled_purchase_orders,

                "total_bills": total_bills,
                "total_bill_amount": str(total_bill_amount),
                "total_paid": str(total_paid),
                "outstanding_amount": str(
                    max(outstanding_amount, Decimal("0.00"))
                ),
            }
        })
   
from decimal import Decimal

from django.db.models import Sum, Q
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from finance.purchaseorder.models import PurchaseOrder
from .serializers import VendorPurchaseOrderSerializer
from .models import Vendor


class VendorPurchaseOrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorPurchaseOrderSerializer
    pagination_class = CustomPagination

    def get_queryset(self):
        vendor_id = self.kwargs["vendor_id"]

        queryset = (
            PurchaseOrder.objects
            .filter(
                company=self.request.user.company,
                vendor_id=vendor_id,
            )
            .select_related(
                "vendor",
                "warehouse",
            )
            .order_by("-created_at")
        )

        # Search
        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(po_number__icontains=search)
                | Q(pr_reference__icontains=search)
            )

        # Order status
        order_status = self.request.query_params.get(
            "order_status"
        )

        if order_status:
            queryset = queryset.filter(
                status=order_status
            )

        # Delivery status
        delivery_status = self.request.query_params.get(
            "delivery_status"
        )

        if delivery_status:
            queryset = queryset.filter(
                receipt_status=delivery_status
            )

        # Bill status
        bill_status = self.request.query_params.get(
            "bill_status"
        )

        if bill_status:
            queryset = queryset.filter(
                bill_status=bill_status
            )

        # Date range
        date_from = self.request.query_params.get(
            "date_from"
        )

        date_to = self.request.query_params.get(
            "date_to"
        )

        if date_from:
            queryset = queryset.filter(
                created_at__date__gte=date_from
            )

        if date_to:
            queryset = queryset.filter(
                created_at__date__lte=date_to
            )

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset()
        )

        # -----------------------------------------
        # Summary
        # -----------------------------------------

        vendor_id = kwargs["vendor_id"]

        all_vendor_orders = (
            PurchaseOrder.objects
            .filter(
                company=request.user.company,
                vendor_id=vendor_id,
            )
        )

        # Apply date range to summary also
        date_from = request.query_params.get(
            "date_from"
        )

        date_to = request.query_params.get(
            "date_to"
        )

        if date_from:
            all_vendor_orders = all_vendor_orders.filter(
                created_at__date__gte=date_from
            )

        if date_to:
            all_vendor_orders = all_vendor_orders.filter(
                created_at__date__lte=date_to
            )

        total_orders = all_vendor_orders.count()

        total_po_value = (
            all_vendor_orders.aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        # Orders waiting for approval
        pending_approval_count = (
            all_vendor_orders
            .filter(status="pending")
            .count()
        )

        # Open orders
        open_orders_count = (
            all_vendor_orders
            .filter(
                status__in=[
                    "approved",
                    "ordered",
                    "partially_received",
                ]
            )
            .count()
        )

        # Completed orders
        completed_orders_count = (
            all_vendor_orders
            .filter(status="received")
            .count()
        )

        # -----------------------------------------
        # Pagination
        # -----------------------------------------

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True,
            )

            response_data = {
                "summary": {
                    "total_orders": total_orders,
                    "total_po_value": str(
                        total_po_value
                    ),
                    "pending_approval_count": (
                        pending_approval_count
                    ),
                    "open_orders_count": (
                        open_orders_count
                    ),
                    "completed_orders_count": (
                        completed_orders_count
                    ),
                },
                "purchase_orders": serializer.data,
            }

            return Response(response_data)

        serializer = self.get_serializer(
            queryset,
            many=True,
        )

        return Response({
            "summary": {
                "total_orders": total_orders,
                "total_po_value": str(
                    total_po_value
                ),
                "pending_approval_count": (
                    pending_approval_count
                ),
                "open_orders_count": (
                    open_orders_count
                ),
                "completed_orders_count": (
                    completed_orders_count
                ),
            },
            "purchase_orders": serializer.data,
        })


from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import VendorDocument
from .serializers import VendorDocumentUploadSerializer


class VendorDocumentUploadView(CreateAPIView):

    serializer_class = VendorDocumentUploadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VendorDocument.objects.filter(
            vendor__company=self.request.user.company
        )

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        document = serializer.save()

        return Response(
            {
                "message": "Vendor document uploaded successfully.",
                "data": self.get_serializer(document).data,
            },
            status=status.HTTP_201_CREATED,
        )


from django.db.models import Q

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Vendor
from finance.bill.models import Bill
from .serializers import VendorBillListSerializer

from django.db.models import Q, Sum, Count


from decimal import Decimal

from django.db.models import Count, Sum

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Vendor
from finance.bill.models import Bill
from .serializers import VendorBillListSerializer
from shared.pagination import CustomPagination


class VendorBillListView(APIView):

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, vendor_id):

        company = request.user.company

        # -----------------------------------
        # Validate vendor
        # -----------------------------------

        vendor = Vendor.objects.filter(
            id=vendor_id,
            company=company,
        ).first()

        if not vendor:
            return Response(
                {
                    "message": "Vendor not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -----------------------------------
        # Base queryset - all bills of vendor
        # -----------------------------------

        vendor_bills = Bill.objects.filter(
            company=company,
            vendor=vendor,
        )

        # -----------------------------------
        # Summary
        # -----------------------------------

        summary_data = vendor_bills.aggregate(
            total_bills=Count("id"),
            total_bill_amount=Sum("total_amount"),
            total_paid=Sum("amount_paid"),
        )

        total_bills = (
            summary_data["total_bills"]
            or 0
        )

        total_bill_amount = (
            summary_data["total_bill_amount"]
            or Decimal("0.00")
        )

        total_paid = (
            summary_data["total_paid"]
            or Decimal("0.00")
        )

        total_balance_due = (
            total_bill_amount - total_paid
        )

        if total_balance_due < Decimal("0.00"):
            total_balance_due = Decimal("0.00")

        overdue_bill_count = vendor_bills.filter(
            status="overdue"
        ).count()

        # -----------------------------------
        # List queryset
        # -----------------------------------

        queryset = (
            vendor_bills
            .select_related("vendor")
        )

        # -----------------------------------
        # Search by PO number
        # -----------------------------------

        search = request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                po_reference__icontains=search
            )

        # -----------------------------------
        # Filter by status
        # -----------------------------------

        status_value = request.query_params.get("status")

        if status_value:
            queryset = queryset.filter(
                status=status_value
            )

        # -----------------------------------
        # Date range
        # -----------------------------------

        date_from = request.query_params.get("date_from")

        if date_from:
            queryset = queryset.filter(
                bill_date__gte=date_from
            )

        date_to = request.query_params.get("date_to")

        if date_to:
            queryset = queryset.filter(
                bill_date__lte=date_to
            )

        # -----------------------------------
        # Ordering
        # -----------------------------------

        queryset = queryset.order_by(
            "-bill_date",
            "-id",
        )

        # -----------------------------------
        # Pagination
        # -----------------------------------

        paginator = self.pagination_class()

        page = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )

        # -----------------------------------
        # Serialize paginated records
        # -----------------------------------

        serializer = VendorBillListSerializer(
            page,
            many=True,
            context={"request": request},
        )

        # -----------------------------------
        # Response
        # -----------------------------------

        return Response(
            {
                "vendor": {
                    "id": vendor.id,
                    "vendor_id": vendor.vendor_id,
                    "name": vendor.name,
                },

                "summary": {
                    "total_bills": total_bills,
                    "total_bill_amount": str(
                        total_bill_amount
                    ),
                    "total_paid": str(
                        total_paid
                    ),
                    "total_balance_due": str(
                        total_balance_due
                    ),
                    "overdue_bill_count": overdue_bill_count,
                },

                "count": paginator.page.paginator.count,

                "next": paginator.get_next_link(),

                "previous": paginator.get_previous_link(),

                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


from decimal import Decimal

from django.db.models import Q, Count, Sum
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Vendor, VendorPayment
from .serializers import VendorPaymentListSerializer
from shared.pagination import CustomPagination


class VendorPaymentListView(APIView):

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, vendor_id):

        company = request.user.company

        # -----------------------------------
        # Validate vendor
        # -----------------------------------

        vendor = Vendor.objects.filter(
            id=vendor_id,
            company=company,
        ).first()

        if not vendor:
            return Response(
                {
                    "message": "Vendor not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -----------------------------------
        # Base queryset
        # -----------------------------------

        vendor_payments = VendorPayment.objects.filter(
            company=company,
            vendor=vendor,
        )

        # -----------------------------------
        # Summary
        # -----------------------------------

        summary_data = vendor_payments.aggregate(
            total_payments=Count("id"),

            total_paid_amount=Sum(
                "amount_paid",
                filter=Q(status="completed"),
            ),

            pending_clearance=Sum(
                "amount_paid",
                filter=Q(status="pending"),
            ),

            failed_payments=Count(
                "id",
                filter=Q(status="cancelled"),
            ),
        )

        total_payments = (
            summary_data["total_payments"]
            or 0
        )

        total_paid_amount = (
            summary_data["total_paid_amount"]
            or Decimal("0.00")
        )

        pending_clearance = (
            summary_data["pending_clearance"]
            or Decimal("0.00")
        )

        failed_payments = (
            summary_data["failed_payments"]
            or 0
        )

        # -----------------------------------
        # This month paid amount
        # -----------------------------------

        today = timezone.localdate()

        this_month_paid_amount = (
            vendor_payments
            .filter(
                status="completed",
                payment_date__year=today.year,
                payment_date__month=today.month,
            )
            .aggregate(
                total=Sum("amount_paid")
            )["total"]
            or Decimal("0.00")
        )

        # -----------------------------------
        # List queryset
        # -----------------------------------

        queryset = (
            vendor_payments
            .select_related(
                "vendor",
                "bill",
            )
        )

        # -----------------------------------
        # Search
        # -----------------------------------

        search = request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(receipt_number__icontains=search)
                | Q(reference_number__icontains=search)
                | Q(bill__bill_number__icontains=search)
            )

        # -----------------------------------
        # Status filter
        # -----------------------------------

        status_value = request.query_params.get("status")

        if status_value:
            queryset = queryset.filter(
                status=status_value
            )

        # -----------------------------------
        # Payment method filter
        # -----------------------------------

        payment_method = request.query_params.get(
            "payment_method"
        )

        if payment_method:
            queryset = queryset.filter(
                payment_method=payment_method
            )

        # -----------------------------------
        # Date range filter
        # -----------------------------------

        date_from = request.query_params.get(
            "date_from"
        )

        date_to = request.query_params.get(
            "date_to"
        )

        if date_from:
            queryset = queryset.filter(
                payment_date__gte=date_from
            )

        if date_to:
            queryset = queryset.filter(
                payment_date__lte=date_to
            )

        # -----------------------------------
        # Ordering
        # -----------------------------------

        queryset = queryset.order_by(
            "-payment_date",
            "-id",
        )

        # -----------------------------------
        # Pagination
        # -----------------------------------

        paginator = self.pagination_class()

        page = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )

        # -----------------------------------
        # Serialize paginated records
        # -----------------------------------

        serializer = VendorPaymentListSerializer(
            page,
            many=True,
            context={"request": request},
        )

        # -----------------------------------
        # Response
        # -----------------------------------

        return Response(
            {
                "vendor": {
                    "id": vendor.id,
                    "vendor_id": vendor.vendor_id,
                    "name": vendor.name,
                },

                "summary": {
                    "total_payments": total_payments,
                    "total_paid_amount": str(
                        total_paid_amount
                    ),
                    "this_month_paid_amount": str(
                        this_month_paid_amount
                    ),
                    "pending_clearance": str(
                        pending_clearance
                    ),
                    "failed_payments": failed_payments,
                },

                "count": paginator.page.paginator.count,

                "next": paginator.get_next_link(),

                "previous": paginator.get_previous_link(),

                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

from decimal import Decimal

from django.db.models import Q, Sum

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from finance.debit_note.models import DebitNote

from .serializers import VendorDebitNoteListSerializer


class VendorDebitNoteListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, vendor_id):

        company = request.user.company

        # ---------------------------------------------------------
        # Validate Vendor
        # ---------------------------------------------------------
        vendor = Vendor.objects.filter(
            id=vendor_id,
            company=company
        ).first()

        if not vendor:
            return Response(
                {
                    "detail": "Vendor not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # ---------------------------------------------------------
        # Base Queryset
        # ---------------------------------------------------------
        base_queryset = (
            DebitNote.objects
            .filter(
                company=company,
                vendor=vendor
            )
            .select_related(
                "vendor",
                "bill"
            )
        )

        # ---------------------------------------------------------
        # SUMMARY
        # ---------------------------------------------------------

        summary_queryset = base_queryset.exclude(
            status="draft"
        )

        total_debit_notes = summary_queryset.count()

        total_debit_amount = (
            summary_queryset.aggregate(
                total=Sum("debit_amount")
            )["total"]
            or Decimal("0.00")
        )

        applied_to_bill_amount = (
            summary_queryset.aggregate(
                total=Sum("applied_amount")
            )["total"]
            or Decimal("0.00")
        )

        pending_unapplied_amount = (
            total_debit_amount - applied_to_bill_amount
        )

        if pending_unapplied_amount < Decimal("0.00"):
            pending_unapplied_amount = Decimal("0.00")

        cancelled_notes = base_queryset.filter(
            status="cancelled"
        ).count()

        # ---------------------------------------------------------
        # FILTERED QUERYSET
        # ---------------------------------------------------------

        queryset = base_queryset

        # Search
        search = request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(dn_number__icontains=search)
                | Q(bill__bill_number__icontains=search)
                | Q(bill_ref__icontains=search)
            )

        # Reason
        reason = request.query_params.get("reason")

        if reason:
            queryset = queryset.filter(
                reason=reason
            )

        # Status
        status_filter = request.query_params.get("status")

        if status_filter:
            queryset = queryset.filter(
                status=status_filter
            )

        # Date range
        date_from = request.query_params.get("date_from")

        if date_from:
            queryset = queryset.filter(
                issue_date__gte=date_from
            )

        date_to = request.query_params.get("date_to")

        if date_to:
            queryset = queryset.filter(
                issue_date__lte=date_to
            )

        # Ordering
        queryset = queryset.order_by(
            "-issue_date",
            "-id"
        )

        # ---------------------------------------------------------
        # PAGINATION
        # ---------------------------------------------------------

        paginator = self.pagination_class()

        page = paginator.paginate_queryset(
            queryset,
            request,
            view=self
        )

        serializer = VendorDebitNoteListSerializer(
            page,
            many=True,
            context={"request": request}
        )

        # ---------------------------------------------------------
        # PAGINATED RESPONSE
        # ---------------------------------------------------------

        return Response(
            {
                "vendor": {
                    "id": vendor.id,
                    "vendor_id": vendor.vendor_id,
                    "name": vendor.name,
                },

                "summary": {
                    "total_debit_notes": total_debit_notes,
                    "total_debit_amount": str(
                        total_debit_amount
                    ),
                    "applied_to_bill_amount": str(
                        applied_to_bill_amount
                    ),
                    "pending_unapplied_amount": str(
                        pending_unapplied_amount
                    ),
                    "cancelled_notes": cancelled_notes,
                },

                "count": paginator.page.paginator.count,

                "next": paginator.get_next_link(),

                "previous": paginator.get_previous_link(),

                "results": serializer.data,
            },
            status=status.HTTP_200_OK
        )