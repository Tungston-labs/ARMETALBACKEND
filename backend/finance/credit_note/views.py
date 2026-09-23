from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal

from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import CreditNote
from .serializers import CreditNoteSerializer
from shared.pagination import CustomPagination


class CreditNoteKPICardView(APIView):
    """
    API view to retrieve KPI card metrics for Credit Notes
    (Total Credit Notes, Total Credit Value, Open Credits, Applied Credits, Cancelled Credits).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Credit Note KPI Card Metrics",
        description="Returns KPI card statistics for credit notes under the authenticated user's company.",
        responses={200: OpenApiResponse(description="Credit Note KPI Statistics")}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if getattr(user, "is_superadmin", False):
            company_id = request.query_params.get("company")
            if company_id:
                base_qs = CreditNote.objects.filter(company_id=company_id)
            else:
                base_qs = CreditNote.objects.all()
        elif hasattr(user, "company") and user.company:
            base_qs = CreditNote.objects.filter(company=user.company)
        else:
            base_qs = CreditNote.objects.none()

        customer_param = request.query_params.get("customer")
        if customer_param:
            base_qs = base_qs.filter(customer_id=customer_param)

        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        stats = base_qs.aggregate(
            total_value=Coalesce(Sum("credit_amount"), Decimal("0.00")),
            open_value=Coalesce(Sum("credit_amount", filter=Q(status="open")), Decimal("0.00")),
            applied_value=Coalesce(Sum("applied_amount"), Decimal("0.00")),
            this_month=Coalesce(Sum("credit_amount", filter=Q(issue_date__gte=start_of_month)), Decimal("0.00")),
        )

        total_credit_notes = base_qs.count()
        open_credit_notes = base_qs.filter(status="open").count()
        cancelled_credits = base_qs.filter(status="cancelled").count()

        return Response({
            "total_credit_notes": total_credit_notes,
            "total_credit_value": stats["total_value"],
            "this_month": stats["this_month"],
            "open_credits": stats["open_value"],
            "open_credit_notes": open_credit_notes,
            "applied_credits": stats["applied_value"],
            "cancelled_credits": cancelled_credits,
        })


class CreditNoteListCreateView(generics.ListCreateAPIView):
    """
    API view to list all credit notes or create a new credit note for the authenticated user's company.
    """
    serializer_class = CreditNoteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "reason", "customer", "issue_date"]
    search_fields = [
        "cn_number",
        "invoice_ref",
        "customer__customer_name",
        "customer__company_name",
        "reason",
        "notes",
    ]
    ordering_fields = [
        "cn_number",
        "invoice_ref",
        "issue_date",
        "credit_amount",
        "applied_amount",
        "created_at",
        "status",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                qs = CreditNote.objects.filter(company_id=company_id)
            else:
                qs = CreditNote.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = CreditNote.objects.filter(company=user.company)
        else:
            qs = CreditNote.objects.none()

        return qs.select_related("company", "customer", "created_by").prefetch_related("items")

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    @extend_schema(
        summary="List Credit Notes",
        description="Retrieves a paginated list of credit notes for the authenticated company, along with KPI statistics.",
        responses={200: CreditNoteSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create New Credit Note",
        description="Creates a new credit note under the user's company.",
        request=CreditNoteSerializer,
        responses={
            201: CreditNoteSerializer,
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

        from django.utils import timezone
        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        stats = base_qs.aggregate(
            total_value=Coalesce(Sum("credit_amount"), Decimal("0.00")),
            open_value=Coalesce(Sum("credit_amount", filter=Q(status="open")), Decimal("0.00")),
            applied_value=Coalesce(Sum("applied_amount"), Decimal("0.00")),
            this_month=Coalesce(Sum("credit_amount", filter=Q(issue_date__gte=start_of_month)), Decimal("0.00")),
        )
        total_credit_notes = base_qs.count()
        open_credit_notes = base_qs.filter(status="open").count()
        cancelled_credits = base_qs.filter(status="cancelled").count()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_credit_notes"] = total_credit_notes
            response.data["total_credit_value"] = stats["total_value"]
            response.data["this_month"] = stats["this_month"]
            response.data["open_credits"] = stats["open_value"]
            response.data["open_credit_notes"] = open_credit_notes
            response.data["applied_credits"] = stats["applied_value"]
            response.data["cancelled_credits"] = cancelled_credits
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_credit_notes": total_credit_notes,
            "total_credit_value": stats["total_value"],
            "this_month": stats["this_month"],
            "open_credits": stats["open_value"],
            "open_credit_notes": open_credit_notes,
            "applied_credits": stats["applied_value"],
            "cancelled_credits": cancelled_credits,
        })


class CreditNoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a credit note by ID.
    """
    serializer_class = CreditNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            qs = CreditNote.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = CreditNote.objects.filter(company=user.company)
        else:
            qs = CreditNote.objects.none()

        return qs.select_related("company", "customer", "created_by").prefetch_related("items")

    @extend_schema(
        summary="Get Credit Note Details",
        description="Retrieves detailed information of a specific credit note by ID.",
        responses={200: CreditNoteSerializer, 404: OpenApiResponse(description="Credit Note Not Found")}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Credit Note (Full)",
        description="Updates all fields of an existing credit note.",
        request=CreditNoteSerializer,
        responses={200: CreditNoteSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Credit Note Not Found")}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Credit Note (Partial)",
        description="Partially updates fields of an existing credit note.",
        request=CreditNoteSerializer,
        responses={200: CreditNoteSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Credit Note Not Found")}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Credit Note",
        description="Deletes a credit note by ID.",
        responses={204: OpenApiResponse(description="No Content"), 404: OpenApiResponse(description="Credit Note Not Found")}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)
