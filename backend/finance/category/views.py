from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from user.permissions import IsHRAdmin, IsCompanyActive
from django.db.models import Count
from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):

    serializer_class = CategorySerializer

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        IsHRAdmin,
    ]

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "category_type",
        "status",
        "parent_category",
    ]

    search_fields = [
        "code",
        "category_name",
        "parent_category__category_name",
    ]

    ordering_fields = [
        "code",
        "category_name",
        "created_at",
        "updated_at",
    ]

    ordering = [
        "category_name"
    ]

    def get_queryset(self):

        user = self.request.user

        if not user.is_authenticated:
            return Category.objects.none()

        if not user.company:
            return Category.objects.none()

        return Category.objects.filter(
            company=user.company
        ).select_related(
            "company",
            "created_by",
            "parent_category"
        )

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data
        )

        if not serializer.is_valid():

            return Response(
                {
                    "message": "Category creation failed.",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer.save(
            company=request.user.company,
            created_by=request.user
        )

        return Response(
            {
                "message": "Category created successfully.",
                "data": serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    # ---------------------------------------------------------
    # LIST
    # ---------------------------------------------------------

    def list(self, request, *args, **kwargs):

        queryset = self.filter_queryset(
            self.get_queryset()
        )

        page = self.paginate_queryset(queryset)

        if page is not None:

            serializer = self.get_serializer(
                page,
                many=True
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = self.get_serializer(
            queryset,
            many=True
        )

        return Response(
            {
                "message": "Categories retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # DETAIL
    # ---------------------------------------------------------

    def retrieve(self, request, *args, **kwargs):

        instance = self.get_object()

        serializer = self.get_serializer(
            instance
        )

        return Response(
            {
                "message": "Category retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # UPDATE / PATCH
    # ---------------------------------------------------------

    def update(self, request, *args, **kwargs):

        partial = kwargs.pop(
            "partial",
            False
        )

        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial
        )

        if not serializer.is_valid():

            return Response(
                {
                    "message": "Category update failed.",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer.save()

        return Response(
            {
                "message": "Category updated successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    def destroy(self, request, *args, **kwargs):

        instance = self.get_object()

        category_name = instance.category_name

        instance.delete()

        return Response(
            {
                "message": (
                    f"Category '{category_name}' "
                    "deleted successfully."
                )
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # PARENT CATEGORIES
    # ---------------------------------------------------------

    @action(
        detail=False,
        methods=["get"],
        url_path="parents"
    )
    def parents(self, request):

        queryset = self.get_queryset().filter(
            parent_category__isnull=True,
            status="active"
        )

        serializer = self.get_serializer(
            queryset,
            many=True
        )

        return Response(
            {
                "message": "Parent categories retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # SUB-CATEGORIES
    # ---------------------------------------------------------

    @action(
        detail=True,
        methods=["get"],
        url_path="subcategories"
    )
    def subcategories(self, request, pk=None):

        parent = self.get_object()

        queryset = self.get_queryset().filter(
            parent_category=parent,
            status="active"
        )

        serializer = self.get_serializer(
            queryset,
            many=True
        )

        return Response(
            {
                "message": "Sub-categories retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    @action(
    detail=False,
    methods=["get"],
    url_path="summary"
    )
    def summary(self, request):

        queryset = self.get_queryset()

        total_categories = queryset.count()

        active_categories = queryset.filter(
            status="active"
        ).count()

        inactive_categories = queryset.filter(
            status="inactive"
        ).count()

        parent_categories = queryset.filter(
            parent_category__isnull=True
        ).count()

        sub_categories = queryset.filter(
            parent_category__isnull=False
        ).count()

        return Response(
            {
                "message": "Category summary retrieved successfully.",
                "data": {
                    "total_categories": total_categories,
                    "active_categories": active_categories,
                    "inactive_categories": inactive_categories,
                    "parent_categories": parent_categories,
                    "sub_categories": sub_categories,
                }
            },
            status=status.HTTP_200_OK
        )