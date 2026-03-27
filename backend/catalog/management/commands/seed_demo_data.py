from django.core.management.base import BaseCommand
from django.utils.text import slugify

from accounts.models import ProducerProfile, User
from catalog.models import Allergen, Category, Product


class Command(BaseCommand):
    help = "Seed demo categories, allergens, producers, and products"

    def handle(self, *args, **options):
        dairy, _ = Category.objects.get_or_create(name="Dairy", defaults={"slug": "dairy"})
        fruit, _ = Category.objects.get_or_create(name="Fruit", defaults={"slug": "fruit"})
        veg, _ = Category.objects.get_or_create(name="Vegetables", defaults={"slug": "vegetables"})
        bakery, _ = Category.objects.get_or_create(name="Bakery", defaults={"slug": "bakery"})

        milk_allergen, _ = Allergen.objects.get_or_create(name="Milk")
        egg_allergen, _ = Allergen.objects.get_or_create(name="Eggs")
        gluten_allergen, _ = Allergen.objects.get_or_create(name="Gluten")
        nuts_allergen, _ = Allergen.objects.get_or_create(name="Nuts")

        producer1, created = User.objects.get_or_create(
            username="greenfarm",
            defaults={
                "email": "greenfarm@example.com",
                "role": User.Role.PRODUCER,
            },
        )
        if created:
            producer1.set_password("Password123!")
            producer1.save()

        ProducerProfile.objects.get_or_create(
            user=producer1,
            defaults={
                "business_name": "Green Farm",
                "contact_phone": "07111111111",
                "address_line1": "12 Farm Lane",
                "city": "Bristol",
                "postcode": "BS1 1AA",
                "is_approved": True,
            },
        )

        producer2, created = User.objects.get_or_create(
            username="sunnybakery",
            defaults={
                "email": "sunnybakery@example.com",
                "role": User.Role.PRODUCER,
            },
        )
        if created:
            producer2.set_password("Password123!")
            producer2.save()

        ProducerProfile.objects.get_or_create(
            user=producer2,
            defaults={
                "business_name": "Sunny Bakery",
                "contact_phone": "07222222222",
                "address_line1": "44 Bread Street",
                "city": "Bath",
                "postcode": "BA1 2BB",
                "is_approved": True,
            },
        )

        demo_products = [
            {
                "producer": producer1,
                "category": dairy,
                "name": "Whole Milk",
                "price": 1.80,
                "stock": 20,
                "description": "Fresh whole milk from a local producer.",
                "is_organic": True,
                "allergens": [milk_allergen],
            },
            {
                "producer": producer1,
                "category": fruit,
                "name": "Apples",
                "price": 2.50,
                "stock": 15,
                "description": "Crisp local apples.",
                "is_organic": False,
                "allergens": [],
            },
            {
                "producer": producer1,
                "category": veg,
                "name": "Carrots",
                "price": 1.20,
                "stock": 8,
                "description": "Seasonal carrots grown nearby.",
                "is_organic": False,
                "allergens": [],
            },
            {
                "producer": producer2,
                "category": bakery,
                "name": "Sourdough Bread",
                "price": 3.40,
                "stock": 10,
                "description": "Fresh artisan sourdough loaf.",
                "is_organic": False,
                "allergens": [gluten_allergen],
            },
            {
                "producer": producer2,
                "category": dairy,
                "name": "Free Range Eggs",
                "price": 2.90,
                "stock": 36,
                "description": "Free range eggs from local hens.",
                "is_organic": False,
                "allergens": [egg_allergen],
            },
            {
                "producer": producer2,
                "category": bakery,
                "name": "Nut Granola Bar",
                "price": 1.60,
                "stock": 12,
                "description": "Crunchy oat bar with mixed nuts.",
                "is_organic": False,
                "allergens": [nuts_allergen, gluten_allergen],
            },
        ]

        for item in demo_products:
            product, _ = Product.objects.get_or_create(
                producer=item["producer"],
                slug=slugify(item["name"]),
                defaults={
                    "category": item["category"],
                    "name": item["name"],
                    "description": item["description"],
                    "price": item["price"],
                    "stock": item["stock"],
                    "is_organic": item["is_organic"],
                    "is_active": True,
                },
            )
            product.category = item["category"]
            product.name = item["name"]
            product.description = item["description"]
            product.price = item["price"]
            product.stock = item["stock"]
            product.is_organic = item["is_organic"]
            product.is_active = True
            product.save()
            product.allergens.set(item["allergens"])

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))