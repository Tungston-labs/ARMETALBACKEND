# purchase_order/views.py

from decimal import Decimal

from django.db.models import Sum, Q
from django.utils import timezone

from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from .models import PurchaseOrder
from .serializers import (
    PurchaseOrderCreateSerializer,
    PurchaseOrderListSerializer,
    VendorDropdownSerializer,
    WarehouseDropdownSerializer,
    ProductDropdownSerializer,
)

from finance.vendor.models import Vendor
from finance.warehouse.models import Warehouse
from finance.product.models import Product
from shared.pagination import CustomPagination



class PurchaseOrderCreateListView(generics.ListCreateAPIView):

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):

        user = self.request.user

        queryset = (
            PurchaseOrder.objects
            .filter(
                company=user.company
            )
            .select_related(
                "vendor",
                "warehouse",
                "created_by",
            )
            .prefetch_related(
                "items__product"
            )
        )

        vendor_id = self.request.query_params.get("vendor")
        status = self.request.query_params.get("status")
        receipt_status = self.request.query_params.get(
            "receipt_status"
        )
        bill_status = self.request.query_params.get(
            "bill_status"
        )
        search = self.request.query_params.get("search")

        # Date range
        from_date = self.request.query_params.get(
            "from_date"
        )
        to_date = self.request.query_params.get(
            "to_date"
        )

        # ------------------------------------------
        # Vendor filter
        # ------------------------------------------

        if vendor_id:

            if not vendor_id.isdigit():

                raise ValidationError({
                    "vendor": "Vendor must be a valid ID."
                })

            queryset = queryset.filter(
                vendor_id=vendor_id
            )

        # ------------------------------------------
        # Status filters
        # ------------------------------------------

        if status:
            queryset = queryset.filter(
                status=status
            )

        if receipt_status:
            queryset = queryset.filter(
                receipt_status=receipt_status
            )

        if bill_status:
            queryset = queryset.filter(
                bill_status=bill_status
            )

        # ------------------------------------------
        # Search
        # ------------------------------------------

        if search:

            queryset = queryset.filter(
                Q(
                    po_number__icontains=search
                )
                | Q(
                    vendor__name__icontains=search
                )
                | Q(
                    pr_reference__icontains=search
                )
            )

        # ------------------------------------------
        # ORDER DATE RANGE
        # ------------------------------------------

        if from_date:

            queryset = queryset.filter(
                order_date__gte=from_date
            )

        if to_date:

            queryset = queryset.filter(
                order_date__lte=to_date
            )

        return queryset.order_by("-created_at")
    def get_serializer_class(self):
        if self.request.method == "POST":
            return PurchaseOrderCreateSerializer

        return PurchaseOrderListSerializer

    def perform_create(self, serializer):
        serializer.save()



class PurchaseOrderDashboardView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = request.user.company

        queryset = PurchaseOrder.objects.filter(
            company=company
        )

        today = timezone.localdate()

        month_start = today.replace(day=1)

        total_orders = queryset.count()

        total_purchase_value = (
            queryset.aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        pending_orders = queryset.filter(
            status__in=["draft", "pending", "approved", "ordered"]
        ).count()

        partially_received = queryset.filter(
            receipt_status="partially_received"
        ).count()

        completed_this_month = queryset.filter(
            status="received",
            order_date__gte=month_start,
            order_date__lte=today,
        ).count()

        return Response({
            "total_purchase_orders": total_orders,
            "total_purchase_value": str(
                total_purchase_value
            ),
            "pending_orders": pending_orders,
            "partially_received": partially_received,
            "completed_orders_this_month": (
                completed_this_month
            ),
        })

class VendorDropdownView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorDropdownSerializer

    def get_queryset(self):
        return Vendor.objects.filter(
            company=self.request.user.company
        ).order_by("name")
class WarehouseDropdownView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WarehouseDropdownSerializer

    def get_queryset(self):
        return Warehouse.objects.filter(
            company=self.request.user.company
        ).order_by("warehouse_name")

class ProductDropdownView(generics.ListAPIView):

    permission_classes = [IsAuthenticated]
    serializer_class = ProductDropdownSerializer

    def get_queryset(self):
        queryset = Product.objects.filter(
            company=self.request.user.company,
            status="active",
        )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(product_name__icontains=search)
                | Q(code__icontains=search)
                | Q(sku__icontains=search)
            )

        return queryset.order_by("product_name")


from django.db.models import ProtectedError
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PurchaseOrder
from .serializers import PurchaseOrderCreateSerializer


class PurchaseOrderDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    permission_classes = [IsAuthenticated]
    serializer_class = PurchaseOrderCreateSerializer

    lookup_field = "id"
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return (
            PurchaseOrder.objects
            .filter(company=self.request.user.company)
            .select_related(
                "vendor",
                "warehouse",
                "created_by",
            )
            .prefetch_related("items__product")
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Avoid deleting orders that have been received or billed.
        if (
            instance.receipt_status != "pending"
            or instance.bill_status != "pending"
        ):
            return Response(
                {
                    "message": (
                        "Cannot delete a purchase order that "
                        "has received items or associated billing."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {
                    "message": (
                        "This purchase order cannot be deleted "
                        "because it is referenced by other records."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Purchase order deleted successfully."
            },
            status=status.HTTP_200_OK,
        )

