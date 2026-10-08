from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from planner.routing import LocationError, directions, geocode_us


@override_settings(ORS_API_KEY="test-key")
class RoutingTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("planner.routing._fetch")
    def test_one_directions_call_and_cached_geocodes(self, fetch):
        fetch.side_effect = [
            {"features": [{"properties": {"country_a": "USA", "label": "Dallas, TX, USA"},
                            "geometry": {"coordinates": [-96.8, 32.8]}}]},
            {"features": [{"properties": {"country_a": "USA", "label": "Austin, TX, USA"},
                            "geometry": {"coordinates": [-97.7, 30.3]}}]},
            {"features": [{"properties": {"summary": {"distance": 300000}},
                            "geometry": {"coordinates": [[-96.8, 32.8], [-97.7, 30.3]]}}]},
        ]
        origin = geocode_us("Dallas, TX")
        destination = geocode_us("Austin, TX")
        first = directions(origin, destination)
        second = directions(geocode_us("Dallas, TX"), geocode_us("Austin, TX"))
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(first, second)

    @patch("planner.routing._fetch")
    def test_non_us_result_rejected(self, fetch):
        fetch.return_value = {"features": [{"properties": {"country_a": "CAN"},
                                             "geometry": {"coordinates": [-79, 43]}}]}
        with self.assertRaises(LocationError):
            geocode_us("Toronto")
