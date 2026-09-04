import calendar
from datetime import date

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils.timezone import now

from superadmin.models import CompanySubscription

COUNTRY_CURRENCY = {
    "IN": "INR",
    "AE": "AED",
    "US": "USD",
    "SG": "SGD",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "JP": "JPY",
    "CN": "CNY",
    "AU": "AUD",
    "CA": "CAD",
}
class SubscriptionEmailService:

    @staticmethod
    def send_subscription_email(company):

        today = now().date()

        billing_day = company.created_at.day

        year = today.year
        month = today.month

        # -------------------------------
        # Calculate next due date
        # -------------------------------
        days = calendar.monthrange(year, month)[1]
        due_day = min(billing_day, days)
        due_date = date(year, month, due_day)

        if today > due_date:
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1

            days = calendar.monthrange(year, month)[1]
            due_day = min(billing_day, days)
            due_date = date(year, month, due_day)

        # ------------------------------------------
        # Fetch all unpaid subscriptions till current month
        # ------------------------------------------
        current_year = today.year
        current_month = today.month


        unpaid_subscriptions = (
            CompanySubscription.objects.filter(
                company=company,
                status="unpaid",
                year=current_year,
                month__lte=current_month
            )
            .order_by("month")
        )

        total_amount = 0
        currency = COUNTRY_CURRENCY.get(company.country, "INR")

        subscription_lines = []

        for sub in unpaid_subscriptions:

            total_amount += sub.amount
            currency = sub.currency

            subscription_lines.append(
                f"{calendar.month_name[sub.month]} {sub.year}\n"
                f"    Employees : {sub.employee_count}\n"
                f"    Amount    : {sub.amount} {currency}\n"
            )

        if subscription_lines:
            subscription_details = "\n".join(subscription_lines)
        else:
            subscription_details = "No unpaid subscriptions."

        # ------------------------------------------
        # Send Email
        # ------------------------------------------
        send_mail(
            subject="Subscription Payment Reminder",

            message=f"""
Dear {company.name},

This is a reminder regarding your Rekory HR System subscription.

The following subscriptions are currently unpaid:

--------------------------------------------------

{subscription_details}

--------------------------------------------------

Total Outstanding : {total_amount} {currency}

Next Due Date : {due_date.strftime("%d %B %Y")}

Please complete the payment before the due date to avoid interruption of your services.

If you have already made the payment, kindly ignore this email.

Regards,
Support System
Tungston Labs
""",

            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[company.email],
            fail_silently=False,
        )


# -------------------------------------only remainder email


import calendar
from datetime import date
from django.conf import settings
from django.core.mail import send_mail
from django.utils.timezone import now


class SubscriptionEmailService:

    @staticmethod
    def send_reminder_email(company, extra_email=None):
        today = now().date()

        billing_day = company.created_at.day

        year = today.year
        month = today.month

        days = calendar.monthrange(year, month)[1]
        due_day = min(billing_day, days)
        due_date = date(year, month, due_day)

        if today > due_date:
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1

            days = calendar.monthrange(year, month)[1]
            due_day = min(billing_day, days)
            due_date = date(year, month, due_day)

        recipients = [company.email]

        if extra_email and extra_email not in recipients:
            recipients.append(extra_email)

        send_mail(
            subject="Subscription Reminder",
            message=f"""
Dear {company.name},

This is a friendly reminder that your Rekory HR System subscription is due soon.

Next Due Date:
{due_date.strftime("%d %B %Y")}

Kindly ensure your subscription is renewed before the due date to avoid any interruption of services.

If you have already completed the payment, please ignore this email.

Regards,

Support Team
Tungston Labs
""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )