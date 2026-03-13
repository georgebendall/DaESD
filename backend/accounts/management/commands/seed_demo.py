# accounts/management/commands/seed_demo.py
# Run:
#   python manage.py seed_demo
#   python manage.py seed_demo --reset

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import User, CustomerProfile, ProducerProfile
from catalog.models import Category, Allergen, Product
from orders.models import Order, OrderItem, ProducerOrder
from payments.models import PaymentTransaction, WeeklySettlement

# Optional: only works if you created the Review model and migrated it
try:
    from reviews.models import Review
except Exception:
    Review = None


class Command(BaseCommand):
    help = "Create demo data: users, profiles, catalog, orders, payments, settlements (and optional reviews)."

    # Demo passwords (same for everyone so the team can login easily)
    ADMIN_PASSWORD = "AdminPass123!"
    PRODUCER_PASSWORD = "ProducerPass123!"
    CUSTOMER_PASSWORD = "CustomerPass123!"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously seeded demo data first.",
        )

    def handle(self, *args, **options):
        reset = options["reset"]

        # -------------------------
        # DEMO USERS
        # -------------------------
        admin_username = "admin1"
        customer_usernames = ["customer1", "customer2"]

        producer_specs = [
            {
                "username": "producer1",
                "email": "bristolvalley@example.com",
                "contact_first": "Sam",
                "contact_last": "Parker",
                "business_name": "Bristol Valley Farm",
                "phone": "07000 100001",
                "address": "12 Valley Road",
                "city": "Bristol",
                "postcode": "BS1 4AB",
                "products": [
                    ("Fresh Carrots", "Vegetables", Decimal("1.50"), 20, ["Nuts"]),
                    ("Seasonal Kale", "Vegetables", Decimal("1.80"), 18, []),
                    ("Cherry Tomatoes", "Vegetables", Decimal("2.40"), 14, []),
                ],
            },
            {
                "username": "producer2",
                "email": "avonorchards@example.com",
                "contact_first": "Aisha",
                "contact_last": "Khan",
                "business_name": "Avon Orchard Co.",
                "phone": "07000 100002",
                "address": "8 Orchard Lane",
                "city": "Bristol",
                "postcode": "BS4 2CD",
                "products": [
                    ("Apple Juice", "Drinks", Decimal("1.99"), 30, []),
                    ("Pear Juice", "Drinks", Decimal("2.10"), 22, []),
                    ("Fresh Apples (Bag)", "Vegetables", Decimal("2.80"), 16, []),
                ],
            },
            {
                "username": "producer3",
                "email": "cliftonbakery@example.com",
                "contact_first": "Luca",
                "contact_last": "Reed",
                "business_name": "Clifton Artisan Bakery",
                "phone": "07000 100003",
                "address": "22 Baker Street",
                "city": "Bristol",
                "postcode": "BS8 1EF",
                "products": [
                    ("Sourdough Bread", "Bakery", Decimal("3.20"), 12, ["Gluten"]),
                    ("Croissants (2 pack)", "Bakery", Decimal("2.90"), 10, ["Gluten", "Milk"]),
                    ("Brownies", "Bakery", Decimal("3.50"), 8, ["Gluten", "Eggs"]),
                ],
            },
            {
                "username": "producer4",
                "email": "harboursidedairy@example.com",
                "contact_first": "Maya",
                "contact_last": "Evans",
                "business_name": "Harbour Side Dairy",
                "phone": "07000 100004",
                "address": "5 Dockside Way",
                "city": "Bristol",
                "postcode": "BS1 6GH",
                "products": [
                    ("Organic Milk", "Dairy", Decimal("2.30"), 20, ["Milk"]),
                    ("Greek Yogurt", "Dairy", Decimal("1.60"), 18, ["Milk"]),
                    ("Mature Cheddar", "Dairy", Decimal("3.80"), 9, ["Milk"]),
                ],
            },
            {
                "username": "producer5",
                "email": "mendipmeats@example.com",
                "contact_first": "Noah",
                "contact_last": "Turner",
                "business_name": "Mendip Pasture Meats",
                "phone": "07000 100005",
                "address": "44 Farm Track",
                "city": "Bristol",
                "postcode": "BS16 1QY",
                "products": [
                    ("Chicken Thighs", "Meat", Decimal("4.50"), 10, []),
                    ("Beef Mince", "Meat", Decimal("5.20"), 12, []),
                    ("Pork Sausages", "Meat", Decimal("4.10"), 14, []),
                ],
            },
        ]

        producer_usernames = [p["username"] for p in producer_specs]
        demo_usernames = producer_usernames + customer_usernames + [admin_username]

        # -------------------------
        # RESET (safe for MongoDB)
        # -------------------------
        if reset:
            self.stdout.write("Reset requested. Deleting old demo data...")

            # If your branch has Cart/CartItem, delete these FIRST (prevents ProtectedError)
            try:
                from orders.models import Cart, CartItem  # type: ignore
                CartItem.objects.all().delete()
                Cart.objects.all().delete()
            except Exception:
                pass

            if Review is not None:
                Review.objects.all().delete()

            PaymentTransaction.objects.all().delete()
            WeeklySettlement.objects.all().delete()

            ProducerOrder.objects.all().delete()
            OrderItem.objects.all().delete()
            Order.objects.all().delete()

            # Clear catalog
            Product.objects.all().delete()
            Category.objects.all().delete()
            Allergen.objects.all().delete()

            # Delete demo profiles + demo users WITHOUT cross-collection join deletes
            demo_users_qs = User.objects.filter(username__in=demo_usernames)
            demo_user_ids = list(demo_users_qs.values_list("id", flat=True))

            CustomerProfile.objects.filter(user_id__in=demo_user_ids).delete()
            ProducerProfile.objects.filter(user_id__in=demo_user_ids).delete()
            demo_users_qs.delete()

            self.stdout.write("Reset completed.")

        # -------------------------
        # 1) ADMIN USER (FORCE PASSWORD)
        # -------------------------
        admin_user, _ = User.objects.get_or_create(
            username=admin_username,
            defaults={"email": "admin1@example.com"},
        )
        admin_user.email = "admin1@example.com"
        admin_user.role = User.Role.ADMIN
        admin_user.is_staff = True
        admin_user.is_superuser = False
        admin_user.is_active = True
        admin_user.set_password(self.ADMIN_PASSWORD)  # IMPORTANT: force known password
        admin_user.save()

        # -------------------------
        # 2) PRODUCERS + PROFILES (FORCE PASSWORD)
        # -------------------------
        producers: list[User] = []
        producer_product_map: dict[str, list[tuple]] = {}

        for spec in producer_specs:
            u, _ = User.objects.get_or_create(
                username=spec["username"],
                defaults={"email": spec["email"]},
            )

            u.email = spec["email"]
            u.role = User.Role.PRODUCER
            u.first_name = spec["contact_first"]
            u.last_name = spec["contact_last"]
            u.is_active = True
            u.set_password(self.PRODUCER_PASSWORD)  # IMPORTANT: force known password
            u.save()

            ProducerProfile.objects.update_or_create(
                user=u,
                defaults={
                    "business_name": spec["business_name"],
                    "contact_phone": spec["phone"],
                    "address_line1": spec["address"],
                    "city": spec["city"],
                    "postcode": spec["postcode"],
                    "is_approved": True,
                },
            )

            producers.append(u)
            producer_product_map[u.username] = spec["products"]

        # -------------------------
        # 3) CUSTOMERS + PROFILES (FORCE PASSWORD)
        # -------------------------
        customers: list[User] = []
        for i, uname in enumerate(customer_usernames, start=1):
            u, _ = User.objects.get_or_create(
                username=uname,
                defaults={"email": f"{uname}@example.com"},
            )

            u.email = f"{uname}@example.com"
            u.role = User.Role.CUSTOMER
            u.is_active = True
            u.set_password(self.CUSTOMER_PASSWORD)  # IMPORTANT: force known password
            u.save()

            CustomerProfile.objects.update_or_create(
                user=u,
                defaults={
                    "phone": f"07111 1111{i}",
                    "postcode": "BS16 1QY",
                },
            )
            customers.append(u)

        # -------------------------
        # 4) CATALOG (CATEGORIES + ALLERGENS)
        # -------------------------
        category_names = ["Vegetables", "Dairy", "Bakery", "Meat", "Drinks"]
        categories: dict[str, Category] = {}
        for name in category_names:
            c, _ = Category.objects.get_or_create(name=name, defaults={"slug": slugify(name)})
            categories[name] = c

        allergen_names = ["Milk", "Eggs", "Gluten", "Nuts"]
        allergens: dict[str, Allergen] = {}
        for name in allergen_names:
            a, _ = Allergen.objects.get_or_create(name=name)
            allergens[name] = a

        # -------------------------
        # 5) PRODUCTS (DIFFERENT PER PRODUCER)
        # -------------------------
        for p_user in producers:
            product_list = producer_product_map.get(p_user.username, [])
            for name, cat_name, price, stock, allergen_list in product_list:
                prod, _ = Product.objects.get_or_create(
                    producer=p_user,
                    slug=slugify(name),
                    defaults={
                        "category": categories[cat_name],
                        "name": name,
                        "description": f"Demo product: {name}",
                        "price": price,
                        "stock": stock,
                        "is_active": True,
                    },
                )

                prod.category = categories[cat_name]
                prod.name = name
                prod.price = price
                prod.stock = stock
                prod.is_active = True
                prod.save()

                prod.allergens.clear()
                for aname in allergen_list:
                    if aname in allergens:
                        prod.allergens.add(allergens[aname])

        # -------------------------
        # 6) ORDERS + ITEMS + PRODUCER SPLIT
        # -------------------------
        commission_rate = Decimal("0.10")

        p1_products = Product.objects.filter(producer=producers[0]).order_by("created_at")
        p2_products = Product.objects.filter(producer=producers[1]).order_by("created_at")

        o1 = Order.objects.create(customer=customers[0], status=Order.Status.PAID)
        OrderItem.objects.create(order=o1, product=p1_products.first(), quantity=2, unit_price=p1_products.first().price)
        OrderItem.objects.create(order=o1, product=p2_products.first(), quantity=1, unit_price=p2_products.first().price)

        o2 = Order.objects.create(customer=customers[1], status=Order.Status.PAID)
        second_p2 = p2_products.all()[1]
        OrderItem.objects.create(order=o2, product=second_p2, quantity=3, unit_price=second_p2.price)

        for order in [o1, o2]:
            by_producer: dict[User, Decimal] = {}
            for item in order.items.all():
                prod_user = item.product.producer
                by_producer.setdefault(prod_user, Decimal("0.00"))
                by_producer[prod_user] += item.line_total

            for prod_user, subtotal in by_producer.items():
                po, _ = ProducerOrder.objects.get_or_create(
                    parent_order=order,
                    producer=prod_user,
                    defaults={"subtotal": subtotal.quantize(Decimal("0.01"))},
                )
                po.subtotal = subtotal.quantize(Decimal("0.01"))
                po.save()

            order.recalculate_totals(commission_rate=commission_rate)
            order.save()

            PaymentTransaction.objects.create(
                order=order,
                status=PaymentTransaction.Status.SUCCEEDED,
                provider="manual",
                amount=order.total,
                currency="GBP",
                provider_reference=f"demo-{order.id}",
                raw_response={"demo": True},
            )

        # -------------------------
        # 7) WEEKLY SETTLEMENTS
        # -------------------------
        today = timezone.now().date()
        start = today - timedelta(days=7)
        end = today

        for prod_user in producers:
            gross = Decimal("0.00")
            for po in ProducerOrder.objects.filter(producer=prod_user):
                gross += po.subtotal

            gross = gross.quantize(Decimal("0.01"))
            commission = (gross * commission_rate).quantize(Decimal("0.01"))
            payout = (gross - commission).quantize(Decimal("0.01"))

            WeeklySettlement.objects.update_or_create(
                producer=prod_user,
                period_start=start,
                period_end=end,
                defaults={
                    "gross_sales": gross,
                    "commission_total": commission,
                    "payout_total": payout,
                    "status": WeeklySettlement.Status.DRAFT,
                },
            )

        # -------------------------
        # 8) OPTIONAL REVIEW
        # -------------------------
        if Review is not None:
            any_product = Product.objects.first()
            Review.objects.get_or_create(
                product=any_product,
                reviewer=customers[0],
                defaults={"rating": 5, "comment": "Great quality. Demo review."},
            )

        self.stdout.write(self.style.SUCCESS("Demo data created successfully."))
        self.stdout.write("Logins created (use USERNAME, not email):")
        self.stdout.write(f"  admin1 / {self.ADMIN_PASSWORD}")
        self.stdout.write(f"  producer1..producer5 / {self.PRODUCER_PASSWORD}")
        self.stdout.write(f"  customer1..customer2 / {self.CUSTOMER_PASSWORD}")