from django.db import models
from django.conf import settings
from django.utils import timezone
from shared.models import TimeStampedModel


class StockAdjustment(TimeStampedModel):

    ADJUSTMENT_TYPE_CHOICES = (
        ("add_stock", "Add Stock"),
        ("reduce_stock", "Reduce Stock"),
        ("remove_stock", "Remove Stock"),
        ("set_exact_quantity", "Set Exact Quantity"),
        ("addition", "Addition (+)"),
        ("subtraction", "Subtraction (-)"),
        ("Add Stock", "Add Stock"),
        ("Reduce Stock", "Reduce Stock"),
        ("Remove Stock", "Remove Stock"),
        ("Set Exact Quantity", "Set Exact Quantity"),
    )

    REASON_CHOICES = (
        ("Damaged Goods", "Damaged Goods"),
        ("Returned Stock", "Returned Stock"),
        ("Lost/Missing", "Lost/Missing"),
        ("New Stock Received", "New Stock Received"),
        ("Other", "Other"),
        ("damaged", "Damaged / Defective Stock"),
        ("inventory_count", "Inventory Count Reconciliation"),
        ("theft", "Stolen / Lost Items"),
        ("correction", "Data Entry Correction"),
        ("return", "Customer / Supplier Return"),
        ("Damaged Stock", "Damaged Stock"),
        ("Inventory Count", "Inventory Count"),
        ("Stolen / Lost Items", "Stolen / Lost Items"),
        ("Data Entry Correction", "Data Entry Correction"),
        ("Customer / Supplier Return", "Customer / Supplier Return"),
        ("other", "Other"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="stock_adjustments"
    )

    code = models.CharField(max_length=50, blank=True)

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.CASCADE,
        related_name="stock_adjustments"
    )

    sku = models.CharField(max_length=100, blank=True, default="")

    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_adjustments"
    )

    current_available_qty = models.IntegerField(default=0)
    adjusted_stock = models.IntegerField(default=0)

    adjustment_type = models.CharField(
        max_length=50,
        choices=ADJUSTMENT_TYPE_CHOICES,
        default="add_stock"
    )

    adjustment_quantity = models.IntegerField(default=1)

    reason = models.CharField(
        max_length=150,
        blank=True,
        default="Damaged Goods"
    )

    reference_document = models.CharField(
        max_length=150,
        blank=True,
        default=""
    )

    adjustment_date = models.DateField(default=timezone.localdate)

    note = models.TextField(blank=True, default="")

    attachment = models.FileField(
        upload_to="stock_adjustments/",
        null=True,
        blank=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_stock_adjustments"
    )

    def save(self, *args, **kwargs):
        if not self.code or not str(self.code).strip():
            from .utils import generate_next_adjustment_code
            self.code = generate_next_adjustment_code(self.company)

        adj_type_lower = str(self.adjustment_type).lower().strip()

        if self.pk is None:
            if self.product:
                if not self.sku:
                    self.sku = self.product.sku or ""
                self.current_available_qty = self.product.current_stock

                if adj_type_lower in ["add_stock", "addition", "increase", "add stock"]:
                    self.product.current_stock += self.adjustment_quantity
                elif adj_type_lower in ["reduce_stock", "remove_stock", "subtraction", "decrease", "reduce stock", "remove stock"]:
                    self.product.current_stock -= self.adjustment_quantity
                elif adj_type_lower in ["set_exact_quantity", "set_exact", "set exact quantity"]:
                    self.product.current_stock = self.adjustment_quantity

                self.product.save(update_fields=["current_stock", "updated_at"])
                self.adjusted_stock = self.product.current_stock
        else:
            if adj_type_lower in ["add_stock", "addition", "increase", "add stock"]:
                self.adjusted_stock = self.current_available_qty + self.adjustment_quantity
            elif adj_type_lower in ["reduce_stock", "remove_stock", "subtraction", "decrease", "reduce stock", "remove stock"]:
                self.adjusted_stock = max(0, self.current_available_qty - self.adjustment_quantity)
            elif adj_type_lower in ["set_exact_quantity", "set_exact", "set exact quantity"]:
                self.adjusted_stock = self.adjustment_quantity

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.product.product_name} ({self.adjustment_type} {self.adjustment_quantity})"

    class Meta:
        db_table = "finance_stock_adjustment"
        ordering = ["-created_at"]
