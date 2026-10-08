"""The only runtime network integration: two cached geocodes and one directions call."""

import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache


class RoutingError(Exception):
    pass


class LocationError(RoutingError):
    pass


def _fetch(url, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": settings.ORS_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "fuel-route-assessment/1.0",
        },
        method="POST" if body is not None else "GET",
    )
    try:
        with urlopen(request, timeout=settings.ORS_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RoutingError(f"Routing provider returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise RoutingError("Routing provider is unavailable or returned invalid data.") from exc


def geocode_us(query):
    normalized = " ".join(query.strip().split())
    cache_key = "geocode:" + hashlib.sha256(normalized.casefold().encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    url = "https://api.openrouteservice.org/geocode/search?" + urlencode(
        {"text": normalized, "boundary.country": "USA", "size": 5}
    )
    data = _fetch(url)
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        country = str(props.get("country_a", "")).upper()
        coords = feature.get("geometry", {}).get("coordinates", [])
        if country == "USA" and len(coords) >= 2:
            result = {"label": props.get("label", normalized), "coordinates": coords[:2]}
            cache.set(cache_key, result, settings.GEOCODE_CACHE_SECONDS)
            return result
    raise LocationError(f"Could not resolve a location in the USA: {normalized}")


def directions(start, finish):
    key_material = json.dumps([start["coordinates"], finish["coordinates"]], separators=(",", ":"))
    cache_key = "directions:" + hashlib.sha256(key_material.encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    data = _fetch(
        "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
        {"coordinates": [start["coordinates"], finish["coordinates"]], "options": {"avoid_borders": "all"}},
    )
    try:
        feature = data["features"][0]
        coordinates = feature["geometry"]["coordinates"]
        meters = float(feature["properties"]["summary"]["distance"])
        if len(coordinates) < 2 or meters <= 0:
            raise ValueError("empty route")
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RoutingError("Routing provider returned a route without usable geometry or distance.") from exc
    route = {"distance_miles": meters / 1609.344, "geometry": coordinates}
    cache.set(cache_key, route, settings.ROUTE_CACHE_SECONDS)
    return route
