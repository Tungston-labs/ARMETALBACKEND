import os
import django
import sys

# Setup django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print("EMAIL_HOST:", settings.EMAIL_HOST)
print("EMAIL_PORT:", settings.EMAIL_PORT)
print("EMAIL_HOST_USER:", settings.EMAIL_HOST_USER)

try:
    send_mail(
        subject="Test SMTP Email from Rekory",
        message="This is a test email verifying that Django SMTP backend settings are configured correctly.",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[settings.EMAIL_HOST_USER], # send to self to verify
        fail_silently=False,
    )
    print("✅ Email sent successfully!")
except Exception as e:
    print("❌ Failed to send email:", str(e))
