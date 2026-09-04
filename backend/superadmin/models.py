import random
import string
from django.db import models
from shared.models import TimeStampedModel  
from django.utils.timezone import now
from calendar import month_name
from user.models import User
from django.core.exceptions import ValidationError
from shared.dataencrpt import EncryptedCharField,EncryptedEmailField,EncryptedIntegerField,EncryptedTextField
from django.db import transaction
from django.core.validators import MinValueValidator, MaxValueValidator
import re
from django.db import models
from shared.models import TimeStampedModel


class SubscriptionFeature(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SubscriptionPlan(TimeStampedModel):

    PLAN_TYPE = (
        ("basic", "Basic"),
        ("enterprise", "Enterprise"),
        ("pro", "Pro"),
        ("custom", "Custom"),
    )

    name = models.CharField(max_length=100)

    plan_type = models.CharField(
        max_length=20,
        choices=PLAN_TYPE
    )
    employee_limit = models.PositiveIntegerField(
        default=0,
        help_text="Number of employees included in the base plan price"
    )

    description = models.CharField(
        max_length=255,
        blank=True
    )

    features = models.ManyToManyField(
        SubscriptionFeature,
        blank=True,
        related_name="plans"
    )

    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    extra_employee_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

def generate_password():
    return 'CMP' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def generate_company_id_from_name(name):
    # remove spaces and special characters
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', name)
    base_id = clean_name.lower()

    # ensure uniqueness
    unique_id = base_id
    counter = 1
    while Company.objects.filter(company_id=unique_id).exists():
        unique_id = f"{base_id}{counter}"
        counter += 1

    return unique_id



COUNTRY_CHOICES = [
    ("IN", "India"),
    ("US", "United States"),
    ("AE", "United Arab Emirates"),
    ("SG", "Singapore"),
    ("GB", "United Kingdom"),
    ("DE", "Germany"),
    ("FR", "France"),
    ("JP", "Japan"),
    ("CN", "China"),
    ("AU", "Australia"),
    ("CA", "Canada"),
    
]


class Company(TimeStampedModel):
    company_id = models.CharField(max_length=200, unique=True, editable=False)
    name = EncryptedCharField(max_length=255)
    address = EncryptedTextField()
    location = models.CharField(max_length=100)
    latitude = models.FloatField(help_text="Latitude of the company location",null=True,blank=True)
    longitude = models.FloatField(help_text="Longitude of the company location",null=True,blank=True)
    country = models.CharField(max_length=300, choices=COUNTRY_CHOICES, blank=True, null=True)
    contact_number = EncryptedCharField(max_length=300)
    email = models.EmailField(unique=True)
    modules = models.JSONField(default=dict)  # e.g. {"attendance": True, "leave": True}
    number_of_employees = models.PositiveIntegerField(default=0, editable=False)
    default_password = models.CharField(max_length=200, editable=False)
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="companies"
    )
    logo = models.FileField(
                upload_to='company_logos/',
                null=True,
                blank=True,
                help_text="Upload PNG or SVG logo."
            )
    amount_per_employee = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    default=0
)


    initial_payment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Advance amount paid during company onboarding (not linked to subscription)"
    )

    basic_salary_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Basic salary percentage of CTC"
    )

    house_allowance_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    transport_allowance_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    special_allowance_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    working_hours_per_day = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=8.0,
        help_text="Total working hours per day"
    )

    half_day_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=4.0,
        help_text="Half day working hours"
    )
    is_active = models.BooleanField(default=True)


    def save(self, *args, **kwargs):

    # ✅ force decimal defaults at DB level
        if self.amount_per_employee is None:
            self.amount_per_employee = 0

        if self.initial_payment is None:
            self.initial_payment = 0

        if not self.company_id:
            self.company_id = generate_company_id_from_name(self.name)

        if not self.default_password:
            self.default_password = generate_password()

        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.name} ({self.company_id})"
    

    def clean(self):
        super().clean()
        if self.logo:
            ext = self.logo.name.lower().split('.')[-1]
            if ext not in ['png', 'svg']:
                raise ValidationError("Only .png or .svg files are allowed for the logo.")
            
        total_percent = (
        self.basic_salary_percent +
        self.house_allowance_percent +
        self.transport_allowance_percent +
        self.special_allowance_percent
    )

        if total_percent > 100:
            raise ValidationError("Total salary percentage cannot exceed 100%.")




class CompanySubscription(TimeStampedModel):
  
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='subscriptions')
    month = models.PositiveSmallIntegerField(choices=[(i, month_name[i]) for i in range(1, 13)])
    year = models.PositiveIntegerField(default=now().year)
    paid_date = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10,default='unpaid')
    currency = models.CharField(max_length=10, default='AED')
    employee_count = models.PositiveIntegerField(default=0)

    amount_per_employee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    class Meta:
        unique_together = ('company', 'month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.company.name} - {month_name[self.month]} {self.year} ({self.status})"



    def save(self, *args, **kwargs):
        # rate = self.company.amount_per_employee or 0
        # expected_amount = round(self.company.number_of_employees * rate, 2)

        # if not self.amount or self.amount != expected_amount:
        #     self.amount = expected_amount

        # detect status change
        is_new = self.pk is None
        previous_status = None

        if not is_new:
            previous_status = CompanySubscription.objects.get(pk=self.pk).status
        from finance.models import FinanceRecord,FinanceCategory

        with transaction.atomic():

            # when marked as paid
            if self.status == "paid":
                if not self.paid_date:
                    self.paid_date = now().date()

                # Activate company
                if not self.company.is_active:
                    self.company.is_active = True
                    self.company.save(update_fields=["is_active"])

                # Activate all company users
                self.company.users.update(is_active=True)

            super().save(*args, **kwargs)

            # ✅ create finance record ONLY when status becomes paid
            if (is_new and self.status == "paid") or (
                previous_status != "paid" and self.status == "paid"
            ):

                # prevent duplicate finance entry
                subscription_category, _ = FinanceCategory.objects.get_or_create(
                    name="subscription",
                    payment_type="IN",
                    company=None
                )

                exists = FinanceRecord.objects.filter(
                    category=subscription_category,
                    payment_type="IN",
                    note__icontains=self.company.company_id,
                    date__month=self.month,
                    date__year=self.year,
                ).exists()

                if not exists:
                    FinanceRecord.objects.create(
                        company=None,  # superadmin income
                        date=self.paid_date,
                        amount=self.amount,
                        payment_type="IN",
                        category=subscription_category,
                        note=f"Subscription payment from {self.company.name} "
                            f"({self.company.company_id}) "
                            f"for {self.month}/{self.year}",
                    )






class ImpersonationRequest(models.Model):
    super_admin = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('super_admin', 'company')




