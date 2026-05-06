from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0009_product_season_months_refresh_allergens"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="image",
            field=models.ImageField(
                blank=True,
                help_text="Optional product image uploaded by the producer.",
                null=True,
                upload_to="products/",
            ),
        ),
    ]
