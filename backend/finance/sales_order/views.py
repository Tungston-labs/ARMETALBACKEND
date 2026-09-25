from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics,status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as http_status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from superadmin.models import Company
from finance.customer.models import Customer
from finance.warehouse.models import Warehouse
from finance.quotation.models import Quotation
from finance.invoice.models import Invoice
from .models import SalesOrder
from .serializers import (
    SalesOrderSerializer,
    SalesOrderListSerializer,
    SalesOrderQuotationSerializer,CustomerSalesOrderSerializer
)
from .filters import SalesOrderFilter
from django.db.models import ProtectedError
from user.permissions import IsCompanyActive, IsHRAdmin



# =========================================================
# HELPERS
# =========================================================

def is_super_admin(user):

    return (
        getattr(user, "is_super_admin", False)
        or getattr(user, "is_superadmin", False)
    )


def get_user_company(user):

    return getattr(
        user,
        "company",
        None
    )


def get_company_from_request(request):

    user = request.user

    company_id = request.query_params.get(
        "company"
    )

    # -----------------------------------------------------
    # SUPER ADMIN
    # -----------------------------------------------------

    if is_super_admin(user):

        if company_id:

            return get_object_or_404(
                Company,
                id=company_id
            )

        return None

    # -----------------------------------------------------
    # COMPANY USER
    # -----------------------------------------------------

    return get_user_company(user)


# =========================================================
# SALES ORDER LIST + CREATE
# =========================================================

class SalesOrderListCreateView(
    generics.ListCreateAPIView
):

    permission_classes = [
        IsAuthenticated
    ]

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_class = SalesOrderFilter

    search_fields = [
        "so_number",
        "customer_name",
        "customer__customer_name",
        "quotation__quote_number",
        "company_name",
    ]

    ordering_fields = [
        "so_number",
        "order_date",
        "delivery_date",
        "due_date",
        "order_value",
        "created_at",
        "status",
        "order_status",
        "delivery_status",
    ]

    ordering = [
        "-created_at"
    ]

    def get_queryset(self):

        queryset = (
            SalesOrder.objects
            .select_related(
                "company",
                "customer",
                "quotation",
                "warehouse",
                "created_by",
            )
            .prefetch_related(
                "items__product"
            )
        )

        company = get_company_from_request(
            self.request
        )

        if company:

            queryset = queryset.filter(
                company=company
            )

        return queryset

    def get_serializer_class(self):

        if self.request.method == "GET":

            return SalesOrderListSerializer

        return SalesOrderSerializer

    def perform_create(self, serializer):

        user = self.request.user

        # -----------------------------------------------------
        # SUPER ADMIN
        # -----------------------------------------------------

        if is_super_admin(user):

            serializer.save(
                created_by=user
            )

            return

        # -----------------------------------------------------
        # NORMAL COMPANY USER
        # -----------------------------------------------------

        company = get_user_company(user)

        if not company:

            raise ValueError(
                "User is not associated with a company."
            )

        serializer.save(
            company=company,
            created_by=user
        )


# =========================================================
# SALES ORDER DETAIL
# =========================================================


class SalesOrderDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    permission_classes = [
        IsAuthenticated
    ]

    serializer_class = SalesOrderSerializer

    def get_queryset(self):
        queryset = (
            SalesOrder.objects
            .select_related(
                "company",
                "customer",
                "quotation",
                "warehouse",
                "created_by",
            )
            .prefetch_related(
                "items__product"
            )
        )

        company = get_company_from_request(
            self.request
        )

        if company:
            queryset = queryset.filter(
                company=company
            )

        return queryset

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    def destroy(self, request, *args, **kwargs):

        instance = self.get_object()

        # Check connected invoices
        if Invoice.objects.filter(
            sales_order=instance
        ).exists():

            return Response(
                {
                    "detail": (
                        "This Sales Order cannot be deleted "
                        "because it is referenced by an Invoice."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        self.perform_destroy(instance)

        return Response(
            {
                "detail": "Sales Order deleted successfully."
            },
            status=status.HTTP_200_OK
        )


# =========================================================
# SUMMARY / KPI
# =========================================================

class SalesOrderSummaryView(
    generics.GenericAPIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        queryset = SalesOrder.objects.all()

        company = get_company_from_request(
            request
        )

        if company:

            queryset = queryset.filter(
                company=company
            )

        total_sales_orders = queryset.count()

        total_order_value = (
            queryset.aggregate(
                total=Sum("order_value")
            )["total"]
            or 0
        )

        pending_orders = queryset.filter(
            order_status="pending"
        ).count()

        partially_delivered = queryset.filter(
            delivery_status="partially_delivered"
        ).count()

        completed_orders = queryset.filter(
            delivery_status="completed"
        ).count()

        return Response({

            "total_sales_order":
                total_sales_orders,

            "total_order_value":
                total_order_value,

            "pending_order":
                pending_orders,

            "partially_delivered":
                partially_delivered,

            "completed_order":
                completed_orders,

        })


# =========================================================
# QUOTATION LIST FOR SO CREATION
# =========================================================

class SalesOrderQuotationListView(
    generics.ListAPIView
):

    permission_classes = [
        IsAuthenticated
    ]

    serializer_class = (
        SalesOrderQuotationSerializer
    )

    search_fields = [
        "quote_number",
        "customer__customer_name",
    ]

    filter_backends = [
        SearchFilter
    ]

    def get_queryset(self):

        queryset = (
            Quotation.objects
            .select_related(
                "company",
                "customer",
            )
            .prefetch_related(
                "items__product"
            )
        )

        company = get_company_from_request(
            self.request
        )

        if company:

            queryset = queryset.filter(
                company=company
            )

        # -----------------------------------------------------
        # Only quotations that can become SO
        # -----------------------------------------------------

        queryset = queryset.filter(
            status__in=[
                "pending",
                "approved",
            ]
        )

        # Don't show quotations that already have SO

        queryset = queryset.filter(
            sales_orders__isnull=True
        )

        return queryset.distinct()


# =========================================================
# QUOTATION PREFILL DETAIL
# =========================================================

class SalesOrderQuotationDetailView(
    generics.RetrieveAPIView
):

    permission_classes = [
        IsAuthenticated
    ]

    serializer_class = (
        SalesOrderQuotationSerializer
    )

    def get_queryset(self):

        queryset = (
            Quotation.objects
            .select_related(
                "company",
                "customer",
            )
            .prefetch_related(
                "items__product"
            )
        )

        company = get_company_from_request(
            self.request
        )

        if company:

            queryset = queryset.filter(
                company=company
            )

        return queryset


# =========================================================
# COMPANY DROPDOWN
# =========================================================

class SalesOrderCompanyListView(
    generics.ListAPIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        if is_super_admin(request.user):

            companies = Company.objects.all()

        else:

            company = get_user_company(
                request.user
            )

            companies = Company.objects.filter(
                id=company.id
            ) if company else Company.objects.none()

        data = []

        for company in companies:

            data.append({

                "id": company.id,

                "name":
                    getattr(
                        company,
                        "name",
                        ""
                    ),

                "email":
                    getattr(
                        company,
                        "email",
                        ""
                    ),

                "phone":
                    getattr(
                        company,
                        "contact_number",
                        ""
                    ),

                "address":
                    getattr(
                        company,
                        "address",
                        ""
                    ),

            })

        return Response(data)


# =========================================================
# CUSTOMER DROPDOWN
# =========================================================

class SalesOrderCustomerListView(
    generics.ListAPIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        company_id = request.query_params.get(
            "company"
        )

        if is_super_admin(request.user):

            if company_id:

                customers = Customer.objects.filter(
                    company_id=company_id
                )

            else:

                customers = Customer.objects.all()

        else:

            company = get_user_company(
                request.user
            )

            if not company:

                return Response([])

            customers = Customer.objects.filter(
                company=company
            )

        search = request.query_params.get(
            "search"
        )

        if search:

            customers = customers.filter(
                Q(customer_name__icontains=search)
                |
                Q(customer_id__icontains=search)
            )

        data = []

        for customer in customers:

            data.append({

                "id":
                    customer.id,

                "customer_id":
                    customer.customer_id,

                "customer_name":
                    customer.customer_name,

                "email":
                    getattr(
                        customer,
                        "admin_email",
                        ""
                    ),

                "phone":
                    getattr(
                        customer,
                        "phone",
                        ""
                    ),

                "billing_address":
                    getattr(
                        customer,
                        "billing_address",
                        ""
                    ),

                "city":
                    getattr(
                        customer,
                        "city",
                        ""
                    ),

                "state":
                    getattr(
                        customer,
                        "state",
                        ""
                    ),

                "country":
                    getattr(
                        customer,
                        "country",
                        ""
                    ),

            })

        return Response(data)


# =========================================================
# WAREHOUSE DROPDOWN
# =========================================================

class SalesOrderWarehouseListView(
    generics.ListAPIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        company_id = request.query_params.get(
            "company"
        )

        if is_super_admin(request.user):

            if company_id:

                warehouses = Warehouse.objects.filter(
                    company_id=company_id
                )

            else:

                warehouses = Warehouse.objects.all()

        else:

            company = get_user_company(
                request.user
            )

            if not company:

                return Response([])

            warehouses = Warehouse.objects.filter(
                company=company
            )

        warehouses = warehouses.filter(
            status="active"
        )

        data = []

        for warehouse in warehouses:

            data.append({

                "id":
                    warehouse.id,

                "code":
                    warehouse.code,

                "warehouse_name":
                    warehouse.warehouse_name,

                "warehouse_type":
                    warehouse.warehouse_type,

                "manager":
                    warehouse.manager,

                "city":
                    warehouse.city,

                "country":
                    warehouse.country,

                "address":
                    warehouse.address_line_1,

                "phone":
                    warehouse.phone_number,

                "email":
                    warehouse.email,

            })

        return Response(data)
    






class CustomerSalesOrderListView(generics.ListAPIView):

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        
    ]

    serializer_class = CustomerSalesOrderSerializer

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    search_fields = [
    "so_number",
    "quotation__quote_number",
]

    ordering_fields = [
        "so_number",
        "order_date",
        "delivery_date",
        "order_value",
        "created_at",
    ]

    ordering = [
        "-order_date",
        "-id",
    ]

    def get_queryset(self):

        user = self.request.user

        if (
            not user.is_authenticated
            or not getattr(user, "company", None)
        ):
            return SalesOrder.objects.none()

        customer_id = self.kwargs.get("customer_id")

        queryset = (
            SalesOrder.objects
            .filter(
                company=user.company,
                customer__id=customer_id,
            )
            .select_related(
                "customer",
                "quotation",
                "warehouse",
            )
            .prefetch_related(
                "invoices",
            )
        )

        # ---------------------------------------
        # DATE RANGE FILTER
        # ---------------------------------------

        date_from = self.request.query_params.get(
            "date_from"
        )

        date_to = self.request.query_params.get(
            "date_to"
        )

        if date_from:
            queryset = queryset.filter(
                order_date__gte=date_from
            )

        if date_to:
            queryset = queryset.filter(
                order_date__lte=date_to
            )

        # ---------------------------------------
        # ORDER STATUS FILTER
        # ---------------------------------------

        order_status = self.request.query_params.get(
            "order_status"
        )

        if order_status:
            queryset = queryset.filter(
                order_status=order_status
            )

        # ---------------------------------------
        # DELIVERY STATUS FILTER
        # ---------------------------------------

        delivery_status = self.request.query_params.get(
            "delivery_status"
        )

        if delivery_status:
            queryset = queryset.filter(
                delivery_status=delivery_status
            )

        return queryset
    




class CustomerSalesOrderSummaryView(generics.GenericAPIView):

    permission_classes = [
        IsAuthenticated,
        IsCompanyActive,
        
    ]

    def get(self, request, customer_id, *args, **kwargs):

        user = request.user

        if not getattr(user, "company", None):
            return Response(
                {
                    "message": "User is not associated with a company.",
                    "data": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------
        # CUSTOMER + COMPANY FILTER
        # ---------------------------------------

        queryset = SalesOrder.objects.filter(
            company=user.company,
            customer_id=customer_id,
        )

        # ---------------------------------------
        # TOTAL ORDERS
        # ---------------------------------------

        total_orders = queryset.count()

        # ---------------------------------------
        # COMPLETED ORDERS
        # ---------------------------------------

        completed_orders = queryset.filter(
            delivery_status="completed"
        ).count()

        # ---------------------------------------
        # OPEN ORDERS
        # ---------------------------------------

        open_orders = queryset.exclude(
            delivery_status__in=[
                "completed",
                "cancelled",
            ]
        ).exclude(
            order_status="rejected"
        ).count()

        # ---------------------------------------
        # TOTAL ORDER AMOUNT
        # ---------------------------------------

        total_order_amount = (
            queryset.aggregate(
                total=Sum("order_value")
            )["total"]
            or 0
        )

        return Response(
            {
                "message": "Customer sales order summary retrieved successfully.",
                "data": {
                    "total_orders": total_orders,
                    "open_orders": open_orders,
                    "completed_orders": completed_orders,
                    "total_order_amount": total_order_amount,
                },
            },
            status=status.HTTP_200_OK,
        )