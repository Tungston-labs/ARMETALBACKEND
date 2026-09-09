from rest_framework import generics, filters
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import F, Q
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Product
from .serializers import ProductSerializer
from shared.pagination import CustomPagination


class ProductKPICardView(APIView):
    """
    API view to retrieve KPI card counts for Products (Total Products, Active Products, Low Stock, Out of Stock, Total Categories).
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Get Product KPI Card Metrics",
        operation_description="Returns KPI card statistics for products and categories under the authenticated user's company.",
        responses={
            200: openapi.Response(
                description="KPI Statistics",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'total_products': openapi.Schema(type=openapi.TYPE_INTEGER, example=1248),
                        'active_products': openapi.Schema(type=openapi.TYPE_INTEGER, example=1175),
                        'low_stock': openapi.Schema(type=openapi.TYPE_INTEGER, example=10),
                        'out_of_stock': openapi.Schema(type=openapi.TYPE_INTEGER, example=22),
                        'total_categories': openapi.Schema(type=openapi.TYPE_INTEGER, example=12),
                    }
                )
            )
        }
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

        prod_qs = base_qs.filter(product_type="product")
        low_stock = prod_qs.filter(current_stock__gt=0).filter(Q(current_stock__lt=10) | Q(current_stock__lt=F("reorder_level"))).count()
        out_of_stock = prod_qs.filter(current_stock__lte=0).count()

        total_categories = base_qs.filter(category__isnull=False).values("category").distinct().count()

        return Response({
            "total_products": total_products,
            "active_products": active_products,
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
    filterset_fields = ["product_type", "status", "category", "warehouse", "unit"]
    search_fields = ["product_name", "code", "sku", "brand", "supplier", "hsn_sac_code"]
    ordering_fields = ["product_name", "code", "cost_price", "selling_price", "current_stock", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                return Product.objects.filter(company_id=company_id)
            return Product.objects.all()

        if hasattr(user, "company") and user.company:
            return Product.objects.filter(company=user.company)

        return Product.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    @swagger_auto_schema(
        operation_summary="List Products & Services",
        operation_description="Retrieves a paginated list of products for the company, including summary counters (total, active, low stock, out of stock, total categories).",
        responses={200: ProductSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Add New Product / Service",
        operation_description="Creates a new product or service. Auto-generates product code (PRD-001) if omitted.",
        request_body=ProductSerializer,
        responses={
            201: ProductSerializer,
            400: "Validation Error"
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        base_qs = self.get_queryset()

        total_products = base_qs.count()
        active_products = base_qs.filter(status="active").count()
        
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
            response.data["low_stock"] = low_stock
            response.data["out_of_stock"] = out_of_stock
            response.data["total_categories"] = total_categories
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_products": total_products,
            "active_products": active_products,
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
            return Product.objects.all()

        if hasattr(user, "company") and user.company:
            return Product.objects.filter(company=user.company)

        return Product.objects.none()

    @swagger_auto_schema(
        operation_summary="Get Product Details",
        operation_description="Retrieves the detailed information of a specific product by ID.",
        responses={200: ProductSerializer, 404: "Product Not Found"}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Edit/Update Product (Full)",
        operation_description="Updates all fields of an existing product.",
        request_body=ProductSerializer,
        responses={200: ProductSerializer, 400: "Validation Error", 404: "Product Not Found"}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Edit/Update Product (Partial)",
        operation_description="Partially updates fields of an existing product.",
        request_body=ProductSerializer,
        responses={200: ProductSerializer, 400: "Validation Error", 404: "Product Not Found"}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Delete Product",
        operation_description="Deletes a product by ID.",
        responses={204: "No Content", 404: "Product Not Found"}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)
