from django.db import models
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

# Load the Fernet key from settings (make sure it's fixed and doesn't change between deploys)
fernet = Fernet(settings.FERNET_KEY)


class EncryptedMixin:
    """
    Mixin for encrypted fields.
    Handles encryption before saving and decryption after fetching.
    """

    def get_prep_value(self, value):
        """Called before saving to DB – always encrypt."""
        if value is not None and value != "":
            return fernet.encrypt(str(value).encode()).decode()
        return value

    def from_db_value(self, value, expression, connection):
        """Called when fetching from DB – try to decrypt."""
        if value is None:
            return value
        try:
            return fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            # Value might already be plaintext (legacy data)
            return value

    def to_python(self, value):
        """Called when assigning value to a model field in Python."""
        if value is None:
            return value
        if isinstance(value, str):
            try:
                return fernet.decrypt(value.encode()).decode()
            except Exception:
                # Already plaintext (or bad token)
                return value
        return value


class EncryptedCharField(EncryptedMixin, models.CharField):
    """Encrypted CharField"""
    pass


class EncryptedTextField(EncryptedMixin, models.TextField):
    """Encrypted TextField"""
    pass


class EncryptedEmailField(EncryptedMixin, models.EmailField):
    """Encrypted EmailField"""
    pass


class EncryptedIntegerField(EncryptedMixin, models.PositiveIntegerField):
    """Encrypted IntegerField"""

    def get_prep_value(self, value):
        if value is not None and value != "":
            return fernet.encrypt(str(int(value)).encode()).decode()
        return value

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        try:
            return int(fernet.decrypt(value.encode()).decode())
        except InvalidToken:
            # If not encrypted (legacy data), return as integer if possible
            try:
                return int(value)
            except ValueError:
                return value

    def to_python(self, value):
        if value is None or value == "":
            return None
        if isinstance(value, int):
            return value
        try:
            return int(fernet.decrypt(value.encode()).decode())
        except Exception:
            return int(value) if value.isdigit() else value
