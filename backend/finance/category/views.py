from rest_framework import generics, filters, status
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Category
from .serializers import CategorySerializer
from shared.pagination import CustomPagination


class CategoryKPICardView(APIView):
    """
    API view to retrieve Category KPI summary metrics (total, active, inactive, product, service).
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Get Category KPI Card Metrics",
        operation_description="Retrieves KPI summary metrics for categories under the authenticated user's company.",
        responses={
            200: openapi.Response(
                description="Category KPI Statistics",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'total_categories': openapi.Schema(type=openapi.TYPE_INTEGER, example=12),
                        'active_categories': openapi.Schema(type=openapi.TYPE_INTEGER, example=10),
                        'inactive_categories': openapi.Schema(type=openapi.TYPE_INTEGER, example=2),
                        'product_categories': openapi.Schema(type=openapi.TYPE_INTEGER, example=8),
                        'service_categories': openapi.Schema(type=openapi.TYPE_INTEGER, example=4),
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
                base_qs = Category.objects.filter(company_id=company_id)
            else:
                base_qs = Category.objects.all()
        elif hasattr(user, "company") and user.company:
            base_qs = Category.objects.filter(company=user.company)
        else:
            base_qs = Category.objects.none()

        total_categories = base_qs.count()
        active_categories = base_qs.filter(status="active").count()
        inactive_categories = base_qs.filter(status="inactive").count()
        product_categories = base_qs.filter(category_type="product").count()
        service_categories = base_qs.filter(category_type="service").count()

        return Response({
            "total_categories": total_categories,
            "active_categories": active_categories,
            "inactive_categories": inactive_categories,
            "product_categories": product_categories,
            "service_categories": service_categories,
        })


class CategoryListCreateView(generics.ListCreateAPIView):
    """
    API view to list all categories or create a new category for the authenticated user's company.
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category_type", "status", "parent_category"]
    search_fields = ["category_name", "code"]
    ordering_fields = ["category_name", "code", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                return Category.objects.filter(company_id=company_id)
            return Category.objects.all()

        if hasattr(user, "company") and user.company:
            return Category.objects.filter(company=user.company)

        return Category.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    @swagger_auto_schema(
        operation_summary="List Categories",
        operation_description="Retrieves a paginated list of categories for the company, including summary metrics.",
        responses={200: CategorySerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Add New Category",
        operation_description="Creates a new category under the user's company.",
        request_body=CategorySerializer,
        responses={
            201: CategorySerializer,
            400: "Validation Error"
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        base_qs = self.get_queryset()

        total_categories = base_qs.count()
        active_categories = base_qs.filter(status="active").count()
        inactive_categories = base_qs.filter(status="inactive").count()
        product_categories = base_qs.filter(category_type="product").count()
        service_categories = base_qs.filter(category_type="service").count()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_categories"] = total_categories
            response.data["active_categories"] = active_categories
            response.data["inactive_categories"] = inactive_categories
            response.data["product_categories"] = product_categories
            response.data["service_categories"] = service_categories
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_categories": total_categories,
            "active_categories": active_categories,
            "inactive_categories": inactive_categories,
            "product_categories": product_categories,
            "service_categories": service_categories,
        })


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a category by ID.
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            return Category.objects.all()

        if hasattr(user, "company") and user.company:
            return Category.objects.filter(company=user.company)

        return Category.objects.none()

    @swagger_auto_schema(
        operation_summary="Get Category Details",
        operation_description="Retrieves detailed information of a specific category by ID.",
        responses={200: CategorySerializer, 404: "Category Not Found"}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Edit/Update Category (Full)",
        operation_description="Updates all fields of an existing category.",
        request_body=CategorySerializer,
        responses={200: CategorySerializer, 400: "Validation Error", 404: "Category Not Found"}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Edit/Update Category (Partial)",
        operation_description="Partially updates fields of an existing category.",
        request_body=CategorySerializer,
        responses={200: CategorySerializer, 400: "Validation Error", 404: "Category Not Found"}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Delete Category",
        operation_description="Deletes a category by ID.",
        responses={204: "No Content", 404: "Category Not Found"}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)
