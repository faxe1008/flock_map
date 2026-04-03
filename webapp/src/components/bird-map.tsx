"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { GeoJSONSource, MapGeoJSONFeature } from "maplibre-gl";

type SightingRead = {
  id: number;
  species_id: number;
  observed_at: string;
  latitude: number;
  longitude: number;
  count: number;
};

type SpeciesRead = {
  id: number;
  common_name: string;
  scientific_name: string;
};

type LocationState = {
  latitude: number;
  longitude: number;
};

type ViewportBounds = {
  swLat: number;
  swLon: number;
  neLat: number;
  neLon: number;
};

type FetchWindow = {
  bounds: ViewportBounds;
  durationKey: string;
};

const DEFAULT_CENTER: [number, number] = [13.405, 52.52];
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

function isViewportCoveredByBounds(viewport: ViewportBounds, bounds: ViewportBounds): boolean {
  return (
    viewport.swLat >= bounds.swLat &&
    viewport.swLon >= bounds.swLon &&
    viewport.neLat <= bounds.neLat &&
    viewport.neLon <= bounds.neLon
  );
}

function clampLatitude(value: number): number {
  return Math.max(-90, Math.min(90, value));
}

function clampLongitude(value: number): number {
  return Math.max(-180, Math.min(180, value));
}

function expandBounds(bounds: ViewportBounds, ratio: number): ViewportBounds {
  const latSpan = Math.max(0.0001, bounds.neLat - bounds.swLat);
  const lonSpan = Math.max(0.0001, bounds.neLon - bounds.swLon);
  const latPad = latSpan * ratio;
  const lonPad = lonSpan * ratio;

  return {
    swLat: clampLatitude(bounds.swLat - latPad),
    swLon: clampLongitude(bounds.swLon - lonPad),
    neLat: clampLatitude(bounds.neLat + latPad),
    neLon: clampLongitude(bounds.neLon + lonPad),
  };
}

function formatObservedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown observation time";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function popupContent(feature: MapGeoJSONFeature): HTMLDivElement {
  const root = document.createElement("div");

  const title = document.createElement("p");
  title.className = "font-semibold text-sm";
  title.textContent = String(feature.properties?.commonName ?? "Unknown species");

  const latin = document.createElement("p");
  latin.className = "font-mono text-xs text-ink-muted";
  latin.textContent = String(feature.properties?.scientificName ?? "");

  const count = document.createElement("p");
  count.className = "mt-2 text-sm";
  count.textContent = `Count: ${String(feature.properties?.count ?? "n/a")}`;

  const observed = document.createElement("p");
  observed.className = "text-xs text-ink-muted";
  observed.textContent = `Observed: ${String(feature.properties?.observedAt ?? "n/a")}`;

  root.append(title, latin, count, observed);
  return root;
}

export function BirdMap() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const lastFetchWindowRef = useRef<FetchWindow | null>(null);

  const [location, setLocation] = useState<LocationState | null>(null);
  const [locationStatus, setLocationStatus] = useState<"idle" | "loading" | "ready" | "denied" | "error">("idle");
  const [locationError, setLocationError] = useState<string | null>(null);

  const [durationHours, setDurationHours] = useState("24");
  const [selectedSpeciesId, setSelectedSpeciesId] = useState("all");
  const [viewportBounds, setViewportBounds] = useState<ViewportBounds | null>(null);

  const [speciesCatalog, setSpeciesCatalog] = useState<SpeciesRead[]>([]);
  const [sightings, setSightings] = useState<SightingRead[]>([]);
  const [isLoadingSightings, setIsLoadingSightings] = useState(false);
  const [sightingsError, setSightingsError] = useState<string | null>(null);
  const [mapReady, setMapReady] = useState(false);

  const requestLocation = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setLocationStatus("error");
      setLocationError("Geolocation is not supported in this browser.");
      return;
    }

    setLocationStatus("loading");
    setLocationError(null);

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const nextLocation = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        };

        setLocation(nextLocation);
        setLocationStatus("ready");

        if (mapRef.current) {
          mapRef.current.flyTo({
            center: [nextLocation.longitude, nextLocation.latitude],
            zoom: 12.5,
            speed: 0.8,
          });
        }
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          setLocationStatus("denied");
          setLocationError("Location access was denied. Enable GPS permission to see nearby sightings.");
          return;
        }

        setLocationStatus("error");
        setLocationError("Could not determine your location. Please try again.");
      },
      {
        enableHighAccuracy: true,
        timeout: 12000,
        maximumAge: 120000,
      },
    );
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      requestLocation();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [requestLocation]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: location ? [location.longitude, location.latitude] : DEFAULT_CENTER,
      zoom: location ? 11 : 4,
      maxZoom: 18,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-left");

    const syncViewportBounds = () => {
      const currentBounds = map.getBounds();
      setViewportBounds({
        swLat: currentBounds.getSouth(),
        swLon: currentBounds.getWest(),
        neLat: currentBounds.getNorth(),
        neLon: currentBounds.getEast(),
      });
    };

    map.on("moveend", syncViewportBounds);

    map.on("load", () => {
      map.addSource("sightings", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: [],
        },
      });

      map.addLayer({
        id: "sightings-circle",
        type: "circle",
        source: "sightings",
        paint: {
          "circle-color": "#28654b",
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 4, 13, 8, 16, 11],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#fffdf6",
          "circle-opacity": 0.85,
        },
      });

      map.addLayer({
        id: "sightings-hit-area",
        type: "circle",
        source: "sightings",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 12, 13, 16, 16, 20],
          "circle-opacity": 0,
        },
      });

      map.addSource("user-location", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: [],
        },
      });

      map.addLayer({
        id: "user-location-ring",
        type: "circle",
        source: "user-location",
        paint: {
          "circle-radius": 14,
          "circle-color": "#2b8be6",
          "circle-opacity": 0.18,
        },
      });

      map.addLayer({
        id: "user-location-dot",
        type: "circle",
        source: "user-location",
        paint: {
          "circle-radius": 6,
          "circle-color": "#2b8be6",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      map.on("mouseenter", "sightings-hit-area", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "sightings-hit-area", () => {
        map.getCanvas().style.cursor = "";
      });

      map.on("click", "sightings-hit-area", (event) => {
        const feature = event.features?.[0] as MapGeoJSONFeature | undefined;
        if (!feature || !feature.geometry || feature.geometry.type !== "Point") {
          return;
        }

        const [lng, lat] = feature.geometry.coordinates;

        if (popupRef.current) {
          popupRef.current.remove();
        }

        popupRef.current = new maplibregl.Popup({ closeButton: true, closeOnMove: true })
          .setLngLat([lng, lat])
          .setDOMContent(popupContent(feature))
          .addTo(map);
      });

      syncViewportBounds();
      setMapReady(true);
    });

    mapRef.current = map;

    return () => {
      popupRef.current?.remove();
      map.remove();
      mapRef.current = null;
      setMapReady(false);
    };
  }, [location]);

  useEffect(() => {
    const fetchSpecies = async () => {
      const response = await fetch("/api/species?limit=500", { cache: "no-store" });
      if (!response.ok) {
        throw new Error("Unable to load species catalog.");
      }

      const payload = (await response.json()) as SpeciesRead[];
      setSpeciesCatalog(payload);
    };

    fetchSpecies().catch(() => {
      setSpeciesCatalog([]);
    });
  }, []);

  useEffect(() => {
    if (!viewportBounds) {
      return;
    }

    const controller = new AbortController();

    const loadSightings = async () => {
      const lastFetchWindow = lastFetchWindowRef.current;
      const durationMatches = lastFetchWindow?.durationKey === durationHours;
      const viewportCovered = lastFetchWindow
        ? isViewportCoveredByBounds(viewportBounds, lastFetchWindow.bounds)
        : false;

      if (durationMatches && viewportCovered) {
        return;
      }

      setIsLoadingSightings(true);
      setSightingsError(null);

      const requestBounds = expandBounds(viewportBounds, 0.35);

      const params = new URLSearchParams({
        sw_lat: String(requestBounds.swLat),
        sw_lon: String(requestBounds.swLon),
        ne_lat: String(requestBounds.neLat),
        ne_lon: String(requestBounds.neLon),
        limit: "500",
      });

      if (durationHours !== "all") {
        params.set("duration_seconds", String(Number(durationHours) * 3600));
      }

      const response = await fetch(`/api/sightings/viewport?${params.toString()}`, {
        signal: controller.signal,
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error("Unable to load sightings.");
      }

      const payload = (await response.json()) as SightingRead[];
      setSightings(payload);
      lastFetchWindowRef.current = {
        bounds: requestBounds,
        durationKey: durationHours,
      };
    };

    loadSightings()
      .catch((error: unknown) => {
        if ((error as Error).name !== "AbortError") {
          setSightingsError("Could not load sightings in this map area. Check that the API is running.");
          setSightings([]);
        }
      })
      .finally(() => {
        setIsLoadingSightings(false);
      });

    return () => {
      controller.abort();
    };
  }, [viewportBounds, durationHours]);

  const speciesById = useMemo(() => {
    return new Map(speciesCatalog.map((species) => [species.id, species]));
  }, [speciesCatalog]);

  const filteredSightings = useMemo(() => {
    if (selectedSpeciesId === "all") {
      return sightings;
    }

    const speciesId = Number(selectedSpeciesId);
    return sightings.filter((sighting) => sighting.species_id === speciesId);
  }, [selectedSpeciesId, sightings]);

  const speciesOptions = useMemo(() => {
    return [...speciesCatalog].sort((left, right) => {
      return left.common_name.localeCompare(right.common_name);
    });
  }, [speciesCatalog]);

  const mapGeoJson = useMemo(() => {
    return {
      type: "FeatureCollection" as const,
      features: filteredSightings.map((sighting) => {
        const species = speciesById.get(sighting.species_id);

        return {
          type: "Feature" as const,
          geometry: {
            type: "Point" as const,
            coordinates: [sighting.longitude, sighting.latitude],
          },
          properties: {
            id: sighting.id,
            commonName: species?.common_name ?? `Species #${sighting.species_id}`,
            scientificName: species?.scientific_name ?? "",
            count: sighting.count,
            observedAt: formatObservedAt(sighting.observed_at),
          },
        };
      }),
    };
  }, [filteredSightings, speciesById]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !map.isStyleLoaded()) {
      return;
    }

    const sightingsSource = map.getSource("sightings") as GeoJSONSource | undefined;
    if (sightingsSource) {
      sightingsSource.setData(mapGeoJson);
    }
  }, [mapGeoJson, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !location || !mapReady || !map.isStyleLoaded()) {
      return;
    }

    const userSource = map.getSource("user-location") as GeoJSONSource | undefined;
    if (!userSource) {
      return;
    }

    userSource.setData({
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [location.longitude, location.latitude],
          },
          properties: {},
        },
      ],
    });
  }, [location, mapReady]);

  const locationBadge =
    locationStatus === "loading"
      ? "Requesting location..."
      : locationStatus === "ready"
        ? "Location active"
        : locationStatus === "denied"
          ? "Location denied"
          : "Location unavailable";

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#eaf2ee_0%,_#f6f3ea_45%,_#f6f3ea_100%)] text-ink">
      <div className="mx-auto flex min-h-screen w-full max-w-md flex-col px-3 py-4 sm:max-w-2xl sm:px-5">
        <header className="rise-in rounded-2xl border border-border/60 bg-surface/90 px-4 py-3 shadow-[0_10px_30px_rgba(25,45,35,0.08)] backdrop-blur-sm">
          <p className="text-xs font-mono uppercase tracking-[0.2em] text-ink-muted">FlockMap</p>
          <h1 className="mt-1 text-2xl font-semibold leading-tight">Nearby Bird Sightings</h1>
          <p className="mt-1 text-sm text-ink-muted">Mobile-first live map powered by your current location.</p>
        </header>

        <section className="rise-in relative mt-3 overflow-hidden rounded-2xl border border-border bg-surface shadow-[0_18px_40px_rgba(25,45,35,0.14)]">
          <div ref={containerRef} className="h-[52dvh] min-h-[360px] w-full sm:h-[64dvh]" />

          <div className="pointer-events-none absolute left-3 top-3 flex flex-col gap-2">
            <span className="inline-flex rounded-full border border-border/80 bg-surface/95 px-3 py-1 text-xs text-ink-muted shadow-sm">
              {locationBadge}
            </span>
            {isLoadingSightings ? (
              <span className="inline-flex rounded-full border border-accent/35 bg-accent-soft/95 px-3 py-1 text-xs text-accent shadow-sm">
                Updating sightings...
              </span>
            ) : null}
          </div>

          <button
            type="button"
            onClick={requestLocation}
            className="absolute bottom-3 right-3 rounded-full border border-accent/30 bg-accent px-4 py-2 text-sm font-medium text-white shadow-lg transition active:scale-95"
          >
            Recenter
          </button>
        </section>

        <section className="rise-in mt-3 rounded-2xl border border-border/80 bg-surface/95 p-4 shadow-[0_12px_30px_rgba(25,45,35,0.1)]">
          <label htmlFor="species" className="text-sm font-medium text-ink">
            Species
          </label>
          <select
            id="species"
            value={selectedSpeciesId}
            onChange={(event) => {
              setSelectedSpeciesId(event.target.value);
            }}
            className="mt-2 w-full rounded-xl border border-border bg-white px-3 py-2.5 text-base text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20"
          >
            <option value="all">All species</option>
            {speciesOptions.map((species) => {
              return (
                <option key={species.id} value={String(species.id)}>
                  {species.common_name} ({species.scientific_name})
                </option>
              );
            })}
          </select>

          <div className="mt-4">
            <label htmlFor="timeframe" className="text-sm font-medium text-ink">
              Time range
            </label>
            <select
              id="timeframe"
              value={durationHours}
              onChange={(event) => {
                setDurationHours(event.target.value);
              }}
              className="mt-2 w-full rounded-xl border border-border bg-white px-3 py-2.5 text-base text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20"
            >
              <option value="6">Last 6 hours</option>
              <option value="24">Last 24 hours</option>
              <option value="72">Last 3 days</option>
              <option value="168">Last 7 days</option>
              <option value="all">All available</option>
            </select>
          </div>

          <div className="mt-4 flex items-center justify-between rounded-xl bg-accent-soft/70 px-3 py-2 text-sm">
            <span className="text-ink-muted">Visible sightings</span>
            <span className="font-semibold text-accent">{filteredSightings.length}</span>
          </div>

          {locationError ? <p className="mt-3 text-sm text-danger">{locationError}</p> : null}
          {sightingsError ? <p className="mt-2 text-sm text-danger">{sightingsError}</p> : null}
        </section>
      </div>
    </main>
  );
}
