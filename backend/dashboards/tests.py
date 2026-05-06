import shutil
import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import CustomerProfile, ProducerProfile, User
from catalog.models import Category, Product
from orders.models import Order, OrderItem


TEST_MEDIA_ROOT = tempfile.mkdtemp()


TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DashboardExperienceTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(
            username="customerdash",
            email="customerdash@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        CustomerProfile.objects.create(user=cls.customer, postcode="BS1 5JG")

        cls.producer = User.objects.create_user(
            username="producerdash",
            email="producerdash@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(
            user=cls.producer,
            business_name="Producer Dash Farm",
            postcode="BS1 4ST",
        )
        cls.category = Category.objects.create(name="Vegetables", slug="vegetables")

    def test_my_orders_page_is_orders_focused(self):
        self.client.force_login(self.customer)

        response = self.client.get(reverse("my_orders"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Orders")
        self.assertNotContains(response, "Products available")
        self.assertContains(response, "Open orders")
        self.assertContains(response, "Completed orders")

    def test_producer_can_upload_product_image(self):
        self.client.force_login(self.producer)
        upload = SimpleUploadedFile("carrots.gif", TINY_GIF, content_type="image/gif")

        response = self.client.post(
            reverse("add_product"),
            {
                "name": "Rainbow Carrots",
                "category": self.category.id,
                "description": "Bright bunches of carrots",
                "image": upload,
                "unit": Product.Unit.KG,
                "price": "3.50",
                "stock": "20",
                "availability_status": Product.AvailabilityStatus.YEAR_ROUND,
                "stock_warning_level": "5",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        product = Product.objects.get(name="Rainbow Carrots")
        self.assertTrue(product.image.name.startswith("products/"))

    def test_delete_product_with_order_history_archives_instead_of_crashing(self):
        self.client.force_login(self.producer)
        product = Product.objects.create(
            producer=self.producer,
            category=self.category,
            name="Asparagus Spears",
            price=Decimal("3.40"),
            stock=Decimal("25"),
            availability_status=Product.AvailabilityStatus.IN_SEASON,
            is_active=True,
        )
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.PAID,
            subtotal=Decimal("10.20"),
            commission_total=Decimal("0.51"),
            total=Decimal("10.71"),
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=3,
            unit_price=Decimal("3.40"),
        )

        response = self.client.post(reverse("delete_product", args=[product.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertFalse(product.is_active)
        self.assertEqual(product.availability_status, Product.AvailabilityStatus.UNAVAILABLE)
