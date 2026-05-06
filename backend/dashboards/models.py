from django.db import models


class Notification(models.Model):
    """Simple in-app notification used for low-stock and dashboard activity."""

    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return self.message
