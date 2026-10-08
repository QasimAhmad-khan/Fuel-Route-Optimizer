import io
import tempfile
import zipfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from planner.management.commands.import_fuel_prices import city_index
from planner.models import FuelStation


class ImportTests(TestCase):
    def test_import_exact_assessment_headers_and_precision(self):
        content = ("OPIS Truckstop ID\tTruckstop Name\tAddress\tCity\tState\tRack ID\tRetail Price\tLatitude\tLongitude\n"
                   "7\tWOODSHED OF BIG CABIN\tI-44, EXIT 283 & US-69\tBig Cabin\tOK\t307\t3.00733333\t36.54\t-95.22\n")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "prices.csv"
            path.write_text(content, encoding="utf-8")
            call_command("import_fuel_prices", path, stdout=io.StringIO())
        item = FuelStation.objects.get(source_id="7")
        self.assertEqual(str(item.price_per_gallon), "3.00733333")
        self.assertEqual(item.name, "WOODSHED OF BIG CABIN")
        self.assertEqual(item.coordinate_source, "provided")

    def test_complete_gazetteer_resolves_small_town(self):
        fields = ["1", "Big Cabin", "Big Cabin", "", "36.54", "-95.22", "P", "PPL",
                  "US", "", "OK", "", "", "", "300"]
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w") as archive:
            archive.writestr("US.txt", "\t".join(fields) + "\n")
        index = city_index(memory.getvalue())
        self.assertEqual(index[("bigcabin", "OK")][:2], (36.54, -95.22))

    def test_duplicate_station_uses_lowest_listed_price(self):
        content = ("OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price,Latitude,Longitude\n"
                   "105,TA CENTER,Road,Bridgeport,MI,260,3.429,43.35,-83.88\n"
                   "105,TA CENTER,Road,Bridgeport,MI,260,3.269,43.35,-83.88\n")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "prices.csv"
            path.write_text(content, encoding="utf-8")
            call_command("import_fuel_prices", path, stdout=io.StringIO())
        self.assertEqual(FuelStation.objects.count(), 1)
        self.assertEqual(str(FuelStation.objects.get().price_per_gallon), "3.26900000")

    def test_canadian_row_is_excluded_even_if_it_has_coordinates(self):
        content = ("OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price,Latitude,Longitude\n"
                   "1,US STOP,Road,Seattle,WA,1,3.10,47.61,-122.33\n"
                   "2,CANADA STOP,Road,Vancouver,BC,1,2.10,49.28,-123.12\n")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "prices.csv"
            path.write_text(content, encoding="utf-8")
            call_command("import_fuel_prices", path, stdout=io.StringIO())
        self.assertEqual(list(FuelStation.objects.values_list("source_id", flat=True)), ["1"])
