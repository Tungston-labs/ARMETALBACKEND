from django.db import models
from django.conf import settings


from employee.models import Employee_db,EmpBankPaymentModel

class EmployeePayrollRecord(models.Model):
    STATUS_CHOICES = [
        ('OnHold', 'OnHold'),
        ('Cancelled', 'Cancelled'),
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
    ]

    employee = models.ForeignKey(Employee_db, on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    salary_date = models.DateField(auto_now_add=True)

    # Snapshot from EmpBankPaymentModel
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    salary_increment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    housing_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    transportation = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    tds_deduction_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_mode = models.CharField(max_length=10, choices=EmpBankPaymentModel.PAYMENT_MODES, blank=True, null=True)
    tax_regime = models.CharField(max_length=10, choices=EmpBankPaymentModel.TAX_REGIMES, blank=True, null=True)
    pan_number = models.CharField(max_length=15, blank=True, null=True)
    account_number = models.CharField(max_length=30, blank=True, null=True)
    payslip_file = models.FileField(upload_to='payslips/', null=True, blank=True)
    working_days = models.PositiveIntegerField(null=True, blank=True)
    days_present = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lop_days = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lop_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)


    # ✅ New fields for HR verification
    hr1_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="payroll_hr1_verified"
    )
    hr2_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="payroll_hr2_verified"
    )
    hr1_verified_at = models.DateTimeField(null=True, blank=True)
    hr2_verified_at = models.DateTimeField(null=True, blank=True)
    incentive_amount = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    default=0.00
    )

    incentive_type = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    incentive_reason = models.TextField(
        blank=True,
        null=True
    )
    deduction_amount = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    default=0.00
    )

    deduction_type = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    deduction_reason = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        unique_together = ('employee', 'month', 'year')

    def is_fully_verified(self):
        return self.hr1_verified_by is not None and self.hr2_verified_by is not None

    def __str__(self):
        return f"{self.employee.name} - {self.month}/{self.year}"
