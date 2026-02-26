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

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously seeded demo data first.",
        )

    def handle(self, *args, **options):
        reset = options["reset"]

        # Fixed usernames so your team has predictable logins.
        producer_usernames = ["producer1", "producer2"]
        customer_usernames = ["customer1", "customer2"]
        admin_username = "admin1"

        demo_usernames = producer_usernames + customer_usernames + [admin_username]

        # -------------------------
        # RESET (safe for MongoDB)
        # -------------------------
        if reset:
            self.stdout.write("Reset requested. Deleting old demo data...")

            # Delete app data first (no cross-collection filters)
            # (Deleting all is simplest and avoids MongoDB join-delete limitations.)
            if Review is not None:
                Review.objects.all().delete()

            PaymentTransaction.objects.all().delete()
            WeeklySettlement.objects.all().delete()

            ProducerOrder.objects.all().delete()
            OrderItem.objects.all().delete()
            Order.objects.all().delete()

            Product.objects.all().delete()
            Category.objects.all().delete()
            Allergen.objects.all().delete()

            # Now delete demo profiles + demo users WITHOUT user__username joins
            demo_users_qs = User.objects.filter(username__in=demo_usernames)
            demo_user_ids = list(demo_users_qs.values_list("id", flat=True))

            # Use user_id (stored ObjectId) so we don't query across collections
            CustomerProfile.objects.filter(user_id__in=demo_user_ids).delete()
            ProducerProfile.objects.filter(user_id__in=demo_user_ids).delete()

            demo_users_qs.delete()

            self.stdout.write("Reset completed.")

        # -------------------------
        # 1) USERS
        # -------------------------
        admin_user, _ = User.objects.get_or_create(
            username=admin_username,
            defaults={
                "email": "admin1@example.com",
                "role": User.Role.ADMIN,
                "is_staff": True,   # allows access to your custom admin dashboard rule
                "is_superuser": False,
            },
        )
        # Always ensure password exists
        if not admin_user.has_usable_password():
            admin_user.set_password("AdminPass123!")
            admin_user.save()

        producers: list[User] = []
        for i, uname in enumerate(producer_usernames, start=1):
            u, _ = User.objects.get_or_create(
                username=uname,
                defaults={
                    "email": f"{uname}@example.com",
                    "role": User.Role.PRODUCER,
                },
            )
            if not u.has_usable_password():
                u.set_password("ProducerPass123!")
                u.save()

            ProducerProfile.objects.get_or_create(
                user=u,
                defaults={
                    "business_name": f"Farm {i}",
                    "contact_phone": f"07000 0000{i}",
                    "city": "Bristol",
                    "postcode": "BS16 1QY",
                    "is_approved": True,
                },
            )
            producers.append(u)

        customers: list[User] = []
        for i, uname in enumerate(customer_usernames, start=1):
            u, _ = User.objects.get_or_create(
                username=uname,
                defaults={
                    "email": f"{uname}@example.com",
                    "role": User.Role.CUSTOMER,
                },
            )
            if not u.has_usable_password():
                u.set_password("CustomerPass123!")
                u.save()

            CustomerProfile.objects.get_or_create(
                user=u,
                defaults={
                    "phone": f"07111 1111{i}",
                    "postcode": "BS16 1QY",
                },
            )
            customers.append(u)

        # -------------------------
        # 2) CATALOG
        # -------------------------
        category_names = ["Vegetables", "Dairy", "Bakery", "Meat", "Drinks"]
        categories: dict[str, Category] = {}
        for name in category_names:
            c, _ = Category.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name)},
            )
            categories[name] = c

        allergen_names = ["Milk", "Eggs", "Gluten", "Nuts"]
        allergens: dict[str, Allergen] = {}
        for name in allergen_names:
            a, _ = Allergen.objects.get_or_create(name=name)
            allergens[name] = a

        product_templates = [
            ("Fresh Carrots", "Vegetables", Decimal("1.50"), 20, ["Nuts"]),
            ("Organic Milk", "Dairy", Decimal("2.30"), 15, ["Milk"]),
            ("Sourdough Bread", "Bakery", Decimal("3.20"), 10, ["Gluten"]),
            ("Free-range Eggs", "Dairy", Decimal("2.80"), 25, ["Eggs"]),
            ("Apple Juice", "Drinks", Decimal("1.99"), 18, []),
        ]

        for p_user in producers:
            for name, cat_name, price, stock, allergen_list in product_templates:
                prod, _ = Product.objects.get_or_create(
                    producer=p_user,
                    slug=slugify(name),  # unique per producer by your constraint
                    defaults={
                        "category": categories[cat_name],
                        "name": name,
                        "description": f"Demo product: {name}",
                        "price": price,
                        "stock": stock,
                        "is_active": True,
                    },
                )

                # keep demo data consistent if it already existed
                prod.category = categories[cat_name]
                prod.name = name
                prod.price = price
                prod.stock = stock
                prod.is_active = True
                prod.save()

                prod.allergens.clear()
                for aname in allergen_list:
                    prod.allergens.add(allergens[aname])

        # -------------------------
        # 3) ORDERS + ITEMS + PRODUCER SPLIT
        # -------------------------
        p1_products = Product.objects.filter(producer=producers[0]).order_by("created_at")
        p2_products = Product.objects.filter(producer=producers[1]).order_by("created_at")

        commission_rate = Decimal("0.10")

        # Order 1: customer1 buys from both producers
        o1 = Order.objects.create(customer=customers[0], status=Order.Status.PAID)
        OrderItem.objects.create(order=o1, product=p1_products.first(), quantity=2, unit_price=p1_products.first().price)
        OrderItem.objects.create(order=o1, product=p2_products.first(), quantity=1, unit_price=p2_products.first().price)

        # Order 2: customer2 buys from producer2 only
        o2 = Order.objects.create(customer=customers[1], status=Order.Status.PAID)
        second_p2 = p2_products.all()[1]
        OrderItem.objects.create(order=o2, product=second_p2, quantity=3, unit_price=second_p2.price)

        for order in [o1, o2]:
            # Create ProducerOrders grouped by product.producer
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

            # Totals on order
            order.recalculate_totals(commission_rate=commission_rate)
            order.save()

            # Payment record
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
        # 4) WEEKLY SETTLEMENTS
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
        # 5) OPTIONAL REVIEW
        # -------------------------
        if Review is not None:
            any_product = Product.objects.first()
            Review.objects.get_or_create(
                product=any_product,
                reviewer=customers[0],
                defaults={"rating": 5, "comment": "Great quality. Demo review."},
            )

        self.stdout.write(self.style.SUCCESS("Demo data created successfully."))
        self.stdout.write("Logins created:")
        self.stdout.write("  admin1 / AdminPass123!")
        self.stdout.write("  producer1 / ProducerPass123!")
        self.stdout.write("  producer2 / ProducerPass123!")
        self.stdout.write("  customer1 / CustomerPass123!")
        self.stdout.write("  customer2 / CustomerPass123!")