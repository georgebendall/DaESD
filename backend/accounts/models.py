from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    """
    Our main user table.

    We keep Django's normal user fields (username, password, etc.)
    and add a role so the rest of the system knows what the user can do.
    """
    producer_business_name = models.CharField(max_length=120, blank=True),
    producer_address_line = models.CharField(max_length=255, blank=True),
    producer_postcode = models.CharField(max_length=12, blank=True),

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        PRODUCER = "producer", "Producer"
        ADMIN = "admin", "Admin"

    # Role is required and controls what parts of the app the user should access.
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True,
        help_text="Defines whether this user is a customer, producer, or admin.",
        
        
    )

    # Make email unique so one email cannot be used for multiple accounts.
    # We keep username too, because it's the simplest path with Django admin.
    email = models.EmailField(unique=True)

    def __str__(self) -> str:
        # Useful label in admin and logs.
        return f"{self.username} ({self.role})"


class CustomerProfile(models.Model):
    """
    Extra information only customers need.

    This is separated from User so we don't mix unrelated fields
    and to keep the core user table small and clean.
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
        """
        Prevent attaching a CustomerProfile to a non-customer user.
        This protects data consistency.
        """
        if self.user and self.user.role != User.Role.CUSTOMER:
            raise ValidationError("CustomerProfile can only be linked to users with role='customer'.")

    def __str__(self) -> str:
        return f"CustomerProfile for {self.user.username}"


class ProducerProfile(models.Model):
    """
    Extra information only producers need.

    Producers represent farms/sellers, so they need business details.
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

    # Optional flag to help later (approval flow, onboarding, etc.)
    is_approved = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        """
        Prevent attaching a ProducerProfile to a non-producer user.
        """
        if self.user and self.user.role != User.Role.PRODUCER:
            raise ValidationError("ProducerProfile can only be linked to users with role='producer'.")

    def __str__(self) -> str:
        return f"ProducerProfile for {self.user.username}"
