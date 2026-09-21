from django.db import models
from django.conf import settings
from shared.models import TimeStampedModel


class Category(TimeStampedModel):

    CATEGORY_TYPE_CHOICES = (
        ("product", "Product"),
        ("service", "Service"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="f_categories"
    )

    code = models.CharField(
        max_length=50
    )

    category_name = models.CharField(
        max_length=150
    )

    # Parent Category
    # NULL = this is a parent/root category
    # ID   = this is a sub-category
    parent_category = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sub_categories"
    )

    category_type = models.CharField(
        max_length=20,
        choices=CATEGORY_TYPE_CHOICES
    )

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
        related_name="created_categories"
    )

    def __str__(self):
        return f"{self.code} - {self.category_name}"

    class Meta:
        db_table = "finance_category"
        ordering = ["category_name"]

        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_category_code_per_company"
            )
        ]