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
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

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

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        response_serializer = self.get_serializer(payment)
        return Response(
            {
                "message": "Vendor payment updated successfully.",
                "data": response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {
                "message": "Vendor payment deleted successfully.",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Vendor Payment KPI Metrics",
        description="Retrieve financial summary KPIs including Total Payments, Payments This Month, Outstanding, and Advance Payments.",
        responses={200: VendorPaymentKPISerializer},
    )
    @action(detail=False, methods=["get"], url_path="kpi")
    def kpi(self, request):
        user = request.user
        company = user.company

        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        vendor_id = request.query_params.get("vendor")

        payment_qs = VendorPayment.objects.filter(company=company)
        bill_qs = Bill.objects.filter(company=company)

        if vendor_id:
            payment_qs = payment_qs.filter(vendor_id=vendor_id)
            bill_qs = bill_qs.filter(vendor_id=vendor_id)

        # 1. Total payments
        total_payments = (
            payment_qs.filter(
                status="completed",
            ).aggregate(
                total=Sum("amount_paid")
            )["total"]
            or Decimal("0.00")
        )

        # 2. Payments this month
        payments_this_month = (
            payment_qs.filter(
                status="completed",
                payment_date__gte=start_of_month,
            ).aggregate(
                total=Sum("amount_paid")
            )["total"]
            or Decimal("0.00")
        )

        # 3. Outstanding payables (total unpaid on non-paid bills)
        outstanding = Decimal("0.00")
        for b in bill_qs.exclude(status="paid"):
            outstanding += b.balance

        # 4. Advance payments
        advance_payments = (
            payment_qs.filter(
                status="completed",
                payment_type="advance_payment",
            ).aggregate(
                total=Sum("amount_paid")
            )["total"]
            or Decimal("0.00")
        )

        data = {
            "total_payments": total_payments,
            "payments_this_month": payments_this_month,
            "outstanding": outstanding,
            "advance_payments": advance_payments,
        }

        serializer = VendorPaymentKPISerializer(data)
        return Response(
            {
                "message": "Vendor payment KPI metrics retrieved successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Export Vendor Payments",
        description="Export vendor payment records in CSV format.",
        responses={200: OpenApiTypes.BINARY},
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="vendor_payments_export.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Payment No",
            "Vendor",
            "Bill No",
            "Payment Date",
            "Payment Type",
            "Payment Method",
            "Amount (SAR)",
            "Reference Number",
            "Status",
            "Notes",
        ])

        for payment in queryset:
            writer.writerow([
                payment.receipt_number,
                payment.vendor.name if payment.vendor else "",
                payment.bill.bill_number if payment.bill else "",
                payment.payment_date,
                payment.get_payment_type_display(),
                payment.get_payment_method_display(),
                payment.amount_paid,
                payment.reference_number,
                payment.get_status_display(),
                payment.notes,
            ])

        return response
