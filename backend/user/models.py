from django.db import models

from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import random
import string


class User(AbstractUser):
    email = models.EmailField(unique=True)
     # Roles
    is_superadmin = models.BooleanField(default=False)
    is_hr_admin = models.BooleanField(default=False)
    is_employee = models.BooleanField(default=False)
    is_hr = models.BooleanField(default=False)
    fcm_token = models.CharField(max_length=255, blank=True, null=True)

    company = models.ForeignKey(
        'superadmin.Company',  # or your actual app label if different
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='users'
    )
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']




def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

class OTP(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timezone.timedelta(minutes=10)

