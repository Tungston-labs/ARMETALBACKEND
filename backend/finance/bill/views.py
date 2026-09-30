from decimal import Decimal
from django.db.models import Sum, Q, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone

from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from .models import Bill
from .serializers import BillSerializer, BillListSerializer
from .filters import BillFilter
from shared.pagination import CustomPagination


def get_user_company(user):
    return getattr(user, "company", None)


class BillKPICardView(APIView):
    """
    API view to retrieve KPI card metrics for Purchase Bills:
    - Total Bill Value (Sum of total_amount)
    - Total Payables (Sum of outstanding balance)
    - Total Debit Notes (Total debit notes value)
    - Overdue Payables (Sum of balance for overdue bills)
    - Total Bills (Count of total bills)
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Purchase Bill KPI Card Metrics",
        description="Returns KPI card statistics for purchase bills under the authenticated user's company.",
        responses={200: OpenApiResponse(description="Purchase Bill KPI Statistics")}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if getattr(user, "is_superadmin", False):
            company_id = request.query_params.get("company")
            if company_id:
                base_qs = Bill.objects.filter(company_id=company_id)
            else:
                base_qs = Bill.objects.all()
        elif hasattr(user, "company") and user.company:
            base_qs = Bill.objects.filter(company=user.company)
        else:
            base_qs = Bill.objects.none()

        vendor_param = request.query_params.get("vendor")
        if vendor_param:
            base_qs = base_qs.filter(vendor_id=vendor_param)

        today = timezone.now().date()

        # Expression for balance per bill
        balance_expr = ExpressionWrapper(
            F("total_amount") - F("amount_paid"),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        total_bill_value = base_qs.aggregate(
            total=Coalesce(Sum("total_amount"), Decimal("0.00"))
        )["total"]

        total_payables = base_qs.exclude(status="paid").annotate(
            rem_balance=balance_expr
        ).aggregate(
            total=Coalesce(Sum("rem_balance"), Decimal("0.00"))
        )["total"]

        overdue_payables = base_qs.filter(
            due_date__lt=today
        ).exclude(status="paid").annotate(
            rem_balance=balance_expr
        ).aggregate(
            total=Coalesce(Sum("rem_balance"), Decimal("0.00"))
        )["total"]

        total_bills = base_qs.count()

        # For total_debit_notes, check if debit notes exist in system, else default to 0.00
        total_debit_notes = Decimal("0.00")

        return Response({
            "total_bill_value": total_bill_value,
            "total_payables": total_payables,
            "total_debit_notes": total_debit_notes,
            "overdue_payables": overdue_payables,
            "total_bills": total_bills,
        }, status=status.HTTP_200_OK)


class BillListCreateView(generics.ListCreateAPIView):
    """
    API view to list purchase bills or create a new purchase bill for the authenticated user's company.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = BillFilter
    search_fields = [
        "bill_number",
        "po_reference",
        "vendor__name",
        "bill_to_name",
        "note",
        "due_date_note",
    ]
    ordering_fields = [
        "bill_number",
        "bill_date",
        "due_date",
        "total_amount",
        "amount_paid",
        "status",
        "created_at",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return BillListSerializer
        return BillSerializer

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                qs = Bill.objects.filter(company_id=company_id)
            else:
                qs = Bill.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = Bill.objects.filter(company=user.company)
        else:
            qs = Bill.objects.none()

        return qs.select_related("company", "vendor", "created_by").prefetch_related("items")

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    @extend_schema(
        summary="List Purchase Bills",
        description="Retrieves a paginated list of purchase bills for the authenticated company, along with KPI statistics.",
        responses={200: BillListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create New Purchase Bill",
        description="Creates a new purchase bill with line items under the user's company.",
        request=BillSerializer,
        responses={
            201: BillSerializer,
            400: OpenApiResponse(description="Validation Error")
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        base_qs = self.get_queryset()

        vendor_param = request.query_params.get("vendor")
        if vendor_param:
            base_qs = base_qs.filter(vendor_id=vendor_param)

        today = timezone.now().date()
        balance_expr = ExpressionWrapper(
            F("total_amount") - F("amount_paid"),
            output_field=DecimalField(max_digits=15, decimal_places=2)
        )

        total_bill_value = base_qs.aggregate(
            total=Coalesce(Sum("total_amount"), Decimal("0.00"))
        )["total"]

        total_payables = base_qs.exclude(status="paid").annotate(
            rem_balance=balance_expr
        ).aggregate(
            total=Coalesce(Sum("rem_balance"), Decimal("0.00"))
        )["total"]

        overdue_payables = base_qs.filter(
            due_date__lt=today
        ).exclude(status="paid").annotate(
            rem_balance=balance_expr
        ).aggregate(
            total=Coalesce(Sum("rem_balance"), Decimal("0.00"))
        )["total"]

        total_bills = base_qs.count()
        total_debit_notes = Decimal("0.00")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_bill_value"] = total_bill_value
            response.data["total_payables"] = total_payables
            response.data["total_debit_notes"] = total_debit_notes
            response.data["overdue_payables"] = overdue_payables
            response.data["total_bills"] = total_bills
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_bill_value": total_bill_value,
            "total_payables": total_payables,
            "total_debit_notes": total_debit_notes,
            "overdue_payables": overdue_payables,
            "total_bills": total_bills,
        })


class BillDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a purchase bill by ID.
    """
    serializer_class = BillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            qs = Bill.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = Bill.objects.filter(company=user.company)
        else:
            qs = Bill.objects.none()

        return qs.select_related("company", "vendor", "created_by").prefetch_related("items")

    @extend_schema(
        summary="Get Purchase Bill Details",
        description="Retrieves detailed information of a specific purchase bill by ID.",
        responses={200: BillSerializer, 404: OpenApiResponse(description="Bill Not Found")}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Purchase Bill (Full)",
        description="Updates all fields of an existing purchase bill.",
        request=BillSerializer,
        responses={200: BillSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Bill Not Found")}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Purchase Bill (Partial)",
        description="Partially updates fields of an existing purchase bill.",
        request=BillSerializer,
        responses={200: BillSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Bill Not Found")}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Purchase Bill",
        description="Deletes a purchase bill by ID.",
        responses={204: OpenApiResponse(description="No Content"), 404: OpenApiResponse(description="Bill Not Found")}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)
