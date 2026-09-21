from django.db import models
from django.conf import settings
from shared.models import TimeStampedModel


class Product(TimeStampedModel):

    PRODUCT_TYPE_CHOICES = (
        ("product", "Product"),
        ("service", "Service"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    UNIT_CHOICES = (
        ("PCS", "Piece (PCS)"),
        ("Box", "Box"),
        ("Pack", "Pack"),
        ("Month", "Month"),
        ("Project", "Project"),
        ("Set", "Set"),
        ("Kg", "Kilogram (Kg)"),
        ("Meter", "Meter"),
        ("Other", "Other"),
    )

    TAX_TYPE_CHOICES = (
        ("vat", "VAT"),
        ("inclusive", "Inclusive"),
        ("exclusive", "Exclusive"),
        ("exempt", "Exempt"),
        ("none", "None"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="products"
    )

    code = models.CharField(max_length=50, blank=True)
    product_name = models.CharField(max_length=200)
    product_type = models.CharField(
        max_length=20,
        choices=PRODUCT_TYPE_CHOICES,
        default="product"
    )
    sku = models.CharField(max_length=100, blank=True, default="")

    category = models.ForeignKey(
        "category.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products"
    )

    sub_category = models.ForeignKey(
        "category.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_category_products"
    )

    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products"
    )

    brand = models.CharField(max_length=100, blank=True, default="")
    supplier = models.CharField(max_length=150, blank=True, default="")

    unit = models.CharField(
        max_length=50,
        choices=UNIT_CHOICES,
        default="PCS"
    )

    hsn_sac_code = models.CharField(max_length=50, blank=True, default="")

    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )

    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )

    opening_stock_qty = models.IntegerField(default=0)
    quantity = models.IntegerField(default=0)
    current_stock = models.IntegerField(default=0)
    reserved_qty = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)

    tax_type = models.CharField(
        max_length=20,
        choices=TAX_TYPE_CHOICES,
        default="vat"
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00
    )

    description = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_products"
    )

    @property
    def stock_status(self):
        if self.product_type == "service":
            return "In Stock"
        if self.current_stock <= 0:
            return "Out of Stock"
        elif self.current_stock < 10 or self.current_stock < self.reorder_level:
            return "Low Stock"
        return "In Stock"

    @property
    def inventory_value(self):
        return self.current_stock * self.selling_price

    def save(self, *args, **kwargs):
        if not self.code or not str(self.code).strip():
            from .utils import generate_next_product_code
            self.code = generate_next_product_code(self.company)

        if self.pk is None:
            if self.current_stock == 0:
                self.current_stock = self.opening_stock_qty + self.quantity
            elif self.quantity > 0 and self.current_stock == self.opening_stock_qty:
                self.current_stock = self.opening_stock_qty + self.quantity
        else:
            try:
                old_instance = Product.objects.get(pk=self.pk)
                if self.quantity != old_instance.quantity:
                    qty_diff = self.quantity - old_instance.quantity
                    self.current_stock += qty_diff
            except Product.DoesNotExist:
                pass

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.product_name}"

    class Meta:
        db_table = "finance_product"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_product_code_per_company"
            )
        ]
