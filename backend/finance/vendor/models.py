from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from shared.models import TimeStampedModel


class Vendor(TimeStampedModel):

    VENDOR_TYPE_CHOICES = (
        ("equipment", "Equipment"),
        ("telecom", "Telecom"),
        ("networking", "Networking"),
        ("software", "Software"),
        ("services", "Services"),
        ("other", "Other"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    PAYMENT_TERM_CHOICES = (
        ("immediate", "Due on Receipt"),
        ("7_days", "7 Days"),
        ("15_days", "15 Days"),
        ("30_days", "30 Days"),
        ("45_days", "45 Days"),
        ("60_days", "60 Days"),
        ("90_days", "90 Days"),
    )

    CURRENCY_CHOICES = (
        ("AED", "AED"),
        ("INR", "INR"),
        ("USD", "USD"),
        ("EUR", "EUR"),
        ("SAR", "SAR"),
        ("GBP", "GBP"),
        ("OMR", "OMR"),
        ("QAR", "QAR"),
        ("BHD", "BHD"),
        ("KWD", "KWD"),
    )

    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="vendors",
    )

    vendor_id = models.CharField(
        max_length=50,
    )

    name = models.CharField(
        max_length=200,
    )

    vendor_type = models.CharField(
        max_length=30,
        choices=VENDOR_TYPE_CHOICES,
        default="other",
    )

    opening_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    cr_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    currency = models.CharField(
        max_length=10,
        choices=CURRENCY_CHOICES,
        default="AED",
    )

    vat_registration_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    payment_term = models.CharField(
        max_length=20,
        choices=PAYMENT_TERM_CHOICES,
        default="30_days",
    )

    cr_expiry_date = models.DateField(
        null=True,
        blank=True,
    )

    # Billing address
    billing_address = models.TextField(
        blank=True,
        default="",
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    state = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    country = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    postal = models.CharField(
        max_length=20,
        blank=True,
        default="",
    )

    # Contact
    phno = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    admin_email = models.EmailField(
        blank=True,
        default="",
    )

    financial_email = models.EmailField(
        blank=True,
        default="",
    )

    technical_email = models.EmailField(
        blank=True,
        default="",
    )

    # Bank details
    bank_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    account_num = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    iban = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    branch = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    client_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_vendors",
    )

    def save(self, *args, **kwargs):
        if not self.vendor_id:
            last_vendor = (
                Vendor.objects
                .filter(company=self.company)
                .order_by("-id")
                .first()
            )

            next_number = (
                int(last_vendor.vendor_id.replace("VEN", ""))
                + 1
                if last_vendor
                else 1
            )

            self.vendor_id = f"VEN{next_number:05d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.vendor_id} - {self.name}"

    class Meta:
        db_table = "finance_vendor"
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["company", "vendor_id"],
                name="unique_vendor_id_per_company",
            )
        ]


class VendorDocument(TimeStampedModel):

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    document = models.FileField(
        upload_to="vendor/documents/",
    )

    document_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
    )

    class Meta:
        db_table = "finance_vendor_document"
        ordering = ["-created_at"]

    def __str__(self):
        return self.document_name or str(self.document)


class VendorBill(TimeStampedModel):
    """
    Basic vendor payable record.

    If your existing purchase/bill module already stores
    vendor bills, use that model instead.
    """

    STATUS_CHOICES = (
        ("unpaid", "Unpaid"),
        ("partially_paid", "Partially Paid"),
        ("paid", "Paid"),
    )

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="vendor_bills",
    )

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="bills",
    )

    bill_number = models.CharField(max_length=100)

    bill_date = models.DateField()

    due_date = models.DateField()

    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    amount_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="unpaid",
    )

    class Meta:
        db_table = "finance_vendor_bill"
        ordering = ["-bill_date"]

        constraints = [
            models.UniqueConstraint(
                fields=["company", "bill_number"],
                name="unique_vendor_bill_number_per_company",
            )
        ]

    @property
    def outstanding_amount(self):
        return max(
            self.total_amount - self.amount_paid,
            Decimal("0.00"),
        )


class VendorPayment(TimeStampedModel):

    STATUS_CHOICES = (
        ("completed", "Completed"),
        ("pending", "Pending"),
        ("cancelled", "Cancelled"),
    )

    company = models.ForeignKey(
        "superadmin.Company",
        on_delete=models.CASCADE,
        related_name="vendor_payments",
    )

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    bill = models.ForeignKey(
        VendorBill,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    receipt_number = models.CharField(
        max_length=100,
    )

    payment_date = models.DateField()

    amount_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="completed",
    )

    class Meta:
        db_table = "finance_vendor_payment"
        ordering = ["-payment_date"]