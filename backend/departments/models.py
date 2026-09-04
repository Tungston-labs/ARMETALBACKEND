from django.db import models
from shared.models import TimeStampedModel
from superadmin.models import Company

class Department(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=100)
    department_code = models.CharField(max_length=10, unique=True)
    department_head = models.ForeignKey(
        'employee.Employee_db',  
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments'
    )

    def __str__(self):
        return f"{self.name} ({self.department_code})"

    class Meta:
        ordering = ['name']  
