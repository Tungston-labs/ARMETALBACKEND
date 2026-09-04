
from django.db import models
from django.utils import timezone
from user.models import User
from departments.models import Department
from shared.models import TimeStampedModel
from shared.dataencrpt import EncryptedCharField,EncryptedEmailField,EncryptedIntegerField,EncryptedTextField
from django.contrib.postgres.fields import ArrayField  
from django.db.models import JSONField  

class Employee_db(TimeStampedModel):
    user = models.OneToOneField(
            User,
            on_delete=models.CASCADE,
            null=True,
            blank=True,
            related_name="employee_profile"
        )
    employee_id = models.CharField(max_length=200, unique=True, editable=False)
    employee_code = models.CharField(
        max_length=200,
        unique=True,
        null=True,
        blank=True
    )
    password = models.CharField(max_length=200,unique=True,null=True,blank=True)
    name = EncryptedCharField(max_length=500)
    name_search = models.CharField(max_length=500, db_index=True, blank=True, null=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    email = models.EmailField(unique=True)
    phno = EncryptedCharField(max_length=500,unique=True,null=True,blank=True)
    address = EncryptedTextField()
    dob = models.DateField()
    gender = models.CharField(max_length=10, choices=[
        ('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')
    ])
    country = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    ]

    blood_group = models.CharField(
        max_length=5,
        choices=BLOOD_GROUP_CHOICES,
        blank=True,
        null=True
    )

    designation = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='employees')
    joining_date = models.DateField(default=timezone.now)
    employment_type = models.CharField(max_length=20, choices=[
        ('Full-time', 'Full-time'), ('Part-time', 'Part-time'), ('Contract', 'Contract')
    ])
    passport_number = EncryptedCharField(max_length=500,blank=True, null=True,unique=True)
    iqama_number = EncryptedCharField(max_length=500,blank=True, null=True,unique=True)
    aadar_number = EncryptedCharField(max_length=500,blank=True, null=True,unique=True)
    insurance_number = EncryptedCharField(max_length=500,blank=True, null=True)
    visa_expiry_date = models.DateField(blank=True, null=True)
    contract_expiry_date = models.DateField(blank=True,null=True)
    total_leave = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    paid_leave = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    idcard = models.ImageField(upload_to='idcard_pics/', blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    ROLE_CHOICES = (
        ('employee', 'Employee'),
        ('hr', 'HR'),
        ('manager', 'Manager'),
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='employee'
    )


    def save(self, *args, **kwargs):

        if not self.employee_id:
            self.employee_id = self.email

        if self.name:
            self.name_search = str(self.name).strip().lower()

        super().save(*args, **kwargs)

        def __str__(self):
            return f"{self.name} - {self.employee_id}"



class EmpBankPaymentModel(models.Model):
    PAYMENT_MODES = [
        ('online', 'Online'),
        ('by cash', 'By Cash'),
        ('cheque', 'Cheque'),
    ]

    TAX_REGIMES = [
        ('old', 'Old Regime'),
        ('new', 'New Regime'),
    ]

    employee = models.OneToOneField(Employee_db, on_delete=models.CASCADE, related_name='bank_details')
    bank_name = models.CharField(max_length=100)
    swift_code = EncryptedCharField(max_length=500, blank=True, null=True)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODES,null=True,blank=True)
    account_number = EncryptedCharField(max_length=500)
    uan_epf_number = EncryptedCharField(max_length=500, blank=True, null=True)
    pan_number = EncryptedCharField(max_length=500)
    tax_regime = models.CharField(max_length=10, choices=TAX_REGIMES)
    tds_deduction_amount = models.DecimalField(max_digits=10, decimal_places=2)
    declaration_80c = models.BooleanField(default=False)
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    salary_increment = models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)

    housing_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True,blank=True)
    transportation = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True,blank=True)
    bank_proof_image = models.ImageField(upload_to='bank_proof/', null=True, blank=True)

    def __str__(self):
        return f"{self.employee.name} - {self.bank_name}"



class TempUpload(models.Model):
    file = models.ImageField(upload_to='temp_uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


class EmpDocument(models.Model):
    employee = models.OneToOneField('Employee_db', on_delete=models.CASCADE, related_name='documents')
    
    # Single image URLs
    passport_image1_url = models.URLField(blank=True, null=True)
    passport_image2_url = models.URLField(blank=True, null=True)
    insurance_image_url = models.URLField(blank=True, null=True)

    # Multiple image URLs as lists
    work_permit_urls = models.JSONField(default=list, blank=True)  # array of URLs
    contract_urls = models.JSONField(default=list, blank=True)
    certificate_urls = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Documents for {self.employee}"





class ScheduleReminder(models.Model):
    employee = models.ForeignKey(Employee_db, on_delete=models.CASCADE, related_name="reminders")
    title = models.CharField(max_length=100)
    body = models.TextField(blank=True)
    scheduled_datetime = models.DateTimeField()  # Combine date and time
    created_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)  # To avoid duplicate notifications
    is_expired = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} - {self.scheduled_datetime}"

from decimal import Decimal


class SalaryIncrement(models.Model):
    employee = models.ForeignKey(
        Employee_db,
        on_delete=models.CASCADE,
        related_name="salary_increments"
    )

    date = models.DateField()
    increment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_salary = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.employee.name} - {self.increment_amount}"