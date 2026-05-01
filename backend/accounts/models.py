from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models


class RoleAwareUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


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

    objects = RoleAwareUserManager()

    @property
    def is_admin_user(self) -> bool:
        return self.is_superuser or self.is_staff or self.role == self.Role.ADMIN

    @property
    def is_producer_user(self) -> bool:
        return self.role == self.Role.PRODUCER and not self.is_admin_user

    @property
    def is_customer_user(self) -> bool:
        return self.role == self.Role.CUSTOMER and not self.is_admin_user

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"


class CustomerProfile(models.Model):
    """
    Extra information only customers need.
    """

    class AccountType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        COMMUNITY_GROUP = "community_group", "Community Group"
        RESTAURANT = "restaurant", "Restaurant"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    account_type = models.CharField(
        max_length=30,
        choices=AccountType.choices,
        default=AccountType.INDIVIDUAL,
    )
    organisation_name = models.CharField(max_length=160, blank=True)
    institutional_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address_line1 = models.CharField(max_length=120, blank=True)
    postcode = models.CharField(max_length=12, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        if self.user and self.user.role != User.Role.CUSTOMER:
            raise ValidationError(
                "CustomerProfile can only be linked to users with role='customer'."
            )
        if self.account_type != self.AccountType.INDIVIDUAL and not self.organisation_name:
            raise ValidationError("Organisation name is required for community group and restaurant accounts.")

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
