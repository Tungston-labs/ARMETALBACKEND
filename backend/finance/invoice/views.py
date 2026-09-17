
from decimal import Decimal

from django.http import FileResponse
from django.db.models import Sum, Avg
from django.core.mail import EmailMessage

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from user.permissions import IsHRAdmin, IsCompanyActive

from finance.product.models import Product
from finance.customer.models import Customer

from .models import Invoice
from .serializers import (
    InvoiceSerializer,
    InvoiceListSerializer,
)
from .filters import InvoiceFilter
from .pdf_utils import generate_invoice_pdf


class InvoiceViewSet(viewsets.ModelViewSet):

    serializer_class = InvoiceSerializer

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

    filterset_class = InvoiceFilter

    search_fields = [
        "invoice_number",
        "customer_name",
        "customer_email",
    ]

    ordering_fields = [
        "created_at",
        "invoice_date",
        "due_date",
        "total_amount",
        "amount_paid",
    ]

    ordering = [
        "-created_at"
    ]

    # ---------------------------------------------------------
    # QUERYSET
    # ---------------------------------------------------------

    def get_queryset(self):

        user = self.request.user

        if not user.is_authenticated or not user.company:
            return Invoice.objects.none()

        return (
            Invoice.objects
            .filter(company=user.company)
            .select_related(
                "company",
                "customer",
                "created_by"
            )
            .prefetch_related(
                "items__product"
            )
        )

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        invoice = serializer.save()

        self.generate_and_save_pdf(invoice)

        response_serializer = self.get_serializer(
            invoice
        )

        return Response(
            {
                "message": "Invoice created successfully.",
                "data": response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    # ---------------------------------------------------------
    # UPDATE
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

        serializer.is_valid(
            raise_exception=True
        )

        invoice = serializer.save()

        self.generate_and_save_pdf(invoice)

        response_serializer = self.get_serializer(
            invoice
        )

        return Response(
            {
                "message": "Invoice updated successfully.",
                "data": response_serializer.data
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # PDF GENERATION
    # ---------------------------------------------------------

    def generate_and_save_pdf(self, invoice):

        if invoice.pdf_file:
            invoice.pdf_file.delete(
                save=False
            )

        pdf_content = generate_invoice_pdf(
            invoice
        )

        invoice.pdf_file.save(
            pdf_content.name,
            pdf_content,
            save=True
        )

    # ---------------------------------------------------------
    # LIST
    # ---------------------------------------------------------

    def list(self, request, *args, **kwargs):

        queryset = self.filter_queryset(
            self.get_queryset()
        )

        page = self.paginate_queryset(
            queryset
        )

        if page is not None:

            serializer = InvoiceListSerializer(
                page,
                many=True
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = InvoiceListSerializer(
            queryset,
            many=True
        )

        return Response(
            {
                "message": "Invoices retrieved successfully.",
                "data": serializer.data
            }
        )

    # ---------------------------------------------------------
    # RETRIEVE
    # ---------------------------------------------------------

    def retrieve(self, request, *args, **kwargs):

        instance = self.get_object()

        serializer = self.get_serializer(
            instance
        )

        return Response(
            {
                "message": "Invoice retrieved successfully.",
                "data": serializer.data
            }
        )

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    def destroy(self, request, *args, **kwargs):

        instance = self.get_object()

        if instance.pdf_file:
            instance.pdf_file.delete(
                save=False
            )

        instance.delete()

        return Response(
            {
                "message": "Invoice deleted successfully."
            },
            status=status.HTTP_200_OK
        )

    # ---------------------------------------------------------
    # DOWNLOAD PDF
    # ---------------------------------------------------------

    @action(
        detail=True,
        methods=["get"],
        url_path="download"
    )
    def download(self, request, pk=None):

        invoice = self.get_object()

        if not invoice.pdf_file:
            self.generate_and_save_pdf(
                invoice
            )

        invoice.pdf_file.open("rb")

        return FileResponse(
            invoice.pdf_file,
            as_attachment=True,
            filename=f"{invoice.invoice_number}.pdf"
        )

    # ---------------------------------------------------------
    # COMPANY DETAILS
    # ---------------------------------------------------------

    @action(
        detail=False,
        methods=["get"],
        url_path="company-details"
    )
    def company_details(self, request):

        company = request.user.company

        return Response(
            {
                "name": company.name,
                "email": company.email,
                "phone": company.contact_number,
                "address": company.address,
                "logo": (
                    request.build_absolute_uri(
                        company.logo.url
                    )
                    if company.logo
                    else None
                )
            }
        )

    # ---------------------------------------------------------
    # PRODUCTS
    # ---------------------------------------------------------

    @action(
        detail=False,
        methods=["get"],
        url_path="products"
    )
    def products(self, request):

        company = request.user.company

        products = Product.objects.filter(
            company=company,
            status="active"
        )

        data = [
            {
                "id": product.id,
                "code": product.code,
                "product_name": product.product_name,
                "rate": product.selling_price,
                "hs_code": product.hsn_sac_code or "",
                "vat_percentage": product.tax_rate,
                "unit": product.unit,
            }
            for product in products
        ]

        return Response(data)

    # ---------------------------------------------------------
    # CUSTOMERS
    # ---------------------------------------------------------

    @action(
        detail=False,
        methods=["get"],
        url_path="customers"
    )
    def customers(self, request):

        customers = Customer.objects.filter(
            company=request.user.company,
            client_status="active"
        ).values(
            "id",
            "customer_id",
            "customer_name",
            "admin_email",
            "phno",
            "billing_address"
        )

        return Response(
            {
                "data": customers
            }
        )

    # ---------------------------------------------------------
    # SEND INVOICE
    # ---------------------------------------------------------

    @action(
        detail=True,
        methods=["post"],
        url_path="send"
    )
    def send_invoice(self, request, pk=None):

        invoice = self.get_object()

        if not invoice.pdf_file:
            self.generate_and_save_pdf(
                invoice
            )

        if not invoice.customer_email:

            return Response(
                {
                    "message": "Customer email is not available."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        email = EmailMessage(
            subject=f"Invoice {invoice.invoice_number}",
            body=(
                f"Dear {invoice.customer_name},\n\n"
                f"Please find attached invoice "
                f"{invoice.invoice_number}.\n\n"
                "Thank you."
            ),
            to=[
                invoice.customer_email
            ]
        )

        email.attach_file(
            invoice.pdf_file.path
        )

        email.send(
            fail_silently=False
        )

        return Response(
            {
                "message": "Invoice sent successfully."
            }
        )

    # ---------------------------------------------------------
    # INVOICE SUMMARY
    # ---------------------------------------------------------

    @action(
        detail=False,
        methods=["get"],
        url_path="summary"
    )
    def summary(self, request):

        queryset = self.get_queryset()

        total_invoice_value = (
            queryset.aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        payment_received = (
            queryset.aggregate(
                total=Sum("amount_paid")
            )["total"]
            or Decimal("0.00")
        )

        outstanding_amount = (
            total_invoice_value
            - payment_received
        )

        average_invoice_value = (
            queryset.aggregate(
                average=Avg("total_amount")
            )["average"]
            or Decimal("0.00")
        )

        total_invoice_count = queryset.count()

        return Response(
            {
                "total_invoice_value": total_invoice_value,
                "payment_received": payment_received,
                "outstanding_amount": outstanding_amount,
                "average_invoice_value": average_invoice_value,
                "total_invoice_count": total_invoice_count,
            }
        )
