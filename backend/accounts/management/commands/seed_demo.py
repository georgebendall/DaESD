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
        customer_specs = [
            {
                "username": "customer1",
                "email": "customer1@example.com",
                "first_name": "Ella",
                "last_name": "Morgan",
                "phone": "07111 111101",
                "postcode": "BS3 2AA",
                "account_type": CustomerProfile.AccountType.INDIVIDUAL,
            },
            {
                "username": "customer2",
                "email": "customer2@example.com",
                "first_name": "Daniel",
                "last_name": "Rees",
                "phone": "07111 111102",
                "postcode": "BS6 5QA",
                "account_type": CustomerProfile.AccountType.INDIVIDUAL,
            },
            {
                "username": "st_marys_school",
                "email": "catering@stmarys-school.org.uk",
                "first_name": "St. Mary's",
                "last_name": "School",
                "phone": "07111 111103",
                "postcode": "BS3 4AB",
                "address_line1": "School Lane, Bristol",
                "organisation_name": "St. Mary's School",
                "institutional_email": "catering@stmarys-school.org.uk",
                "account_type": CustomerProfile.AccountType.COMMUNITY_GROUP,
            },
            {
                "username": "the_clifton_kitchen",
                "email": "orders@cliftonkitchen.co.uk",
                "first_name": "The Clifton",
                "last_name": "Kitchen",
                "phone": "07111 111104",
                "postcode": "BS8 2EF",
                "address_line1": "44 Clifton Road, Bristol",
                "organisation_name": "The Clifton Kitchen",
                "institutional_email": "orders@cliftonkitchen.co.uk",
                "account_type": CustomerProfile.AccountType.RESTAURANT,
            },
        ]
        customer_usernames = [c["username"] for c in customer_specs]

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
                    {
                        "name": "Bulk Potatoes",
                        "category": "Vegetables",
                        "price": Decimal("1.10"),
                        "stock": Decimal("150"),
                        "unit": Product.Unit.KG,
                        "description": "Bulk potatoes packed for school kitchens and catering orders.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": [],
                    },
                    {
                        "name": "Organic Carrots",
                        "category": "Vegetables",
                        "price": Decimal("1.50"),
                        "stock": Decimal("140"),
                        "unit": Product.Unit.KG,
                        "description": "Certified organic carrots grown in rich Bristol Valley soil.",
                        "is_organic": True,
                        "availability": Product.AvailabilityStatus.IN_SEASON,
                        "allergens": [],
                    },
                    {
                        "name": "Cherry Tomatoes",
                        "category": "Vegetables",
                        "price": Decimal("2.40"),
                        "stock": Decimal("18"),
                        "description": "Sweet greenhouse tomatoes, perfect for salads and sauces.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": [],
                    },
                    {
                        "name": "Organic Heritage Tomatoes",
                        "category": "Vegetables",
                        "price": Decimal("2.95"),
                        "stock": Decimal("14"),
                        "description": "Certified organic mixed tomatoes with deep seasonal flavour.",
                        "is_organic": True,
                        "availability": Product.AvailabilityStatus.IN_SEASON,
                        "allergens": [],
                    },
                    {
                        "name": "Seasonal Kale",
                        "category": "Vegetables",
                        "price": Decimal("1.80"),
                        "stock": Decimal("18"),
                        "description": "Leafy kale harvested fresh while in season.",
                        "is_organic": True,
                        "availability": Product.AvailabilityStatus.IN_SEASON,
                        "allergens": [],
                    },
                    {
                        "name": "Bunched Beetroot",
                        "category": "Vegetables",
                        "price": Decimal("1.90"),
                        "stock": Decimal("15"),
                        "description": "Earthy red beetroot from Bristol Valley Farm.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": [],
                    },
                    {
                        "name": "Organic Spinach",
                        "category": "Vegetables",
                        "price": Decimal("2.10"),
                        "stock": Decimal("16"),
                        "description": "Certified organic spinach leaves, washed and ready to cook.",
                        "is_organic": True,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": [],
                    },
                    {
                        "name": "Asparagus Spears",
                        "category": "Vegetables",
                        "price": Decimal("3.40"),
                        "stock": Decimal("12"),
                        "description": "Spring asparagus, currently out of season.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.OUT_OF_SEASON,
                        "allergens": [],
                    },
                ],
            },
            {
                "username": "producer2",
                "email": "hillsidedairy@example.com",
                "contact_first": "Aisha",
                "contact_last": "Khan",
                "business_name": "Hillside Dairy",
                "phone": "07000 100002",
                "address": "8 Hillside Lane",
                "city": "Bath",
                "postcode": "BA2 7HD",
                "products": [
                    {
                        "name": "Fresh Milk",
                        "category": "Dairy & Eggs",
                        "price": Decimal("1.80"),
                        "stock": Decimal("160"),
                        "unit": Product.Unit.L,
                        "description": "Fresh whole milk from Hillside Dairy.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": ["Milk"],
                    },
                    {
                        "name": "Organic Whole Milk",
                        "category": "Dairy & Eggs",
                        "price": Decimal("2.30"),
                        "stock": Decimal("20"),
                        "description": "Certified organic whole milk from pasture-fed cows.",
                        "is_organic": True,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": ["Milk"],
                    },
                    {
                        "name": "Free Range Eggs",
                        "category": "Dairy & Eggs",
                        "price": Decimal("2.90"),
                        "stock": Decimal("36"),
                        "description": "Free range eggs from local hens.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.IN_SEASON,
                        "allergens": ["Eggs"],
                    },
                    {
                        "name": "Greek Yogurt",
                        "category": "Dairy & Eggs",
                        "price": Decimal("1.60"),
                        "stock": Decimal("18"),
                        "description": "Thick cultured yogurt made with local milk.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": ["Milk"],
                    },
                    {
                        "name": "Mature Cheddar",
                        "category": "Dairy & Eggs",
                        "price": Decimal("3.80"),
                        "stock": Decimal("9"),
                        "description": "Aged farmhouse cheddar with a rich dairy flavour.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.UNAVAILABLE,
                        "allergens": ["Milk"],
                    },
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
                    {
                        "name": "Sourdough Bread",
                        "category": "Bakery",
                        "price": Decimal("3.20"),
                        "stock": Decimal("12"),
                        "description": "Slow-fermented sourdough loaf baked fresh each morning.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": ["Gluten"],
                    },
                    {
                        "name": "Organic Seeded Loaf",
                        "category": "Bakery",
                        "price": Decimal("3.60"),
                        "stock": Decimal("10"),
                        "description": "Certified organic seeded bread containing gluten.",
                        "is_organic": True,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": ["Gluten"],
                    },
                    {
                        "name": "Hazelnut Brownies",
                        "category": "Bakery",
                        "price": Decimal("3.50"),
                        "stock": Decimal("8"),
                        "description": "Chocolate brownies with roasted nuts and free range eggs.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.IN_SEASON,
                        "allergens": ["Gluten", "Eggs", "Nuts"],
                    },
                ],
            },
            {
                "username": "producer4",
                "email": "cliftonmarketgarden@example.com",
                "contact_first": "Maya",
                "contact_last": "Evans",
                "business_name": "Clifton Market Garden",
                "phone": "07000 100004",
                "address": "5 Orchard Way",
                "city": "Bristol",
                "postcode": "BS1 6GH",
                "products": [
                    {
                        "name": "Bulk Carrots",
                        "category": "Vegetables",
                        "price": Decimal("1.35"),
                        "stock": Decimal("130"),
                        "unit": Product.Unit.KG,
                        "description": "Bulk carrots prepared for catering and school meal service.",
                        "is_organic": True,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": [],
                    },
                    {
                        "name": "Lettuce",
                        "category": "Vegetables",
                        "price": Decimal("1.40"),
                        "stock": Decimal("80"),
                        "unit": Product.Unit.HEAD,
                        "description": "Crisp lettuce heads packed fresh for quick-turnaround orders.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.IN_SEASON,
                        "allergens": [],
                        "is_surplus": True,
                        "surplus_discount_percent": 30,
                        "surplus_expires_at": timezone.now() + timedelta(days=2),
                        "surplus_note": "Perfect condition, must sell quickly",
                        "best_before_date": timezone.localdate() + timedelta(days=4),
                    },
                    {
                        "name": "Little Gem Lettuce",
                        "category": "Vegetables",
                        "price": Decimal("1.10"),
                        "stock": Decimal("60"),
                        "unit": Product.Unit.HEAD,
                        "description": "Small lettuce heads for local kitchens.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.IN_SEASON,
                        "allergens": [],
                    },
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
                    {
                        "name": "Chicken Thighs",
                        "category": "Meat",
                        "price": Decimal("4.50"),
                        "stock": Decimal("10"),
                        "description": "Free range chicken thighs from Mendip Pasture Meats.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": [],
                    },
                    {
                        "name": "Beef Mince",
                        "category": "Meat",
                        "price": Decimal("5.20"),
                        "stock": Decimal("12"),
                        "description": "Lean beef mince, packed fresh for local restaurants.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.YEAR_ROUND,
                        "allergens": [],
                    },
                    {
                        "name": "Pork Sausages",
                        "category": "Meat",
                        "price": Decimal("4.10"),
                        "stock": Decimal("14"),
                        "description": "Traditional pork sausages.",
                        "is_organic": False,
                        "availability": Product.AvailabilityStatus.IN_SEASON,
                        "allergens": ["Gluten"],
                    },
                ],
            },
        ]

        producer_usernames = [p["username"] for p in producer_specs]
        demo_usernames = producer_usernames + customer_usernames + [admin_username]

        # -------------------------
        # RESET (safe for rerunning against PostgreSQL)
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
        for spec in customer_specs:
            u, _ = User.objects.get_or_create(
                username=spec["username"],
                defaults={"email": spec["email"]},
            )

            u.email = spec["email"]
            u.role = User.Role.CUSTOMER
            u.first_name = spec["first_name"]
            u.last_name = spec["last_name"]
            u.is_active = True
            u.set_password(self.CUSTOMER_PASSWORD)  # IMPORTANT: force known password
            u.save()

            CustomerProfile.objects.update_or_create(
                user=u,
                defaults={
                    "phone": spec["phone"],
                    "postcode": spec["postcode"],
                    "address_line1": spec.get("address_line1", ""),
                    "organisation_name": spec.get("organisation_name", ""),
                    "institutional_email": spec.get("institutional_email", ""),
                    "account_type": spec.get("account_type", CustomerProfile.AccountType.INDIVIDUAL),
                },
            )
            customers.append(u)

        # -------------------------
        # 4) CATALOG (CATEGORIES + ALLERGENS)
        # -------------------------
        category_names = ["Vegetables", "Dairy & Eggs", "Bakery", "Meat", "Drinks"]
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
            for item in product_list:
                slug = slugify(item["name"])
                prod, _ = Product.objects.get_or_create(
                    producer=p_user,
                    slug=slug,
                    defaults={
                        "category": categories[item["category"]],
                        "name": item["name"],
                        "description": item["description"],
                        "price": item["price"],
                        "stock": item["stock"],
                        "unit": item.get("unit", Product.Unit.EACH),
                        "is_organic": item["is_organic"],
                        "availability_status": item["availability"],
                        "is_surplus": item.get("is_surplus", False),
                        "surplus_discount_percent": item.get("surplus_discount_percent", 0),
                        "surplus_expires_at": item.get("surplus_expires_at"),
                        "surplus_note": item.get("surplus_note", ""),
                        "best_before_date": item.get("best_before_date"),
                    },
                )

                prod.category = categories[item["category"]]
                prod.name = item["name"]
                prod.description = item["description"]
                prod.price = item["price"]
                prod.stock = item["stock"]
                prod.unit = item.get("unit", Product.Unit.EACH)
                prod.is_organic = item["is_organic"]
                prod.availability_status = item["availability"]
                prod.is_surplus = item.get("is_surplus", False)
                prod.surplus_discount_percent = item.get("surplus_discount_percent", 0)
                prod.surplus_expires_at = item.get("surplus_expires_at")
                prod.surplus_note = item.get("surplus_note", "")
                prod.best_before_date = item.get("best_before_date")
                prod.save()

                prod.allergens.clear()
                for aname in item["allergens"]:
                    if aname in allergens:
                        prod.allergens.add(allergens[aname])

        # -------------------------
        # 6) ORDERS + ITEMS + PRODUCER SPLIT
        # -------------------------
        commission_rate = Decimal("0.10")

        demo_order_ids = list(
            PaymentTransaction.objects.filter(provider_reference__startswith="demo-")
            .values_list("order_id", flat=True)
        )
        if demo_order_ids:
            PaymentTransaction.objects.filter(order_id__in=demo_order_ids).delete()
            ProducerOrder.objects.filter(parent_order_id__in=demo_order_ids).delete()
            OrderItem.objects.filter(order_id__in=demo_order_ids).delete()
            Order.objects.filter(id__in=demo_order_ids).delete()

        p1_products = Product.objects.filter(producer=producers[0], is_active=True).order_by("created_at")
        p2_products = Product.objects.filter(producer=producers[1], is_active=True).order_by("created_at")

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
