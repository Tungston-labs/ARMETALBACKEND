from rest_framework import generics, filters, status
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Warehouse
from .serializers import WarehouseSerializer
from shared.pagination import CustomPagination


class WarehouseKPICardView(APIView):
    """
    API view to retrieve KPI card counts for Warehouses (Total, Active, Inactive).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Warehouse KPI Card Metrics",
        description="Returns KPI card statistics for warehouses under the authenticated user's company.",
        responses={200: OpenApiResponse(description="Warehouse KPI Statistics")}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if getattr(user, "is_superadmin", False):
            company_id = request.query_params.get("company")
            if company_id:
                base_qs = Warehouse.objects.filter(company_id=company_id)
            else:
                base_qs = Warehouse.objects.all()
        elif hasattr(user, "company") and user.company:
            base_qs = Warehouse.objects.filter(company=user.company)
        else:
            base_qs = Warehouse.objects.none()

        total_warehouses = base_qs.count()
        active_warehouses = base_qs.filter(status="active").count()
        inactive_warehouses = base_qs.filter(status="inactive").count()

        return Response({
            "total_warehouses": total_warehouses,
            "active_warehouses": active_warehouses,
            "inactive_warehouses": inactive_warehouses,
        })


class WarehouseListCreateView(generics.ListCreateAPIView):
    """
    API view to list all warehouses or create a new warehouse for the authenticated user's company.
    """
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "warehouse_type", "city", "country"]
    search_fields = ["warehouse_name", "code", "city", "country", "phone_number", "email"]
    ordering_fields = ["warehouse_name", "code", "created_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                return Warehouse.objects.filter(company_id=company_id)
            return Warehouse.objects.all()

        if hasattr(user, "company") and user.company:
            return Warehouse.objects.filter(company=user.company)

        return Warehouse.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    @extend_schema(
        summary="List Warehouses",
        description="Retrieves a paginated list of warehouses for the authenticated company, along with overall statistics (total, active, inactive count).",
        responses={200: WarehouseSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Add New Warehouse",
        description="Creates a new warehouse under the user's company.",
        request=WarehouseSerializer,
        responses={
            201: WarehouseSerializer,
            400: OpenApiResponse(description="Validation Error (e.g. duplicate warehouse code)")
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        base_qs = self.get_queryset()

        total_warehouses = base_qs.count()
        active_warehouses = base_qs.filter(status="active").count()
        inactive_warehouses = base_qs.filter(status="inactive").count()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_warehouses"] = total_warehouses
            response.data["active_warehouses"] = active_warehouses
            response.data["inactive_warehouses"] = inactive_warehouses
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_warehouses": total_warehouses,
            "active_warehouses": active_warehouses,
            "inactive_warehouses": inactive_warehouses,
        })


class WarehouseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a warehouse by ID.
    """
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            return Warehouse.objects.all()

        if hasattr(user, "company") and user.company:
            return Warehouse.objects.filter(company=user.company)

        return Warehouse.objects.none()

    @extend_schema(
        summary="Get Warehouse Details",
        description="Retrieves the detailed information of a specific warehouse by ID.",
        responses={200: WarehouseSerializer, 404: OpenApiResponse(description="Warehouse Not Found")}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Warehouse (Full)",
        description="Updates all fields of an existing warehouse.",
        request=WarehouseSerializer,
        responses={200: WarehouseSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Warehouse Not Found")}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Warehouse (Partial)",
        description="Partially updates fields of an existing warehouse.",
        request=WarehouseSerializer,
        responses={200: WarehouseSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Warehouse Not Found")}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Warehouse",
        description="Deletes a warehouse by ID.",
        responses={204: OpenApiResponse(description="No Content"), 404: OpenApiResponse(description="Warehouse Not Found")}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)
