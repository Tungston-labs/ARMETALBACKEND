from django.db import models
from django.conf import settings
from shared.models import TimeStampedModel


class Warehouse(TimeStampedModel):

    WAREHOUSE_TYPE_CHOICES = (
        ("main", "Main"),
        ("distribution", "Distribution"),
        ("regional", "Regional"),
        ("service", "Service"),
        ("spare_parts", "Spare Parts"),
        ("other", "Other"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="warehouses"
    )

    code = models.CharField(max_length=50, blank=True)

    warehouse_name = models.CharField(max_length=150)

    warehouse_type = models.CharField(
        max_length=50,
        choices=WAREHOUSE_TYPE_CHOICES,
        default="main"
    )

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_warehouses"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active"
    )

    operating_since = models.DateField(null=True, blank=True)

    country = models.CharField(max_length=100, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    address_line_1 = models.CharField(max_length=255, blank=True, default="")
    address_line_2 = models.CharField(max_length=255, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    phone_number = models.CharField(max_length=30, blank=True, default="")
    email = models.EmailField(max_length=254, blank=True, default="")
    storage_capacity = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_warehouses"
    )

    def save(self, *args, **kwargs):
        if not self.code or not str(self.code).strip():
            from .utils import generate_next_warehouse_code
            self.code = generate_next_warehouse_code(self.company)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.warehouse_name}"

    class Meta:
        db_table = "finance_warehouse"
        ordering = ["warehouse_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_warehouse_code_per_company"
            )
        ]
