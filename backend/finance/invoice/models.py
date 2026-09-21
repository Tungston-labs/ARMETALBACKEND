from decimal import Decimal

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator

from shared.models import TimeStampedModel


class Invoice(TimeStampedModel):

    PAYMENT_STATUS_CHOICES = (
        ("paid", "Paid"),
        ("unpaid", "Unpaid"),
        ("partially_paid", "Partially Paid"),
    )

    id = models.BigAutoField(primary_key=True)

    # ---------------------------------------------------------
    # COMPANY
    # ---------------------------------------------------------

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="invoices"
    )

    # ---------------------------------------------------------
    # CUSTOMER
    # ---------------------------------------------------------

    customer = models.ForeignKey(
        "customer.Customer",
        on_delete=models.PROTECT,
        related_name="invoices"
    )

    # ---------------------------------------------------------
    # SALES ORDER
    # ---------------------------------------------------------

    sales_order = models.ForeignKey(
        "sales_order.SalesOrder",
        on_delete=models.PROTECT,
        related_name="invoices",
        null=True,
        blank=True
    )

    # ---------------------------------------------------------
    # INVOICE DETAILS
    # ---------------------------------------------------------

    invoice_number = models.CharField(
        max_length=50
    )

    invoice_date = models.DateField()

    due_date = models.DateField()

    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default="unpaid"
    )

    # ---------------------------------------------------------
    # COMPANY SNAPSHOT
    # ---------------------------------------------------------

    company_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    company_email = models.EmailField(
        blank=True,
        default=""
    )

    company_phone = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    company_address = models.TextField(
        blank=True,
        default=""
    )

    # ---------------------------------------------------------
    # CUSTOMER SNAPSHOT
    # ---------------------------------------------------------

    customer_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    customer_email = models.EmailField(
        blank=True,
        default=""
    )

    customer_phone = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    customer_address = models.TextField(
        blank=True,
        default=""
    )

    # ---------------------------------------------------------
    # PAYMENT DETAILS
    # ---------------------------------------------------------

    account_holder = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    account_number = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    iban = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    qr_code = models.ImageField(
        upload_to="invoice_qr_codes/",
        null=True,
        blank=True
    )

    # ---------------------------------------------------------
    # TOTALS
    # ---------------------------------------------------------

    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total_vat = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
        ]
    )

    round_off = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    amount_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
        ]
    )

    # ---------------------------------------------------------
    # PDF
    # ---------------------------------------------------------

    pdf_file = models.FileField(
        upload_to="invoices/",
        null=True,
        blank=True
    )

    # ---------------------------------------------------------
    # CREATED BY
    # ---------------------------------------------------------

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices"
    )

    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------

    def save(self, *args, **kwargs):

        if not self.invoice_number:

            last_invoice = (
                Invoice.objects
                .filter(company=self.company)
                .order_by("-id")
                .first()
            )

            if last_invoice:

                try:

                    last_number = int(
                        last_invoice.invoice_number.replace(
                            "INV",
                            ""
                        )
                    )

                except (ValueError, AttributeError):

                    last_number = 0

                next_number = last_number + 1

            else:

                next_number = 1

            self.invoice_number = f"INV{next_number:03d}"

        super().save(*args, **kwargs)

    # ---------------------------------------------------------
    # STRING
    # ---------------------------------------------------------

    def __str__(self):

        return self.invoice_number

    # ---------------------------------------------------------
    # META
    # ---------------------------------------------------------

    class Meta:

        db_table = "finance_invoice"

        ordering = ["-created_at"]

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "company",
                    "invoice_number"
                ],
                name="unique_invoice_number_per_company"
            ),

        ]


class InvoiceItem(TimeStampedModel):

    id = models.BigAutoField(primary_key=True)

    # ---------------------------------------------------------
    # INVOICE
    # ---------------------------------------------------------

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items"
    )

    # ---------------------------------------------------------
    # SALES ORDER ITEM
    # ---------------------------------------------------------

    sales_order_item = models.ForeignKey(
        "sales_order.SalesOrderItem",
        on_delete=models.PROTECT,
        related_name="invoice_items",
        null=True,
        blank=True
    )

    # ---------------------------------------------------------
    # PRODUCT
    # ---------------------------------------------------------

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.PROTECT,
        related_name="invoice_items"
    )

    # ---------------------------------------------------------
    # ITEM DETAILS
    # ---------------------------------------------------------

    particular = models.CharField(
        max_length=500
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01"))
        ]
    )

    hs_code = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    rate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00"))
        ]
    )

    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
        ]
    )

    vat_sar = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    # ---------------------------------------------------------
    # CALCULATE
    # ---------------------------------------------------------

    def calculate_amounts(self):

        self.amount = (
            self.quantity *
            self.rate
        )

        self.vat_sar = (
            self.amount *
            self.vat_percentage /
            Decimal("100")
        )

    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------

    def save(self, *args, **kwargs):

        self.calculate_amounts()

        super().save(*args, **kwargs)

    # ---------------------------------------------------------
    # STRING
    # ---------------------------------------------------------

    def __str__(self):

        return self.particular

    # ---------------------------------------------------------
    # META
    # ---------------------------------------------------------

    class Meta:

        db_table = "finance_invoice_item"