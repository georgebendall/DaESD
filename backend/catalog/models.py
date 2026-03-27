from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from accounts.models import User


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def _generate_unique_slug(self) -> str:
        base = slugify(self.name) or "category"
        base = base[:120]
        slug = base
        i = 2

        while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            suffix = f"-{i}"
            slug = base[: 120 - len(suffix)] + suffix
            i += 1

        return slug

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Allergen(models.Model):
    name = models.CharField(max_length=80, unique=True)

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    class AvailabilityStatus(models.TextChoices):
        IN_SEASON = "in_season", "In Season"
        YEAR_ROUND = "year_round", "Available Year-Round"
        OUT_OF_SEASON = "out_of_season", "Out of Season"
        UNAVAILABLE = "unavailable", "Unavailable"

    class Unit(models.TextChoices):
        EACH = "each", "Each"
        KG = "kg", "Kilogram"
        G = "g", "Gram"
        L = "l", "Litre"
        ML = "ml", "Millilitre"

    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="products",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )

    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, blank=True)
    description = models.TextField(blank=True)

    unit = models.CharField(
        max_length=10,
        choices=Unit.choices,
        default=Unit.EACH,
        help_text="How this product is sold.",
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    stock = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="How much stock is available right now.",
    )

    availability_status = models.CharField(
        max_length=30,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.YEAR_ROUND,
        help_text="Controls whether customers should see this product.",
    )

    stock_warning_level = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=5,
        help_text="Low stock alert threshold for this product.",
    )

    allergens = models.ManyToManyField(
        Allergen,
        blank=True,
        related_name="products",
        help_text="Optional list of allergens for this product.",
    )

    is_organic = models.BooleanField(
        default=False,
        help_text="Tick if this product is organically certified.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="If false, the product is hidden from customers.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["producer", "slug"],
                name="uniq_product_slug_per_producer",
            )
        ]

    def clean(self) -> None:
        if self.producer and getattr(self.producer, "role", None) != User.Role.PRODUCER:
            raise ValidationError("Product.producer must be a user with role='producer'.")

        if self.stock is not None and self.stock < 0:
            raise ValidationError("Stock cannot be negative.")

    @property
    def is_low_stock(self) -> bool:
        return self.stock <= self.stock_warning_level

    def update_customer_visibility(self) -> None:
        visible_statuses = {
            self.AvailabilityStatus.IN_SEASON,
            self.AvailabilityStatus.YEAR_ROUND,
        }
        self.is_active = self.stock > 0 and self.availability_status in visible_statuses

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = slugify(self.name)

        self.update_customer_visibility()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.unit}) - producer={self.producer.username}"


class ProductInventoryHistory(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory_history",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_changes_made",
    )
    old_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    new_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    old_availability_status = models.CharField(max_length=30, blank=True)
    new_availability_status = models.CharField(max_length=30, blank=True)

    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Inventory change for {self.product.name} at {self.created_at:%Y-%m-%d %H:%M}"