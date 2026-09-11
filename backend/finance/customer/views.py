from django.shortcuts import render

# Create your views here.
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import (
    DjangoFilterBackend
)

from rest_framework.filters import (
    SearchFilter,
    OrderingFilter
)

from user.permissions import (
    IsHRAdmin,
    IsCompanyActive
)

from .models import (
    Customer,
    CustomerDocument
)

from .serializers import (
    CustomerSerializer,
    CustomerDocumentSerializer
)


class CustomerViewSet(viewsets.ModelViewSet):

    serializer_class = CustomerSerializer

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
        "client_status",
    ]

    search_fields = [
        "customer_id",
        "customer_name",
        "company_name",
        "cr_number",
        "vat_number",
        "admin_email",
        "financial_email",
        "technical_email",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "customer_name",
        "customer_id",
    ]

    ordering = [
        "-created_at"
    ]

    def get_queryset(self):

        user = self.request.user

        if not user.is_authenticated:
            return Customer.objects.none()

        if not user.company:
            return Customer.objects.none()

        return (
            Customer.objects
            .filter(company=user.company)
            .select_related(
                "company",
                "created_by"
            )
            .prefetch_related(
                "documents"
            )
        )

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    def create(
        self,
        request,
        *args,
        **kwargs
    ):

        serializer = self.get_serializer(
            data=request.data
        )

        if not serializer.is_valid():

            return Response(
                {
                    "message": "Customer creation failed.",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        customer = serializer.save(
            company=request.user.company,
            created_by=request.user
        )

        # ---------------------------------------------
        # MULTIPLE DOCUMENTS
        # ---------------------------------------------

        documents = request.FILES.getlist(
            "documents"
        )

        document_objects = []

        for file in documents:

            document_objects.append(
                CustomerDocument(
                    customer=customer,
                    document=file,
                    document_name=file.name
                )
            )

        if document_objects:

            CustomerDocument.objects.bulk_create(
                document_objects
            )

        serializer = self.get_serializer(
            customer
        )

        return Response(
            {
                "message": "Customer created successfully.",
                "data": serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    # ---------------------------------------------------------
    # LIST
    # ---------------------------------------------------------

    def list(
        self,
        request,
        *args,
        **kwargs
    ):

        queryset = self.filter_queryset(
            self.get_queryset()
        )

        page = self.paginate_queryset(
            queryset
        )

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
                "message": "Customers retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # RETRIEVE
    # ---------------------------------------------------------

    def retrieve(
        self,
        request,
        *args,
        **kwargs
    ):

        instance = self.get_object()

        serializer = self.get_serializer(
            instance
        )

        return Response(
            {
                "message": "Customer retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # UPDATE / PATCH
    # ---------------------------------------------------------

    def update(
        self,
        request,
        *args,
        **kwargs
    ):

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
                    "message": "Customer update failed.",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        customer = serializer.save()

        # ---------------------------------------------
        # ADD NEW DOCUMENTS
        # ---------------------------------------------

        documents = request.FILES.getlist(
            "documents"
        )

        document_objects = []

        for file in documents:

            document_objects.append(
                CustomerDocument(
                    customer=customer,
                    document=file,
                    document_name=file.name
                )
            )

        if document_objects:

            CustomerDocument.objects.bulk_create(
                document_objects
            )

        serializer = self.get_serializer(
            customer
        )

        return Response(
            {
                "message": "Customer updated successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    def destroy(
        self,
        request,
        *args,
        **kwargs
    ):

        instance = self.get_object()

        customer_name = instance.customer_name

        instance.delete()

        return Response(
            {
                "message": (
                    f"Customer '{customer_name}' "
                    "deleted successfully."
                )
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    @action(
        detail=False,
        methods=["get"],
        url_path="summary"
    )
    def summary(
        self,
        request
    ):

        queryset = self.get_queryset()

        total_customers = queryset.count()

        active_customers = queryset.filter(
            client_status="active"
        ).count()

        inactive_customers = queryset.filter(
            client_status="inactive"
        ).count()

        # ---------------------------------------------
        # NEW CUSTOMERS THIS MONTH
        # ---------------------------------------------

        today = timezone.localdate()

        new_customers_this_month = queryset.filter(
            created_at__year=today.year,
            created_at__month=today.month
        ).count()

        # ---------------------------------------------
        # PAYMENT RECEIVED
        # ---------------------------------------------

        payment_received = 0

        return Response(
            {
                "message": (
                    "Customer summary retrieved "
                    "successfully."
                ),
                "data": {
                    "total_customers": total_customers,
                    "active_customers": active_customers,
                    "new_customers_this_month": (
                        new_customers_this_month
                    ),
                    "inactive_customers": (
                        inactive_customers
                    ),
                    "payment_received": payment_received,
                }
            },
            status=status.HTTP_200_OK
        )