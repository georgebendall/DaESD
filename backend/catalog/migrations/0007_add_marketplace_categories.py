from django.db import migrations
from django.utils.text import slugify


def add_marketplace_categories(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")

    for name in ["Fruit", "Herbs", "Pantry"]:
        Category.objects.get_or_create(
            name=name,
            defaults={"slug": slugify(name)},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_product_best_before_date_alter_product_unit"),
    ]

    operations = [
        migrations.RunPython(add_marketplace_categories, migrations.RunPython.noop),
    ]
