# path: backend/reviews/models.py

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import User
from orders.models import Order, ProducerOrder


class Review(models.Model):
    """
    A customer review for a product.

    Rules:
    - reviewer must be a customer user
    - rating is 1 to 5
    - one customer can only review the same product once
    - NEW: must have purchased product (TC-024)
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

    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "reviewer"],
                name="uniq_review_per_product_per_customer",
            )
        ]

    def clean(self) -> None:
        from orders.models import OrderItem

        # ✅ KEEP: role validation
        if self.reviewer and getattr(self.reviewer, "role", None) != User.Role.CUSTOMER:
            raise ValidationError("Review.reviewer must be a user with role='customer'.")

        # Demo-friendly but closer to production:
        # customer must have paid for the order and the producer must have accepted it.
        has_purchased = OrderItem.objects.filter(
            order__customer=self.reviewer,
            order__status__in=[Order.Status.PAID, Order.Status.COMPLETED],
            order__producer_orders__producer=self.product.producer,
            order__producer_orders__status__in=[
                ProducerOrder.Status.ACCEPTED,
                ProducerOrder.Status.DISPATCHED,
                ProducerOrder.Status.COMPLETED,
            ],
            product=self.product,
        ).exists()

        if not has_purchased:
            raise ValidationError("You can review a product after payment once the producer has accepted the order.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Review {self.rating}/5 by {self.reviewer.username}"
