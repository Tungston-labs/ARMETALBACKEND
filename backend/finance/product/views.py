from rest_framework import generics, filters
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import F, Q
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter, OpenApiTypes

from .models import Product
from .serializers import ProductSerializer
from shared.pagination import CustomPagination


class ProductKPICardView(APIView):
    """
    API view to retrieve KPI card counts for Products (Total Products, Active/In Stock Products, Low Stock, Out of Stock, Total Categories).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Product KPI Card Metrics",
        description="Returns KPI card statistics for products and categories under the authenticated user's company.",
        responses={200: OpenApiResponse(description="KPI Statistics")}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if getattr(user, "is_superadmin", False):
            company_id = request.query_params.get("company")
            if company_id:
                base_qs = Product.objects.filter(company_id=company_id)
            else:
                base_qs = Product.objects.all()
        elif hasattr(user, "company") and user.company:
            base_qs = Product.objects.filter(company=user.company)
        else:
            base_qs = Product.objects.none()

        total_products = base_qs.count()
        active_products = base_qs.filter(status="active").count()
        in_stock_count = base_qs.filter(
            Q(product_type="service") |
            (Q(product_type="product", current_stock__gte=10) & Q(current_stock__gte=F("reorder_level")))
        ).count()

        prod_qs = base_qs.filter(product_type="product")
        low_stock = prod_qs.filter(current_stock__gt=0).filter(
            Q(current_stock__lt=10) | Q(current_stock__lt=F("reorder_level"))
        ).count()
        out_of_stock = prod_qs.filter(current_stock__lte=0).count()

        total_categories = base_qs.filter(category__isnull=False).values("category").distinct().count()

        return Response({
            "total_products": total_products,
            "active_products": active_products,
            "in_stock": in_stock_count,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "total_categories": total_categories,
        })


class ProductListCreateView(generics.ListCreateAPIView):
    """
    API view to list all products or create a new product/service for the user's company.
    """
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["product_type", "category", "warehouse", "unit"]
    search_fields = ["product_name", "code", "sku", "brand", "supplier", "hsn_sac_code"]
    ordering_fields = ["product_name", "code", "cost_price", "selling_price", "current_stock", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                qs = Product.objects.filter(company_id=company_id)
            else:
                qs = Product.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = Product.objects.filter(company=user.company)
        else:
            qs = Product.objects.none()

        status_param = self.request.query_params.get("status") or self.request.query_params.get("stock_status")
        if status_param:
            val = status_param.lower().strip()
            if val in ["out_of_stock", "out of stock", "out", "outofstock"]:
                qs = qs.filter(product_type="product", current_stock__lte=0)
            elif val in ["low_stock", "low stock", "low", "lowstock"]:
                qs = qs.filter(product_type="product", current_stock__gt=0).filter(
                    Q(current_stock__lt=10) | Q(current_stock__lt=F("reorder_level"))
                )
            elif val in ["in_stock", "in stock", "in", "instock", "active_stock", "active stock"]:
                qs = qs.filter(
                    Q(product_type="service") |
                    (Q(product_type="product", current_stock__gte=10) & Q(current_stock__gte=F("reorder_level")))
                )
            elif val == "inactive":
                qs = qs.filter(status="inactive")
            elif val == "active":
                qs = qs.filter(
                    Q(status="active") & (
                        Q(product_type="service") |
                        (Q(product_type="product", current_stock__gte=10) & Q(current_stock__gte=F("reorder_level")))
                    )
                )

        return qs.select_related("company", "category", "warehouse", "created_by")

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    @extend_schema(
        summary="List Products & Services",
        description="Retrieves a paginated list of products for the company, including summary counters (total, active, low stock, out of stock, total categories). Filter by stock status using 'status' or 'stock_status'.",
        parameters=[
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter products by stock status (In Stock, Low Stock, Out of Stock) or active status. Choices: 'in_stock', 'low_stock', 'out_of_stock', 'active', 'inactive'.",
                enum=["in_stock", "low_stock", "out_of_stock", "active", "inactive"]
            ),
            OpenApiParameter(
                name="stock_status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter products by stock status: 'in_stock' (>= 10 or service), 'low_stock' (< 10 or < reorder level), 'out_of_stock' (<= 0).",
                enum=["in_stock", "low_stock", "out_of_stock"]
            ),
        ],
        responses={200: ProductSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Add New Product / Service",
        description="Creates a new product or service. Auto-generates product code (PRD-001) if omitted.",
        request=ProductSerializer,
        responses={
            201: ProductSerializer,
            400: OpenApiResponse(description="Validation Error")
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        base_qs = self.get_queryset()

        total_products = base_qs.count()
        active_products = base_qs.filter(status="active").count()
        in_stock_count = base_qs.filter(
            Q(product_type="service") |
            (Q(product_type="product", current_stock__gte=10) & Q(current_stock__gte=F("reorder_level")))
        ).count()
        
        # Stock status calculations for physical products
        prod_qs = base_qs.filter(product_type="product")
        low_stock = prod_qs.filter(current_stock__gt=0).filter(Q(current_stock__lt=10) | Q(current_stock__lt=F("reorder_level"))).count()
        out_of_stock = prod_qs.filter(current_stock__lte=0).count()

        total_categories = base_qs.filter(category__isnull=False).values("category").distinct().count()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_products"] = total_products
            response.data["active_products"] = active_products
            response.data["in_stock"] = in_stock_count
            response.data["low_stock"] = low_stock
            response.data["out_of_stock"] = out_of_stock
            response.data["total_categories"] = total_categories
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_products": total_products,
            "active_products": active_products,
            "in_stock": in_stock_count,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "total_categories": total_categories,
        })


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a product by ID.
    """
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            qs = Product.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = Product.objects.filter(company=user.company)
        else:
            qs = Product.objects.none()

        return qs.select_related("company", "category", "warehouse", "created_by")

    @extend_schema(
        summary="Get Product Details",
        description="Retrieves the detailed information of a specific product by ID.",
        responses={200: ProductSerializer, 404: OpenApiResponse(description="Product Not Found")}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Product (Full)",
        description="Updates all fields of an existing product.",
        request=ProductSerializer,
        responses={200: ProductSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Product Not Found")}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Product (Partial)",
        description="Partially updates fields of an existing product.",
        request=ProductSerializer,
        responses={200: ProductSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Product Not Found")}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Product",
        description="Deletes a product by ID.",
        responses={204: OpenApiResponse(description="No Content"), 404: OpenApiResponse(description="Product Not Found")}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

