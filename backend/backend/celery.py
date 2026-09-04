import os
from celery import Celery
from celery.schedules import crontab  # import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Add Celery Beat schedule
app.conf.beat_schedule = {
    "delete-expired-reminders-every-hour": {
        "task": "employee.tasks.delete_expired_reminders",
        "schedule": crontab(minute=0, hour="*"),  # runs every hour
    },
}
