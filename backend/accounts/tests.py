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
                "account_type": "individual",
                "phone": "07123456789",
                "address_line1": "1 Park Street",
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

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            reverse("register_customer"),
            {
                "username": "weakpass",
                "email": "weak@example.com",
                "account_type": "individual",
                "phone": "07123456789",
                "address_line1": "1 Test Road",
                "postcode": "BS1 5JG",
                "password1": "123",
                "password2": "123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="weakpass").exists())

    def test_community_group_registration_requires_organisation_name(self):
        response = self.client.post(
            reverse("register_customer"),
            {
                "username": "schoolgroup",
                "email": "school@example.com",
                "account_type": "community_group",
                "institutional_email": "school@example.com",
                "phone": "07123456789",
                "address_line1": "School Lane",
                "postcode": "BS1 5JG",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="schoolgroup").exists())

    def test_restaurant_registration_stores_account_type_fields(self):
        response = self.client.post(
            reverse("register_customer"),
            {
                "username": "restaurant1",
                "email": "orders@example.com",
                "account_type": "restaurant",
                "organisation_name": "The Clifton Kitchen",
                "institutional_email": "orders@example.com",
                "phone": "07123456789",
                "address_line1": "44 Clifton Road",
                "postcode": "BS6 5QA",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("customer_dashboard"))
        profile = CustomerProfile.objects.get(user__username="restaurant1")
        self.assertEqual(profile.account_type, CustomerProfile.AccountType.RESTAURANT)
        self.assertEqual(profile.organisation_name, "The Clifton Kitchen")

    def test_login_remember_me_controls_session_expiry(self):
        user = User.objects.create_user(
            username="rememberme",
            email="rememberme@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        CustomerProfile.objects.create(user=user, postcode="BS1 5JG")

        response = self.client.post(
            reverse("login"),
            {"username": "rememberme", "password": "StrongPass123!", "remember_me": "on"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertGreater(self.client.session.get_expiry_age(), 60 * 60 * 24)

        self.client.logout()
        response = self.client.post(
            reverse("login"),
            {"username": "rememberme", "password": "StrongPass123!"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get_expire_at_browser_close(), True)

    def test_login_lockout_after_repeated_failures(self):
        User.objects.create_user(
            username="lockeduser",
            email="locked@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )

        for _ in range(5):
            response = self.client.post(
                reverse("login"),
                {"username": "lockeduser", "password": "wrong-password"},
            )
            self.assertEqual(response.status_code, 200)

        blocked = self.client.post(
            reverse("login"),
            {"username": "lockeduser", "password": "StrongPass123!"},
        )

        self.assertContains(blocked, "Too many failed login attempts")
        self.assertFalse("_auth_user_id" in self.client.session)

    def test_login_lockout_only_applies_to_the_same_username(self):
        User.objects.create_user(
            username="lockeduser",
            email="locked@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )

        for _ in range(5):
            response = self.client.post(
                reverse("login"),
                {"username": "lockeduser", "password": "wrong-password"},
            )
            self.assertEqual(response.status_code, 200)

        blocked_same_user = self.client.post(
            reverse("login"),
            {"username": "lockeduser", "password": "StrongPass123!"},
        )
        self.assertContains(blocked_same_user, "Too many failed login attempts")

        other_user_response = self.client.post(
            reverse("login"),
            {"username": "otheruser", "password": "StrongPass123!"},
        )
        self.assertEqual(other_user_response.status_code, 302)
