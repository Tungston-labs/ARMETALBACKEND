# purchase_order/models.py

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from shared.models import TimeStampedModel


class PurchaseOrder(TimeStampedModel):

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("ordered", "Ordered"),
        ("partially_received", "Partially Received"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    )

    RECEIPT_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("partially_received", "Partially Received"),
        ("received", "Received"),
    )

    BILL_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("partially_billed", "Partially Billed"),
        ("billed", "Billed"),
    )

    SHIPPING_METHOD_CHOICES = (
        ("road", "Road"),
        ("air", "Air"),
        ("sea", "Sea"),
        ("courier", "Courier"),
        ("pickup", "Pickup"),
        ("other", "Other"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="purchase_orders",
    )

    po_number = models.CharField(
        max_length=50,
        blank=True,
    )

    vendor = models.ForeignKey(
        "vendor.Vendor",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )

    # Optional PR reference until the Purchase Requisition
    # model and its app label are confirmed.
    pr_reference = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    order_date = models.DateField()

    expected_delivery_date = models.DateField(
        null=True,
        blank=True,
    )

    payment_terms = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
    )

    receipt_status = models.CharField(
        max_length=30,
        choices=RECEIPT_STATUS_CHOICES,
        default="pending",
    )

    bill_status = models.CharField(
        max_length=30,
        choices=BILL_STATUS_CHOICES,
        default="pending",
    )

    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )

    shipping_method = models.CharField(
        max_length=30,
        choices=SHIPPING_METHOD_CHOICES,
        default="road",
    )

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_vat = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    discount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    round_off = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    notes = models.TextField(
        blank=True,
        default="",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchase_orders",
    )

    class Meta:
        db_table = "purchase_order"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "po_number"],
                name="unique_purchase_order_number_per_company",
            )
        ]

    def __str__(self):
        return self.po_number


class PurchaseOrderItem(TimeStampedModel):

    id = models.BigAutoField(primary_key=True)

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
            "product.Product",
            on_delete=models.PROTECT,
            related_name="purchase_order_items"
        )

    description = models.TextField(
        blank=True,
        default="",
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    hs_code = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    rate = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    vat_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        db_table = "purchase_order_item"
        ordering = ["id"]

    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.product}"