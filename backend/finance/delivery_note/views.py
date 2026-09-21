from django.db import models, transaction
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.shortcuts import get_object_or_404

from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import DeliveryNote, DeliveryNoteItem
from .serializers import (
    DeliveryNoteSerializer,
    update_product_inventory_on_delivery,
    update_so_item_delivered_qty,
)
from shared.pagination import CustomPagination
from finance.sales_order.models import SalesOrder, SalesOrderItem


class DeliveryNoteKPICardView(APIView):
    """
    API view to retrieve KPI card metrics for Delivery Notes
    (Total Deliveries, Pending Deliveries, Partially Delivered, Delivered, Delivery Value).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Delivery Note KPI Card Metrics",
        description="Returns KPI card statistics for delivery notes under the authenticated user's company.",
        responses={200: OpenApiResponse(description="Delivery Note KPI Statistics")}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if getattr(user, "is_superadmin", False):
            company_id = request.query_params.get("company")
            if company_id:
                base_qs = DeliveryNote.objects.filter(company_id=company_id)
            else:
                base_qs = DeliveryNote.objects.all()
        elif hasattr(user, "company") and user.company:
            base_qs = DeliveryNote.objects.filter(company=user.company)
        else:
            base_qs = DeliveryNote.objects.none()

        stats = base_qs.aggregate(
            total_value=Coalesce(Sum("delivery_value"), Decimal("0.00"))
        )

        total_deliveries = base_qs.count()
        pending_deliveries = base_qs.filter(delivery_status="pending").count()
        partially_delivered = base_qs.filter(
            Q(delivery_status="partially_delivered") | Q(delivery_status="partial")
        ).count()
        delivered = base_qs.filter(delivery_status="delivered").count()

        return Response({
            "total_deliveries": total_deliveries,
            "pending_deliveries": pending_deliveries,
            "partially_delivered": partially_delivered,
            "delivered": delivered,
            "delivery_value": stats["total_value"],
        })


class DeliveryNoteListCreateView(generics.ListCreateAPIView):
    """
    API view to list all delivery notes or create a new delivery note for the authenticated user's company.
    """
    serializer_class = DeliveryNoteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["delivery_status", "invoice_status", "customer", "warehouse", "delivery_date", "sales_order"]
    search_fields = [
        "dn_number",
        "so_ref",
        "customer__customer_name",
        "customer__company_name",
        "warehouse__warehouse_name",
        "notes",
    ]
    ordering_fields = [
        "dn_number",
        "so_ref",
        "delivery_date",
        "delivery_value",
        "created_at",
        "delivery_status",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            company_id = self.request.query_params.get("company")
            if company_id:
                qs = DeliveryNote.objects.filter(company_id=company_id)
            else:
                qs = DeliveryNote.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = DeliveryNote.objects.filter(company=user.company)
        else:
            qs = DeliveryNote.objects.none()

        return qs.select_related("company", "customer", "warehouse", "sales_order", "created_by").prefetch_related("items")

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, "company", None)
        serializer.save(company=company, created_by=user)

    @extend_schema(
        summary="List Delivery Notes",
        description="Retrieves a paginated list of delivery notes for the authenticated company, along with KPI statistics.",
        responses={200: DeliveryNoteSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create New Delivery Note",
        description="Creates a new delivery note under the user's company.",
        request=DeliveryNoteSerializer,
        responses={
            201: DeliveryNoteSerializer,
            400: OpenApiResponse(description="Validation Error")
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        base_qs = self.get_queryset()

        stats = base_qs.aggregate(
            total_value=Coalesce(Sum("delivery_value"), Decimal("0.00"))
        )
        total_deliveries = base_qs.count()
        pending_deliveries = base_qs.filter(delivery_status="pending").count()
        partially_delivered = base_qs.filter(
            Q(delivery_status="partially_delivered") | Q(delivery_status="partial")
        ).count()
        delivered = base_qs.filter(delivery_status="delivered").count()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["total_deliveries"] = total_deliveries
            response.data["pending_deliveries"] = pending_deliveries
            response.data["partially_delivered"] = partially_delivered
            response.data["delivered"] = delivered
            response.data["delivery_value"] = stats["total_value"]
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "total_deliveries": total_deliveries,
            "pending_deliveries": pending_deliveries,
            "partially_delivered": partially_delivered,
            "delivered": delivered,
            "delivery_value": stats["total_value"],
        })


class DeliveryNoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, edit (PUT/PATCH), or delete a delivery note by ID.
    """
    serializer_class = DeliveryNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superadmin", False):
            qs = DeliveryNote.objects.all()
        elif hasattr(user, "company") and user.company:
            qs = DeliveryNote.objects.filter(company=user.company)
        else:
            qs = DeliveryNote.objects.none()

        return qs.select_related("company", "customer", "warehouse", "sales_order", "created_by").prefetch_related("items")

    @transaction.atomic
    def perform_destroy(self, instance):
        items = list(instance.items.all())
        sales_order = instance.sales_order
        for item in items:
            update_product_inventory_on_delivery(item.product, -item.quantity)
            so_item = item.sales_order_item
            item.delete()
            if so_item:
                update_so_item_delivered_qty(so_item)

        instance.delete()
        if sales_order:
            sales_order.update_delivery_status()

    @extend_schema(
        summary="Get Delivery Note Details",
        description="Retrieves detailed information of a specific delivery note by ID.",
        responses={200: DeliveryNoteSerializer, 404: OpenApiResponse(description="Delivery Note Not Found")}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Delivery Note (Full)",
        description="Updates all fields of an existing delivery note.",
        request=DeliveryNoteSerializer,
        responses={200: DeliveryNoteSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Delivery Note Not Found")}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Edit/Update Delivery Note (Partial)",
        description="Partially updates fields of an existing delivery note.",
        request=DeliveryNoteSerializer,
        responses={200: DeliveryNoteSerializer, 400: OpenApiResponse(description="Validation Error"), 404: OpenApiResponse(description="Delivery Note Not Found")}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Delivery Note",
        description="Deletes a delivery note by ID.",
        responses={204: OpenApiResponse(description="No Content"), 404: OpenApiResponse(description="Delivery Note Not Found")}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class DeliveryNoteSalesOrderPrefillView(APIView):
    """
    API View to prefill Delivery Note details and line items directly from a Sales Order.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Prefill Delivery Note from Sales Order",
        description="Returns prefilled details and item lines for creating a Delivery Note from a specific Sales Order.",
        responses={200: OpenApiResponse(description="Prefilled Delivery Note Data")}
    )
    def get(self, request, so_id, *args, **kwargs):
        user = request.user
        if getattr(user, "is_superadmin", False):
            so = get_object_or_404(SalesOrder, id=so_id)
        elif hasattr(user, "company") and user.company:
            so = get_object_or_404(SalesOrder, id=so_id, company=user.company)
        else:
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        already_delivered_value = DeliveryNote.objects.filter(
            sales_order=so
        ).exclude(
            delivery_status="cancelled"
        ).aggregate(total=Sum("delivery_value"))["total"] or Decimal("0.00")

        balance_to_deliver_value = max(Decimal("0.00"), so.order_value - already_delivered_value)

        items_data = []
        for item in so.items.select_related("product").all():
            deliv_qty = item.delivered_quantity or Decimal("0.00")
            delivering_now = max(Decimal("0.00"), item.quantity - deliv_qty)
            
            line_base = delivering_now * item.rate
            line_vat = line_base * (item.vat_percentage / Decimal("100"))
            line_amount = line_base + line_vat

            status_str = "Pending"
            if deliv_qty >= item.quantity and item.quantity > 0:
                status_str = "Fully Delivered"
            elif deliv_qty > 0:
                status_str = "Partial"

            items_data.append({
                "sales_order_item": item.id,
                "product": item.product.id if item.product else None,
                "product_name": item.product.product_name if item.product else (item.service_name or "Item"),
                "item_name": item.product.product_name if item.product else "",
                "service_name": item.service_name,
                "description": item.description,
                "ordered_qty": item.quantity,
                "already_delivered": deliv_qty,
                "delivering_now": delivering_now,
                "quantity": delivering_now,
                "balance": max(Decimal("0.00"), item.quantity - deliv_qty - delivering_now),
                "hs_code": item.hs_code,
                "rate": item.rate,
                "vat_percentage": item.vat_percentage,
                "vat_amount": line_vat,
                "amount": line_amount,
                "status": status_str,
            })

        data = {
            "sales_order": so.id,
            "so_ref": so.so_number,
            "customer": so.customer_id,
            "customer_name": so.customer_name,
            "warehouse": so.warehouse_id,
            "shipping_address": so.customer_address,
            "so_order_value": so.order_value,
            "so_already_delivered_value": already_delivered_value,
            "so_balance_to_deliver_value": balance_to_deliver_value,
            "items": items_data,
        }
        return Response(data)
