from rest_framework import generics, filters, status
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Category
from .serializers import CategorySerializer
from shared.pagination import CustomPagination


class CategoryKPICardView(APIView):
    """
    API view to retrieve Category KPI summary metrics (total, active, inactive, product, service).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Category KPI Card Metrics",
        description="Retrieves KPI summary metrics for categories under the authenticated user's company.",
        responses={200: OpenApiResponse(description="Category KPI Statistics")}
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

    @extend_schema(
        summary="List Categories",
        description="Retrieves a paginated list of categories for the company, including summary metrics.",
        responses={200: CategorySerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Add New Category",
        description="Creates a new category under the user's company.",
        request=CategorySerializer,
        responses={
            201: CategorySerializer,
            400: OpenApiResponse(description="Validation Error")
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

    @extend_schema(
        summary="Get Category Details",
        description="Retrieves detailed information of a specific category by ID.",
        responses={200: CategorySerializer, 404: OpenApiResponse(description="Category Not Found")}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Category (Full)",
        description="Updates all fields of an existing category.",
        request=CategorySerializer,
        responses={200: CategorySerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Category Not Found")}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Category (Partial)",
        description="Partially updates fields of an existing category.",
        request=CategorySerializer,
        responses={200: CategorySerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Category Not Found")}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Category",
        description="Deletes a category by ID.",
        responses={204: OpenApiResponse(description="No Content"), 404: OpenApiResponse(description="Category Not Found")}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

