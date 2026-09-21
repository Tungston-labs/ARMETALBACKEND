from django.db import models
from django.conf import settings
from shared.models import TimeStampedModel


class DeliveryNote(TimeStampedModel):

    DELIVERY_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("dispatched", "Dispatched"),
        ("partially_delivered", "Partially Delivered"),
        ("partial", "Partial"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    )

    INVOICE_STATUS_CHOICES = (
        ("not_invoiced", "Not Invoiced"),
        ("partially_invoiced", "Partially Invoiced"),
        ("fully_invoiced", "Fully Invoiced"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="delivery_notes"
    )

    dn_number = models.CharField(
        max_length=50,
        blank=True
    )

    sales_order = models.ForeignKey(
        "sales_order.SalesOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_notes"
    )

    so_ref = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    customer = models.ForeignKey(
        "customer.Customer",
        on_delete=models.CASCADE,
        related_name="delivery_notes"
    )

    delivery_date = models.DateField()

    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_notes"
    )

    delivery_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    delivery_status = models.CharField(
        max_length=50,
        choices=DELIVERY_STATUS_CHOICES,
        default="delivered"
    )

    invoice_status = models.CharField(
        max_length=50,
        choices=INVOICE_STATUS_CHOICES,
        default="not_invoiced"
    )

    # From details
    from_company_name = models.CharField(
        max_length=200,
        blank=True,
        default="Tungston Labs"
    )

    from_address = models.TextField(
        blank=True,
        default=""
    )

    from_phone_number = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    from_email = models.EmailField(
        blank=True,
        default=""
    )

    # Delivery / Shipping Details
    shipping_address = models.TextField(
        blank=True,
        default=""
    )

    contact_person = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )

    contact_phone = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    contact_email = models.EmailField(
        blank=True,
        default=""
    )

    # Financial Breakdown
    sub_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    total_vat = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    notes = models.TextField(
        blank=True,
        default=""
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_delivery_notes"
    )

    def save(self, *args, **kwargs):
        if self.sales_order and not self.so_ref:
            self.so_ref = self.sales_order.so_number
        if not self.dn_number or not str(self.dn_number).strip():
            from .utils import generate_next_dn_number
            self.dn_number = generate_next_dn_number(self.company)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dn_number} - {self.customer}"

    class Meta:
        db_table = "finance_delivery_note"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "dn_number"],
                name="unique_dn_number_per_company"
            )
        ]


class DeliveryNoteItem(TimeStampedModel):

    id = models.BigAutoField(primary_key=True)

    delivery_note = models.ForeignKey(
        DeliveryNote,
        on_delete=models.CASCADE,
        related_name="items"
    )

    sales_order_item = models.ForeignKey(
        "sales_order.SalesOrderItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_note_items"
    )

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_note_items"
    )

    item_name = models.CharField(
        max_length=200,
        blank=True,
        default=""
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
        max_digits=10,
        decimal_places=2,
        default=1.00
    )

    hs_code = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )

    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15.00
    )

    vat_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    def save(self, *args, **kwargs):
        if self.rate and self.quantity:
            base_val = self.rate * self.quantity
            if not self.vat_amount:
                self.vat_amount = base_val * (self.vat_percentage / 100)
            if not self.amount:
                self.amount = base_val + self.vat_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_name or self.service_name or 'Item'} ({self.quantity} x {self.rate})"

    class Meta:
        db_table = "finance_delivery_note_item"
