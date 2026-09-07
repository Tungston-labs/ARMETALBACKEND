from django.db import models
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
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

    code = models.CharField(
        max_length=50,
        unique=True
    )

    category_name = models.CharField(
        max_length=150
    )

    parent_category = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
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

    def clean(self):
        if self.parent_category:
            if self.parent_category.category_type != self.category_type:
                raise ValidationError(
                    "Parent category must have the same category type."
                )

            if self.parent_category.pk == self.pk:
                raise ValidationError(
                    "A category cannot be its own parent."
                )

    def __str__(self):
        return f"{self.code} - {self.category_name}"

    class Meta:
        db_table = "finance_category"
        ordering = ["category_name"]
