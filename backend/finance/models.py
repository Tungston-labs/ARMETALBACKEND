from django.db import models
from superadmin.models import Company

# Create your models here.
from django.db import models
class FinanceCategory(models.Model):
    PAYMENT_TYPE_CHOICES = (
        ("IN", "Income"),
        ("OUT", "Expense"),
    )

    name = models.CharField(max_length=100)
    payment_type = models.CharField(max_length=3, choices=PAYMENT_TYPE_CHOICES)

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,null=True,
        blank=True,
        related_name="finance_categories"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.company})"
    

class FinanceRecord(models.Model):
    PAYMENT_TYPE_CHOICES = (
        ("IN", "Income"),
        ("OUT", "Expense"),
    )

    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(
        max_length=3,
        choices=PAYMENT_TYPE_CHOICES
    )
    category = models.ForeignKey(
    FinanceCategory,
    on_delete=models.CASCADE,
    related_name="records"
)
    note = models.TextField(blank=True, null=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="finance_records"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - {self.amount}"
