from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from planner.optimizer import Candidate, NoFuelPlan, optimize_purchases, project_stations


def station(mile, price, identifier):
    return Candidate(identifier, identifier, "", "Town", "TX", Decimal(price),
                     40.0, -100.0, "provided", mile, 0.0)


class FuelOptimizationTests(SimpleTestCase):
    def test_multiple_stops_buy_only_enough_to_reach_cheaper_station(self):
        plan = optimize_purchases(1000, [station(400, "4", "expensive"),
                                         station(600, "3", "cheap"),
                                         station(900, "5", "late")])
        self.assertEqual([stop["station_id"] for stop in plan["fuel_stops"]], ["expensive", "cheap"])
        self.assertEqual([stop["gallons"] for stop in plan["fuel_stops"]], [10.0, 40.0])
        self.assertEqual(plan["total_money_spent_on_fuel_usd"], "160.00")
        self.assertEqual(plan["fuel_consumed_gallons"], 100.0)

    def test_short_trip_uses_existing_fuel_and_has_no_purchase(self):
        plan = optimize_purchases(250, [])
        self.assertEqual(plan["fuel_stops"], [])
        self.assertEqual(plan["total_money_spent_on_fuel_usd"], "0")
        self.assertEqual(plan["fuel_remaining_at_finish_gallons"], 25.0)

    def test_unreachable_station_raises(self):
        with self.assertRaises(NoFuelPlan):
            optimize_purchases(1100, [station(600, "2", "unreachable")])

    def test_exact_500_mile_leg_is_reachable(self):
        plan = optimize_purchases(1000, [station(500, "3", "midpoint")])
        self.assertEqual(plan["total_money_spent_on_fuel_usd"], "150.00")

    def test_projection_excludes_distant_station(self):
        geometry = [[-100, 40], [-90, 40]]
        near = SimpleNamespace(source_id="near", name="Near", address="", city="X", state="TX",
                               price_per_gallon=Decimal("3"), latitude=40, longitude=-95,
                               coordinate_source="provided")
        far = SimpleNamespace(source_id="far", name="Far", address="", city="Y", state="TX",
                              price_per_gallon=Decimal("2"), latitude=42, longitude=-95,
                              coordinate_source="provided")
        found = project_stations(geometry, 1000, [near, far])
        self.assertEqual([item.source_id for item in found], ["near"])
        self.assertAlmostEqual(found[0].mile, 500, places=1)
