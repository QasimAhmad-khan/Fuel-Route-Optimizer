# Existing ETTO planner review

Reviewed [QasimAhmad-khan/ETTO-Trip-Planner](https://github.com/QasimAhmad-khan/ETTO-Trip-Planner), including `backend/trips/services/geocode.py`, `routing.py`, `views.py`, its tests, and backend configuration.

| Existing part | Assessment decision |
| --- | --- |
| Django backend and JSON API structure | Reused the service/view separation, request validation pattern, and SQLite setup in a smaller standalone Django 6.1.2 project. |
| ORS geocoding and directions integration | Reused the provider and cached-geocode idea. Adapted geocoding to require a US result and routing to request GeoJSON directly, avoiding polyline decoding. |
| Existing fuel stop chunking | Replaced. It inserts a stop every 1,000 miles and does not use station prices or model a 500-mile tank. |
| HOS simulation, ELD logs, pickup/dropoff workflow | Excluded because the new assignment only needs start/finish, route, stops, and cost. |
| React/Leaflet frontend | Used Leaflet in a small demonstration map. The API remains the deliverable and returns GeoJSON for other clients. |
| Existing tests | Retained the practice of focused Django tests; added new optimizer, importer, API, and routing-call tests for this assignment. |

The new routing client is adapted rather than copied verbatim: the older client accepts raw coordinates without US validation, reads keys at import time, may fall back to a second directions call, and uses the HGV profile. The assessment's call-count and input constraints warrant a dedicated integration.
