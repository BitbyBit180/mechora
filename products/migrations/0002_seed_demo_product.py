from django.db import migrations


def create_demo_product(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.update_or_create(
        product_code="P-PLATE01",
        defaults={
            "name": "Demonstration metal plate",
            "description": "Synthetic centered plate with scratches or pits",
            "is_active": True,
        },
    )


def remove_demo_product(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(product_code="P-PLATE01").delete()


class Migration(migrations.Migration):
    dependencies = [("products", "0001_initial")]
    operations = [migrations.RunPython(create_demo_product, remove_demo_product)]
