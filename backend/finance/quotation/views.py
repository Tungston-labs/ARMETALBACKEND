from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal

from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Quotation, QuotationConversion
from .serializers import (
    QuotationSerializer,
    QuotationConversionSerializer,
)
from shared.pagination import CustomPagination


class QuotationKPICardView(APIView):
    """
    API view to retrieve KPI card metrics for Quotations
    (Total Quotation Value, Negotiation Amount, Approved Quotes, Rejected Quotes, Pending Quotes).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Quotation KPI Card Metrics",
        description="Returns KPI card statistics for quotations under the authenticated user's company.",
        responses={200: OpenApiResponse(description="Quotation KPI Statistics")}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if getattr(user, "is_superadmin", False):
            company_id = request.query_params.get("company")
            if company_id:
                base_qs = Quotation.objects.filter(company_id=company_id)
            else:
                base_qs = Quotation.objects.all()
        elif hasattr(user, "company") and user.company:
            base_qs = Quotation.objects.filter(company=user.company)
        else:
            base_qs = Quotation.objects.none()

        stats = base_qs.aggregate(
            total_value=Coalesce(Sum("quote_amount"), Decimal("0.00")),
            total_negotiation=Coalesce(Sum("negotiation_amount"), Decimal("0.00"))
        )

        approved_quotes = base_qs.filter(status="approved").count()
        rejected_quotes = base_qs.filter(status="rejected").count()
        pending_quotes = base_qs.filter(status="pending").count()

        return Response({
            "total_quotation_value": stats["total_value"],
            "negotiation_amount": stats["total_negotiation"],
            "approved_quotes": approved_quotes,
            "rejected_quotes": rejected_quotes,
            "pending_quotes": pending_quotes,
        })


class QuotationListCreateView(generics.ListCreateAPIView):
    """
    API view to list all quotations or create a new quotation for the authenticated user's company.
    """
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "customer", "issue_date", "valid_till"]
    search_fields = [
        "quote_number",
        "customer__customer_name",
        "customer__company_name",
        "bill_to_name",
        "notes",
    ]
    ordering_fields = [
        "quote_number",
        "issue_date",
        "valid_till",
        "quote_amount",
        "negotiation_amount",
        "created_at",
        "status",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                qs = Quotation.objects.filter(company_id=company_id)
            else:
                qs = Quotation.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = Quotation.objects.filter(company=user.company)
        else:
            qs = Quotation.objects.none()

        return qs.select_related("company", "customer", "created_by").prefetch_related("items", "conversions")

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    @extend_schema(
        summary="List Quotations",
        description="Retrieves a paginated list of quotations for the authenticated company, along with KPI statistics.",
        responses={200: QuotationSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create New Quotation",
        description="Creates a new quotation under the user's company.",
        request=QuotationSerializer,
        responses={
            201: QuotationSerializer,
            400: OpenApiResponse(description="Validation Error")
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        customer_param = request.query_params.get("customer")
        if customer_param:
            base_qs = self.get_queryset().filter(customer_id=customer_param)
        else:
            base_qs = self.get_queryset()

        total_quotations = base_qs.count()
        stats = base_qs.aggregate(
            total_value=Coalesce(Sum("quote_amount"), Decimal("0.00")),
            total_negotiation=Coalesce(Sum("negotiation_amount"), Decimal("0.00"))
        )
        approved_quotes = base_qs.filter(status="approved").count()
        rejected_quotes = base_qs.filter(status="rejected").count()
        pending_quotes = base_qs.filter(status="pending").count()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_quotations"] = total_quotations
            response.data["total_quotation_value"] = stats["total_value"]
            response.data["negotiation_amount"] = stats["total_negotiation"]
            response.data["approved_quotes"] = approved_quotes
            response.data["rejected_quotes"] = rejected_quotes
            response.data["pending_quotes"] = pending_quotes
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_quotations": total_quotations,
            "total_quotation_value": stats["total_value"],
            "negotiation_amount": stats["total_negotiation"],
            "approved_quotes": approved_quotes,
            "rejected_quotes": rejected_quotes,
            "pending_quotes": pending_quotes,
        })


class QuotationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a quotation by ID.
    """
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            qs = Quotation.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = Quotation.objects.filter(company=user.company)
        else:
            qs = Quotation.objects.none()

        return qs.select_related("company", "customer", "created_by").prefetch_related("items", "conversions")

    @extend_schema(
        summary="Get Quotation Details",
        description="Retrieves detailed information of a specific quotation by ID.",
        responses={200: QuotationSerializer, 404: OpenApiResponse(description="Quotation Not Found")}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Quotation (Full)",
        description="Updates all fields of an existing quotation.",
        request=QuotationSerializer,
        responses={200: QuotationSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Quotation Not Found")}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Quotation (Partial)",
        description="Partially updates fields of an existing quotation.",
        request=QuotationSerializer,
        responses={200: QuotationSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Quotation Not Found")}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Quotation",
        description="Deletes a quotation by ID.",
        responses={204: OpenApiResponse(description="No Content"), 404: OpenApiResponse(description="Quotation Not Found")}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class QuotationConvertSOView(APIView):
    """
    API view to convert a quotation into a Sales Order / Record Payment transaction.
    Corresponds to clicking 'Convert SO' in the list page (Image 3 modal).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Convert Quotation to Sales Order",
        description="Converts the quotation into a Sales Order and records payment/SO transaction details.",
        request=QuotationConversionSerializer,
        responses={
            201: QuotationConversionSerializer,
            400: OpenApiResponse(description="Validation Error"),
            404: OpenApiResponse(description="Quotation Not Found")
        }
    )
    def post(self, request, pk, *args, **kwargs):
        user = request.user
        company = getattr(user, "company", None)

        try:
            if getattr(user, "is_superadmin", False):
                quotation = Quotation.objects.get(pk=pk)
            elif company:
                quotation = Quotation.objects.get(pk=pk, company=company)
            else:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except Quotation.DoesNotExist:
            return Response({"detail": "Quotation not found."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()

        # Default fields if omitted
        if not data.get("invoice_no"):
            data["invoice_no"] = quotation.quote_number or f"CLT{quotation.id:06d}"

        if "invoice_amount" not in data or data.get("invoice_amount") is None:
            data["invoice_amount"] = str(quotation.quote_amount)

        if "amount_received" not in data or data.get("amount_received") is None:
            data["amount_received"] = str(quotation.quote_amount)

        if not data.get("payment_date"):
            data["payment_date"] = timezone.localdate().isoformat()

        serializer = QuotationConversionSerializer(data=data)
        if serializer.is_valid():
            conversion = serializer.save(
                quotation=quotation,
                customer=quotation.customer,
                company=quotation.company,
                created_by=user
            )

            # Update Quotation status to converted
            quotation.status = "converted"
            quotation.save(update_fields=["status"])

            return Response({
                "message": "Quotation converted to Sales Order successfully.",
                "conversion": serializer.data,
                "quotation": QuotationSerializer(quotation).data
            }, status=status.HTTP_201_CREATED)

        return Response({
            "message": "Conversion failed.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
