from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Product
from .models import CustomerProfile, ProducerProfile, User


class RoleAuthenticationTests(TestCase):
    def test_customer_signup_creates_non_admin_customer(self):
        response = self.client.post(
            reverse("register_customer"),
            {
                "username": "customer1",
                "email": "customer1@example.com",
                "phone": "07123456789",
                "postcode": "AB1 2CD",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("customer_dashboard"))
        user = User.objects.get(username="customer1")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())

    def test_producer_signup_creates_non_admin_producer(self):
        response = self.client.post(
            reverse("register_producer"),
            {
                "username": "producer1",
                "email": "producer1@example.com",
                "business_name": "Producer One",
                "contact_phone": "07123456789",
                "address_line1": "1 Farm Lane",
                "city": "Bath",
                "postcode": "BA1 1AA",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("producer_dashboard"))
        user = User.objects.get(username="producer1")
        self.assertEqual(user.role, User.Role.PRODUCER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(ProducerProfile.objects.filter(user=user).exists())

    def test_createsuperuser_style_user_is_admin_and_redirected(self):
        admin = User.objects.create_superuser(
            username="admin1",
            email="admin1@example.com",
            password="StrongPass123!",
        )

        self.assertEqual(admin.role, User.Role.ADMIN)
        self.client.login(username="admin1", password="StrongPass123!")
        response = self.client.get(reverse("after_login"))

        self.assertRedirects(response, reverse("admin_dashboard"))

    def test_role_login_redirects(self):
        customer = User.objects.create_user(
            username="customer2",
            email="customer2@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        CustomerProfile.objects.create(user=customer)
        producer = User.objects.create_user(
            username="producer2",
            email="producer2@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(user=producer, business_name="Producer Two", postcode="BA2 2BB")

        self.client.login(username="customer2", password="StrongPass123!")
        self.assertRedirects(self.client.get(reverse("after_login")), reverse("customer_dashboard"))

        self.client.logout()
        self.client.login(username="producer2", password="StrongPass123!")
        self.assertRedirects(self.client.get(reverse("after_login")), reverse("producer_dashboard"))

    def test_wrong_dashboard_access_is_blocked(self):
        customer = User.objects.create_user(
            username="customer3",
            email="customer3@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        CustomerProfile.objects.create(user=customer)
        producer = User.objects.create_user(
            username="producer3",
            email="producer3@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(user=producer, business_name="Producer Three", postcode="BA3 3BB")

        self.client.login(username="customer3", password="StrongPass123!")
        self.assertRedirects(
            self.client.get(reverse("producer_dashboard")),
            reverse("after_login"),
            fetch_redirect_response=False,
        )

        self.client.logout()
        self.client.login(username="producer3", password="StrongPass123!")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_producer_cannot_manage_another_producers_product(self):
        owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(user=owner, business_name="Owner Farm", postcode="BA4 4BB")
        other = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(user=other, business_name="Other Farm", postcode="BA5 5BB")
        category = Category.objects.create(name="Dairy")
        product = Product.objects.create(
            producer=owner,
            category=category,
            name="Milk",
            price=2.50,
            stock=10,
        )

        self.client.login(username="other", password="StrongPass123!")
        edit_response = self.client.get(reverse("edit_product", args=[product.id]))
        delete_response = self.client.post(reverse("delete_product", args=[product.id]))

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
