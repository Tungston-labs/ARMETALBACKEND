from django.db import models
from django.conf import settings

from shared.models import TimeStampedModel


class Customer(TimeStampedModel):

    INDUSTRY_CHOICES = (
        ("construction", "Construction"),
        ("manufacturing", "Manufacturing"),
        ("retail", "Retail"),
        ("healthcare", "Healthcare"),
        ("education", "Education"),
        ("technology", "Technology"),
        ("hospitality", "Hospitality"),
        ("finance", "Finance"),
        ("real_estate", "Real Estate"),
        ("other", "Other"),
    )

    CURRENCY_CHOICES = (
        ("AED", "AED"),
        ("USD", "USD"),
        ("EUR", "EUR"),
        ("GBP", "GBP"),
        ("INR", "INR"),
        ("SAR", "SAR"),
        ("QAR", "QAR"),
        ("BHD", "BHD"),
        ("KWD", "KWD"),
        ("OMR", "OMR"),
    )

    PAYMENT_TERM_CHOICES = (
        ("immediate", "Immediate"),
        ("7_days", "7 Days"),
        ("15_days", "15 Days"),
        ("30_days", "30 Days"),
        ("45_days", "45 Days"),
        ("60_days", "60 Days"),
        ("90_days", "90 Days"),
    )

    CLIENT_STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="customers"
    )

    customer_id = models.CharField(
        max_length=50
    )

    customer_name = models.CharField(
        max_length=200
    )

    company_name = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )

    industry = models.CharField(
        max_length=50,
        choices=INDUSTRY_CHOICES
    )

    website = models.URLField(
        blank=True,
        default=""
    )

    cr_number = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    currency = models.CharField(
        max_length=10,
        choices=CURRENCY_CHOICES
    )

    vat_number = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    payment_term = models.CharField(
        max_length=20,
        choices=PAYMENT_TERM_CHOICES,
        default="30_days"
    )

    cr_expiry_date = models.DateField(
        null=True,
        blank=True
    )

    # -----------------------------------------
    # BILLING ADDRESS
    # -----------------------------------------

    billing_address = models.TextField(
        blank=True,
        default=""
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    state = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    country = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    postal = models.CharField(
        max_length=20,
        blank=True,
        default=""
    )

    # -----------------------------------------
    # CONTACT INFORMATION
    # -----------------------------------------

    phno = models.CharField(
        max_length=30,
        blank=True,
        default=""
    )

    admin_email = models.EmailField(
        blank=True,
        default=""
    )

    financial_email = models.EmailField(
        blank=True,
        default=""
    )

    technical_email = models.EmailField(
        blank=True,
        default=""
    )

    client_status = models.CharField(
        max_length=20,
        choices=CLIENT_STATUS_CHOICES,
        default="active"
    )

    # -----------------------------------------
    # FINANCIAL INFORMATION
    # -----------------------------------------

    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    opening_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )

    notes = models.TextField(
        blank=True,
        default=""
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_customers"
    )

    def save(self, *args, **kwargs):

        if not self.customer_id:
            last_customer = (
                Customer.objects
                .filter(company=self.company)
                .order_by("-id")
                .first()
            )

            if last_customer:
                try:
                    last_number = int(
                        last_customer.customer_id.replace(
                            "CUS", ""
                        )
                    )
                except (ValueError, AttributeError):
                    last_number = 0

                next_number = last_number + 1

            else:
                next_number = 1

            self.customer_id = f"CUS{next_number:03d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_id} - {self.customer_name}"

    class Meta:
        db_table = "finance_customer"

        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["company", "customer_id"],
                name="unique_customer_id_per_company"
            )
        ]


class CustomerDocument(TimeStampedModel):

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    document = models.FileField(
        upload_to="customer_documents/"
    )

    document_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    def __str__(self):
        return (
            self.document_name
            or self.document.name
        )

    class Meta:
        db_table = "finance_customer_document"