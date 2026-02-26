# reviews/models.py
# Stores product reviews written by customers.

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import User


class Review(models.Model):
    """
    A customer review for a product.

    Rules:
    - reviewer must be a customer user
    - rating is 1 to 5
    - one customer can only review the same product once
    """

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="reviews",
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviews",
    )

    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])

    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "reviewer"],
                name="uniq_review_per_product_per_customer",
            )
        ]

    def clean(self) -> None:
        if self.reviewer and getattr(self.reviewer, "role", None) != User.Role.CUSTOMER:
            raise ValidationError("Review.reviewer must be a user with role='customer'.")

    def __str__(self) -> str:
        return f"Review {self.rating}/5 by {self.reviewer.username}"