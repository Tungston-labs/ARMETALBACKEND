from django.db import models
from superadmin.models import Company
import datetime
OFF_DAYS = [
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
]

class PublicHoliday(models.Model):

    HOLIDAY_TYPES = [
        ('public', 'Public Holiday'),
        ('company', 'Company Holiday'),
        ('company_off_day', 'Company Off Day'),
        ('second_saturday', 'Second Saturday'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='holidays'
    )

    date = models.DateField(
        null=True,
        blank=True
    )

    day = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    off_day_weekday = models.IntegerField(
        choices=OFF_DAYS,
        null=True,
        blank=True
    )

    description = models.CharField(max_length=255)

    holiday_type = models.CharField(
        max_length=20,
        choices=HOLIDAY_TYPES,
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['date']

    def save(self, *args, **kwargs):
        # Auto-fetch day from date (e.g. Monday, Tuesday...)
        if self.date:
            self.day = self.date.strftime('%A')  # e.g. Sunday
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.date} ({self.day}) - {self.description}"
    
    
