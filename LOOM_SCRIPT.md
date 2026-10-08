# Loom walkthrough (target: 4 minutes)

1. **0:00–0:35 — Problem and setup.** Show the README: Django 6.1.2, 500-mile range, 10 mpg, 6,598 imported unique US stations. Mention the city-centroid limitation.
2. **0:35–1:50 — Postman.** Import `postman_collection.json`, send Health, then Dallas → Denver and Los Angeles → New York. Show `distance_miles`, `fuel_stops`, `total_money_spent_on_fuel_usd`, and `map_geojson` features. Explain that starting fuel defaults to 50 gallons and is prepaid.
3. **1:50–2:35 — Map.** Open `/map/`, run Dallas → Denver, zoom to fuel markers, and show the purchase list. If an ORS key is unavailable, record this after configuring one rather than presenting mocked data as live.
4. **2:35–3:35 — Code overview.** Show `planner/routing.py` (two cached geocodes, one GeoJSON directions call), `planner/optimizer.py` (project onto route and choose cheaper reachable stations), and `import_fuel_prices.py` (one-time gazetteer, full price precision, duplicate handling).
5. **3:35–4:00 — Verification.** Run `python manage.py test`; show passing count. Mention one known limitation: station coordinates are city estimates because the supplied CSV has no latitude/longitude.

Keep the Loom under five minutes. Share the video link and a GitHub repository containing this folder's source, README, collection, and tests. Do not commit `.env` or `db.sqlite3`.
