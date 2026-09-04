# employee/tasks.py
from celery import shared_task
from datetime import datetime
from .models import ScheduleReminder
from employee.utils import send_push_notification  # your FCM helper

@shared_task
def send_reminder(reminder_id):
    try:
        reminder = ScheduleReminder.objects.get(id=reminder_id)
        user = reminder.employee.user
        token = user.fcm_token

        if token:
            send_push_notification(
                user=user,
                title=f"Reminder: {reminder.title}",
                message=reminder.body
            )

        reminder.notified = True
        reminder.save()

    except ScheduleReminder.DoesNotExist:
        pass

@shared_task
def soft_delete_expired_reminders():
    now = datetime.now()
    ScheduleReminder.objects.filter(scheduled_datetime__lt=now, is_expired=False).update(is_expired=True)

