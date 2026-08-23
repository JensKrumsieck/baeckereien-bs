"""Fetch all bakeries in Braunschweig via Overpass API, write name/address/lat/lon to CSV."""
import csv
import sys
import time
import urllib.request
import urllib.parse
import json

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "bakeries-braunschweig-fetch/1.0 (contact: jkrumsieck@gmail.com)"

QUERY = """
[out:json][timeout:60];
area["boundary"="administrative"]["name"="Braunschweig"]["admin_level"="6"]->.a;
(
  node["shop"="bakery"](area.a);
  way["shop"="bakery"](area.a);
  relation["shop"="bakery"](area.a);
);
out center tags;
"""

OUT_FILE = "bakeries_braunschweig.csv"


def fetch():
    data = urllib.parse.urlencode({"data": QUERY}).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def reverse_geocode(lat, lon):
    params = urllib.parse.urlencode({
        "format": "jsonv2",
        "lat": lat,
        "lon": lon,
        "zoom": 18,
        "addressdetails": 1,
    })
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)

    addr = data.get("address", {})
    street = addr.get("road")
    housenumber = addr.get("house_number")
    postcode = addr.get("postcode")
    city = addr.get("city") or addr.get("town") or addr.get("village")

    parts = []
    if street:
        parts.append(f"{street} {housenumber}".strip() if housenumber else street)
    if postcode or city:
        parts.append(" ".join(p for p in [postcode, city] if p))

    return ", ".join(parts), street


def build_address(tags):
    parts = []
    street = tags.get("addr:street")
    housenumber = tags.get("addr:housenumber")
    postcode = tags.get("addr:postcode")
    city = tags.get("addr:city")

    if street:
        parts.append(f"{street} {housenumber}".strip() if housenumber else street)
    if postcode or city:
        parts.append(" ".join(p for p in [postcode, city] if p))

    return ", ".join(parts), street


def main():
    print("Fetching bakeries from Overpass API...")
    result = fetch()
    elements = result.get("elements", [])

    rows = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name", "")

        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            lat, lon = center.get("lat"), center.get("lon")

        address, street = build_address(tags)
        if not address and lat is not None and lon is not None:
            print(f"Reverse geocoding {name or el['type'] + '/' + str(el['id'])}...")
            try:
                address, street = reverse_geocode(lat, lon)
            except Exception as exc:
                print(f"  reverse geocode failed: {exc}", file=sys.stderr)
            time.sleep(1)  # Nominatim usage policy: max 1 request/sec

        if not name:
            name = f"Bäckerei {street}" if street else "Bäckerei"

        rows.append({
            "name": name,
            "address": address,
            "lat": lat,
            "lon": lon,
        })

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "address", "lat", "lon"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} bakeries to {OUT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
