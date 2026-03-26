# orders/models.py
# This file defines everything about ordering.
# Goal: support "one checkout" where a customer buys from multiple producers,
# and we split it into ProducerOrder records (one per producer).

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from accounts.models import User


class Order(models.Model):
    """
    The main order placed by a customer at checkout.

    This is the "parent" order. It can contain products from multiple producers.

    We store money totals on the order so old orders do not change later.
    (If product prices change, the order totals stay the same.)
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"         # created but not paid yet
        PAID = "paid", "Paid"                 # payment confirmed
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    is_recurring_instance = models.BooleanField(default=False)

    recurring_template = models.ForeignKey(
        "RecurringOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_orders"
    )
    # Snapshot money fields.
    # subtotal = sum of item line totals
    # commission_total = platform fee
    # total = subtotal + commission_total
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    commission_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        """
        Keep role logic consistent:
        only a customer can place an Order.
        """
        if self.customer and getattr(self.customer, "role", None) != User.Role.CUSTOMER:
            raise ValidationError("Order.customer must be a user with role='customer'.")

    def recalculate_totals(self, commission_rate: Decimal = Decimal("0.10")) -> None:
        """
        Recalculate subtotal, commission, total.

        commission_rate is a simple percentage, e.g. 0.10 for 10%.
        We save totals so they are stable and do not change over time.
        """
        subtotal = Decimal("0.00")

        for item in self.items.all():
            subtotal += item.line_total

        # Keep money to 2 decimal places
        subtotal = subtotal.quantize(Decimal("0.01"))
        commission = (subtotal * commission_rate).quantize(Decimal("0.01"))
        total = (subtotal + commission).quantize(Decimal("0.01"))

        self.subtotal = subtotal
        self.commission_total = commission
        self.total = total

    def __str__(self) -> str:
        return f"Order {self.id} ({self.status})"


class OrderItem(models.Model):
    """
    One product line inside an order.

    We store unit_price at the moment of purchase (snapshot),
    so price changes later do not change historical orders.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="How many units of this product were purchased.",
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Snapshot of the product price at purchase time.",
    )

    @property
    def line_total(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

    def clean(self) -> None:
        """
        Basic consistency:
        - producer role should own the product (product.producer.role == producer)
        - (stock rules are enforced during checkout logic, not here)
        """
        if self.product and getattr(self.product.producer, "role", None) != User.Role.PRODUCER:
            raise ValidationError("OrderItem.product must belong to a producer user.")

    def __str__(self) -> str:
        return f"{self.quantity} x {self.product.name}"


class ProducerOrder(models.Model):
    """
    A sub-order created from the main Order, one per producer.

    Example:
    - Customer buys from Producer A and Producer B in one checkout.
    - We create 2 ProducerOrder rows linked to the same parent order.

    This helps:
    - producers see only their part
    - status can be tracked per producer (packed/dispatched)
    - settlements can be calculated per producer
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DISPATCHED = "dispatched", "Dispatched"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    parent_order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="producer_orders",
    )

    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="producer_orders",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # Subtotal for just this producer’s items.
    # This is stored for reporting/settlement (stable over time).
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevent duplicates: one ProducerOrder per producer per parent order
        constraints = [
            models.UniqueConstraint(
                fields=["parent_order", "producer"],
                name="uniq_producer_order_per_parent",
            )
        ]

    def clean(self) -> None:
        """
        Ensure producer role correctness.
        """
        if self.producer and getattr(self.producer, "role", None) != User.Role.PRODUCER:
            raise ValidationError("ProducerOrder.producer must be a user with role='producer'.")

    def __str__(self) -> str:
        return f"ProducerOrder {self.id} (producer={self.producer.username})"
    
class Cart(models.Model):
    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart({self.customer_id})"

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), 0)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="uniq_cart_product")
        ]

    def __str__(self):
        return f"CartItem(cart={self.cart_id}, product={self.product_id}, qty={self.quantity})"

    @property
    def unit_price(self):
        # uses live product price (simple + fine for now)
        return getattr(self.product, "price", 0)

    @property
    def line_total(self):
        return self.unit_price * self.quantity
    
   # TEMPLATE (recurring setup)
class RecurringOrder(models.Model):
    """
    Template for weekly/fortnightly orders.
    """

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurring_orders",
    )

    name = models.CharField(max_length=100, default="Weekly Order")

    recurrence = models.CharField(
        max_length=20,
        choices=[("weekly", "Weekly"), ("fortnightly", "Fortnightly")]
    )

    order_day = models.CharField(max_length=10)
    delivery_day = models.CharField(max_length=10)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.customer})"


class RecurringOrderItem(models.Model):
    recurring_order = models.ForeignKey(
        RecurringOrder,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.product} x {self.quantity}"