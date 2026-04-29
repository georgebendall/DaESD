from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Category, Product


class ProductTests(TestCase):

    def setUp(self):
        self.customer = User.objects.create_user(
            username="cust",
            password="pass",
            role="customer"
        )
        self.customer.customer_profile.postcode = "BS1 5JG"
        self.customer.customer_profile.save()

        self.producer = User.objects.create_user(
            username="prod",
            password="pass",
            role="producer"
        )
        self.producer.producer_profile.postcode = "BS1 4DJ"
        self.producer.producer_profile.save()

        self.category = Category.objects.create(name="Vegetables")

        self.product = Product.objects.create(
            name="Carrots",
            producer=self.producer,
            category=self.category,
            price=2.50,
            stock=10,
        )

    def test_category_filter(self):
        response = self.client.get(
            reverse("product_list"),
            {"category": self.category.slug}
        )
        self.assertContains(response, "Carrots")

    def test_food_miles(self):
        self.client.login(username="cust", password="pass")
        response = self.client.get(reverse("product_detail", args=[self.product.id]))
        self.assertContains(response, "food miles")
