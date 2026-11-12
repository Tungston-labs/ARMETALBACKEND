from django.db.models.deletion import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)
from rest_framework import filters, generics, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from shared.pagination import CustomPagination

from .filters import WarehouseFilter
from .serializers import WarehouseSerializer
from .utils import (
    ZERO_DECIMAL,
    annotate_warehouse_queryset,
    build_warehouse_export_response,
    calculate_warehouse_kpis,
    get_scoped_warehouse_queryset,
    resolve_request_company,
)


class WarehouseKPICardView(APIView):
    """
    API view to retrieve KPI card metrics for Warehouses:
    Total Warehouses, Total Stock Value, Active Warehouses, Inactive Warehouses,
    Average Capacity Used (%), and Near Full Capacity count.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Warehouse KPI Card Metrics",
        description="Returns KPI card statistics for warehouses under the authenticated user's company.",
        responses={200: OpenApiResponse(description="Warehouse KPI Statistics")},
    )
    def get(self, request, *args, **kwargs):
        scoped_qs = get_scoped_warehouse_queryset(request)
        company = resolve_request_company(request)
        return Response(calculate_warehouse_kpis(scoped_qs, company=company))


class WarehouseQueryMixin:
    """
    Shared queryset, filtering, searching, and ordering configuration for
    warehouse list and export endpoints.
    """

    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = WarehouseFilter
    search_fields = [
        "warehouse_name",
        "code",
        "manager",
        "city",
        "country",
        "phone_number",
        "email",
    ]
    ordering_fields = [
        "warehouse_name",
        "code",
        "created_at",
        "status",
        "city",
        "manager",
        "total_units",
        "stock_value",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        return annotate_warehouse_queryset(get_scoped_warehouse_queryset(self.request))


class WarehouseListCreateView(WarehouseQueryMixin, generics.ListCreateAPIView):
    """
    API view to list all warehouses or create a new warehouse for the authenticated user's company.
    Supports `?export=csv` / `?export=xlsx` for exporting filtered rows.
    """

    pagination_class = CustomPagination

    def perform_create(self, serializer):
        company = resolve_request_company(self.request)
        if not company:
            raise DRFValidationError({"company": "User is not associated with a company."})
        instance = serializer.save(company=company, created_by=self.request.user)
        instance.total_units = ZERO_DECIMAL
        instance.stock_value = ZERO_DECIMAL
        instance.total_products = 0
        instance.low_stock_products = 0
        instance.out_of_stock_products = 0

    @extend_schema(
        summary="List Warehouses",
        description=(
            "Retrieves a paginated list of warehouses for the authenticated company, "
            "along with overall KPI statistics. Pass `?export=csv` or `?export=xlsx` to download."
        ),
        parameters=[
            OpenApiParameter(
                name="export",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Set to 'csv' or 'xlsx' to export matching warehouses.",
                enum=["csv", "xlsx", "excel", "true", "1"],
            ),
            OpenApiParameter(
                name="near_full",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Filter warehouses near full capacity (>= 80%).",
            ),
        ],
        responses={200: WarehouseSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Add New Warehouse",
        description="Creates a new warehouse under the user's company.",
        request=WarehouseSerializer,
        responses={
            201: WarehouseSerializer,
            400: OpenApiResponse(description="Validation Error (e.g. duplicate warehouse code)"),
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        export_param = (request.query_params.get("export") or "").lower().strip()
        queryset = self.filter_queryset(self.get_queryset())

        if export_param in ("1", "true", "csv", "excel", "xlsx"):
            fmt = "xlsx" if export_param == "xlsx" else "csv"
            return build_warehouse_export_response(queryset, export_format=fmt)

        kpis = calculate_warehouse_kpis(
            get_scoped_warehouse_queryset(request),
            company=resolve_request_company(request),
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data.update(kpis)
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            **kpis,
        })


class WarehouseExportView(WarehouseQueryMixin, generics.GenericAPIView):
    """
    API view to export filtered warehouses as CSV (default) or XLSX.
    """

    @extend_schema(
        summary="Export Warehouses",
        description="Exports filtered warehouse rows as a downloadable CSV or XLSX file.",
        parameters=[
            OpenApiParameter(
                name="export",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Export file format: 'csv' (default) or 'xlsx'.",
                enum=["csv", "xlsx"],
            ),
        ],
        responses={200: OpenApiResponse(description="Downloadable CSV/XLSX file")},
    )
    def get(self, request, *args, **kwargs):
        fmt = (
            request.query_params.get("export")
            or request.query_params.get("file_format")
            or "csv"
        ).lower().strip()
        if fmt not in ("csv", "xlsx"):
            fmt = "csv"
        queryset = self.filter_queryset(self.get_queryset())
        return build_warehouse_export_response(queryset, export_format=fmt)


class WarehouseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a warehouse by ID.
    """

    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return annotate_warehouse_queryset(get_scoped_warehouse_queryset(self.request))

    @extend_schema(
        summary="Get Warehouse Details",
        description="Retrieves the detailed information of a specific warehouse by ID.",
        responses={200: WarehouseSerializer, 404: OpenApiResponse(description="Warehouse Not Found")},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Warehouse (Full)",
        description="Updates all fields of an existing warehouse.",
        request=WarehouseSerializer,
        responses={
            200: WarehouseSerializer,
            400: OpenApiResponse(description="Validation Error"),
            404: OpenApiResponse(description="Warehouse Not Found"),
        },
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Warehouse (Partial)",
        description="Partially updates fields of an existing warehouse.",
        request=WarehouseSerializer,
        responses={
            200: WarehouseSerializer,
            400: OpenApiResponse(description="Validation Error"),
            404: OpenApiResponse(description="Warehouse Not Found"),
        },
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Warehouse",
        description="Deletes a warehouse by ID.",
        responses={
            204: OpenApiResponse(description="No Content"),
            400: OpenApiResponse(description="Cannot delete referenced warehouse"),
            404: OpenApiResponse(description="Warehouse Not Found"),
        },
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "Cannot delete this warehouse because it is referenced by existing records."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
