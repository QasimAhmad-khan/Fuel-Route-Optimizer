import json
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from planner.models import FuelStation


@override_settings(ORS_API_KEY="test-key")
class PlanApiTests(TestCase):
    def setUp(self):
        for source_id, longitude, price in [("a", -96, "4"), ("b", -94, "3"), ("c", -91, "5")]:
            FuelStation.objects.create(source_id=source_id, name=source_id, city="Test", state="TX",
                                       price_per_gallon=Decimal(price), latitude=40, longitude=longitude)

    @patch("planner.views.directions")
    @patch("planner.views.geocode_us")
    def test_returns_map_stops_and_total(self, geocode, routing):
        geocode.side_effect = [
            {"label": "Start, USA", "coordinates": [-100, 40]},
            {"label": "Finish, USA", "coordinates": [-90, 40]},
        ]
        routing.return_value = {"geometry": [[-100, 40], [-90, 40]], "distance_miles": 1000.0}
        response = self.client.post("/api/v1/plan/", data=json.dumps({"start": "Start, TX", "finish": "Finish, TX"}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_money_spent_on_fuel_usd"], "160.00")
        self.assertEqual([stop["station_id"] for stop in body["fuel_stops"]], ["a", "b"])
        self.assertEqual(len(body["map_geojson"]["features"]), 5)
        self.assertEqual(geocode.call_count, 2)
        routing.assert_called_once()

    def test_invalid_inputs_are_rejected(self):
        response = self.client.post("/api/v1/plan/", data=json.dumps({"start": "Dallas", "finish": "Dallas"}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/v1/plan/", data=json.dumps({"start": "Dallas", "finish": "Austin",
                                                                    "starting_fuel_gallons": 51}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)

    @patch("planner.views.geocode_us")
    def test_distinct_labels_resolving_to_same_place_are_rejected(self, geocode):
        geocode.return_value = {"label": "Dallas, TX", "coordinates": [-96.8, 32.8]}
        response = self.client.post("/api/v1/plan/", data=json.dumps({"start": "Dallas", "finish": "Dallas, TX"}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_health_reports_imported_data(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["fuel_station_count"], 3)

    def test_map_viewer_serves_leaflet_client(self):
        response = self.client.get("/map/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "leaflet@1.9.4")
        self.assertContains(response, "basemap.nationalmap.gov")
        self.assertNotContains(response, "tile.openstreetmap.org")
        self.assertContains(response, "/api/v1/plan/")
