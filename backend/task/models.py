from django.db import models
from shared.models import TimeStampedModel
from employee.models import Employee_db

# Create your models here.
class DailyTask(TimeStampedModel):
    employee = models.ForeignKey(Employee_db, on_delete=models.CASCADE, related_name='tasks')
    project = models.CharField(max_length=100)
    task = models.TextField()
    time_taken = models.DecimalField(max_digits=5, decimal_places=2)
    description =models.TextField(null=True,blank=True)

    def __str__(self):
        return f"{self.employee.name} - {self.date} - {self.project}"