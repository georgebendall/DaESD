from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from accounts.models import User


class Order(models.Model):
    """
    Main order placed by a customer.
    Can contain products from multiple producers.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
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
        related_name="generated_orders",
    )

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    commission_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        if self.customer and getattr(self.customer, "role", None) != User.Role.CUSTOMER:
            raise ValidationError("Order.customer must be a user with role='customer'.")

    def recalculate_totals(self, commission_rate: Decimal = Decimal("0.05")) -> None:
        subtotal = Decimal("0.00")

        for item in self.items.all():
            subtotal += item.line_total

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
    Stores unit_price snapshot at purchase time.
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
    def producer(self):
        return self.product.producer if self.product else None

    @property
    def line_total(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

    def clean(self) -> None:
        if self.product and getattr(self.product.producer, "role", None) != User.Role.PRODUCER:
            raise ValidationError("OrderItem.product must belong to a producer user.")

        if self.product and not self.product.is_active:
            raise ValidationError("This product is not currently available.")

        if self.product and self.quantity and self.product.stock is not None:
            if self.quantity > self.product.stock:
                raise ValidationError(f"Only {self.product.stock} left in stock for {self.product.name}.")

    def __str__(self) -> str:
        return f"{self.quantity} x {self.product.name}"


class ProducerOrder(models.Model):
    """
    One sub-order per producer for a parent order.
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

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["parent_order", "producer"],
                name="uniq_producer_order_per_parent",
            )
        ]

    def clean(self) -> None:
        if self.producer and getattr(self.producer, "role", None) != User.Role.PRODUCER:
            raise ValidationError("ProducerOrder.producer must be a user with role='producer'.")

    def recalculate_subtotal(self) -> None:
        subtotal = Decimal("0.00")
        for item in self.parent_order.items.filter(product__producer=self.producer):
            subtotal += item.line_total
        self.subtotal = subtotal.quantize(Decimal("0.01"))

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

    def clean(self) -> None:
        if self.customer and getattr(self.customer, "role", None) != User.Role.CUSTOMER:
            raise ValidationError("Cart.customer must be a user with role='customer'.")

    @property
    def subtotal(self) -> Decimal:
        return sum((item.line_total for item in self.items.all()), Decimal("0.00"))

    def __str__(self):
        return f"Cart({self.customer_id})"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="cart_items",
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        default=1,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="uniq_cart_product")
        ]

    def clean(self) -> None:
        if self.cart and getattr(self.cart.customer, "role", None) != User.Role.CUSTOMER:
            raise ValidationError("CartItem.cart must belong to a customer cart.")

        if self.product and not self.product.is_active:
            raise ValidationError("This product is not currently available.")

        if self.product and self.quantity and self.product.stock is not None:
            if self.quantity > self.product.stock:
                raise ValidationError(f"Only {self.product.stock} left in stock for {self.product.name}.")

    @property
    def unit_price(self) -> Decimal:
        return getattr(self.product, "price", Decimal("0.00"))

    @property
    def line_total(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

    def __str__(self):
        return f"CartItem(cart={self.cart_id}, product={self.product_id}, qty={self.quantity})"


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
        choices=[("weekly", "Weekly"), ("fortnightly", "Fortnightly")],
    )

    order_day = models.CharField(max_length=10)
    delivery_day = models.CharField(max_length=10)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        if self.customer and getattr(self.customer, "role", None) != User.Role.CUSTOMER:
            raise ValidationError("RecurringOrder.customer must be a user with role='customer'.")

    def __str__(self):
        return f"{self.name} ({self.customer})"


class RecurringOrderItem(models.Model):
    recurring_order = models.ForeignKey(
        RecurringOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="recurring_items",
    )

    quantity = models.PositiveIntegerField(default=1)

    def clean(self) -> None:
        if self.product and not self.product.is_active:
            raise ValidationError("Recurring orders can only include active products.")

    def __str__(self):
        return f"{self.product} x {self.quantity}"