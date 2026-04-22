from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Allergen, Category, Product


class MarketplaceSeedAndCatalogueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", reset=True, stdout=StringIO())

    def test_seed_demo_loads_marketplace_data_and_can_rerun(self):
        initial_product_count = Product.objects.count()

        call_command("seed_demo", stdout=StringIO())

        self.assertEqual(Product.objects.count(), initial_product_count)
        self.assertTrue(User.objects.filter(username="admin1", is_staff=True).exists())
        self.assertTrue(User.objects.filter(username="producer1", producer_profile__business_name="Bristol Valley Farm").exists())
        self.assertTrue(User.objects.filter(username="producer2", producer_profile__business_name="Hillside Dairy").exists())
        self.assertGreaterEqual(Product.objects.filter(category__name="Vegetables").count(), 5)
        self.assertGreaterEqual(Product.objects.filter(category__name="Dairy & Eggs").count(), 3)
        self.assertGreaterEqual(Product.objects.filter(is_organic=True).count(), 5)
        self.assertGreaterEqual(Product.objects.filter(is_organic=False).count(), 5)

    def test_category_browsing_returns_only_visible_category_products(self):
        response = self.client.get(reverse("product_list"), {"category": "vegetables"})
        names = {product.name for product in response.context["products"]}

        self.assertIn("Organic Carrots", names)
        self.assertIn("Cherry Tomatoes", names)
        self.assertGreaterEqual(len(names), 5)
        self.assertNotIn("Fresh Milk", names)
        self.assertNotIn("Asparagus Spears", names)

    def test_search_is_case_insensitive_and_searches_product_description_producer_and_allergens(self):
        tomatoes_response = self.client.get(reverse("product_list"), {"q": "ToMaToEs"})
        tomato_names = {product.name for product in tomatoes_response.context["products"]}
        self.assertIn("Cherry Tomatoes", tomato_names)
        self.assertIn("Organic Heritage Tomatoes", tomato_names)

        producer_response = self.client.get(reverse("product_list"), {"q": "hillside"})
        producer_names = {product.name for product in producer_response.context["products"]}
        self.assertIn("Fresh Milk", producer_names)

        allergen_response = self.client.get(reverse("product_list"), {"q": "nuts"})
        allergen_names = {product.name for product in allergen_response.context["products"]}
        self.assertTrue({"Hazelnut Brownies", "Nutty Granola"} & allergen_names)

        empty_response = self.client.get(reverse("product_list"), {"q": "zzzz-no-product"})
        self.assertContains(empty_response, "No products found.")

    def test_organic_and_allergen_filters_work_together(self):
        organic_response = self.client.get(reverse("product_list"), {"organic": "1"})
        organic_products = list(organic_response.context["products"])
        self.assertTrue(organic_products)
        self.assertTrue(all(product.is_organic for product in organic_products))

        milk = Allergen.objects.get(name="Milk")
        dairy_response = self.client.get(
            reverse("product_list"),
            {"category": "dairy-eggs", "allergen": str(milk.id)},
        )
        dairy_names = {product.name for product in dairy_response.context["products"]}
        self.assertIn("Fresh Milk", dairy_names)
        self.assertNotIn("Free Range Eggs", dairy_names)

        nuts = Allergen.objects.get(name="Nuts")
        exclude_response = self.client.get(reverse("product_list"), {"exclude_allergen": str(nuts.id)})
        excluded_names = {product.name for product in exclude_response.context["products"]}
        self.assertNotIn("Hazelnut Brownies", excluded_names)
        self.assertNotIn("Nutty Granola", excluded_names)

    def test_product_details_show_certification_allergens_and_availability(self):
        carrots = Product.objects.get(name="Organic Carrots")
        response = self.client.get(reverse("product_detail", args=[carrots.id]))

        self.assertContains(response, "Certified Organic")
        self.assertContains(response, "No common allergens listed")
        self.assertContains(response, "In Season")

        milk = Product.objects.get(name="Fresh Milk")
        response = self.client.get(reverse("product_detail", args=[milk.id]))
        self.assertContains(response, "Not Certified Organic")
        self.assertContains(response, "Milk")
        self.assertContains(response, "Available Year-Round")

    def test_unavailable_products_are_hidden_from_catalogue_but_visible_to_owner(self):
        hidden_product = Product.objects.get(name="Mature Cheddar")
        self.assertFalse(hidden_product.is_active)

        response = self.client.get(reverse("product_list"), {"q": "Mature Cheddar"})
        self.assertFalse(any(product.name == "Mature Cheddar" for product in response.context["products"]))

        producer = User.objects.get(username="producer2")
        self.client.force_login(producer)
        dashboard_response = self.client.get(reverse("producer_stock"))
        self.assertContains(dashboard_response, "Mature Cheddar")
