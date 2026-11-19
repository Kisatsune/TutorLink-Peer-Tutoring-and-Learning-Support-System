import secrets

from django.conf import settings
from django.db import models


def generate_key():
    """A random 40-character hexadecimal token."""
    return secrets.token_hex(20)


class ApiToken(models.Model):
    """One login token per administrator. The Tkinter app sends it in the
    'Authorization: Token <key>' header on every request."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_token"
    )
    key = models.CharField(max_length=40, unique=True, default=generate_key)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Token for {self.user.username}"
