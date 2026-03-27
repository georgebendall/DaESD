from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    """
    Main user model.
    Keeps Django auth fields and adds a role for permissions.
    """

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        PRODUCER = "producer", "Producer"
        ADMIN = "admin", "Admin"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True,
        help_text="Defines whether this user is a customer, producer, or admin.",
    )

    email = models.EmailField(unique=True)

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"


class CustomerProfile(models.Model):
    """
    Extra information only customers need.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    phone = models.CharField(max_length=30, blank=True)
    postcode = models.CharField(max_length=12, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        if self.user and self.user.role != User.Role.CUSTOMER:
            raise ValidationError(
                "CustomerProfile can only be linked to users with role='customer'."
            )

    def __str__(self) -> str:
        return f"CustomerProfile for {self.user.username}"


class ProducerProfile(models.Model):
    """
    Extra information only producers need.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="producer_profile",
    )
    business_name = models.CharField(max_length=120)
    contact_phone = models.CharField(max_length=30, blank=True)
    address_line1 = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=80, blank=True)
    postcode = models.CharField(max_length=12, blank=True)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        if self.user and self.user.role != User.Role.PRODUCER:
            raise ValidationError(
                "ProducerProfile can only be linked to users with role='producer'."
            )

    def __str__(self) -> str:
        return f"ProducerProfile for {self.user.username}"