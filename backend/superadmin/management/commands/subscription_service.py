import calendar
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils.timezone import now

from superadmin.models import Company, CompanySubscription


GRACE_PERIOD_DAYS = 5


class SubscriptionService:


    @staticmethod
    def get_due_date(company):

        today = now().date()

        billing_day = company.created_at.day

        year = today.year
        month = today.month


        # Get days in current month
        days_in_month = calendar.monthrange(
            year,
            month
        )[1]


        # Handle 29/30/31 cases
        due_day = min(
            billing_day,
            days_in_month
        )


        due_date = date(
            year,
            month,
            due_day
        )


        return due_date



    @staticmethod
    def check_subscription():

        today = now().date()


        result = {
            "checked": 0,
            "reminder_sent": 0,
            "frozen": 0
        }



        companies = Company.objects.all()


        for company in companies:


            result["checked"] += 1



            due_date = (
                SubscriptionService
                .get_due_date(company)
            )


            freeze_date = (
                due_date +
                timedelta(
                    days=GRACE_PERIOD_DAYS
                )
            )


            reminder_date = (
                due_date -
                timedelta(days=2)
            )


            subscription_month = due_date.month
            subscription_year = due_date.year



            paid = CompanySubscription.objects.filter(

                company=company,

                month=subscription_month,

                year=subscription_year,

                status="paid"

            ).exists()



            # ===============================
            # Already Paid
            # ===============================

            if paid:

                continue



            # ===============================
            # 2 Days Before Due Date
            # ===============================

            if today == reminder_date:


                SubscriptionService.send_email(

                    company,

                    "Subscription Payment Reminder",

                    f"""
Dear {company.name},

Your subscription payment is due on:

{due_date}

Please complete payment before the due date.

Thank you.
"""

                )


                result["reminder_sent"] += 1



            # ===============================
            # Due Date Email
            # ===============================

            if today == due_date:


                SubscriptionService.send_email(

                    company,

                    "Subscription Due Today",

                    f"""
Dear {company.name},

Today is your subscription due date.

Due Date:
{due_date}

Grace period:
{GRACE_PERIOD_DAYS} days

Account freeze date:
{freeze_date}

Please complete payment to avoid service interruption.

"""

                )


                result["reminder_sent"] += 1




            # ===============================
            # Freeze After Grace Period
            # ===============================

            if today > freeze_date:


                if company.is_active:


                    company.is_active = False


                    company.save(
                        update_fields=[
                            "is_active"
                        ]
                    )


                    updated_users = (
                        company.users.update(
                            is_active=False
                        )
                    )


                    SubscriptionService.send_email(

                        company,

                        "Account Frozen",

                        f"""
Dear {company.name},

Your account has been frozen.

Reason:
Subscription payment not received.

Due Date:
{due_date}

Please complete payment to restore access.

"""

                    )


                    result["frozen"] += 1



        return result





    # =====================================
    # Manual Freeze
    # =====================================

    @staticmethod
    def freeze_company(company):


        company.is_active = False

        company.save(
            update_fields=[
                "is_active"
            ]
        )


        users = company.users.update(
            is_active=False
        )


        return users




    # =====================================
    # Manual Unfreeze
    # =====================================

    @staticmethod
    def unfreeze_company(company):


        company.is_active = True


        company.save(
            update_fields=[
                "is_active"
            ]
        )


        users = company.users.update(
            is_active=True
        )


        return users




    # =====================================
    # Email
    # =====================================

    @staticmethod
    def send_email(company, subject, message):


        send_mail(

            subject,

            message,

            settings.DEFAULT_FROM_EMAIL,

            [
                company.email
            ],

            fail_silently=True

        )