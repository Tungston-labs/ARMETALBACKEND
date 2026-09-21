from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from shared.models import TimeStampedModel


class SalesOrder(TimeStampedModel):

    ORDER_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("rejected", "Rejected"),
        ("processing", "Processing"),
    )

    DELIVERY_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("partially_delivered", "Partially Delivered"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    PAYMENT_TERMS_CHOICES = (
        ("due_on_receipt", "Due on Receipt"),
        ("net_7", "Net 7"),
        ("net_15", "Net 15"),
        ("net_30", "Net 30"),
        ("net_45", "Net 45"),
        ("net_60", "Net 60"),
    )

    id = models.BigAutoField(primary_key=True)

    # ---------------------------------------------------------
    # MAIN REFERENCES
    # ---------------------------------------------------------

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="sales_orders"
    )

    quotation = models.ForeignKey(
        "quotation.Quotation",
        on_delete=models.PROTECT,
        related_name="sales_orders"
    )

    customer = models.ForeignKey(
        "customer.Customer",
        on_delete=models.PROTECT,
        related_name="sales_orders"
    )

    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.PROTECT,
        related_name="sales_orders",
        null=True,
        blank=True
    )

    # ---------------------------------------------------------
    # SALES ORDER NUMBER
    # ---------------------------------------------------------

    so_number = models.CharField(
        max_length=50,
        blank=True
    )

    # ---------------------------------------------------------
    # DATES
    # ---------------------------------------------------------

    order_date = models.DateField()

    delivery_date = models.DateField(
        null=True,
        blank=True
    )

    due_date = models.DateField(
        null=True,
        blank=True
    )

    # ---------------------------------------------------------
    # PAYMENT
    # ---------------------------------------------------------

    payment_terms = models.CharField(
        max_length=30,
        choices=PAYMENT_TERMS_CHOICES,
        default="net_15"
    )

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    order_status = models.CharField(
        max_length=30,
        choices=ORDER_STATUS_CHOICES,
        default="pending"
    )

    delivery_status = models.CharField(
        max_length=30,
        choices=DELIVERY_STATUS_CHOICES,
        default="pending"
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

    order_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    notes = models.TextField(
        blank=True,
        default=""
    )

    # ---------------------------------------------------------
    # CREATED BY
    # ---------------------------------------------------------

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sales_orders"
    )

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    def clean(self):

        if self.delivery_date and self.order_date:
            if self.delivery_date < self.order_date:
                raise ValidationError({
                    "delivery_date": "Delivery date cannot be before order date."
                })

        if self.due_date and self.order_date:
            if self.due_date < self.order_date:
                raise ValidationError({
                    "due_date": "Due date cannot be before order date."
                })

        if self.customer and self.company:
            if self.customer.company_id != self.company_id:
                raise ValidationError(
                    "Customer does not belong to the selected company."
                )

        if self.quotation and self.company:
            if self.quotation.company_id != self.company_id:
                raise ValidationError(
                    "Quotation does not belong to the selected company."
                )

        if self.warehouse and self.company:
            if self.warehouse.company_id != self.company_id:
                raise ValidationError(
                    "Warehouse does not belong to the selected company."
                )

    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------

    def save(self, *args, **kwargs):

        if not self.so_number or not str(self.so_number).strip():

            from .utils import generate_next_sales_order_number

            self.so_number = generate_next_sales_order_number(
                self.company
            )

        super().save(*args, **kwargs)

    # ---------------------------------------------------------
    # TOTAL CALCULATION
    # ---------------------------------------------------------

    def calculate_totals(self):

        items = self.items.all()

        subtotal = Decimal("0.00")
        total_vat = Decimal("0.00")

        for item in items:

            item.calculate_amounts()

            subtotal += item.amount_before_vat
            total_vat += item.vat_amount

        self.subtotal = subtotal
        self.total_vat = total_vat

        self.order_value = (
            subtotal
            + total_vat
            - self.discount
            + self.round_off
        )

        self.save(
            update_fields=[
                "subtotal",
                "total_vat",
                "order_value"
            ]
        )

    # ---------------------------------------------------------
    # DELIVERY STATUS
    # ---------------------------------------------------------

    def update_delivery_status(self):

        items = list(self.items.all())

        if not items:

            new_status = "pending"

        elif all(
            item.delivered_quantity <= Decimal("0.00")
            for item in items
        ):

            new_status = "pending"

        elif all(
            item.delivered_quantity >= item.quantity
            for item in items
        ):

            new_status = "completed"

        else:

            new_status = "partially_delivered"

        if self.delivery_status != new_status:

            self.delivery_status = new_status

            self.save(
                update_fields=["delivery_status"]
            )

    def __str__(self):
        return self.so_number

    class Meta:

        db_table = "finance_sales_order"

        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "so_number"
                ],
                name="unique_sales_order_number_per_company"
            ),

            models.UniqueConstraint(
                fields=[
                    "company",
                    "quotation"
                ],
                name="unique_sales_order_per_quotation"
            )
        ]


class SalesOrderItem(TimeStampedModel):

    id = models.BigAutoField(primary_key=True)

    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="items"
    )

    quotation_item = models.ForeignKey(
        "quotation.QuotationItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_order_items"
    )

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_order_items"
    )

    service_name = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )

    description = models.TextField(
        blank=True,
        default=""
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01"))
        ]
    )

    delivered_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00"))
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

    amount_before_vat = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    vat_amount = models.DecimalField(
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

        self.amount_before_vat = (
            self.quantity * self.rate
        )

        self.vat_amount = (
            self.amount_before_vat
            * self.vat_percentage
            / Decimal("100")
        )

        self.amount = (
            self.amount_before_vat
            + self.vat_amount
        )

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    def clean(self):

        if self.delivered_quantity > self.quantity:

            raise ValidationError({
                "delivered_quantity":
                    "Delivered quantity cannot exceed ordered quantity."
            })

        if self.product and self.sales_order:

            if self.product.company_id != self.sales_order.company_id:

                raise ValidationError(
                    "Product does not belong to the sales order company."
                )

    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------

    def save(self, *args, **kwargs):

        self.calculate_amounts()

        super().save(*args, **kwargs)

    @property
    def remaining_quantity(self):

        remaining = (
            self.quantity
            - self.delivered_quantity
        )

        return max(
            remaining,
            Decimal("0.00")
        )

    def __str__(self):

        return (
            self.service_name
            or (
                self.product.product_name
                if self.product
                else "Sales Order Item"
            )
        )

    class Meta:

        db_table = "finance_sales_order_item"