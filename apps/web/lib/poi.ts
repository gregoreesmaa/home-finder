// Buyer-defined points of interest (#74): workplace, school, etc.
//
// A POI never overrides generic scoring (school proximity still scores in
// the schools dim); it adds a separate, labelled travel-time badge per
// listing computed client-side from stored coordinates. Speeds mirror
// services/scoring/livability.py (documented estimates, bird-flight).

export interface Poi {
  lat: number;
  lon: number;
  label: string;
}

/** km/h estimates — must match livability.py SPEED_* constants. */
export const POI_SPEEDS = { walk: 4.5, bike: 15.0, car: 35.0 } as const;

export type PoiMode = keyof typeof POI_SPEEDS;

export function haversineKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const r = 6371;
  const dLa = ((bLat - aLat) * Math.PI) / 180;
  const dLo = ((bLon - aLon) * Math.PI) / 180;
  const la1 = (aLat * Math.PI) / 180;
  const la2 = (bLat * Math.PI) / 180;
  const h =
    Math.sin(dLa / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLo / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}

/** Estimated minutes per mode, or null when the listing has no coords. */
export function poiMinutes(
  lat: number | null | undefined,
  lon: number | null | undefined,
  poi: Poi,
): Record<PoiMode, number> | null {
  if (typeof lat !== "number" || typeof lon !== "number") return null;
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  const km = haversineKm(lat, lon, poi.lat, poi.lon);
  return {
    walk: Math.round((km / POI_SPEEDS.walk) * 60),
    bike: Math.round((km / POI_SPEEDS.bike) * 60),
    car: Math.round((km / POI_SPEEDS.car) * 60),
  };
}

const MODE_ET: Record<PoiMode, string> = { walk: "jalgsi", bike: "rattaga", car: "autoga" };

/**
 * One badge line per POI, e.g. "Töö · autoga ~18 min".
 * Walk time joins when walkable (<= 45 min) so nearby options read locator-local.
 */
export function poiBadge(
  lat: number | null | undefined,
  lon: number | null | undefined,
  poi: Poi,
): string | null {
  const m = poiMinutes(lat, lon, poi);
  if (!m) return null;
  let s = `${poi.label} · ${MODE_ET.car} ~${m.car} min`;
  if (m.walk <= 45) s += ` · ${MODE_ET.walk} ~${m.walk} min`;
  return s;
}

/** Parse repeated `?poi=lat,lon,label` params (label may contain commas). */
export function parsePois(search: URLSearchParams): Poi[] {
  const out: Poi[] = [];
  for (const raw of search.getAll("poi")) {
    const [la, lo, ...rest] = raw.split(",");
    const lat = Number(la);
    const lon = Number(lo);
    const label = rest.join(",").trim();
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) continue;
    if (!label) continue;
    out.push({ lat, lon, label });
  }
  return out.slice(0, 5); // cap: URL-shared, keep it short
}

/** Serialize POIs back to URL params (skips invalid entries). */
export function poisToParams(pois: Poi[]): string[] {
  return pois
    .filter(
      (p) =>
        Number.isFinite(p.lat) &&
        Number.isFinite(p.lon) &&
        p.label.trim().length > 0,
    )
    .slice(0, 5)
    .map((p) => `${p.lat},${p.lon},${p.label}`);
}
