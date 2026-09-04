from django.db import models
from employee.models import Employee_db
from superadmin.models import Company


class Project(models.Model):

    PUNCH_TYPE_CHOICES = [
        ('on_site', 'On Site'),
        ('variant', 'Variant'),
        ('bench', 'Bench'),
    ]

    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    name = models.CharField(max_length=255)

    punch_type = models.CharField(
        max_length=20,
        choices=PUNCH_TYPE_CHOICES,
        default='on_site'
    )

    latitude = models.FloatField(
        blank=True,
        null=True
    )

    longitude = models.FloatField(
        blank=True,
        null=True
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='projects',
        null=True,
        blank=True
    )

    employees = models.ManyToManyField(
        Employee_db,
        related_name='projects',
        blank=True
    )
    team_leads = models.ManyToManyField(
        Employee_db,
        related_name='team_lead_projects',
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='in_progress'
    )

    # NEW
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium'
    )

    # NEW
    start_date = models.DateField(
        null=True,
        blank=True
    )

    # KEEP THESE EXACTLY AS THEY WERE
    created_at = models.DateField(
        max_length=20,
        null=True,
        blank=True
    )

    updated_at = models.DateField(
        max_length=20,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.name