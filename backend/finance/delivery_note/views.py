from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from decimal import Decimal

from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import DeliveryNote
from .serializers import DeliveryNoteSerializer
from shared.pagination import CustomPagination


class DeliveryNoteKPICardView(APIView):
    """
    API view to retrieve KPI card metrics for Delivery Notes
    (Total Deliveries, Pending Deliveries, Partially Delivered, Delivered, Delivery Value).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Delivery Note KPI Card Metrics",
        description="Returns KPI card statistics for delivery notes under the authenticated user's company.",
        responses={200: OpenApiResponse(description="Delivery Note KPI Statistics")}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if getattr(user, "is_superadmin", False):
            company_id = request.query_params.get("company")
            if company_id:
                base_qs = DeliveryNote.objects.filter(company_id=company_id)
            else:
                base_qs = DeliveryNote.objects.all()
        elif hasattr(user, "company") and user.company:
            base_qs = DeliveryNote.objects.filter(company=user.company)
        else:
            base_qs = DeliveryNote.objects.none()

        stats = base_qs.aggregate(
            total_value=Coalesce(Sum("delivery_value"), Decimal("0.00"))
        )

        total_deliveries = base_qs.count()
        pending_deliveries = base_qs.filter(delivery_status="pending").count()
        partially_delivered = base_qs.filter(
            Q(delivery_status="partially_delivered") | Q(delivery_status="partial")
        ).count()
        delivered = base_qs.filter(delivery_status="delivered").count()

        return Response({
            "total_deliveries": total_deliveries,
            "pending_deliveries": pending_deliveries,
            "partially_delivered": partially_delivered,
            "delivered": delivered,
            "delivery_value": stats["total_value"],
        })


class DeliveryNoteListCreateView(generics.ListCreateAPIView):
    """
    API view to list all delivery notes or create a new delivery note for the authenticated user's company.
    """
    serializer_class = DeliveryNoteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["delivery_status", "invoice_status", "customer", "warehouse", "delivery_date"]
    search_fields = [
        "dn_number",
        "so_ref",
        "customer__customer_name",
        "customer__company_name",
        "warehouse__warehouse_name",
        "notes",
    ]
    ordering_fields = [
        "dn_number",
        "so_ref",
        "delivery_date",
        "delivery_value",
        "created_at",
        "delivery_status",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                qs = DeliveryNote.objects.filter(company_id=company_id)
            else:
                qs = DeliveryNote.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = DeliveryNote.objects.filter(company=user.company)
        else:
            qs = DeliveryNote.objects.none()

        return qs.select_related("company", "customer", "warehouse", "created_by").prefetch_related("items")

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    @extend_schema(
        summary="List Delivery Notes",
        description="Retrieves a paginated list of delivery notes for the authenticated company, along with KPI statistics.",
        responses={200: DeliveryNoteSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create New Delivery Note",
        description="Creates a new delivery note under the user's company.",
        request=DeliveryNoteSerializer,
        responses={
            201: DeliveryNoteSerializer,
            400: OpenApiResponse(description="Validation Error")
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        base_qs = self.get_queryset()

        stats = base_qs.aggregate(
            total_value=Coalesce(Sum("delivery_value"), Decimal("0.00"))
        )
        total_deliveries = base_qs.count()
        pending_deliveries = base_qs.filter(delivery_status="pending").count()
        partially_delivered = base_qs.filter(
            Q(delivery_status="partially_delivered") | Q(delivery_status="partial")
        ).count()
        delivered = base_qs.filter(delivery_status="delivered").count()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_deliveries"] = total_deliveries
            response.data["pending_deliveries"] = pending_deliveries
            response.data["partially_delivered"] = partially_delivered
            response.data["delivered"] = delivered
            response.data["delivery_value"] = stats["total_value"]
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_deliveries": total_deliveries,
            "pending_deliveries": pending_deliveries,
            "partially_delivered": partially_delivered,
            "delivered": delivered,
            "delivery_value": stats["total_value"],
        })


class DeliveryNoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a delivery note by ID.
    """
    serializer_class = DeliveryNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            qs = DeliveryNote.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = DeliveryNote.objects.filter(company=user.company)
        else:
            qs = DeliveryNote.objects.none()

        return qs.select_related("company", "customer", "warehouse", "created_by").prefetch_related("items")

    @extend_schema(
        summary="Get Delivery Note Details",
        description="Retrieves detailed information of a specific delivery note by ID.",
        responses={200: DeliveryNoteSerializer, 404: OpenApiResponse(description="Delivery Note Not Found")}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Delivery Note (Full)",
        description="Updates all fields of an existing delivery note.",
        request=DeliveryNoteSerializer,
        responses={200: DeliveryNoteSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Delivery Note Not Found")}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Delivery Note (Partial)",
        description="Partially updates fields of an existing delivery note.",
        request=DeliveryNoteSerializer,
        responses={200: DeliveryNoteSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Delivery Note Not Found")}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Delivery Note",
        description="Deletes a delivery note by ID.",
        responses={204: OpenApiResponse(description="No Content"), 404: OpenApiResponse(description="Delivery Note Not Found")}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)
