import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from superadmin.models import Company, CompanySubscription, SubscriptionPlan
from django.utils.timezone import now

# Find the companies
testing_company = Company.objects.filter(company_id="testingcompany").first()
dummy_company = Company.objects.filter(company_id="dummy").first()
rekory_company = Company.objects.filter(company_id="rekory").first()
uae_rekory = Company.objects.filter(company_id="uaerekory").first()
us_rekory = Company.objects.filter(company_id="uerekory").first()

current_year = now().date().year

# Enforce subscription plan assignments to ensure different plan distributions
enterprise_plan = SubscriptionPlan.objects.filter(name__icontains="Enterprise").first()
pro_plan = SubscriptionPlan.objects.filter(name__icontains="PRO").first()
basic_plan = SubscriptionPlan.objects.filter(name__icontains="Basic").first()

if testing_company and enterprise_plan:
    testing_company.plan = enterprise_plan
    testing_company.save()

if uae_rekory and pro_plan:
    uae_rekory.plan = pro_plan
    uae_rekory.save()

if us_rekory and basic_plan:
    us_rekory.plan = basic_plan
    us_rekory.save()

# Update or create paid subscriptions for months
# Let's seed paid subscriptions with realistic amounts for various months in 2026
subscriptions_data = [
    # (company, month, amount, status, currency)
    # DUMMY
    (dummy_company, 1, 1500.00, "paid", "AED"),
    (dummy_company, 2, 2200.00, "paid", "AED"),
    (dummy_company, 3, 1800.00, "paid", "AED"),
    (dummy_company, 4, 1200.00, "paid", "AED"),
    (dummy_company, 5, 2100.00, "paid", "AED"),
    (dummy_company, 6, 2150.00, "paid", "AED"),
    (dummy_company, 7, 1850.00, "paid", "AED"),
    (dummy_company, 8, 3000.00, "paid", "AED"),
    
    # Testing Company (Enterprise plan)
    (testing_company, 5, 2000.00, "paid", "INR"),
    (testing_company, 6, 2000.00, "paid", "INR"),
    (testing_company, 7, 2000.00, "paid", "INR"),
    (testing_company, 8, 2000.00, "paid", "INR"),

    # UAE-REKORY (PRO plan)
    (uae_rekory, 6, 1800.00, "paid", "SAR"),
    (uae_rekory, 7, 1800.00, "paid", "SAR"),
    (uae_rekory, 8, 1800.00, "paid", "SAR"),

    # US-REKORY (Basic plan)
    (us_rekory, 7, 1000.00, "paid", "USD"),
    (us_rekory, 8, 1000.00, "paid", "USD"),
]

for company, month, amount, status, currency in subscriptions_data:
    if company:
        sub, created = CompanySubscription.objects.get_or_create(
            company=company,
            month=month,
            year=current_year,
            defaults={
                "amount": amount,
                "status": status,
                "currency": currency,
                "paid_date": now().date()
            }
        )
        if not created:
            sub.amount = amount
            sub.status = status
            sub.currency = currency
            if status == "paid" and not sub.paid_date:
                sub.paid_date = now().date()
            sub.save()

print("Database subscriptions seeded successfully with realistic paid records!")
