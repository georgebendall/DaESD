from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomerProfile, ProducerProfile, User
from catalog.models import Category, Product
from payments.models import PaymentTransaction

from .models import Cart, CartItem, Order, OrderItem, ProducerOrder, RecurringOrder


def _future_date(days=5):
    return timezone.localdate() + timezone.timedelta(days=days)


class OrderHistoryTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="ordercustomer",
            email="ordercustomer@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        CustomerProfile.objects.create(
            user=self.customer,
            postcode="BS1 5JG",
            phone="07123456789",
        )
        self.producer = User.objects.create_user(
            username="orderproducer",
            email="orderproducer@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(
            user=self.producer,
            business_name="Order Producer",
            postcode="BS1 4DJ",
        )
        category = Category.objects.create(name="Vegetables")
        self.product = Product.objects.create(
            producer=self.producer,
            category=category,
            name="Organic Carrots",
            price=Decimal("2.50"),
            stock=20,
        )

        self.order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.PAID,
            subtotal=Decimal("5.00"),
            commission_total=Decimal("0.25"),
            total=Decimal("5.25"),
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            unit_price=Decimal("2.50"),
        )
        PaymentTransaction.objects.create(
            order=self.order,
            amount=Decimal("5.25"),
            status=PaymentTransaction.Status.SUCCEEDED,
            provider="manual",
            currency="GBP",
            provider_reference="txn-123456789",
        )

    def test_order_detail_shows_delivery_and_masked_payment_info(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("order_detail", args=[self.order.id]))

        self.assertContains(response, "Delivery postcode")
        self.assertContains(response, "BS1 5JG")
        self.assertContains(response, "Contact phone")
        self.assertContains(response, "07123456789")
        self.assertContains(response, "Payment information")
        self.assertContains(response, "*****6789")
        self.assertNotContains(response, "txn-123456789")


class BusinessOrderFlowsTests(TestCase):
    def setUp(self):
        self.community_user = User.objects.create_user(
            username="schoolgroup",
            email="catering@stmarys-school.org.uk",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        CustomerProfile.objects.create(
            user=self.community_user,
            account_type=CustomerProfile.AccountType.COMMUNITY_GROUP,
            organisation_name="St. Mary's School",
            institutional_email="catering@stmarys-school.org.uk",
            address_line1="School Lane",
            postcode="BS3 2AA",
        )
        self.restaurant_user = User.objects.create_user(
            username="cliftonkitchen",
            email="orders@cliftonkitchen.co.uk",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        CustomerProfile.objects.create(
            user=self.restaurant_user,
            account_type=CustomerProfile.AccountType.RESTAURANT,
            organisation_name="The Clifton Kitchen",
            institutional_email="orders@cliftonkitchen.co.uk",
            address_line1="44 Clifton Road",
            postcode="BS6 5QA",
        )

        veg = Category.objects.create(name="Vegetables")
        dairy = Category.objects.create(name="Dairy")
        bakery = Category.objects.create(name="Bakery")

        self.producer1 = User.objects.create_user(
            username="farm1",
            email="farm1@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(user=self.producer1, business_name="Farm One", postcode="BS1 4DJ")
        self.producer2 = User.objects.create_user(
            username="farm2",
            email="farm2@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(user=self.producer2, business_name="Farm Two", postcode="BA2 7HD")
        self.producer3 = User.objects.create_user(
            username="farm3",
            email="farm3@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(user=self.producer3, business_name="Farm Three", postcode="BS8 1EF")

        self.potatoes = Product.objects.create(
            producer=self.producer1,
            category=veg,
            name="Potatoes",
            price=Decimal("1.20"),
            stock=100,
            unit=Product.Unit.KG,
        )
        self.milk = Product.objects.create(
            producer=self.producer2,
            category=dairy,
            name="Milk",
            price=Decimal("1.80"),
            stock=80,
            unit=Product.Unit.L,
        )
        self.carrots = Product.objects.create(
            producer=self.producer3,
            category=veg,
            name="Carrots",
            price=Decimal("2.50"),
            stock=140,
            unit=Product.Unit.KG,
        )
        self.surplus_lettuce = Product.objects.create(
            producer=self.producer3,
            category=veg,
            name="Lettuce",
            price=Decimal("3.00"),
            stock=50,
            unit=Product.Unit.HEAD,
            is_surplus=True,
            surplus_discount_percent=30,
            surplus_expires_at=timezone.now() + timezone.timedelta(days=2),
            surplus_note="Perfect condition, must sell quickly",
        )

    def test_community_group_bulk_checkout_creates_multivendor_order(self):
        cart = Cart.objects.create(customer=self.community_user)
        CartItem.objects.create(cart=cart, product=self.potatoes, quantity=50)
        CartItem.objects.create(cart=cart, product=self.milk, quantity=30)
        CartItem.objects.create(cart=cart, product=self.carrots, quantity=20)

        self.client.force_login(self.community_user)
        review = self.client.get(reverse("checkout_now"))
        self.assertContains(review, "Farm One")
        self.assertContains(review, "Farm Two")
        self.assertContains(review, "Farm Three")
        self.assertContains(review, "50 kg")
        self.assertContains(review, "30 litres")
        self.assertContains(review, "20 kg")
        self.assertContains(review, "Network commission (5%)")

        response = self.client.post(
            reverse("checkout_now"),
            {
                "delivery_address": "St. Mary's School\nSchool Lane\nBS3 2AA",
                "delivery_date": (_future_date(5)).isoformat(),
                "special_instructions": "Delivery to kitchen entrance, contact kitchen manager",
            },
        )

        self.assertEqual(response.status_code, 302)
        order = Order.objects.latest("id")
        self.assertEqual(order.delivery_address, "St. Mary's School\nSchool Lane\nBS3 2AA")
        self.assertEqual(order.special_instructions, "Delivery to kitchen entrance, contact kitchen manager")
        self.assertEqual(order.producer_orders.count(), 3)
        detail = self.client.get(reverse("order_detail", args=[order.id]))
        self.assertContains(detail, "Farm One")
        self.assertContains(detail, "Farm Two")
        self.assertContains(detail, "Farm Three")

    def test_restaurant_checkout_can_create_recurring_order_template(self):
        cart = Cart.objects.create(customer=self.restaurant_user)
        CartItem.objects.create(cart=cart, product=self.potatoes, quantity=10)
        CartItem.objects.create(cart=cart, product=self.milk, quantity=5)

        self.client.force_login(self.restaurant_user)
        response = self.client.post(
            reverse("checkout_now"),
            {
                "delivery_address": "44 Clifton Road\nBS6 5QA",
                "delivery_date": (_future_date(5)).isoformat(),
                "make_recurring": "on",
                "recurring_name": "Weekly Ingredients",
                "recurrence": "weekly",
                "order_day": "monday",
                "delivery_day": "wednesday",
            },
        )

        self.assertEqual(response.status_code, 302)
        recurring = RecurringOrder.objects.get(customer=self.restaurant_user)
        self.assertEqual(recurring.name, "Weekly Ingredients")
        self.assertEqual(recurring.items.count(), 2)
        self.assertIsNotNone(recurring.next_delivery_date)
        recurring_page = self.client.get(reverse("recurring_orders"))
        self.assertContains(recurring_page, "Weekly Ingredients")
        self.assertContains(recurring_page, "Active")

    def test_checkout_rejects_delivery_date_inside_48_hour_lead_time(self):
        cart = Cart.objects.create(customer=self.community_user)
        CartItem.objects.create(cart=cart, product=self.potatoes, quantity=5)

        self.client.force_login(self.community_user)
        response = self.client.post(
            reverse("checkout_now"),
            {
                "delivery_address": "St. Mary's School\nSchool Lane\nBS3 2AA",
                "delivery_date": timezone.localdate().isoformat(),
                "special_instructions": "",
            },
            follow=True,
        )

        self.assertContains(response, "Please choose a delivery date at least 48 hours from today.")
        self.assertEqual(Order.objects.count(), 0)

    def test_recurring_order_can_be_loaded_into_cart_without_changing_template(self):
        recurring = RecurringOrder.objects.create(
            customer=self.restaurant_user,
            name="Weekly Ingredients",
            recurrence="weekly",
            order_day="monday",
            delivery_day="wednesday",
        )
        recurring.schedule_next_delivery()
        recurring.save()
        recurring.items.create(product=self.potatoes, quantity=8)

        self.client.force_login(self.restaurant_user)
        response = self.client.post(reverse("recurring_order_load_to_cart", args=[recurring.id]))

        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(customer=self.restaurant_user)
        self.assertEqual(cart.items.get(product=self.potatoes).quantity, 8)
        self.assertEqual(recurring.items.get(product=self.potatoes).quantity, 8)

    def test_recurring_order_can_be_edited_paused_and_cancelled(self):
        recurring = RecurringOrder.objects.create(
            customer=self.restaurant_user,
            name="Weekly Ingredients",
            recurrence="weekly",
            order_day="monday",
            delivery_day="wednesday",
        )
        recurring.schedule_next_delivery()
        recurring.save()

        self.client.force_login(self.restaurant_user)
        edit_response = self.client.post(
            reverse("recurring_order_edit", args=[recurring.id]),
            {
                "name": "Fortnightly Kitchen Order",
                "recurrence": "fortnightly",
                "order_day": "tuesday",
                "delivery_day": "thursday",
            },
        )
        self.assertEqual(edit_response.status_code, 302)
        recurring.refresh_from_db()
        self.assertEqual(recurring.name, "Fortnightly Kitchen Order")
        self.assertEqual(recurring.recurrence, "fortnightly")

        self.client.post(reverse("recurring_order_toggle", args=[recurring.id]), {"action": "pause"})
        recurring.refresh_from_db()
        self.assertEqual(recurring.status, RecurringOrder.Status.PAUSED)

        self.client.post(reverse("recurring_order_toggle", args=[recurring.id]), {"action": "cancel"})
        recurring.refresh_from_db()
        self.assertEqual(recurring.status, RecurringOrder.Status.CANCELLED)

    def test_producer_can_accept_and_decline_sub_orders(self):
        order = Order.objects.create(
            customer=self.community_user,
            status=Order.Status.PENDING,
            delivery_date=_future_date(5),
        )
        OrderItem.objects.create(order=order, product=self.potatoes, quantity=4, unit_price=self.potatoes.price)
        producer_order = ProducerOrder.objects.create(
            parent_order=order,
            producer=self.producer1,
            status=ProducerOrder.Status.PENDING,
        )
        producer_order.recalculate_subtotal()
        producer_order.save()

        self.client.force_login(self.producer1)
        orders_page = self.client.get(reverse("producer_orders"))
        self.assertContains(orders_page, "Accept")
        self.assertContains(orders_page, "Decline")

        accept_response = self.client.post(
            reverse("update_producer_order_status", args=[producer_order.id]),
            {"status": "accepted"},
            follow=True,
        )
        self.assertContains(accept_response, "has been accepted")
        producer_order.refresh_from_db()
        self.assertEqual(producer_order.status, ProducerOrder.Status.ACCEPTED)

        producer_order.status = ProducerOrder.Status.PENDING
        producer_order.save()
        decline_response = self.client.post(
            reverse("update_producer_order_status", args=[producer_order.id]),
            {"status": "cancelled"},
            follow=True,
        )
        self.assertContains(decline_response, "has been declined")
        producer_order.refresh_from_db()
        self.assertEqual(producer_order.status, ProducerOrder.Status.CANCELLED)

    def test_bulk_cart_groups_items_by_producer_and_shows_names(self):
        cart = Cart.objects.create(customer=self.community_user)
        CartItem.objects.create(cart=cart, product=self.potatoes, quantity=50)
        CartItem.objects.create(cart=cart, product=self.milk, quantity=30)
        CartItem.objects.create(cart=cart, product=self.carrots, quantity=20)

        self.client.force_login(self.community_user)
        response = self.client.get(reverse("cart_page"))

        self.assertContains(response, "Farm One")
        self.assertContains(response, "Farm Two")
        self.assertContains(response, "Farm Three")
        self.assertContains(response, "50 kg")
        self.assertContains(response, "30 litres")
        self.assertContains(response, "20 kg")

    def test_cart_add_rejects_quantity_above_stock_with_left_in_stock_message(self):
        self.client.force_login(self.community_user)
        response = self.client.post(
            reverse("cart_add", args=[self.potatoes.id]),
            {"quantity": "150", "next": reverse("product_list")},
            follow=True,
        )

        self.assertContains(response, "The quantity requested is not available. Only 100 left in stock for Farm One.")

    def test_surplus_discounted_price_is_used_in_cart(self):
        cart = Cart.objects.create(customer=self.restaurant_user)
        CartItem.objects.create(cart=cart, product=self.surplus_lettuce, quantity=2)

        self.client.force_login(self.restaurant_user)
        response = self.client.get(reverse("cart_page"))

        self.assertContains(response, "£2.10")
        self.assertContains(response, "Lettuce")

    def test_payment_page_marks_order_paid_and_records_transaction(self):
        order = Order.objects.create(
            customer=self.community_user,
            status=Order.Status.PENDING,
            subtotal=Decimal("20.00"),
            commission_total=Decimal("1.00"),
            total=Decimal("21.00"),
            delivery_date=_future_date(5),
        )

        self.client.force_login(self.community_user)
        response = self.client.post(reverse("payment_page", args=[order.id]), follow=True)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertTrue(PaymentTransaction.objects.filter(order=order, amount=Decimal("21.00")).exists())
        self.assertContains(response, "Payment completed successfully.")
