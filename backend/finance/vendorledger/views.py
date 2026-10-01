from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import VendorLedger
from .serializers import (
    VendorLedgerCreateSerializer,
    VendorLedgerListSerializer,
)


class VendorLedgerListCreateView(
    generics.ListCreateAPIView
):
    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):
        queryset = (
            VendorLedger.objects
            .filter(
                company=self.request.user.company
            )
            .select_related(
                "vendor",
                "bill",
                "purchase_order",
                "payment",
                "created_by",
            )
        )

        vendor = self.request.query_params.get(
            "vendor"
        )

        transaction_type = (
            self.request.query_params.get(
                "transaction_type"
            )
        )

        status = self.request.query_params.get(
            "status"
        )

        search = self.request.query_params.get(
            "search"
        )

        date_from = self.request.query_params.get(
            "date_from"
        )

        date_to = self.request.query_params.get(
            "date_to"
        )

        if vendor:
            queryset = queryset.filter(
                vendor_id=vendor
            )

        if transaction_type:
            queryset = queryset.filter(
                transaction_type=transaction_type
            )

        if status:
            queryset = queryset.filter(
                vendor__client_status=status
            )

        if date_from:
            queryset = queryset.filter(
                entry_date__gte=date_from
            )

        if date_to:
            queryset = queryset.filter(
                entry_date__lte=date_to
            )

        if search:
            queryset = queryset.filter(
                Q(vendor__vendor_id__icontains=search)
                | Q(vendor__name__icontains=search)
                | Q(reference_number__icontains=search)
                | Q(description__icontains=search)
            )

        return queryset.order_by(
            "-entry_date",
            "-id",
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VendorLedgerCreateSerializer

        return VendorLedgerListSerializer
    

class VendorLedgerDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):
        return (
            VendorLedger.objects
            .filter(
                company=self.request.user.company
            )
            .select_related(
                "vendor",
                "bill",
                "purchase_order",
                "payment",
                "created_by",
            )
        )

    def get_serializer_class(self):
        if self.request.method in [
            "PUT",
            "PATCH",
        ]:
            return VendorLedgerCreateSerializer

        return VendorLedgerListSerializer