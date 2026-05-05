from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomerProfile, ProducerProfile, User
from catalog.models import Category, Product
from orders.models import Order, OrderItem, ProducerOrder

from .models import Review


class ReviewFlowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Vegetables", slug="vegetables-test-reviews")
        self.producer = User.objects.create_user(
            username="reviewproducer",
            email="reviewproducer@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(
            user=self.producer,
            business_name="Review Farm",
            postcode="BS1 4DJ",
        )
        self.customer = User.objects.create_user(
            username="reviewcustomer",
            email="reviewcustomer@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        CustomerProfile.objects.create(
            user=self.customer,
            postcode="BS1 5JG",
        )
        self.other_customer = User.objects.create_user(
            username="nopurchasecustomer",
            email="nopurchasecustomer@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        CustomerProfile.objects.create(
            user=self.other_customer,
            postcode="BS3 2AA",
        )
        self.product = Product.objects.create(
            producer=self.producer,
            category=self.category,
            name="Review Carrots",
            unit=Product.Unit.KG,
            price=Decimal("2.50"),
            stock=Decimal("80.00"),
        )

    def test_paid_purchase_customer_can_submit_review(self):
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.PAID,
            subtotal=Decimal("10.00"),
            commission_total=Decimal("0.50"),
            total=Decimal("10.50"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2,
            unit_price=self.product.price,
        )
        ProducerOrder.objects.create(
            parent_order=order,
            producer=self.producer,
            status=ProducerOrder.Status.ACCEPTED,
            subtotal=Decimal("5.00"),
        )

        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("product_review_create", args=[self.product.id]),
            {"rating": "5", "comment": "Very fresh and good quality."},
            follow=True,
        )

        self.assertContains(response, "Thanks for leaving a review.")
        self.assertTrue(
            Review.objects.filter(
                product=self.product,
                reviewer=self.customer,
                rating=5,
                comment="Very fresh and good quality.",
            ).exists()
        )

    def test_customer_without_paid_or_completed_purchase_cannot_submit_review(self):
        self.client.force_login(self.other_customer)
        response = self.client.post(
            reverse("product_review_create", args=[self.product.id]),
            {"rating": "4", "comment": "Looks good."},
            follow=True,
        )

        self.assertContains(response, "You can review a product after payment once the producer has accepted the order.")
        self.assertFalse(Review.objects.filter(product=self.product, reviewer=self.other_customer).exists())

    def test_product_detail_shows_review_form_only_for_eligible_customer(self):
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.PAID,
            subtotal=Decimal("10.00"),
            commission_total=Decimal("0.50"),
            total=Decimal("10.50"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=1,
            unit_price=self.product.price,
        )
        ProducerOrder.objects.create(
            parent_order=order,
            producer=self.producer,
            status=ProducerOrder.Status.ACCEPTED,
            subtotal=Decimal("2.50"),
        )

        self.client.force_login(self.customer)
        eligible_response = self.client.get(reverse("product_detail", args=[self.product.id]))
        self.assertContains(eligible_response, "Submit Review")

        self.client.force_login(self.other_customer)
        ineligible_response = self.client.get(reverse("product_detail", args=[self.product.id]))
        self.assertContains(ineligible_response, "You can review this product after you have paid and the producer has accepted the order.")
