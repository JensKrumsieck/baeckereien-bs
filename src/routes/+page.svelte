<script lang="ts">
  import { onMount } from "svelte";
  import Papa from "papaparse";
  import haversineDistance from "haversine-distance";
  import "leaflet/dist/leaflet.css";
  import "leaflet-defaulticon-compatibility/dist/leaflet-defaulticon-compatibility.css";
  import bakeriesCsv from "$lib/assets/bakeries_braunschweig.csv?raw";
  import districtsRaw from "$lib/assets/districts.geojson?raw";
  import residentialCsv from "$lib/assets/residential_braunschweig.csv?raw";

  interface Bakery {
    name: string;
    address: string;
    lat: number;
    lon: number;
  }

  interface LatLon {
    lat: number;
    lon: number;
  }

  function parseCsv(text: string): Bakery[] {
    const { data } = Papa.parse<{
      name: string;
      address: string;
      lat: string;
      lon: string;
    }>(text, { header: true, skipEmptyLines: true });

    return data.map((row) => ({
      name: row.name,
      address: row.address,
      lat: parseFloat(row.lat),
      lon: parseFloat(row.lon),
    }));
  }

  function parseResidentialCsv(text: string): LatLon[] {
    const { data } = Papa.parse<{ lat: string; lon: string }>(text, {
      header: true,
      skipEmptyLines: true,
    });

    return data
      .map((row) => ({ lat: parseFloat(row.lat), lon: parseFloat(row.lon) }))
      .filter((p) => !Number.isNaN(p.lat) && !Number.isNaN(p.lon));
  }

  // Walking speed assumption for the meter -> minute labels: ~4.8 km/h (80 m/min).
  // Distances here are beeline (Haversine), not routed, so they undershoot the real walk.
  interface CoverageBucket {
    maxMeters: number;
    color: string;
    label: string;
  }

  // Secondary brand ramp from app.css (--color-secondary-*), light -> dark.
  const COVERAGE_BUCKETS: CoverageBucket[] = [
    { maxMeters: 300, color: "#a6ccbf", label: "bis 4 Min." },
    { maxMeters: 600, color: "#5f9885", label: "4–8 Min." },
    { maxMeters: 1000, color: "#005538", label: "8–13 Min." },
    { maxMeters: 1500, color: "#003221", label: "13–19 Min." },
    { maxMeters: Infinity, color: "#002216", label: "über 19 Min." },
  ];

  interface CoverageStat {
    label: string;
    color: string;
    count: number;
    pct: number;
  }

  interface FootRoute {
    coordinates: [number, number][];
    distanceMeters: number;
    durationSeconds: number;
  }

  async function routeOnFoot(from: LatLon, to: LatLon): Promise<FootRoute> {
    const url = `https://routing.openstreetmap.de/routed-foot/route/v1/foot/${from.lon},${from.lat};${to.lon},${to.lat}?overview=full&geometries=geojson`;
    const res = await fetch(url);
    const data = await res.json();
    if (data.code !== "Ok")
      throw new Error(data.message ?? "Routing fehlgeschlagen");
    const route = data.routes[0];
    return {
      coordinates: route.geometry.coordinates.map(
        ([lon, lat]: [number, number]) => [lat, lon],
      ),
      distanceMeters: route.distance,
      durationSeconds: route.duration,
    };
  }

  let mapContainer: HTMLDivElement;
  let query = $state("");
  let status = $state("");
  let loading = $state(false);
  let showCoverage = $state(true);
  let coverageStats = $state<CoverageStat[]>([]);
  let coverageHeadline = $state("");
  let legendCollapsed = $state(false);

  let leafletMod: typeof import("leaflet");
  let geocoder: InstanceType<
    typeof import("leaflet-geosearch").OpenStreetMapProvider
  >;
  let map: import("leaflet").Map;
  let bakeryMarkers: { bakery: Bakery; marker: import("leaflet").Marker }[] =
    [];
  let userIcon: import("leaflet").DivIcon;
  let userMarker: import("leaflet").Marker | null = null;
  let routeLayer: import("leaflet").Polyline | null = null;
  let coverageLayer: import("leaflet").LayerGroup | null = null;

  function toggleCoverage() {
    showCoverage = !showCoverage;
    if (!coverageLayer) return;
    if (showCoverage) {
      coverageLayer.addTo(map);
    } else {
      coverageLayer.remove();
    }
  }

  async function locateNearestBakery(userLoc: LatLon) {
    status = "Berechne nächste Bäckerei zu Fuß …";
    const L = leafletMod;

    userMarker?.remove();
    routeLayer?.remove();
    userMarker = L.marker([userLoc.lat, userLoc.lon], { icon: userIcon })
      .addTo(map)
      .bindPopup("Dein Standort")
      .openPopup();

    const candidates = bakeryMarkers
      .map((bm) => ({
        bm,
        straightMeters: haversineDistance(userLoc, bm.bakery),
      }))
      .sort((a, b) => a.straightMeters - b.straightMeters)
      .slice(0, 3);

    let best: {
      bm: (typeof candidates)[number]["bm"];
      route: FootRoute;
    } | null = null;

    for (const { bm } of candidates) {
      try {
        const route = await routeOnFoot(userLoc, bm.bakery);
        if (!best || route.distanceMeters < best.route.distanceMeters) {
          best = { bm, route };
        }
      } catch {
        // Kandidat überspringen, nächsten versuchen
      }
    }

    if (!best) {
      status = "Route konnte nicht berechnet werden.";
      return;
    }

    routeLayer = L.polyline(best.route.coordinates, {
      color: "#0ba1dd", // --color-himmel-600, matches the user-location marker
      weight: 5,
    }).addTo(map);
    best.bm.marker.openPopup();
    map.fitBounds(routeLayer.getBounds(), { padding: [40, 40] });

    const km = (best.route.distanceMeters / 1000).toFixed(2);
    const min = Math.round(best.route.durationSeconds / 60);
    status = `Nächste Bäckerei: ${best.bm.bakery.name} — ${km} km, ca. ${min} Min. zu Fuß`;
  }

  async function handleSearch(e: SubmitEvent) {
    e.preventDefault();
    if (!query.trim() || loading) return;
    loading = true;
    status = "Suche Adresse …";
    try {
      const results = await geocoder.search({ query });
      if (!results.length) {
        status = "Adresse nicht gefunden.";
        return;
      }
      await locateNearestBakery({ lat: results[0].y, lon: results[0].x });
    } catch {
      status = "Fehler bei der Adresssuche.";
    } finally {
      loading = false;
    }
  }

  function handleGeolocate() {
    if (loading) return;
    if (!navigator.geolocation) {
      status = "Geolocation wird von diesem Browser nicht unterstützt.";
      return;
    }
    loading = true;
    status = "Standort wird ermittelt …";
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          await locateNearestBakery({
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
          });
        } catch {
          status = "Fehler bei der Routenberechnung.";
        } finally {
          loading = false;
        }
      },
      () => {
        status = "Standort konnte nicht ermittelt werden.";
        loading = false;
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  onMount(() => {
    let localMap: import("leaflet").Map | undefined;

    (async () => {
      const L = await import("leaflet");
      leafletMod = L;
      // @ts-expect-error no type declarations shipped for this package
      await import("leaflet-defaulticon-compatibility");

      const { OpenStreetMapProvider } = await import("leaflet-geosearch");
      geocoder = new OpenStreetMapProvider({
        params: {
          countrycodes: "de",
          viewbox: "10.30,52.40,10.70,52.15",
          bounded: 1,
        },
      });

      userIcon = L.divIcon({
        className: "",
        html: '<div style="background:var(--color-himmel-600);width:16px;height:16px;border-radius:50%;border:3px solid white;box-shadow:0 0 4px rgba(0,0,0,0.5)"></div>',
        iconSize: [16, 16],
        iconAnchor: [8, 8],
      });

      const bakeryIcon = L.divIcon({
        className: "",
        html: `<svg width="28" height="28" viewBox="0 0 24 24" style="filter:drop-shadow(0 1px 2px rgba(0,0,0,0.4))">
          <path fill="#008939" stroke="white" stroke-width="1" d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
          <circle cx="12" cy="9" r="3" fill="white"/>
        </svg>`,
        iconSize: [28, 28],
        iconAnchor: [14, 27],
        popupAnchor: [0, -24],
      });

      const bakeries = parseCsv(bakeriesCsv);
      const cityBounds = L.geoJSON(JSON.parse(districtsRaw)).getBounds();

      localMap = L.map(mapContainer, {
        maxBounds: cityBounds.pad(0.1),
        zoomSnap: 0.1,
        renderer: L.canvas(),
        maxBoundsViscosity: 1,
        zoomControl: false,
      }).setView(cityBounds.getCenter(), 11);
      map = localMap;
      map.setMinZoom(map.getBoundsZoom(cityBounds));
      L.control.zoom({ position: "bottomright" }).addTo(map);
      legendCollapsed = window.innerWidth < 640;

      L.tileLayer(
        "https://api.jenskrumsieck.de/openstreetmap/{s}/{z}/{x}/{y}.png",
        {
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 21,
          minZoom: 11,
        },
      ).addTo(map);

      const group = L.featureGroup();
      for (const bakery of bakeries) {
        if (Number.isNaN(bakery.lat) || Number.isNaN(bakery.lon)) continue;
        const marker = L.marker([bakery.lat, bakery.lon], { icon: bakeryIcon })
          .bindPopup(`<strong>${bakery.name}</strong><br>${bakery.address}`)
          .addTo(group);
        bakeryMarkers.push({ bakery, marker });
      }
      group.addTo(map);

      if (group.getLayers().length) {
        map.fitBounds(group.getBounds(), { padding: [20, 20] });
      }

      const residentialPoints = parseResidentialCsv(residentialCsv);
      const counts = COVERAGE_BUCKETS.map(() => 0);
      const localCoverageLayer = L.layerGroup();

      for (const point of residentialPoints) {
        let minDist = Infinity;
        for (const bakery of bakeries) {
          const d = haversineDistance(point, bakery);
          if (d < minDist) minDist = d;
        }
        const bucketIndex = COVERAGE_BUCKETS.findIndex(
          (b) => minDist <= b.maxMeters,
        );
        counts[bucketIndex]++;
        L.circleMarker([point.lat, point.lon], {
          radius: 3,
          weight: 1,
          color: "#ffffff",
          opacity: 0.9,
          fillColor: COVERAGE_BUCKETS[bucketIndex].color,
          fillOpacity: 0.85,
        }).addTo(localCoverageLayer);
      }

      coverageLayer = localCoverageLayer;
      if (showCoverage) coverageLayer.addTo(map);

      const total = residentialPoints.length;
      if (total) {
        coverageStats = COVERAGE_BUCKETS.map((b, i) => ({
          label: b.label,
          color: b.color,
          count: counts[i],
          pct: (counts[i] / total) * 100,
        }));
        const within8min = counts[0] + counts[1];
        coverageHeadline = `ca. ${((within8min / total) * 100).toFixed(0)}% aller Wohngebäude liegen (Luftlinie) höchstens 8 Gehminuten von der nächsten Bäckerei entfernt.`;
      }
    })();

    return () => localMap?.remove();
  });

  const pageTitle = "Bäckereien in Braunschweig – Karte & Routenplaner";
  const pageDescription =
    "Alle Bäckereien in Braunschweig auf einer interaktiven Karte. Adresse eingeben oder Standort nutzen und die nächste Bäckerei zu Fuß erreichen.";
  const canonicalUrl = "https://broetchen.jenskrumsieck.de/";
</script>

<svelte:head>
  <title>{pageTitle}</title>
  <meta name="description" content={pageDescription} />
  <link rel="canonical" href={canonicalUrl} />

  <meta property="og:type" content="website" />
  <meta property="og:title" content={pageTitle} />
  <meta property="og:description" content={pageDescription} />
  <meta property="og:url" content={canonicalUrl} />
  <meta property="og:locale" content="de_DE" />

  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content={pageTitle} />
  <meta name="twitter:description" content={pageDescription} />

  {@html `<script type="application/ld+json">${JSON.stringify({
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: pageTitle,
    description: pageDescription,
    url: canonicalUrl,
    applicationCategory: "MapApplication",
    operatingSystem: "Any",
    inLanguage: "de-DE",
  })}</script>`}
</svelte:head>

<div class="relative h-full w-full">
  <div
    class="absolute top-2 sm:top-4 left-1/2 z-1000 w-[min(94vw,32rem)] -translate-x-1/2 space-y-2 rounded-lg bg-neutral-500/95 p-2 sm:p-3 shadow-lg"
  >
    <form onsubmit={handleSearch} class="flex gap-1.5 sm:gap-2">
      <input
        bind:value={query}
        type="text"
        placeholder="Adresse eingeben …"
        class="min-w-0 flex-1 rounded border border-grey-300 px-2.5 sm:px-3 py-2 text-sm"
      />
      <button
        type="submit"
        disabled={loading}
        class="shrink-0 rounded bg-primary-600 px-2.5 sm:px-3 py-2 text-sm text-white disabled:opacity-50"
      >
        Suchen
      </button>
      <button
        type="button"
        onclick={handleGeolocate}
        disabled={loading}
        title="Meinen Standort verwenden"
        class="shrink-0 rounded border border-grey-300 px-2.5 sm:px-3 py-2 text-sm disabled:opacity-50"
      >
        📍
      </button>
    </form>
    {#if status}
      <p class="text-sm text-grey-700">{status}</p>
    {/if}
  </div>

  {#if coverageStats.length}
    <div
      class="absolute bottom-2 left-2 sm:bottom-4 sm:left-4 z-1000 w-[min(85vw,20rem)] space-y-2 rounded-lg bg-neutral-500/95 p-3 text-sm shadow-lg"
    >
      <div class="flex items-start gap-2">
        <button
          type="button"
          onclick={() => (legendCollapsed = !legendCollapsed)}
          class="flex flex-1 items-start gap-1.5 text-left font-semibold text-grey-900"
        >
          <span class="mt-0.5 shrink-0 text-grey-400"
            >{legendCollapsed ? "▸" : "▾"}</span
          >
          <span>{coverageHeadline}</span>
        </button>
        <button
          type="button"
          onclick={toggleCoverage}
          class="shrink-0 rounded border border-grey-300 px-2 py-1 text-xs whitespace-nowrap"
        >
          {showCoverage ? "Ausblenden" : "Einblenden"}
        </button>
      </div>
      {#if !legendCollapsed}
        <ul class="space-y-1">
          {#each coverageStats as stat (stat.label)}
            <li class="flex items-center gap-2">
              <span
                class="h-3 w-3 shrink-0 rounded-sm"
                style="background:{stat.color}"
              ></span>
              <span class="flex-1 text-grey-700">{stat.label}</span>
              <span class="text-grey-500">{stat.pct.toFixed(0)}%</span>
            </li>
          {/each}
        </ul>
        <p class="text-xs text-grey-500">
          Luftlinie zur nächsten Bäckerei je Wohngebäude, {coverageStats.reduce(
            (sum, s) => sum + s.count,
            0,
          )} Gebäude · ~4,8 km/h Gehtempo angenommen
        </p>
      {/if}
    </div>
  {/if}

  <div bind:this={mapContainer} class="h-full w-full"></div>
</div>

<style>
  :global(.leaflet-container) {
    background: var(--color-neutral-600);
  }
</style>
