# Fuel Route API

A Django 6.1.2 assessment project. `POST /api/v1/plan/` accepts two US locations and returns route GeoJSON, cost-aware fuel stops, gallons bought at each stop, and the total spent on fuel during the trip. A small browser map at `/map/` renders the same API response for demonstration.

## Quick start (Windows PowerShell)

Use Python 3.13 or 3.12. Run these commands from this folder:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `ORS_API_KEY` in `.env` to a free [openrouteservice API key](https://openrouteservice.org/plans/). Then:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py import_fuel_prices "C:\path\to\fuel-prices-for-be-assessment.csv" --replace --download-gazetteer
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py runserver
```

`--download-gazetteer` downloads the complete US GeoNames city file **once at import time**, including small towns such as Big Cabin. If you already have `US.zip`, use `--gazetteer C:\path\to\US.zip` instead. The import is repeatable; `--replace` discards previously imported prices. Neither GeoNames nor any station geocoder is contacted during a planning request.

Open <http://127.0.0.1:8000/map/> to see the route and stops on a map. The API is at <http://127.0.0.1:8000/api/v1/plan/>. Health is at <http://127.0.0.1:8000/health/>.

## API request

```http
POST /api/v1/plan/
Content-Type: application/json

{"start":"Dallas, TX","finish":"Denver, CO","starting_fuel_gallons":50}
```

`start` and `finish` are geocoded within the US. `starting_fuel_gallons` is optional and defaults to 50 (a full tank). The tank capacity is 50 gallons because the maximum range is 500 miles at 10 mpg. The result includes:

- `map_geojson`: a GeoJSON FeatureCollection with the full route LineString, start/finish Points, and fuel-stop Points.
- `fuel_stops`: station, address, city/state, route mile, price, gallons, and purchase cost.
- `total_money_spent_on_fuel_usd`: the sum of purchases made **during** this trip, rounded to cents. Fuel already in the tank is treated as prepaid. A journey shorter than 500 miles with a full tank may have zero trip purchases.
- `fuel_consumed_gallons`: route miles / 10, whether or not those gallons were bought during this trip.
- `elapsed_ms` and `candidate_stations_considered` for demonstration.

HTTP 400 covers malformed input; 422 covers unresolved US locations or a route that cannot be covered by available stations; 502 covers upstream routing errors; 503 means a missing API key or empty station table.

## How it works

1. Cache US-restricted geocodes for both locations (two requests on first use).
2. Call ORS `driving-car/geojson` once for the route. The GeoJSON response contains the geometry and distance. The ORS call is cached for an hour.
3. Fetch nearby stations using a database bounding box and project their imported coordinates onto the route with Shapely. Stations farther than 10 straight-line miles from the route are excluded.
4. Walk stations in route order. At a station, buy only enough to reach the first cheaper reachable station; if none exists within 500 miles, fill enough to reach the destination or the full 50-gallon tank. This minimizes purchase cost on the fixed route under the stated fuel model.

First uncached request: **two geocoding calls plus one directions call**. If locations are cached, only the directions call remains. Repeated identical requests use no ORS calls in the same process. The local-memory cache is suitable for this assessment; use Redis for shared caching across production workers.

## Fuel-price data and accuracy

The supplied assessment file has 8,151 rows. The import of that file produced **6,598 unique US stations**. It omitted 620 Canadian rows and 31 US rows whose city could not be resolved from the complete GeoNames gazetteer. Duplicate OPIS IDs refer to the same city/state; when listed prices differ, the import retains the lowest price. Eight-decimal input prices are preserved.

The file contains no station latitude/longitude. Import therefore uses **city centroids**, and the response labels those coordinates as `city_centroid`. The displayed marker and route mile are estimates, not verified truckstop driveways. A future file with `Latitude` and `Longitude` columns takes precedence and is marked `provided`. Detour road distance and detour fuel are not part of the price optimization. Verify an exit and price before driving. The optimizer's exact cost claim applies to the fixed route and the imported station positions, not to an unknown road detour.

The route uses ORS's generic driving-car profile because this assessment does not define truck dimensions. The route request avoids country borders. ORS's [public API restrictions](https://openrouteservice.org/restrictions/) include a 6,000 km maximum driving route distance.

The one-time city dataset comes from [GeoNames](https://www.geonames.org/) under CC BY 4.0. ORS routing uses OpenStreetMap data. The browser demo uses the public-domain [USGS The National Map](https://www.usgs.gov/faqs/what-are-terms-uselicensing-map-services-and-data-national-map) basemap through [Leaflet](https://leafletjs.com/), with USGS attribution shown on the map.

## Tests and demo

Run `.\.venv\Scripts\python.exe manage.py test -v 2`. The suite covers multiple fuel purchases, cheaper stations, a 500-mile boundary, unreachable gaps, route projection, input errors, exact CSV headers and price precision, duplicate IDs, small-town lookup, US geocode validation, and caching/call counts. The included [Postman collection](postman_collection.json) provides health and route requests. [LOOM_SCRIPT.md](LOOM_SCRIPT.md) is a four-minute demonstration outline.

This checkout was tested with Python 3.13.5 and Django 6.1.2. A live ORS request requires your own API key; the automated tests mock only the external provider.
