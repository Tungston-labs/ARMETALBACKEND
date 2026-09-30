from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from rest_framework import (
    viewsets,
    generics,
    filters,
    status,
)

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

from user.permissions import (
    IsHRAdmin,
    IsCompanyActive,
)

from shared.pagination import CustomPagination

from .models import (
    Vendor,
    VendorBill,
    VendorPayment,
    VendorDocument,
)

from .serializers import (
    VendorSerializer,
    VendorCreateSerializer,
)


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

            vendor_document.document.save(
                uploaded_file.name,
                uploaded_file,
                save=True,
            )

            saved_documents.append(
                vendor_document
            )

        # Refresh
        vendor = (
            Vendor.objects
            .filter(
                company=request.user.company,
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

        serializer = VendorSerializer(
            vendor,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "message": (
                    "Vendor documents uploaded "
                    "successfully."
                ),
                "documents_uploaded": len(
                    saved_documents
                ),
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


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

        month_start = today.replace(
            day=1
        )

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
            },
            status=status.HTTP_200_OK,
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

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(po_number__icontains=search)
                | Q(pr_reference__icontains=search)
            )

        order_status = self.request.query_params.get(
            "order_status"
        )

        delivery_status = self.request.query_params.get(
            "delivery_status"
        )

        bill_status = self.request.query_params.get(
            "bill_status"
        )

        if order_status:
            queryset = queryset.filter(
                status=order_status
            )

        if delivery_status:
            queryset = queryset.filter(
                receipt_status=delivery_status
            )

        if bill_status:
            queryset = queryset.filter(
                bill_status=bill_status
            )

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset()
        )

        # Summary should be based on ALL purchase orders
        # of this vendor, not the filtered search result.
        vendor_id = kwargs["vendor_id"]

        all_vendor_orders = PurchaseOrder.objects.filter(
            company=request.user.company,
            vendor_id=vendor_id,
        )

        total_orders = all_vendor_orders.count()

        total_po_value = (
            all_vendor_orders.aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        # Orders waiting for approval
        pending_approval_count = all_vendor_orders.filter(
            status="pending"
        ).count()

        # Open orders
        open_orders_count = all_vendor_orders.filter(
            status__in=[
                "approved",
                "ordered",
                "partially_received",
            ]
        ).count()

        # Completed orders
        completed_orders_count = all_vendor_orders.filter(
            status="received"
        ).count()

        # Pagination
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True,
            )

            response_data = {
                "summary": {
                    "total_orders": total_orders,
                    "total_po_value": str(total_po_value),
                    "pending_approval_count": pending_approval_count,
                    "open_orders_count": open_orders_count,
                    "completed_orders_count": completed_orders_count,
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
                "total_po_value": str(total_po_value),
                "pending_approval_count": pending_approval_count,
                "open_orders_count": open_orders_count,
                "completed_orders_count": completed_orders_count,
            },
            "purchase_orders": serializer.data,
        })