from rest_framework import generics, filters, status
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import F, Q, Sum, ExpressionWrapper, DecimalField
from drf_spectacular.utils import extend_schema, OpenApiResponse

from finance.product.models import Product
from shared.pagination import CustomPagination
from .models import StockAdjustment
from .serializers import InventoryListSerializer, StockAdjustmentSerializer


class InventoryKPICardView(APIView):
    """
    API view to retrieve Inventory KPI metrics:
    - total_stock_items
    - in_stock
    - low_stock
    - out_of_stock
    - total_inventory_value
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Inventory KPI Metrics",
        description="Returns KPI card statistics for Inventory (Total Items, In Stock, Low Stock, Out of Stock, Total Inventory Value).",
        responses={200: OpenApiResponse(description="Inventory KPI Statistics")}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if getattr(user, "is_superadmin", False):
            company_id = request.query_params.get("company")
            if company_id:
                base_qs = Product.objects.filter(company_id=company_id, product_type="product")
            else:
                base_qs = Product.objects.filter(product_type="product")
        elif hasattr(user, "company") and user.company:
            base_qs = Product.objects.filter(company=user.company, product_type="product")
        else:
            base_qs = Product.objects.none()

        total_stock_items = base_qs.count()
        in_stock = base_qs.filter(current_stock__gt=0).count()
        low_stock = base_qs.filter(current_stock__gt=0).filter(
            Q(current_stock__lt=10) | Q(current_stock__lt=F("reorder_level"))
        ).count()
        out_of_stock = base_qs.filter(current_stock__lte=0).count()

        inventory_value_expr = ExpressionWrapper(
            F("current_stock") * F("selling_price"),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )
        total_value_agg = base_qs.aggregate(total_val=Sum(inventory_value_expr))
        total_inventory_value = total_value_agg["total_val"] or 0.00

        return Response({
            "total_stock_items": total_stock_items,
            "in_stock": in_stock,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "total_inventory_value": total_inventory_value,
        })


class InventoryListView(generics.ListAPIView):
    """
    API view to list Product Inventory rows with filters and summary counters.
    """
    serializer_class = InventoryListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "warehouse"]
    search_fields = ["product_name", "code", "sku", "brand"]
    ordering_fields = ["product_name", "code", "current_stock", "reorder_level", "updated_at"]
    ordering = ["-updated_at"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                qs = Product.objects.filter(company_id=company_id, product_type="product")
            else:
                qs = Product.objects.filter(product_type="product")
        elif hasattr(user, "company") and user.company:
            qs = Product.objects.filter(company=user.company, product_type="product")
        else:
            return Product.objects.none()

        stock_status = self.request.query_params.get("stock_status")
        if stock_status:
            stock_status = stock_status.lower().strip()
            if stock_status == "out_of_stock":
                qs = qs.filter(current_stock__lte=0)
            elif stock_status == "low_stock":
                qs = qs.filter(current_stock__gt=0).filter(
                    Q(current_stock__lt=10) | Q(current_stock__lt=F("reorder_level"))
                )
            elif stock_status == "in_stock":
                qs = qs.filter(current_stock__gt=0)

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            qs = qs.filter(updated_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(updated_at__date__lte=end_date)

        return qs.select_related("company", "category", "warehouse")

    @extend_schema(
        summary="List Inventory Items",
        description="Retrieves a paginated list of inventory stock items with search, warehouse, category, and stock status filters.",
        responses={200: InventoryListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        base_qs = self.get_queryset()

        total_stock_items = base_qs.count()
        in_stock = base_qs.filter(current_stock__gt=0).count()
        low_stock = base_qs.filter(current_stock__gt=0).filter(
            Q(current_stock__lt=10) | Q(current_stock__lt=F("reorder_level"))
        ).count()
        out_of_stock = base_qs.filter(current_stock__lte=0).count()

        inventory_value_expr = ExpressionWrapper(
            F("current_stock") * F("selling_price"),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )
        total_value_agg = base_qs.aggregate(total_val=Sum(inventory_value_expr))
        total_inventory_value = total_value_agg["total_val"] or 0.00

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_stock_items"] = total_stock_items
            response.data["in_stock"] = in_stock
            response.data["low_stock"] = low_stock
            response.data["out_of_stock"] = out_of_stock
            response.data["total_inventory_value"] = total_inventory_value
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_stock_items": total_stock_items,
            "in_stock": in_stock,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "total_inventory_value": total_inventory_value,
        })


class StockAdjustmentListCreateView(generics.ListCreateAPIView):
    """
    API view to list all stock adjustments or create/confirm a new stock adjustment.
    """
    serializer_class = StockAdjustmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["product", "warehouse", "adjustment_type", "reason"]
    search_fields = ["code", "sku", "reason", "reference_document", "product__product_name"]
    ordering_fields = ["created_at", "adjustment_date", "adjustment_quantity"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                qs = StockAdjustment.objects.filter(company_id=company_id)
            else:
                qs = StockAdjustment.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = StockAdjustment.objects.filter(company=user.company)
        else:
            qs = StockAdjustment.objects.none()

        return qs.select_related("company", "product", "warehouse", "created_by")

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    @extend_schema(
        summary="List Stock Adjustments",
        description="Retrieves a paginated list of stock adjustment audit logs for the company.",
        responses={200: StockAdjustmentSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Confirm / Create Stock Adjustment",
        description="Creates a new stock adjustment entry and updates the product available stock quantity (+ or -).",
        request=StockAdjustmentSerializer,
        responses={
            201: StockAdjustmentSerializer,
            400: OpenApiResponse(description="Validation Error")
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class StockAdjustmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a stock adjustment audit record by ID.
    """
    serializer_class = StockAdjustmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            qs = StockAdjustment.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = StockAdjustment.objects.filter(company=user.company)
        else:
            qs = StockAdjustment.objects.none()

        return qs.select_related("company", "product", "warehouse", "created_by")

    @extend_schema(
        summary="Get Stock Adjustment Details",
        description="Retrieves detailed information of a specific stock adjustment by ID.",
        responses={200: StockAdjustmentSerializer, 404: OpenApiResponse(description="Stock Adjustment Not Found")}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Stock Adjustment (Full)",
        description="Updates all fields of an existing stock adjustment record.",
        request=StockAdjustmentSerializer,
        responses={200: StockAdjustmentSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Not Found")}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Stock Adjustment (Partial)",
        description="Partially updates fields of an existing stock adjustment record.",
        request=StockAdjustmentSerializer,
        responses={200: StockAdjustmentSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Not Found")}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Stock Adjustment Record",
        description="Deletes a stock adjustment audit record by ID.",
        responses={204: OpenApiResponse(description="No Content"), 404: OpenApiResponse(description="Not Found")}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)
