from django.core.management.base import BaseCommand
from datetime import date, timedelta
import calendar
from django.utils.timezone import now
from django.core.mail import send_mail
from django.conf import settings

from superadmin.models import Company, CompanySubscription


class Command(BaseCommand):
    help = "Freeze users of companies after grace period if unpaid and send email"

    def handle(self, *args, **kwargs):
        today = now().date()

        for company in Company.objects.all():

            billing_day = company.created_at.day
            year, month = today.year, today.month

            # -------- Due date calculation --------
            days_in_month = calendar.monthrange(year, month)[1]
            due_day = min(billing_day, days_in_month)
            due_date = date(year, month, due_day)

            # If today before due → check previous cycle
            if today <= due_date:
                if month == 1:
                    month, year = 12, year - 1
                else:
                    month -= 1

                days_in_month = calendar.monthrange(year, month)[1]
                due_day = min(billing_day, days_in_month)
                due_date = date(year, month, due_day)

            # -------- Grace period --------
            freeze_date = due_date + timedelta(days=10)

            # -------- Check paid status --------
            is_paid = CompanySubscription.objects.filter(
                company=company,
                month=month,
                year=year,
                status="paid"
            ).exists()

            # =====================================================
            # 1️⃣ Send expiry reminder (during grace period)
            # =====================================================
            if not is_paid and today <= freeze_date:

                send_mail(
                    subject="Subscription Expiry Reminder",
                    message=(
                        f"Dear {company.name},\n\n"
                        f"Your monthly subscription is pending.\n"
                        f"Due Date: {due_date}\n"
                        f"Grace Period Ends: {freeze_date}\n\n"
                        f"Please make payment to avoid account freeze."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[company.email],
                    fail_silently=True,
                )

                continue  # don't freeze yet

            # =====================================================
            # 2️⃣ Freeze company after grace period
            # =====================================================
            if not is_paid and today > freeze_date:

                updated = company.users.update(is_active=False)

                # Send freeze notification
                send_mail(
                    subject="Account Frozen – Subscription Unpaid",
                    message=(
                        f"Dear {company.name},\n\n"
                        f"Your account has been frozen due to unpaid "
                        f"subscription for {month}/{year}.\n\n"
                        f"Please complete payment to restore access."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[company.email],
                    fail_silently=True,
                )

                self.stdout.write(
                    f"Frozen {updated} users of company {company.company_id}"
                )
