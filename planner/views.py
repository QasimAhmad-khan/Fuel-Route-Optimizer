import json
import math
import time

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from planner.models import FuelStation
from planner.optimizer import NoFuelPlan, optimize_purchases, project_stations
from planner.routing import LocationError, RoutingError, directions, geocode_us


def health(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed."}, status=405)
    return JsonResponse({"status": "ok", "fuel_station_count": FuelStation.objects.count(),
                         "routing_configured": bool(settings.ORS_API_KEY)})


def map_viewer(request):
    if request.method != "GET":
        return _bad_request("Method not allowed.", 405)
    return render(request, "planner/map.html")


def _bad_request(message, status=400):
    return JsonResponse({"error": message}, status=status)


@csrf_exempt  # A stateless JSON API for Postman; no cookie authentication is used.
def plan_route(request):
    if request.method != "POST":
        return _bad_request("Use POST with a JSON body.", 405)
    if len(request.body) > 4096:
        return _bad_request("Request body is too large.", 413)
    try:
        payload = json.loads(request.body)
    except (UnicodeDecodeError, ValueError):
        return _bad_request("Body must be valid JSON.")
    if not isinstance(payload, dict):
        return _bad_request("Body must be a JSON object.")
    start, finish = payload.get("start"), payload.get("finish")
    if not all(isinstance(value, str) and 2 <= len(value.strip()) <= 200 for value in (start, finish)):
        return _bad_request("start and finish must be USA location strings of 2–200 characters.")
    if start.strip().casefold() == finish.strip().casefold():
        return _bad_request("start and finish must differ.")
    try:
        starting_gallons = float(payload.get("starting_fuel_gallons", 50))
    except (TypeError, ValueError):
        return _bad_request("starting_fuel_gallons must be a number from 0 to 50.")
    if not math.isfinite(starting_gallons) or not 0 <= starting_gallons <= 50:
        return _bad_request("starting_fuel_gallons must be a number from 0 to 50.")
    if not settings.ORS_API_KEY:
        return _bad_request("ORS_API_KEY is not configured.", 503)
    if not FuelStation.objects.exists():
        return _bad_request("No fuel prices have been imported.", 503)

    started = time.perf_counter()
    try:
        origin = geocode_us(start)
        destination = geocode_us(finish)
        route = directions(origin, destination)
    except LocationError as exc:
        return _bad_request(str(exc), 422)
    except RoutingError as exc:
        return _bad_request(str(exc), 502)

    geometry = route["geometry"]
    latitudes = [point[1] for point in geometry]
    longitudes = [point[0] for point in geometry]
    # SQL bounding box avoids projecting every fuel station in the country.
    stations = FuelStation.objects.filter(
        latitude__gte=min(latitudes) - 0.25,
        latitude__lte=max(latitudes) + 0.25,
        longitude__gte=min(longitudes) - 1.0,
        longitude__lte=max(longitudes) + 1.0,
    ).only("source_id", "name", "address", "city", "state", "price_per_gallon",
           "latitude", "longitude", "coordinate_source")
    try:
        candidates = project_stations(geometry, route["distance_miles"], stations)
        plan = optimize_purchases(route["distance_miles"], candidates, starting_gallons)
    except NoFuelPlan as exc:
        return _bad_request(str(exc), 422)

    features = [{"type": "Feature", "properties": {"kind": "route"},
                 "geometry": {"type": "LineString", "coordinates": geometry}}]
    for stop in plan["fuel_stops"]:
        features.append({"type": "Feature", "properties": {"kind": "fuel_stop", "station_id": stop["station_id"],
                         "price_per_gallon_usd": stop["price_per_gallon_usd"]},
                         "geometry": {"type": "Point", "coordinates": stop["coordinates"]}})
    return JsonResponse({
        "start": origin,
        "finish": destination,
        "distance_miles": round(route["distance_miles"], 2),
        "vehicle": {"maximum_range_miles": 500, "miles_per_gallon": 10,
                    "starting_fuel_gallons": starting_gallons},
        "map_geojson": {"type": "FeatureCollection", "features": features},
        **plan,
        "candidate_stations_considered": len(candidates),
        "pricing_note": "Total is fuel purchased during this trip; fuel already in the tank is excluded. Station coordinates without source latitude/longitude are city centroids; detours are not priced.",
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
    })
