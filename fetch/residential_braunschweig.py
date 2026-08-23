"""Fetch all residential building centroids in Braunschweig via Overpass API, write lat/lon to CSV."""
import csv
import urllib.request
import urllib.parse
import json

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "residential-braunschweig-fetch/1.0 (contact: jkrumsieck@gmail.com)"

BUILDING_TYPES = "residential|house|apartments|terrace|semidetached_house|detached|bungalow"

QUERY = f"""
[out:json][timeout:180];
area["boundary"="administrative"]["name"="Braunschweig"]["admin_level"="6"]->.a;
(
  nwr["building"~"^({BUILDING_TYPES})$"](area.a);
  nwr["building"="yes"]["addr:housenumber"](area.a);
  nwr["building"="yes"]["addr:street"]["addr:housenumber"](area.a);
);
out center;
"""

OUT_FILE = "residential_braunschweig.csv"


def fetch():
    data = urllib.parse.urlencode({"data": QUERY}).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=200) as resp:
        return json.load(resp)


def main():
    print("Fetching residential buildings from Overpass API...")
    result = fetch()
    elements = result.get("elements", [])

    rows = []
    for el in elements:
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            lat, lon = center.get("lat"), center.get("lon")

        if lat is None or lon is None:
            continue

        rows.append({"lat": lat, "lon": lon})

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["lat", "lon"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} residential buildings to {OUT_FILE}")


if __name__ == "__main__":
    main()
