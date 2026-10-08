"""Import the assessment CSV; resolve city centroids once, never during API requests."""

import csv
import hashlib
import io
import re
import zipfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.request import Request, urlopen

import geonamescache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from planner.models import FuelStation

GEONAMES_URL = "https://download.geonames.org/export/dump/US.zip"
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())


def normalized(value):
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def column(row, *names):
    normalized_row = {normalized(key): value for key, value in row.items()}
    return next((normalized_row[name] for name in map(normalized, names) if name in normalized_row), "")


def city_index(gazetteer_bytes=None):
    """Prefer complete US GeoNames dump; fall back to bundled cities >=500 people."""
    result = {}
    if gazetteer_bytes is not None:
        with zipfile.ZipFile(io.BytesIO(gazetteer_bytes)) as archive:
            with archive.open("US.txt") as source:
                for raw in source:
                    fields = raw.decode("utf-8", errors="replace").rstrip("\n").split("\t")
                    if len(fields) < 15 or fields[6] != "P" or fields[8] != "US":
                        continue
                    state = fields[10].upper()
                    if len(state) != 2:
                        continue
                    try:
                        latitude, longitude, population = float(fields[4]), float(fields[5]), int(fields[14] or 0)
                    except ValueError:
                        continue
                    for name in (fields[1], fields[2]):
                        key = (normalized(name), state)
                        if key not in result or population > result[key][2]:
                            result[key] = (latitude, longitude, population)
        return result
    cache = geonamescache.GeonamesCache(min_city_population=500)
    for city in cache.get_cities().values():
        if city.get("countrycode") != "US":
            continue
        key = (normalized(city["name"]), city["admin1code"].upper())
        population = int(city.get("population") or 0)
        if key not in result or population > result[key][2]:
            result[key] = (float(city["latitude"]), float(city["longitude"]), population)
    return result


class Command(BaseCommand):
    help = "Load assessment fuel prices. --download-gazetteer resolves even small towns offline at runtime."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=Path)
        parser.add_argument("--replace", action="store_true")
        parser.add_argument("--gazetteer", type=Path, help="Existing GeoNames US.zip")
        parser.add_argument("--download-gazetteer", action="store_true", help="Fetch GeoNames US.zip once at import time")

    def handle(self, *args, **options):
        if options["gazetteer"] and options["download_gazetteer"]:
            raise CommandError("Choose --gazetteer or --download-gazetteer, not both.")
        path = options["csv_path"]
        if not path.is_file():
            raise CommandError(f"File not found: {path}")
        gazetteer_bytes = None
        if options["gazetteer"]:
            gazetteer_bytes = options["gazetteer"].read_bytes()
        elif options["download_gazetteer"]:
            try:
                request = Request(GEONAMES_URL, headers={"User-Agent": "fuel-route-assessment/1.0"})
                with urlopen(request, timeout=60) as response:
                    gazetteer_bytes = response.read()
            except Exception as exc:
                raise CommandError(f"Could not download US gazetteer: {exc}") from exc
        locations = city_index(gazetteer_bytes)
        skipped = Counter()
        examples = []
        objects = {}
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            first_line = source.readline()
            source.seek(0)
            delimiter = "\t" if "\t" in first_line else ","
            reader = csv.DictReader(source, delimiter=delimiter)
            headers = {normalized(header) for header in (reader.fieldnames or [])}
            if not {"city", "state", "retailprice"}.issubset(headers):
                raise CommandError("CSV needs City, State, and Retail Price columns.")
            for line_number, row in enumerate(reader, start=2):
                name = column(row, "Truckstop Name", "Name").strip() or "Unnamed station"
                address = column(row, "Address").strip()
                city = column(row, "City").strip()
                state = column(row, "State").strip().upper()
                if state not in US_STATES:
                    skipped["outside USA"] += 1
                    continue
                try:
                    price = Decimal(column(row, "Retail Price", "Price").replace("$", "").strip())
                    if not price.is_finite() or price <= 0 or price >= 100:
                        raise InvalidOperation()
                    raw_lat = column(row, "Latitude", "Lat")
                    raw_lon = column(row, "Longitude", "Lon", "Lng")
                    if raw_lat and raw_lon:
                        latitude, longitude = float(raw_lat), float(raw_lon)
                        coordinate_source = "provided"
                    else:
                        latitude, longitude, _ = locations[(normalized(city), state)]
                        coordinate_source = "city_centroid"
                    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                        raise ValueError("invalid coordinates")
                except (InvalidOperation, ValueError, KeyError):
                    reason = "unresolved US city or invalid price/coordinates"
                    skipped[reason] += 1
                    if len(examples) < 10:
                        examples.append(f"line {line_number}: {city}, {state}")
                    continue
                raw_id = column(row, "OPIS Truckstop ID", "Station ID", "ID").strip()
                source_id = raw_id or hashlib.sha1(f"{name}|{address}|{city}|{state}".encode()).hexdigest()
                if source_id in objects and objects[source_id].price_per_gallon <= price:
                    continue
                objects[source_id] = FuelStation(
                    source_id=source_id,
                    name=name[:200], address=address[:250], city=city[:120], state=state[:2],
                    price_per_gallon=price, latitude=latitude, longitude=longitude,
                    coordinate_source=coordinate_source,
                )
        if not objects:
            raise CommandError("No valid stations found; existing data was not changed.")
        with transaction.atomic():
            if options["replace"]:
                FuelStation.objects.all().delete()
            FuelStation.objects.bulk_create(
                list(objects.values()), batch_size=500,
                update_conflicts=True, unique_fields=["source_id"],
                update_fields=["name", "address", "city", "state", "price_per_gallon", "latitude", "longitude", "coordinate_source"],
            )
        self.stdout.write(self.style.SUCCESS(f"Imported {len(objects)} stations; skipped {sum(skipped.values())} rows: {dict(skipped)}."))
        if examples:
            self.stdout.write("Skipped examples: " + "; ".join(examples))
