# payments/models.py
# This app stores money-related records.
#
# 1) PaymentTransaction:
#    One record per payment attempt or payment event for an order.
#    Example: paid, failed, refunded.
#
# 2) WeeklySettlement:
#    One record per producer per week that stores:
#    gross sales, platform commission, and payout to producer.

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from accounts.models import User


class PaymentTransaction(models.Model):
    """
    Records payment information for an Order.

    Why we store this:
    - If payment fails and the customer retries, you get a history.
    - If you need to prove "this order was paid", you have a record.
    - You can store a reference from a payment provider (Stripe/PayPal/etc.).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"     # created, waiting for provider confirmation
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payment_transactions",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # Which system processed it (later you can change names)
    provider = models.CharField(
        max_length=40,
        default="manual",
        help_text="Payment provider name, e.g. stripe, paypal, manual.",
    )

    # Money fields stored as a snapshot
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Total amount charged (snapshot).",
    )

    currency = models.CharField(
        max_length=10,
        default="GBP",
        help_text="Currency code, e.g. GBP.",
    )

    # Provider reference id / receipt / transaction id
    provider_reference = models.CharField(
        max_length=120,
        blank=True,
        help_text="Transaction id from the payment provider.",
    )

    # Optional JSON/text for debugging and demos (store provider response)
    raw_response = models.JSONField(
        blank=True,
        null=True,
        help_text="Optional provider response data for debugging.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        """
        Basic rule:
        - Only orders that belong to customers should be paid.
        """
        if self.order and getattr(self.order.customer, "role", None) != User.Role.CUSTOMER:
            raise ValidationError("PaymentTransaction.order must belong to a customer order.")

    def __str__(self) -> str:
        return f"PaymentTransaction {self.id} (order={self.order_id}, status={self.status})"


class WeeklySettlement(models.Model):
    """
    Stores weekly payouts for a producer.

    Why we store this:
    - Admin can see what each producer should be paid for a week.
    - It locks the numbers in time (history).
    - You can export it later to CSV for the assignment/demo.

    You create one settlement per producer per week range.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"       # calculated but not final
        FINAL = "final", "Final"       # approved/final numbers
        PAID = "paid", "Paid"          # money sent to producer

    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="weekly_settlements",
    )

    # Week range (you choose your own week boundaries later)
    period_start = models.DateField()
    period_end = models.DateField()

    # Totals stored as snapshots
    gross_sales = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    commission_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payout_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        # Prevent duplicates: only one settlement per producer per time period
        constraints = [
            models.UniqueConstraint(
                fields=["producer", "period_start", "period_end"],
                name="uniq_settlement_producer_period",
            )
        ]

    def clean(self) -> None:
        """
        Rules:
        - The settlement must be for a producer user.
        - period_start must be before or equal to period_end.
        """
        if self.producer and getattr(self.producer, "role", None) != User.Role.PRODUCER:
            raise ValidationError("WeeklySettlement.producer must be a user with role='producer'.")

        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValidationError("period_start must be before or equal to period_end.")

        # Money cannot be negative
        for field_name in ["gross_sales", "commission_total", "payout_total"]:
            value = getattr(self, field_name, None)
            if value is not None and value < 0:
                raise ValidationError(f"{field_name} cannot be negative.")

    def __str__(self) -> str:
        return f"Settlement {self.id} (producer={self.producer.username}, {self.period_start} to {self.period_end})"