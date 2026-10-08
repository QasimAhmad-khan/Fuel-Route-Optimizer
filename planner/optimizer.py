"""Project stations onto a fixed route, then compute optimal purchases on it."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import cos, radians

from shapely.geometry import LineString, Point

MILES_PER_GALLON = 10.0
MAX_RANGE_MILES = 500.0
TANK_GALLONS = MAX_RANGE_MILES / MILES_PER_GALLON


class NoFuelPlan(Exception):
    pass


@dataclass(frozen=True)
class Candidate:
    source_id: str
    name: str
    address: str
    city: str
    state: str
    price_per_gallon: Decimal
    latitude: float
    longitude: float
    coordinate_source: str
    mile: float
    distance_from_route_miles: float


def project_stations(geometry, total_miles, stations, max_distance_miles=10.0):
    """Use GEOS projection in local mile units; no per-station API requests."""
    mean_lat = sum(point[1] for point in geometry) / len(geometry)
    x_scale = 69.172 * max(cos(radians(mean_lat)), 0.01)
    y_scale = 69.0
    line = LineString([(lon * x_scale, lat * y_scale) for lon, lat in geometry])
    if line.length == 0:
        raise NoFuelPlan("Route geometry has zero length.")
    candidates = []
    for station in stations:
        point = Point(station.longitude * x_scale, station.latitude * y_scale)
        offset = line.distance(point)
        if offset > max_distance_miles:
            continue
        mile = total_miles * line.project(point) / line.length
        candidates.append(Candidate(
            source_id=station.source_id,
            name=station.name,
            address=station.address,
            city=station.city,
            state=station.state,
            price_per_gallon=station.price_per_gallon,
            latitude=station.latitude,
            longitude=station.longitude,
            coordinate_source=station.coordinate_source,
            mile=mile,
            distance_from_route_miles=offset,
        ))
    return sorted(candidates, key=lambda station: (station.mile, station.price_per_gallon, station.source_id))


def optimize_purchases(total_miles, candidates, starting_gallons=50.0):
    """Greedy gas-station theorem: buy to the first cheaper reachable price, else fill.

    This is exact for fuel purchases on a fixed route when stop detours are ignored.
    The finish is a zero-price sentinel, so no excess fuel is purchased at the end.
    """
    if not 0 <= starting_gallons <= TANK_GALLONS:
        raise ValueError("starting_gallons must be between 0 and 50")
    remaining = float(starting_gallons)
    last_mile = 0.0
    stops = []
    total_cost = Decimal("0")
    ordered = [candidate for candidate in candidates if 0 <= candidate.mile < total_miles]
    for index, station in enumerate(ordered):
        remaining -= (station.mile - last_mile) / MILES_PER_GALLON
        if remaining < -1e-7:
            raise NoFuelPlan("No reachable fuel station covers this route segment.")
        remaining = max(0.0, remaining)
        last_mile = station.mile
        cheaper_mile = None
        for next_station in ordered[index + 1:]:
            if next_station.mile - station.mile > MAX_RANGE_MILES + 1e-7:
                break
            if next_station.price_per_gallon < station.price_per_gallon:
                cheaper_mile = next_station.mile
                break
        if total_miles - station.mile <= MAX_RANGE_MILES and cheaper_mile is None:
            cheaper_mile = total_miles
        target = TANK_GALLONS if cheaper_mile is None else (cheaper_mile - station.mile) / MILES_PER_GALLON
        gallons = max(0.0, min(TANK_GALLONS, target) - remaining)
        if gallons > 1e-7:
            cost = (Decimal(str(gallons)) * station.price_per_gallon).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_cost += cost
            remaining += gallons
            stops.append({
                "station_id": station.source_id,
                "name": station.name,
                "address": station.address,
                "city": station.city,
                "state": station.state,
                "coordinates": [station.longitude, station.latitude],
                "coordinate_source": station.coordinate_source,
                "mile_marker": round(station.mile, 1),
                "distance_from_route_miles": round(station.distance_from_route_miles, 1),
                "price_per_gallon_usd": str(station.price_per_gallon),
                "gallons": round(gallons, 3),
                "cost_usd": str(cost),
            })
    remaining -= (total_miles - last_mile) / MILES_PER_GALLON
    if remaining < -1e-7:
        raise NoFuelPlan("No reachable fuel station covers this route segment.")
    return {"fuel_stops": stops, "total_money_spent_on_fuel_usd": str(total_cost),
            "fuel_consumed_gallons": round(total_miles / MILES_PER_GALLON, 3),
            "fuel_remaining_at_finish_gallons": round(max(0.0, remaining), 3)}
