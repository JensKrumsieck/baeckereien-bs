# backen

Interactive map of all bakeries in Braunschweig, built with SvelteKit + Leaflet.

- Search an address or use your location → routes to the nearest bakery on foot (OSRM foot routing).
- Coverage layer: every residential building in the city, colored by beeline walking time to its nearest bakery, with a headline stat and bucket legend.

## Data

Bakeries and residential buildings are fetched from OpenStreetMap via Overpass and checked into `src/lib/assets/` as CSV/GeoJSON so the app has no runtime dependency on Overpass.

```sh
python fetch/bakeries_braunschweig.py
python fetch/residential_braunschweig.py
```

Re-run and copy the output CSV into `src/lib/assets/` to refresh the data.

## Developing

```sh
npm install
npm run dev
```

## Building

```sh
npm run build
npm run preview
```
