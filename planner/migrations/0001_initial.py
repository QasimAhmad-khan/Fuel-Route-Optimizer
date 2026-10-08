from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="FuelStation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_id", models.CharField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("address", models.CharField(blank=True, max_length=250)),
                ("city", models.CharField(max_length=120)),
                ("state", models.CharField(max_length=2)),
                ("price_per_gallon", models.DecimalField(decimal_places=8, max_digits=12)),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("coordinate_source", models.CharField(default="provided", max_length=20)),
            ],
        ),
        migrations.AddIndex(
            model_name="fuelstation",
            index=models.Index(fields=["latitude", "longitude"], name="planner_fue_latitud_a0ae5a_idx"),
        ),
    ]
