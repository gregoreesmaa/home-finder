// Vector overlays for /layers: the source features each layer scores,
// drawn ABOVE the raster heatmap so it is obvious which places a layer
// prioritises. Parks keeps its polygon outlines (see outlines.ts); point
// layers reuse the already-fetched viewport points; density layers
// (walkability/pedinfra/cycling, which have no snapshot points) fetch a
// viewport-capped sample from the foot-graph sidecar via
// /api/layers/<layer>/overlay.

import type { BBoxLike, LayerId, LayerPoint } from "./layers";

/** One overlay marker: position + optional sizing weight. */
export interface OverlayPoint {
  lon: number;
  lat: number;
  /** Sizing weight (transit: GTFS weekday trips; parks: hectares; else 1). */
  w?: number;
}

/**
 * Render cap for markers (performance): the points path already clips to
 * the view tile server-side, but a Harju-wide transit tile still holds
 * ~8k stops — far too many for circle markers. Hubs-first for transit
 * (weight-sorted), deterministic stride samples otherwise.
 */
export const OVERLAY_CAP = 800;

/** Server-side cap mirror (Overpass `out center 2000` parity); clamped. */
export const OVERLAY_FETCH_CAP = 2000;

/** Density layers have no snapshot points file: they need the graph sidecar. */
export function needsGraphOverlay(layer: LayerId): boolean {
  return layer === "walkability" || layer === "pedinfra" || layer === "cycling";
}

/** Marker sizing weight for one feature point. */
export function overlayWeight(p: LayerPoint, layer: LayerId): number {
  if (layer === "transit") return p.t ?? 0;
  if (typeof p.a === "number") return p.a;
  return 1;
}

/**
 * Viewport points -> capped overlay markers. Finite coords only; transit
 * sorts hubs-first so the cap keeps the highest-trip stops, other layers
 * stride-sample (deterministic, keeps spatial spread).
 */
export function selectOverlayPoints(
  points: LayerPoint[],
  layer: LayerId,
  cap: number = OVERLAY_CAP,
): OverlayPoint[] {
  const valid = points.filter(
    (p) => Number.isFinite(p.lon) && Number.isFinite(p.lat),
  );
  if (layer === "transit") {
    return [...valid]
      .sort((a, b) => overlayWeight(b, layer) - overlayWeight(a, layer))
      .slice(0, Math.max(0, cap))
      .map((p) => ({ lon: p.lon, lat: p.lat, w: overlayWeight(p, layer) }));
  }
  if (valid.length <= cap || cap <= 0) {
    return (cap <= 0 ? [] : valid).map((p) => ({
      lon: p.lon,
      lat: p.lat,
      w: overlayWeight(p, layer),
    }));
  }
  const stride = valid.length / cap;
  const out: OverlayPoint[] = [];
  for (let i = 0; i < cap; i++) {
    const p = valid[Math.floor(i * stride)];
    out.push({ lon: p.lon, lat: p.lat, w: overlayWeight(p, layer) });
  }
  return out;
}

/** Marker core color per layer (white casing is added by the painter). */
export function overlayColorFor(layer: LayerId): string {
  switch (layer) {
    case "transit":
      return "#1d4ed8";
    case "schools":
      return "#9333ea";
    case "walkability":
      return "#0d9488";
    case "pedinfra":
      return "#65a30d";
    case "cycling":
      return "#0284c7";
    case "grocery":
      return "#d97706";
    case "healthcare":
      return "#e11d48";
    case "parks":
      return "#166534";
    // Batch B1 amenity layers (point overlays, stride-sampled like grocery).
    case "pets":
      return "#ea580c";
    case "community":
      return "#4f46e5";
    case "culture":
      return "#db2777";
    case "nightlife":
      return "#ca8a04";
    case "libraries":
      return "#92400e";
    // Batch B5 public-safety layers (point overlays, stride-sampled).
    case "safety":
      return "#dc2626";
    case "emergency":
      return "#f97316";
    case "hydrants":
      return "#0369a1";
    case "evac":
      return "#57534c";
    case "dispatch":
      return "#6b21a8";
    // Batch G07B env-health layers (point overlays, stride-sampled).
    case "brownsoil":
      return "#422006";
    case "oiltank":
      return "#334155";
    case "agriland":
      return "#84cc16";
    // G11D-HOOK (#135): leftover-B layers (point overlays, stride-sampled
    // like grocery; alley/trailprivacy plot their derived way samples).
    case "mailbox":
      return "#c2410c";
    case "postal":
      return "#2563eb";
    case "alley":
      return "#44403c";
    case "trailprivacy":
      return "#3f6212";
    // Batch G07D env-health layers (point overlays, stride-sampled).
    case "agrifield":
      return "#16a34a";
    case "wildcorr":
      return "#365314";
    // G07C-HOOK(#142): p257 habitat-edge samples (NOT #365314: sibling
    // wildcorr already owns that green; colors must stay distinct).
    case "vectorhabitat":
      return "#a21caf";
    // Group G06B heritage-leftover layers (point overlays, stride-sampled).
    case "plaster":
      return "#b45309";
    case "antiques":
      return "#0f766e";
    // woodfire marks mapped wooden houses = the risk SOURCES (red family
    // reads as danger origins; the raster stays green = safe).
    case "woodfire":
      return "#991b1b";
    // Batch G11C leftover-A layers (point overlays, stride-sampled).
    case "schoolbus":
      return "#0e7490";
    case "recspecial":
      return "#059669";
    case "medspecial":
      return "#9d174d";
    case "worship":
      return "#6d28d9";
    case "forage":
      return "#4d7c0f";
    // Batch B6 mobility/access layers (point overlays, stride-sampled).
    case "droneclear":
      return "#a16207";
    case "droneviab":
      return "#15803d";
    case "rentbleed":
      return "#be123c";
    // Batch G07 env-health layers (point overlays, stride-sampled).
    case "industprox":
      return "#155e75";
    case "odorsrc":
      return "#713f12";
    // Group G06 heritage layer (point overlay, stride-sampled).
    case "heritage":
      return "#7c2d12";
    // G02B-HOOK (#137): lift proxy (point overlay, stride-sampled).
    case "liftproxy":
      return "#0891b2";
    // G03-HOOK (#151): drainage proxy markers (point overlay,
    // stride-sampled like grocery). #1e40af: deep water blue, distinct
    // from liftproxy #0891b2 and every other marker (distinct-color test).
    case "drainage":
      return "#1e40af";
    // G03D-HOOK (#154): moorage + shoredist markers (point overlays,
    // stride-sampled like grocery). #0c4a6e: dark harbor blue (one
    // shade deeper than drainage #1e40af); #047857: emerald-700 shore
    // green (one shade deeper than recspecial #059669). Both distinct
    // from every other marker (distinct-color test).
    case "moorage":
      return "#0c4a6e";
    case "shoredist":
      return "#047857";
    // G08A-HOOK (#167): wildfire fuel-edge markers (point overlay,
    // stride-sampled like grocery). #9a3412: burnt orange (fire
    // association), distinct from woodfire #991b1b, forage #4d7c0f
    // and every other marker (distinct-color test).
    case "wildfire":
      return "#9a3412";
  }
}

/**
 * Legend line per layer: what the markers ARE plus the weight behind
 * them (same halves/bonuses as bonusSpecFor in layers.ts). Estonian.
 */
export function overlayLegendFor(layer: LayerId): string {
  switch (layer) {
    case "parks":
      return "Haljasalade piirid · sees loeb roheliseks (pindala küllastus 15 ha)";
    case "transit":
      return "Peatused · suurus = väljumisi tööpäevas (küllastus 1500, +10 kahe liigi puhul)";
    case "schools":
      return "Koolid ja lasteaiad · +12 punkti iga liigi eest (max +36)";
    case "walkability":
      return "Ristmikud (≥3 haru) · tihedus (küllastus 300)";
    case "pedinfra":
      return "Tänavavõrgu valim · alusvõrk, millele kõnniteede km tihedus arvutati (küllastus 12 km)";
    case "cycling":
      return "Tänavavõrgu valim · alusvõrk, millele rattateede km tihedus arvutati (küllastus 3 km)";
    case "grocery":
      return "Toidupoed · lähedaste poodide arv (küllastus 6)";
    case "healthcare":
      return "Apteegid ja arstid · lähedaste arv (küllastus 20)";
    // Batch B1 amenity layers: nearby-POI counts, saturating halves from
    // layers_batch1.ts B1_BONUS (same numbers as bonusSpecFor).
    case "pets":
      return "Koerapargid ja loomaarstid · lähedaste arv (küllastus 5,7)";
    case "community":
      return "Kogukonnaruumid · lähedaste arv (küllastus 3,3)";
    case "culture":
      return "Teatrid ja muuseumid · lähedaste arv (küllastus 4,5)";
    case "nightlife":
      return "Baarid ja kinod · lähedaste arv (küllastus 7,5)";
    case "libraries":
      return "Raamatukogud · lähedaste arv (küllastus 3)";
    // Batch B5 public-safety layers: nearby-POI counts, saturating halves
    // from layers_batch5.ts B5_BONUS (same numbers as bonusSpecFor).
    // Evac scores trunk/primary road-km density, hence the km unit.
    case "safety":
      return "Politseipunktid · lähedaste arv (hinnang, küllastus 1)";
    case "emergency":
      return "Päästekomandod ja haiglad · lähedaste arv (hinnang, küllastus 2)";
    case "hydrants":
      return "Tuletõrjehüdrandid · lähedaste arv (küllastus 6)";
    case "evac":
      return "Magistraalteede tihedus (hinnang, küllastus 2 km)";
    case "dispatch":
      return "Politsei/pääste/haigla · lähedaste arv (hinnang, küllastus 3)";
    // Batch G07B env-health layers: nearest-source distance, same halves
    // as g07bBonusSpecFor in layers_group07b.ts.
    case "brownsoil":
      return "Endised tööstusalad · kaugus lähima pruunväljani (hinnang, poolkaugus 500 m)";
    case "oiltank":
      return "Mahutid · kaugus lähima mahutini (hinnang, poolkaugus 500 m)";
    case "agriland":
      return "Põllud ja õued · kaugus lähima põlluni (hinnang, poolkaugus 800 m)";
    // G11D-HOOK (#135): leftover-B markers + weights (halves/bonuses from
    // layers_group11d.ts G11D_BONUS, same numbers as bonusSpecFor).
    case "mailbox":
      return "Postkastid · lähedaste arv (hinnang, küllastus 2,5)";
    case "postal":
      return "Postkontorid ja pakiautomaadid · lähedaste arv (küllastus 12)";
    case "alley":
      return "Taga-teede tihedus · teede km (küllastus 0,3 km)";
    case "trailprivacy":
      return "Matkaradade tihedus · teede km, PÖÖRATUD (privaatsus, poolväärtus 1500 m)";
    // Batch G07D env-health layers: nearest-source distance, same halves
    // as g07dBonusSpecFor in layers_group07d.ts.
    case "agrifield":
      return "Põllud, heinamaad ja kasvuhooned · kaugus lähima haritava maani (hinnang, poolkaugus 800 m)";
    case "wildcorr":
      return "Metsad, märgalad ja kaitsealad · kaugus lähima elupaigani (hinnang, poolkaugus 500 m)";
    // G07C-HOOK(#142): p257 elupaigaproksi — markerid on serva valim,
    // skoor tuleb kaugusest (poolkaugus 300 m).
    case "vectorhabitat":
      return "Puugi-/sääseelupaiga serv · mida kaugemal, seda rahulikum (proksi, hinnang, poolkaugus 300 m)";
    // Group G06B heritage-leftover layers: nearby-POI counts with halves
    // from layers_group06b.ts GROUP06B_BONUS (same numbers as
    // bonusSpecFor); woodfire is inverse (nearest-distance, pöördskaala).
    case "plaster":
      return "Krohvfassaadiga hooned · lähedaste arv (hinnang, küllastus 6)";
    case "antiques":
      return "Antiigipoed · lähedaste arv (hinnang, küllastus 1)";
    case "woodfire":
      return "Puidust hooned · lähim kaugus, pöördskaala (hinnang, poolväärtus 0,21 km)";
    // Batch G11C leftover-A layers: nearby-POI counts, saturating halves
    // from layers_group11c.ts G11C_BONUS (same numbers as bonusSpecFor).
    // Schoolbus is a hinnang proxy (stop-served schools, never a route).
    case "schoolbus":
      return "Peatusega koolid · lähedaste arv (hinnang, küllastus 4)";
    case "recspecial":
      return "Erispordipaigad · lähedaste arv (küllastus 8)";
    case "medspecial":
      return "Haiglad ja hambaarstid · lähedaste arv (küllastus 5)";
    case "worship":
      return "Pühakojad · lähedaste arv (küllastus 2,5)";
    case "forage":
      return "Metsaüksused · lähedaste arv (küllastus 12)";
    // Batch B6 mobility/access layers (p220/p270/p386): source features,
    // honestly labeled proksi/hinnang; halves from layers_batch6.ts
    // B6_CAL (same numbers as bonusSpecFor). droneviab dots mark the
    // airspace sites — the park yard leg lives raster-side only.
    case "droneclear":
      return "Lennuväljad ja helikopteriväljakud · kauguse-hinnang (proksi, mitte EANS DroneMap, küllastus 1300 m)";
    case "droneviab":
      return "Lennuväljad ja maandumisalad · min-hinnang (proksi, mitte EANS DroneMap, küllastus 800 m)";
    case "rentbleed":
      return "Ülikoolid, kolledžid ja ühiselamud · kauguse-hinnang (proksi, mitte üüriregister, küllastus 800 m)";
    // Batch G07 env-health layers: nearest-source distance, same halves
    // as g07BonusSpecFor in layers_group07.ts.
    case "industprox":
      return "Tööstusalad · kaugus lähima alani (hinnang, poolkaugus 500 m)";
    case "odorsrc":
      return "Reoveepuhastid ja prügilad · kaugus lähima allikani (hinnang, poolkaugus 500 m)";
    // Group G06 heritage layer: nearby-POI count, saturating half from
    // layers_group06.ts GROUP06_BONUS (same number as bonusSpecFor).
    case "heritage":
      return "Muinsusobjektid · lähedaste arv (hinnang, küllastus 2)";
    // G02B-HOOK (#137): lift proxy — nearby high-rise count, same half
    // as bonusSpecFor (see layers_group02b.ts G02B_BONUS).
    case "liftproxy":
      return "Kõrghooned (5+ korrust) · lähedaste arv (hinnang, küllastus 2)";
    // G03-HOOK (#151): drainage proxy (p50) — mapped source water, the
    // raster holds the full quietness field.
    case "drainage":
      return "Veekogud, rannajoon ja märgalad · kauguse-hinnang (drenaažiproksi, küllastus 300 m)";
    // G03D-HOOK (#154): moorage (p332) — mapped facilities, the raster
    // holds the full count field; shoredist (p340) — mapped shoreline,
    // the raster holds the full quietness field.
    case "moorage":
      return "Sadamad ja sildumiskohad · lähedaste arv (hinnang, küllastus 1, luba krundi-põhine)";
    case "shoredist":
      return "Rannajoon ja järved (jõed/märgalad välja) · kauguse-hinnang (ehituskeeluvööndi proksi, küllastus 100 m)";
    // G08A-HOOK (#167): wildfire (p69) — mapped fuel edges, the raster
    // holds the full quietness field.
    case "wildfire":
      return "Mets ja võsa (kütus, niit/soo välja) · kauguse-hinnang (tuleohutusproksi, küllastus 100 m)";
  }
}

function isOverlayPoint(p: unknown): p is OverlayPoint {
  const q = p as Partial<OverlayPoint>;
  return (
    typeof q?.lon === "number" &&
    typeof q?.lat === "number" &&
    Number.isFinite(q.lon) &&
    Number.isFinite(q.lat)
  );
}

function cleanWeight(w: unknown): number | undefined {
  if (typeof w !== "number" || !Number.isFinite(w) || w < 0) return undefined;
  return w;
}

/**
 * Density-layer overlay sample via our server proxy (foot-graph sidecar,
 * local 2026-09-12 snapshot). Null on any failure: the overlay is a
 * visual aid, never load-bearing — the raster stays.
 */
export async function fetchGraphOverlay(
  layer: LayerId,
  bbox: BBoxLike,
  cap: number = OVERLAY_CAP,
  fetchImpl: typeof fetch = fetch,
): Promise<OverlayPoint[] | null> {
  try {
    const q = new URLSearchParams({
      minlon: String(bbox.minlon),
      minlat: String(bbox.minlat),
      maxlon: String(bbox.maxlon),
      maxlat: String(bbox.maxlat),
      cap: String(Math.min(OVERLAY_FETCH_CAP, Math.max(1, Math.floor(cap)))),
    });
    const res = await fetchImpl(`/api/layers/${layer}/overlay?${q.toString()}`);
    if (!res.ok) return null;
    const body = (await res.json()) as { points?: unknown };
    if (!Array.isArray(body?.points)) return null;
    const out: OverlayPoint[] = [];
    for (const p of body.points) {
      if (!isOverlayPoint(p)) continue;
      const w = cleanWeight((p as { w?: unknown }).w);
      out.push(w === undefined ? { lon: p.lon, lat: p.lat } : { lon: p.lon, lat: p.lat, w });
    }
    return out;
  } catch {
    return null;
  }
}
