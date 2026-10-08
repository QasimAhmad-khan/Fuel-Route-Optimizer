from django.db import models


class FuelStation(models.Model):
    source_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=250, blank=True)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    price_per_gallon = models.DecimalField(max_digits=12, decimal_places=8)
    latitude = models.FloatField()
    longitude = models.FloatField()
    coordinate_source = models.CharField(max_length=20, default="provided")

    class Meta:
        indexes = [models.Index(fields=["latitude", "longitude"])]
