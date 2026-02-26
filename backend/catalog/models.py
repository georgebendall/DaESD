from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from accounts.models import User  # we use this only to check User.Role in clean()


class Category(models.Model):
    """
    Product categories, like:
    - Vegetables
    - Dairy
    - Bakery

    We keep a slug so URLs can look clean later (e.g. /category/vegetables).
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class Allergen(models.Model):
    """
    Allergens list, like:
    - Milk
    - Eggs
    - Gluten

    This is a separate table so we don't repeat allergen names on every product.
    """

    name = models.CharField(max_length=80, unique=True)

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    """
    A product that a producer sells.

    Important rule:
    - producer must be a User with role='producer'
    """

    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # safer than CASCADE: you don't want products deleted by accident
        related_name="products",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,  # categories should not be deleted if products exist
        related_name="products",
    )

    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160)

    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],  # stops negative prices
    )

    stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],  # stops negative stock
        help_text="How many units are available right now.",
    )

    allergens = models.ManyToManyField(
        Allergen,
        blank=True,
        related_name="products",
        help_text="Optional list of allergens for this product.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="If false, the product is hidden from customers.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # This helps prevent two products from the same producer having the same slug.
        # It also helps your teammates safely build URLs later.
        constraints = [
            models.UniqueConstraint(
                fields=["producer", "slug"],
                name="uniq_product_slug_per_producer",
            )
        ]

    def clean(self) -> None:
        """
        Protect data consistency:
        - only a producer user can own products
        """
        if self.producer and getattr(self.producer, "role", None) != User.Role.PRODUCER:
            raise ValidationError("Product.producer must be a user with role='producer'.")

        # Simple extra protection:
        # If stock is 0, product can still exist, but it's effectively unavailable.
        if self.stock is not None and self.stock < 0:
            raise ValidationError("Stock cannot be negative.")

    def __str__(self) -> str:
        return f"{self.name} (producer={self.producer.username})"