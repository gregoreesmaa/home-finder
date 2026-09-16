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
  // GTFS-HOOK (#483): gtfsstops markers size by scheduled Wednesday
  // departures; mapped-only Elron stations (no t) read 1, never 0.
  if (layer === "gtfsstops") return p.t ?? 1;
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
    // G08D-HOOK (#170): vernalpool markers (point overlay,
    // stride-sampled like grocery). #475569: murky-pond slate (one
    // shade lighter than oiltank #334155, grayer than evac #57534c).
    // Distinct from every other marker (distinct-color test).
    case "vernalpool":
      return "#475569";
    // G08C-HOOK (#169): surgeroad + slidebuf markers (point overlays,
    // stride-sampled like grocery). #64748b: slate storm gray (surge
    // sky; NOT #475569 — taken by vernalpool — distinct from alley
    // #44403c and evac #57534c); #78716c: stone cliff gray (distinct
    // from plaster #b45309 and every other marker — distinct-color
    // test).
    case "surgeroad":
      return "#64748b";
    case "slidebuf":
      return "#78716c";
    // G08B-HOOK (#168): windtunnel + saltspray markers (point overlays,
    // stride-sampled like grocery). #71717a: zinc concrete (towers; NOT
    // #475569 — taken by vernalpool); #0ea5e9: sky-500 spray. Both
    // distinct from every other marker (distinct-color test).
    case "windtunnel":
      return "#71717a";
    case "saltspray":
      return "#0ea5e9";
    // G05B-HOOK (#162): gardens + buildout markers (point overlays,
    // stride-sampled like grocery). #4ade80: fresh sprout green
    // (lighter than agrifield #16a34a, yellower than agriland
    // #84cc16); #eab308: caution-tape yellow (construction; warmer
    // than evac #57534c, distinct from hydrants #0369a1). Both
    // distinct from every other marker (distinct-color test).
    case "gardens":
      return "#4ade80";
    case "buildout":
      return "#eab308";
    // G05D-HOOK (#164): strsat marker (point overlay, stride-sampled
    // like grocery). #e879f9: fuchsia-400 neon hospitality pink (guest
    // turnover; NOT #db2777 — taken by culture — and NOT #a21caf —
    // taken by vectorhabitat). Distinct from every other marker
    // (distinct-color test).
    case "strsat":
      return "#e879f9";
    // G05A-HOOK (#161): ehitus + korterstock markers (point overlays,
    // stride-sampled like grocery). #fbbf24: amber construction-sign
    // (cranes); #f9a8d4: soft pink housing (rental stock; NOT #e879f9 —
    // taken by strsat). Both distinct from every other marker
    // (distinct-color test).
    case "ehitus":
      return "#fbbf24";
    case "korterstock":
      return "#f9a8d4";
    // G05C-HOOK (#163): commbleed + windsolar + viewshed markers (point
    // overlays, stride-sampled like grocery). #7e22ce: purple-700 neon
    // (retail glow); #facc15: yellow-400 solar (NOT #eab308 — taken by
    // buildout); #f43f5e: rose-500 scenic. All distinct from every
    // other marker (distinct-color test).
    case "commbleed":
      return "#7e22ce";
    case "windsolar":
      return "#facc15";
    case "viewshed":
      return "#f43f5e";
    // G05E-HOOK (#165): equestrian marker (point overlay,
    // stride-sampled like grocery). #8b4513: saddle brown (stables;
    // NOT #92400e — taken by libraries — and NOT #713f12/#7c2d12 —
    // taken by other batches). Distinct from every other marker
    // (distinct-color test).
    case "equestrian":
      return "#8b4513";
    // G05F-HOOK (#166): upcycle marker (point overlay, stride-sampled
    // like grocery). #2dd4bf: verdigris teal (weathered copper on
    // derelict roofs; lighter than walkability #0d9488, antiques
    // #0f766e, schoolbus #0e7490 and liftproxy #0891b2). Distinct
    // from every other marker (distinct-color test).
    case "upcycle":
      return "#2dd4bf";
    // G10R-HOOK (#171): skyview marker (point overlay, stride-sampled
    // like grocery). #7dd3fc: sky-300 open-sky blue (the saturated
    // blues #0ea5e9/#0284c7/#2563eb are taken by earlier layers).
    // Distinct from every other marker (distinct-color test).
    case "skyview":
      return "#7dd3fc";
    // G18A-HOOK (#172): dayopen + glassglare markers (point overlays,
    // stride-sampled like grocery). #38bdf6: sky-400 daylight (NOT
    // #0ea5e9 — taken by saltspray — and NOT #0284c7 — taken by
    // cycling); #fb7185: rose-400 glare flash (NOT #f43f5e — taken by
    // viewshed — and NOT #e11d48 — taken by healthcare). Both distinct
    // from every other marker (distinct-color test).
    case "dayopen":
      return "#38bdf6";
    case "glassglare":
      return "#fb7185";
    // G18B-HOOK (#173): fishbowl + mossrisk + daylight markers (point
    // overlays, stride-sampled like grocery). #0f172a: slate-900 asphalt
    // (street corners; NOT #334155 oiltank / #475569 saltspray / #64748b
    // slidebuf — the darkest slate, clearly separated); #052e16:
    // green-950 deep moss shade (forest stands; NOT #166534 parks /
    // #365314 trailprivacy — the darkest green); #67e8f9: cyan-300
    // morning sky (daylight; NOT #0ea5e9 saltspray sky-500 — clearly
    // lighter). All distinct from every other marker (distinct-color test).
    case "fishbowl":
      return "#0f172a";
    case "mossrisk":
      return "#052e16";
    case "daylight":
      return "#67e8f9";
    // G17A-HOOK (#177): compost + gritbin + leafdrop markers (point
    // overlays, stride-sampled like grocery). #a3e635: lime-400 compost
    // green (NOT #84cc16 — taken by agriland — and NOT #4ade80 — taken
    // by gardens); #a8a29e: stone-400 galvanized metal (grit bins; NOT
    // #7dd3fc — taken by skyview); #fb923c: orange-400 autumn leaf (NOT
    // #ea580c — taken by culture — and NOT #f97316 — taken by dispatch).
    // All distinct from every other marker (distinct-color test).
    case "compost":
      return "#a3e635";
    case "gritbin":
      return "#a8a29e";
    case "leafdrop":
      return "#fb923c";
    // G17B-HOOK (#178): lawncare marker (point overlay,
    // stride-sampled like grocery). #bef264: lime-200 fresh-cut grass
    // (NOT #a3e635 — taken by compost — and NOT #4ade80 — taken by
    // gardens — and NOT #84cc16 — taken by agriland). Distinct from
    // every other marker (distinct-color test).
    case "lawncare":
      return "#bef264";
    // G17R-HOOK (#196): privroad marker (point overlay,
    // stride-sampled like grocery). #d4a373: sandy gravel tan (dirt
    // eratee; NOT #b45309 — taken by plaster — and NOT #fbbf24 —
    // taken by ehitus — and NOT #92400e — taken by libraries).
    // Distinct from every other marker (distinct-color test).
    case "privroad":
      return "#d4a373";
    // B10C-HOOK (#230): utility markers (point overlays, stride-sampled
    // like grocery). #075985: sky-800 deep tap-water blue (NOT #0c4a6e
    // — taken by moorage — and NOT #0369a1 — taken by hydrants);
    // #14532d: green-900 dark recycling green (NOT #3f6212 — taken by
    // trailprivacy — and NOT #166534 — taken by parks); #164e63:
    // cyan-950 fiber-optic teal (NOT #155e75 — taken by industprox —
    // and NOT #0e7490 — taken by schoolbus); #831843: pink-900
    // crowdsource magenta (measurement sites, never masts). All
    // distinct from every other marker (distinct-color test).
    // P4-031-HOOK (#484): senscom marker (point overlay,
    // stride-sampled like grocery). #06b6d4: cyan-500 breathing air
    // (NOT #0ea5e9 — taken by saltspray — and NOT #0284c7 — taken by
    // cycling — and NOT #0d9488/#0f766e/#0e7490/#0891b2 — taken by
    // walkability/antiques/schoolbus/liftproxy). Distinct from every
    // other marker (distinct-color test).
    case "senscom":
      return "#06b6d4";
    // OOKLA-HOOK (#489): ookla tile markers (point overlay,
    // stride-sampled like grocery). #172554: blue-950 wired broadband
    // (NOT #1e3a8a — taken by floodzone on main #487 — and NOT
    // #1e40af — taken by drainage — and NOT #1d4ed8 — taken by
    // transit); #be185d: pink-700 airwaves mobile
    // (NOT #be123c — taken — and NOT #9d174d — and NOT #db2777 —
    // taken by culture — and NOT #ec4899 — taken by activity).
    // Distinct from every other marker (distinct-color test).
    case "ookla_fixed":
      return "#172554";
    case "ookla_mobile":
      return "#be185d";
    case "water":
      return "#075985";
    case "waste":
      return "#14532d";
    case "fiber":
      return "#164e63";
    case "mobile":
      return "#831843";
    // OSMDAILY-HOOK (#482): daily-life markers (point overlays,
    // stride-sampled like grocery). #f59e0b: amber-500 market basket
    // (NOT #d97706 — taken by grocery — and NOT #fbbf24 — taken by
    // ehitus); #ec4899: pink-500 evening buzz (NOT #db2777 — taken by
    // culture — and NOT #f43f5e); #7c3aed: violet-600 gallery wall
    // (NOT #9333ea — taken by schools — and NOT #6d28d9); #b91c1c:
    // red-700 cafe hearth (NOT #dc2626 — taken by safety — and NOT
    // #991b1b); #1e293b: slate-800 doorstep key (NOT #0f172a — taken
    // by fishbowl — and NOT #334155); #854d0e: yellow-900 fringe
    // warning (NOT #713f12 — and NOT #a16207). All distinct from every
    // other marker (distinct-color test).
    case "dailyshop":
      return "#f59e0b";
    case "activity":
      return "#ec4899";
    case "herd":
      return "#7c3aed";
    case "thirdplace":
      return "#b91c1c";
    case "taxidoor":
      return "#1e293b";
    case "lastshop":
      return "#854d0e";
    // GTFS-HOOK (#483): gtfsstops markers (point overlay, stride-sampled
    // like grocery). #8b5cf6: violet-500 schedule-board violet (lighter
    // than herd #7c3aed; NOT #6d28d9 — taken by worship — and NOT
    // #9333ea — taken by schools — and NOT #7e22ce — taken by commbleed
    // — and NOT #4f46e5 — taken by community). Distinct from every
    // other marker (distinct-color test).
    case "gtfsstops":
      return "#8b5cf6";
    // RSAFE-HOOK (#481): roadsafety marker (point overlay,
    // stride-sampled like grocery). #fde047: yellow-400 zebra-crossing
    // paint (NOT #facc15 — taken — and NOT #fbbf24 — taken by ehitus —
    // and NOT #eab308 — taken). Distinct from every other marker
    // (distinct-color test).
    case "roadsafety":
      return "#fde047";
    // ACCBLACK-HOOK (#490): accblack marker (measured blackspots, none
    // plotted yet). #7f1d1d: red-900 crash red (NOT #b91c1c / #991b1b /
    // #881337 / #be123c / #dc2626 — all taken). Distinct from every
    // other marker (distinct-color test).
    case "accblack":
      return "#7f1d1d";
    // STATKOV-HOOK (#485): choropleth colors (registry contract --
    // these layers are raster-only exact fills with NO point markers,
    // so the overlay slot stays empty and the toggle reads (0); the
    // raster holds the full field). #3b82f6: blue-500 migration tide (NOT
    // #1d4ed8 -- taken by transit -- and NOT #0284c7 -- taken by
    // cycling); #d946ef: fuchsia-500 construction crane (NOT #ec4899 --
    // sibling #482 activity -- and NOT #e879f9 -- taken by strsat);
    // #14b8a6: teal-500 ledger ink (NOT #0d9488 -- taken by walkability
    // -- and NOT #2dd4bf -- taken by upcycle). All distinct from every
    // other marker (distinct-color test).
    case "kovmigr":
      return "#3b82f6";
    case "kovehit":
      return "#d946ef";
    case "kovfisc":
      return "#14b8a6";
    // P4PARK-HOOK (#479): parking marker (point overlay,
    // stride-sampled like grocery). #1f2937: gray-800 asphalt (NOT
    // #0f172a — taken by fishbowl — and NOT #334155 — taken by
    // oiltank — and NOT #475569 — taken by vernalpool). Distinct
    // from every other marker (distinct-color test).
    case "parking":
      return "#1f2937";
    // MARUKOV-HOOK (#486): choropleth colors (registry contract --
    // these layers are raster-only exact fills with NO point markers,
    // so the overlay slot stays empty and the toggle reads (0); the
    // raster holds the full field). #22c55e: green-500 new-growth
    // green (NOT #16a34a -- taken by agrifield -- and NOT #4ade80 --
    // taken by gardens); #6366f1: indigo-500 ledger-flow indigo (NOT
    // #4f46e5 -- taken by community); #a855f7: purple-500 resale
    // purple (NOT #9333ea -- taken by schools -- and NOT #7c3aed --
    // taken by herd -- and NOT #8b5cf6 -- taken by gtfsstops);
    // #ef4444: red-500 market-pulse red (NOT #dc2626 -- taken by
    // safety -- and NOT #f43f5e; NOT #06b6d4 -- taken by senscom).
    // All distinct from every other marker (distinct-color test).
    case "kovkasv":
      return "#22c55e";
    case "kovkaive":
      return "#6366f1";
    case "kovedas":
      return "#a855f7";
    case "kovkiirus":
      return "#ef4444";
    // FLOOD-HOOK (#487): floodzone polygon fill (choropleth, never a
    // gradient). #1e3a8a: blue-900 deep flood water (NOT #1e40af —
    // taken by drainage — and NOT #0c4a6e — taken by moorage — and NOT
    // #0ea5e9 — taken by saltspray — and NOT #7dd3fc — taken by
    // skyview — and NOT #3b82f6 — taken by kovmigr). Distinct from
    // every other marker (distinct-color test).
    case "floodzone":
      return "#1e3a8a";
    // P4OSM-HOOK (#480): walkability + darkness markers (point overlays,
    // stride-sampled like grocery). #78350f: amber-900 trodden-sidewalk
    // ochre (NOT #92400e — taken by libraries — and NOT #713f12/#7c2d12
    // — taken by other batches); #312e81: indigo-900 December night
    // (NOT #1e40af/#1d4ed8 — taken by earlier layers — and NOT #0f172a
    // — taken by vectorhabitat). Both distinct from every other marker
    // (distinct-color test).
    case "blockwalk":
      return "#78350f";
    case "darkness":
      return "#312e81";

    // MAAPARCEL-HOOK (#491): maaparcel polygon casing (omandivorm-class
    // choropleth, never a gradient). #701a75: fuchsia-900 cadastral
    // purple (NOT #a21caf — taken by plaster — and NOT #d946ef — taken
    // by kovehit — and NOT #e879f9 — taken by strsat). Distinct from
    // every other marker (distinct-color test).
    case "maaparcel":
      return "#701a75";

    // EELIS-HOOK (#488): nature-polygon fills (choropleths, never a
    // gradient). #1a2e05: lime-950 deep reserve green (NOT #365314 --
    // taken by wildcorr -- and NOT #3f6212 -- taken by trailprivacy);
    // #10b981: emerald-500 meadow (NOT #22c55e — taken by kovkasv on
    // main #486 — and NOT #16a34a -- taken by agrifield -- and NOT
    // #4ade80 -- taken by lastshop); #9c4221: orange-800 stump brown
    // (NOT #78350f — taken by blockwalk on main #480 — and NOT
    // #92400e -- taken by libraries -- and NOT #713f12 -- taken by
    // odorsrc). All distinct from every other marker
    // (distinct-color test).
    case "eeliskaitse":
      return "#1a2e05";
    case "eelisniit":
      return "#10b981";
    case "eelisraie":
      return "#9c4221";

    // PLANKTPR-HOOK (#492): planktpr marker (polygon layer — the point
    // overlay stays empty live, so this colors only the toggle dot).
    // #4c1d95: violet-900 decree ink (NOT #312e81 — taken by darkness
    // on main #480 — and NOT #4f46e5 — taken by community — and NOT
    // #6b21a8 — taken by dispatch; darker value than both, and layers
    // never co-render). Distinct from every other marker
    // (distinct-color test).
    case "planktpr":
      return "#4c1d95";
    // TERVISE-HOOK (#494): tervise marker (point overlay,
    // stride-sampled like grocery). #34d399: emerald-400 lagoon water
    // (NOT #059669 — taken — and NOT #06b6d4 — taken by senscom — and
    // NOT #2dd4bf — taken by upcycle — and NOT #14b8a6 — taken by
    // kovehit — and NOT #0d9488 — taken by walkability). Distinct from
    // every other marker (distinct-color test).
    case "tervise":
      return "#34d399";
    // SPORT-HOOK (#607): sport slice markers (point overlays,
    // stride-sampled like grocery). #c4b5fd: violet-300 hall lights
    // (NOT #a78bfa/#8b5cf6 — taken by nearby violets — and NOT
    // #ddd6fe); #86efac: green-300 turf (NOT #4ade80/#22c55e/#16a34a
    // — taken — and NOT #bef264 — taken); #bae6fd: sky-200 pool water
    // (NOT #7dd3fc/#38bdf8/#0ea5e9 — taken — and NOT #e0f2fe).
    // Distinct from every other marker (distinct-color test).
    case "sport_hall":
      return "#c4b5fd";
    case "sport_field":
      return "#86efac";
    case "sport_pool":
      return "#bae6fd";
    // EHIS-HOOK (#608): ehis slice markers (point overlays,
    // stride-sampled like grocery). #c7d2fe: indigo-200 schoolbook
    // (NOT #c4b5fd — taken by sport_hall); #fbcfe8: pink-200
    // kindergarten (NOT #fda4af — taken by asumedia); #a5f3fc:
    // cyan-200 hobby (NOT #67e8f9 — taken — and NOT #bae6fd — taken
    // by sport_pool). Distinct from every other marker
    // (distinct-color test).
    case "ehis_school":
      return "#c7d2fe";
    case "ehis_kindergarten":
      return "#fbcfe8";
    case "ehis_hobby":
      return "#a5f3fc";
    // KLIIMA-HOOK (#611): kliima slice markers (point overlays,
    // stride-sampled like grocery). #e0f2fe: sky-100 station ice
    // (NOT #bae6fd — taken by sport_pool — and NOT #f0f9ff — near
    // white, invisible dot); #fef3c7: amber-100 dry hay for the
    // dryness slice (NOT #ffedd5 — taken by medre_gp — and NOT
    // #fde047/#fbbf24 — taken). Distinct from every other marker
    // (distinct-color test).
    case "kliima_frost":
      return "#e0f2fe";
    case "kliima_wet":
      return "#fef3c7";
    // FIXIT-HOOK (#623): fixit pin marker (point overlay,
    // stride-sampled like grocery). #fdba74: orange-300 notice pin
    // (NOT #fb923c/#f97316 — taken). Distinct from every other marker
    // (distinct-color test).
    case "fixit":
      return "#fdba74";
    // SEVESO-HOOK (#613): seveso marker (polygon layer — the point
    // overlay stays empty live, so this colors only the toggle dot).
    // #3b0764: purple-950 hazard violet (NOT #4c1d95 — taken by
    // planktpr — and NOT #6b21a8/#7e22ce — taken; darkest violet of
    // the three, and layers never co-render). Distinct from every
    // other marker (distinct-color test).
    case "seveso":
      return "#3b0764";
    // MEDRE-HOOK (#609): medre slice markers (Step-1 honest-empty —
    // the point overlay stays empty live, so this colors only the
    // toggle dot). #ffedd5: orange-100 clinic paper; #ede9fe:
    // violet-100 care card (NOT #c4b5fd — taken by sport_hall).
    // Distinct from every other marker (distinct-color test).
    case "medre_gp":
      return "#ffedd5";
    case "medre_clinic":
      return "#ede9fe";
    // OHUSEIRE-HOOK (#610): station marker (thin point overlay,
    // stride-sampled like grocery). #94a3b8: slate-400 inlet steel
    // (verified free 2026-09-16 — no other marker uses it). Distinct
    // from every other marker (distinct-color test).
    case "ohuseire":
      return "#94a3b8";
    // POI-HOOK (#612): long-tail slice markers (point overlays,
    // stride-sampled like grocery). #d8b4fe: purple-300 book spines;
    // #fde68a: amber-200 mailbox yellow; #bbf7d0: green-200 pharmacy
    // cross (NOT #e0f2fe/#fef3c7 — reserved by kliima #611 — and NOT
    // #c4b5fd/#fbbf24/#4ade80 — taken). Distinct from every other
    // marker (distinct-color test).
    case "poi_library":
      return "#d8b4fe";
    case "poi_post":
      return "#fde68a";
    case "poi_pharmacy":
      return "#bbf7d0";
    // ASUMEDIA-HOOK (#495): asumedia marker (empty-on-purpose layer —
    // the point overlay stays empty live, so this colors only the
    // toggle dot). #fda4af: rose-300 asking-price blush (NOT #fb7185
    // — taken by glassglare — and NOT #f9a8d4 — taken by korterstock
    // — and NOT #be123c — taken by rentbleed; lighter value than all,
    // and layers never co-render). Distinct from every other marker
    // (distinct-color test).
    case "asumedia":
      return "#fda4af";
    // PAASTE-HOOK (#493): paaste markers (honest-empty point overlay,
    // stride-sampled like grocery — today zero markers). #450a0a:
    // red-950 deep ember (NOT #7f1d1d — taken by accblack on main #490,
    // merge-order precedent — and NOT #b91c1c — taken by thirdplace —
    // and NOT #dc2626 — taken by safety — and NOT #ef4444 — taken by
    // kovkiirus — and NOT #991b1b — taken). Distinct from every other
    // marker (distinct-color test).
    case "paaste":
      return "#450a0a";
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
    // G08D-HOOK (#170): vernalpool (p447) — mapped ephemeral ponds,
    // the raster holds the full quietness field.
    case "vernalpool":
      return "Ajutised tiigid/vannid (kraavid/jõed/sood välja) · kauguse-hinnang (kevadlompide proksi, poolkaugus 300 m)";
    // G08C-HOOK (#169): surgeroad (p334) — exposed streets, the raster
    // holds the full quietness field; slidebuf (p336) — mapped slopes,
    // the raster holds the full quietness field.
    case "surgeroad":
      return "Lainetustsooni tänavad (rannast ≤150 m) · kauguse-hinnang (kõrgvee proksi, poolkaugus 150 m)";
    case "slidebuf":
      return "Pangad ja järsakud (jõed/märgalad välja) · kauguse-hinnang (varingu proksi, poolkaugus 100 m)";
    // G08B-HOOK (#168): windtunnel (p255) — mapped 5+-storey towers,
    // the raster holds the full calmness field; saltspray (p333) —
    // mapped SEA shore only, the raster holds the full field.
    case "windtunnel":
      return "Kõrghooned (5+ korrust) · tuuletunneli-hinnang (lähedus, poolkaugus 200 m, ilmajaama mõõtmine puudub)";
    case "saltspray":
      return "Mererannajoon (järved välja) · soolapritsme kauguse-hinnang (poolkaugus 500 m, korrosioonikiirust mõõdetud pole)";
    // G05B-HOOK (#162): gardens (p106) — mapped growing sites, the
    // raster holds the full count field; buildout (p146) — mapped
    // construction, the raster holds the full count field.
    case "gardens":
      return "Kogukonnaaiad ja aiandusühistud · lähedaste arv (hinnang, küllastus 1, muld krundi-põhine)";
    case "buildout":
      return "Ehitusplatsid · lähedaste arv (hinnang, küllastus 2, tihenemissurve — planeeringu sihttihedus teadmata)";
    // G05D-HOOK (#164): strsat (p230) — mapped tourist beds, the
    // raster holds the full inverse-saturation field.
    case "strsat":
      return "Turismimajutus (korterid/külalismajad/hostelid/hotellid) · küllastussurve-hinnang (pöörd-lähedus, poolkaugus 350 m, Airbnb loendust mõõdetud pole)";
    // G05A-HOOK (#161): ehitus (p42) — mapped construction sites, the
    // raster holds the full count field; korterstock (p44) — mapped
    // apartment footprints, the raster holds the full count field.
    case "ehitus":
      return "Ehitusplatsid (maa-ala + hooned) · arengu-hinnang (lähedaste arv, küllastus 1, planeeringuotsust mõõdetud pole)";
    case "korterstock":
      return "Korterelamud · üürituru-hinnang (lähedaste arv, küllastus 15, üürihindu mõõdetud pole)";
    // G05C-HOOK (#163): commbleed (p223) — mapped commercial zones,
    // the raster holds the full calmness field; windsolar (p224) —
    // mapped farm-scale turbines/solar, the raster holds the full
    // field; viewshed (p225) — mapped viewpoints, the raster holds
    // the full count field.
    case "commbleed":
      return "Äri- ja kaubandusmaad + kaubanduskeskused · kauguse-hinnang (valgumisproksi, poolkaugus 300 m, KOV otsus puudub)";
    case "windsolar":
      return "Tuulikud + maapealsed päikesepargid (katusepaneelid välja) · kauguse-hinnang (poolkaugus 800 m, tootmisregister puudub)";
    case "viewshed":
      return "Vaatepunktid · lähedaste arv (vaatekaitse-hinnang, küllastus 1, kõrguspiirangute register puudub)";
    // G05E-HOOK (#165): equestrian (p381) — mapped riding campuses,
    // the raster holds the full count field.
    case "equestrian":
      return "Ratsakeskused + maneežid + tallid + ratsateed · lähedaste arv (juurdepääsu-hinnang, küllastus 1, KOV planeeringuotsus puudub)";
    // G05F-HOOK (#166): upcycle (p485) — mapped derelict buildings,
    // the raster holds the full count field.
    case "upcycle":
      return "Mahajäetud/kasutusest väljas hooned (punkrid ja vanalipud välja) · lähedaste arv (ümberarenduse-hinnang, küllastus 2, KOV otsus puudub)";
    // G10R-HOOK (#171): skyview (p215) — mapped tall buildings +
    // forest, the raster holds the full calmness field.
    case "skyview":
      return "Kõrghooned (5+ korrust) + mets · kauguse-hinnang (poolkaugus 150 m, suunatakistust mõõdetud pole)";
    // G18A-HOOK (#172): dayopen (p34) — mapped tall masses, the
    // raster holds the full calmness field; glassglare (p305) —
    // mapped glass facades, the raster holds the full field.
    case "dayopen":
      return "Kõrghooned (korruseid ≥4) · kauguse-hinnang (päevavalguse avatus, poolkaugus 150 m, päikesetunde mõõdetud pole)";
    case "glassglare":
      return "Klaas/peegelfassaadid · kauguse-hinnang (peegeldus-surve, poolkaugus 200 m, lukse mõõdetud pole)";
    // G18B-HOOK (#173): fishbowl (p468) — settled junctions, the raster
    // holds the full calmness field; mossrisk (p479) — mapped forest
    // stands, the raster holds the full field; daylight (p405) — mapped
    // buildings, the raster holds the full inverted-count field.
    case "fishbowl":
      return "Asustatud ristmikud (≥3 haru, hoonete lähedal) · kauguse-hinnang (nurgakrundi-privaatsusproksi, poolkaugus 150 m, katastritunnistus puudub)";
    case "mossrisk":
      return "Metsapolügoonid + puuderead (tänavapuud välja) · kauguse-hinnang (samblarisk-proksi, poolkaugus 250 m, niiskusmõõtmine puudub)";
    case "daylight":
      return "Hooned (valim) · PÖÖRATUD tihedus-hinnang (päevavalguse avarus, küllastus 150, luksimõõtmine puudub)";
    // G17A-HOOK (#177): compost (p187) — mapped composting stations,
    // the raster holds the full count field; gritbin (p311) — mapped
    // grit bins, the raster holds the full count field; leafdrop
    // (p312) — mapped green-waste drop-offs, the raster holds the
    // full count field.
    case "compost":
      return "Jäätmejaamad + biokogumine · lähedaste arv (komposti-hinnang, küllastus 1, võimsusregister puudub)";
    case "gritbin":
      return "Liivakastid · lähedaste arv (talihoolduse-hinnang, küllastus 1, sahaplaan puudub)";
    case "leafdrop":
      return "Haljasjäätmete punktid · lähedaste arv (kogumise-hinnang, küllastus 1, veograafik puudub)";
    // G17B-HOOK (#178): lawncare (p469) — mapped mown lawns, the
    // raster holds the full count field.
    case "lawncare":
      return "Niidetavad murualad (aasad välja) · lähedaste arv (hooldusnähtavuse-hinnang, küllastus 20, niitmiskontrolli register puudub)";
    // G17R-HOOK (#196): privroad (p245) — mapped shared private
    // roads, the raster holds the full calmness field.
    case "privroad":
      return "Jagatud erateed (parklad ja sissesõiduteed välja) · kauguse-hinnang (teehooldusproksi, poolkaugus 200 m, KÜ leping puudub)";
    // B10C-HOOK (#230): utility layers (p53/p54) — mapped amenity counts.
    // The communal networks (tap water, organized collection) are NOT on
    // these maps — the dots are the public points themselves. Fiber
    // (p51) dots are a thinned honest sample (valim), the raster holds
    // the full field; mobile (p51) dots are measurement sites (never
    // masts), the raster models coverage discs.
    case "water":
      return "Avalikud veepunktid · lähedaste arv (küllastus 1)";
    case "waste":
      return "Taara- ja jäätmepunktid · lähedaste arv (küllastus 6)";
    case "fiber":
      return "Fiiber-katvusega aadresside valim · tihedus (teatatud, küllastus 50)";
    case "mobile":
      return "Mõõtmiskohad (mitte mastid!) · tugevaima kärje leviala";
    // OSMDAILY-HOOK (#482): daily-life layers (P4-027/032/044/045/049/
    // 061) — mapped shop/culture/doorstep counts. The communal
    // networks (delivery windows, opening hours, closure calendars)
    // are NOT on these maps — the dots are the mapped points
    // themselves; lastshop red is a warning (absence), never measured.
    case "dailyshop":
      return "Toidupoed (valik kaardistatuid) · lähedaste arv (hinnang, küllastus 8, tarneaken puudub)";
    case "activity":
      return "Õhtuse kasutusega kohad · lähedaste arv (kasutus-hinnang, küllastus 12, mitte turvalisus)";
    case "herd":
      return "Galeriid/muuseumid · lähedaste arv (maitse-hinnang, küllastus 3, mitte väärtushinnang)";
    case "thirdplace":
      return "Kohvikud/saunad/raamatukogud · lähedaste arv (kuuluvus-hinnang, küllastus 12, lahtiolekuajad teadmata)";
    case "taxidoor":
      return "Sissepääsud (sh trepikojad) · lähedaste arv (leitavuse-hinnang, küllastus 30, parkimisreeglid puuduvad)";
    case "lastshop":
      return "Pood/apteek/sularaha · lähedaste arv (HOIATUS-hinnang, küllastus 12, sulgemine mõõtmata)";
    // GTFS-HOOK (#483): gtfsstops (p15) — TLT-city GTFS stops with
    // scheduled Wednesday departures + mapped-only Elron stations; the
    // Euclidean fallback holds the scheduled-service density field.
    case "gtfsstops":
      return "GTFS peatused (buss/tramm/troll + kaardistatud Elroni jaamad) · suurus = sõiduplaanilised väljumised kolmapäevas (küllastus 1500, õhtune täituvus teadmata — EI OLE loendusandmeid)";
    // RSAFE-HOOK (#481): roadsafety (p13, P4-012 proxy) — mapped
    // crossings + calming, the raster holds the full count field. The
    // usage-not-safety caveat rides along (P4-032 precedent): dots are
    // mapping usage, never accident truth.
    case "roadsafety":
      return "Märgistatud ülekäigud + rahustid · lähedaste arv (kasutus-hinnang, küllastus 60, õnnetusstatistika puudub)";
    // ACCBLACK-HOOK (#490, reopen #522): accblack (P4-012 measured
    // slice) — projected Transpordiamet points from the snapshot
    // sidecar; the field is unknown outside the Tallinn window.
    case "accblack":
      return "Rasked liiklusõnnetused (mõõdetud mustad punktid) · 300 m aken (projekteeritud Tallinna punktid, ~1 m; väljaspool akent teadmata)";
    // P4-031-HOOK (#484): senscom (P4-031) — DIY outdoor locations from
    // the Tallinn extract; the band field (not the dots) is the score:
    // 1 andur <=500 m -> 60, 2-3 -> 70, 4+ -> 80 (lagi); anduriteta
    // hoov stays unknown (scorer NULL: hinnang + EI OLE).
    case "senscom":
      return "DIY-välisandurid (Tallinna väljavõte) · tunnistajate arv 500 m raadiuses (1 -> 60, 2-3 -> 70, 4+ -> 80, lagi; kalibreerimata, mitte mõõtmine)";
    // OOKLA-HOOK (#489): ookla fixed/mobile (P4-009) — quarterly tile
    // download averages from the Tallinn extract; the band field (not
    // the dots) is the score: nearest qualifying tile (≥5 testi)
    // <= 1 km -> <30 Mbit/s 35, <100 55, <300 75, muidu 85 (lagi);
    // ruuduta ala stays unknown (scorer NULL: hinnang + EI OLE).
    // Throughput only — power cuts and contract speeds unmeasured.
    case "ookla_fixed":
      return "Ookla fikseeritud kvartaliruudud (2026-Q1 väljavõte) · lähiruut 1 km raadiuses (≥5 testi): <30 Mbit/s -> 35, <100 -> 55, <300 -> 75, muidu 85 (lagi; läbilase, mitte lepingukiirus — katkestused teadmata)";
    case "ookla_mobile":
      return "Ookla mobiilsed kvartaliruudud (2026-Q1 väljavõte) · lähiruut 1 km raadiuses (≥5 testi): <30 Mbit/s -> 35, <100 -> 55, <300 -> 75, muidu 85 (lagi; läbilase, mitte levikaart — katkestused teadmata)";
    // STATKOV-HOOK (#485): choropleth legends (P4-025/050/019) -- each
    // KOV one flat colour off its 2025 PX-table band; rida puudu = EI
    // OLE (punane = halb VÕI tundmatu, mitte null-hinne). No markers:
    // the legend describes the fills, the toggle reads (0).
    case "kovmigr":
      return "KOV rändesaldo 2025/1000 el (hinnang: +10→75, −5→60, −20→45, muidu 30; rida puudu EI OLE)";
    case "kovehit":
      return "KOV valminud eluruumid 2025/1000 el (hinnang, lagi 70: 20→30, 10→45, 4→60, muidu 70; load EI OLE)";
    case "kovfisc":
      return "KOV põhitegevuse marginaal 2025 % (hinnang, lagi 70: 10→70, 5→60, 0→45, muidu 30; võlg EI OLE)";
    // P4PARK-HOOK (#479): parking (P4-013) — mapped bays + lots, the
    // raster holds the full count field.
    case "parking":
      return "Kaardistatud parklad (taskud + platsid) · lähedaste arv (asukoha-hinnang, küllastus 75, vabade kohtade arv ega elanikuluba pole)";
    // MARUKOV-HOOK (#486): choropleth legends (p41/p149/p43/p484) --
    // each KOV one flat colour off its quarterly MARU band; rida/paar
    // puudu = EI OLE (punane = halb VÕI tundmatu, mitte null-hinne).
    // No markers: the legend describes the fills, the toggle reads (0).
    case "kovkasv":
      return "KOV mediaanhinna aastakasv YoY% (hinnang: −5→75, 0→65, +5→50, +10→40, muidu 30; paaritu KOV EI OLE)";
    case "kovkaive":
      return "KOV kvartali tehingute arv (hinnang: 300→80, 100→65, 30→50, muidu 35; rida puudu EI OLE)";
    case "kovedas":
      return "KOV sügavus + suund (hinnang: 70/55/50/35; poolik jalapaar EI OLE, maaklerivõrdlus EI OLE)";
    case "kovkiirus":
      return "KOV käibe QoQ-muutus % (NÕRK hinnang, lagi 70: +10→70, −10→55, muidu 40; laoseis EI OLE)";
    // FLOOD-HOOK (#487): floodzone (p112, KAUR choropleth) — named zone
    // fills, never a gradient. The outside-unknown caveat rides along
    // (OTA PR #131 precedent): outside every polygon is teadmata, never
    // dry — the register carries no T-bands and zero Tallinn polygons.
    case "floodzone":
      return "KAUR üleujutusohuga alad · tsoonis = hinnang (nimeline polügoon), väljaspool = teadmata, mitte kuiv (T-bändid ja Tallinna polügoonid registris puuduvad)";
    // P4OSM-HOOK (#480): walkability + darkness (P4-029/P4-035) — mapped
    // evidence counts, saturating halves from layers_p4osm.ts P4OSM_BONUS
    // (same numbers as bonusSpecFor). Both are hinnangud, never measured:
    // no Mapillary/KartaView frames, no lamp inventory feed.
    case "blockwalk":
      return "Kõnniteed/katted/valgustid · lähedaste arv (küllastus 1000, hinnang — fassaadi-tõde puudub)";
    case "darkness":
      return "lit-märgistused · lähedaste arv (küllastus 500, hinnang — lampide loendus puudub)";
    // MAAPARCEL-HOOK (#491): maaparcel (p364, kataster omandivorm-class
    // choropleth) — register facts, never suspicion scores. The
    // outside-unknown caveat rides along (OTA PR #131 precedent):
    // outside the harvested sample window is teadmata, never empty —
    // and municipal/state land needs the RIK hoonestus-check, never a
    // verdict off the fill color.
    case "maaparcel":
      return "Katastritunnused omandivormi järgi · roheline = era, oranž = munitsipaal, roosa = riigi, hall = muu/teadmata (fakt, mitte hinnang; munitsipaal/riigi → RIK hoonestuse kontroll) · väljaspool = teadmata, mitte tühi (proovivalim: 100 tunnust Kesklinna aknas)";

    // EELIS-HOOK (#488): nature polygons (P4-015/024/030 slices) — named
    // zone fills, never a gradient. The outside-unknown caveat rides
    // along (OTA PR #131 precedent): outside every polygon is teadmata,
    // never clear — the snapshot rows gate by distance, the LABEL scores.
    case "eeliskaitse":
      return "EELIS kaitsealad · tsoonis = piiranguala-hinnang (nimeline polügoon), väljaspool = teadmata, mitte piirangutevaba (I/II liigid EI OLE avalikud)";
    case "eelisniit":
      return "EELIS niiduelupaigad · tsoonis = jäme proksi-hinnang (rakk, mitte liigiväide), väljaspool = teadmata, mitte puugivaba (rohevõrgustik EI OLE)";
    case "eelisraie":
      return "EELIS raiealad · tsoonis = muutuslipp-hinnang (register, mitte satelliit), väljaspool = teadmata, mitte muutumatu (raieluba EI OLE)";

    // PLANKTPR-HOOK (#492): planktpr (p47) — kehtestatud designated-use
    // polygons as exact fills (elamu 80 / sega 60 / äri 35 / piirang 20,
    // lagi 80); the dated WFS negative rides along (live harvest holds
    // no polygons — outside the fills there is no hinnang, never a
    // faked score; OSM landuse is never painted as zoning).
    case "planktpr":
      return "Sihtotstarbe-polügoonid (kehtestatud, hinnang: elamu roheline 80 / sega 60 / äri 35 / piirang punane 20, lagi 80; PLANK-WFS 2026-09-13 seisuga MAAS, TPR-il liidest EI OLE — väljaspool polügoone hinnangut pole)";
    // TERVISE-HOOK (#494): tervise (P4-024) — Terviseameti seirepunktid
    // projekteeritud väljavõttest; lähima punkti kvaliteedibänd
    // 1 km raadiuses (80 väga hea … 30 halb, lagi; kvaliteet teadmata
    // = hinnangut pole, mitte keskmine).
    case "tervise":
      return "Suplusvee seirepunktid (Terviseameti väljavõte) · lähima punkti kvaliteet 1 km raadiuses (80 väga hea, 70 hea, 60 piisav/teadmata, 45 kesine, 30 halb; lagi 80, joogivee seire puudub)";
    // SPORT-HOOK (#607): sport slices (P4-048) — sliced register venues
    // from the snapshot sidecar; the band field (not the dots) is the
    // score: nearest sliced venue <= 500 m -> 80, <= 1 km -> 65,
    // <= 2 km -> 50; beyond stays unknown (scorer NULL: hinnang +
    // EI OLE; linnulennult, ajad/hinnad ostja kontroll).
    case "sport_hall":
      return "Spordisaalid ja võimlad (Spordiregistri väljavõte) · lähim saal 2 km raadiuses (≤500 m -> 80, ≤1 km -> 65, ≤2 km -> 50; kauguse-hinnang linnulennult, lahtiolekuajad/hinnad teadmata)";
    case "sport_field":
      return "Staadionid ja väliväljakud (Spordiregistri väljavõte) · lähim väljak 2 km raadiuses (≤500 m -> 80, ≤1 km -> 65, ≤2 km -> 50; kauguse-hinnang linnulennult)";
    case "sport_pool":
      return "Ujulate ligidus (Spordiregister + Terviseameti ujulate loend) · lähim ujula 2 km raadiuses (≤500 m -> 80, ≤1 km -> 65, ≤2 km -> 50; kauguse-hinnang linnulennult, veekvaliteeti ei hinnata)";
    // EHIS-HOOK (#608): ehis slices (P4-011) — measured register
    // school buildings from the snapshot sidecar; the band field (not
    // the dots) is the score: nearest sliced building <= 500 m -> 80,
    // <= 1 km -> 65, <= 2 km -> 50; beyond stays unknown (scorer NULL:
    // hinnang + EI OLE; linnulennult, kvaliteet/keel ostja kontroll).
    case "ehis_school":
      return "Koolid lähedal (EHISe väljavõte) · lähim kool 2 km raadiuses (≤500 m -> 80, ≤1 km -> 65, ≤2 km -> 50; kauguse-hinnang linnulennult, kvaliteet ja õppekeel teadmata)";
    case "ehis_kindergarten":
      return "Lasteaiad lähedal (EHISe väljavõte) · lähim lasteaed 2 km raadiuses (≤500 m -> 80, ≤1 km -> 65, ≤2 km -> 50; kauguse-hinnang linnulennult, kohtade arv teadmata)";
    case "ehis_hobby":
      return "Huvikoolid lähedal (EHISe väljavõte, õhuke valim: 10 hoonet Harjumaal) · lähim huvikool 2 km raadiuses (≤500 m -> 80, ≤1 km -> 65, ≤2 km -> 50; kauguse-hinnang linnulennult)";
    // MEDRE-HOOK (#609): medre slices (P4-011 GP half) — Step-1
    // honest-empty: no ADS join owned, so the field is unknown
    // everywhere until Step 2 lands joined points (linkage_rate 0,
    // stated). Bands below are the dormant kernel (same table as the
    // scorer); proximity is coverage, never care quality (status leg
    // NULL — avatud-olek teadmata).
    case "medre_gp":
      return "Perearstid (TEHIK medre väljavõte, EI OLE liitmist) · vastuvõtukoht 2 km raadiuses (≤500 m -> 80, ≤1 km -> 65, ≤2 km -> 50, uinuv — punkte pole; lähedus, mitte kvaliteet; avatud-olek teadmata)";
    case "medre_clinic":
      return "Perearstikeskused (TEHIK medre väljavõte, EI OLE liitmist) · üldarstiabi tegevuskoht 2 km raadiuses (≤500 m -> 80, ≤1 km -> 65, ≤2 km -> 50, uinuv — punkte pole; eriarstiabi väljas)";
    // OHUSEIRE-HOOK (#610): thin station layer (P4-031) — 3 Tallinna
    // jaama (Rahu / Liivalaia / Õismäe, seis 2026-09-16); the band
    // field (not the dots) is the score: jaam 2 km raadiuses -> 60,
    // beyond stays unknown (scorer NULL). The scorer's 2+ -> 70 lives
    // scorer-side only (stated); reference inlets interpolate across
    // districts — never a doorstep measurement, never heating truth.
    case "ohuseire":
      return "Õhuseire jaamad (Keskkonnaagentuuri väljavõte: Rahu / Liivalaia / Õismäe) · jaam 2 km raadiuses -> 60 (lameda linnaosa-hinnang; 2+ jaama 70 ainult skooris; mõõtmine ega küte-tõde teadmata)";
    // KLIIMA-HOOK (#611): kliima slices (P4 winter-mildness + wetness
    // station legs) — harvested 1991-2020 normals from
    // Keskkonnaagentuur; the band field (not the dots) is the score:
    // nearest ranked cell within 70 km takes its rank band (frost
    // 70/55/40 across 3 cells, wet 70/40 across 2 — Pakri
    // sademenormatiivita); beyond stays unknown (scorer NULL: hinnang
    // + EI OLE; interpolatsiooni pole, tänavataseme gradiente pole).
    case "kliima_frost":
      return "Talvine leebus (Keskkonnaagentuur 1991-2020) · lähima jaamaraku külmapäevade järjestus 70 km raadiuses (Pakri 70 / Harku 55 / Kuusiku 40; 3 jämedat rakku, interpolatsiooni pole)";
    case "kliima_wet":
      return "Kuivus (Keskkonnaagentuur 1991-2020) · lähima jaamaraku aastasademete järjestus 70 km raadiuses (Harku 70 / Kuusiku 40; Pakri 22/30 täisaastat ehk normatiivita — teadmata, mitte niiske)";
    // POI-HOOK (#612): long-tail slices — register points from the
    // monthly huvipunktid vahekiht; the band field (not the dots) is
    // the score: nearest sliced POI ≤300 m -> 85, ≤600 m -> 70,
    // ≤1 km -> 55; beyond stays unknown (scorer NULL: hinnang; post
    // includes parcel lockers — dominant access, stated).
    case "poi_library":
      return "Raamatukogud lähedal (Maa- ja Ruumiameti väljavõte: 124 Harjumaal) · lähim raamatukogu 1 km raadiuses (≤300 m -> 85, ≤600 m -> 70, ≤1 km -> 55; kauguse-hinnang linnulennult, kogu teadmata)";
    case "poi_post":
      return "Post lähedal (Maa- ja Ruumiameti väljavõte: 536 Harjumaal, sh 521 pakiautomaati) · lähim post/pakiautomaat 1 km raadiuses (≤300 m -> 85, ≤600 m -> 70, ≤1 km -> 55; kauguse-hinnang linnulennult)";
    case "poi_pharmacy":
      return "Apteegid lähedal (Ravimiameti väljavõte: 187 Harjumaal) · lähim apteek 1 km raadiuses (≤300 m -> 85, ≤600 m -> 70, ≤1 km -> 55; kauguse-hinnang linnulennult, nõuanne teadmata)";
    // FIXIT-HOOK (#623): fixit pins (P4 kaebused) — individual
    // reports, NOT place quality. Density measures REPORTING
    // activity (who bothers to report), never livability: an empty
    // map means no reports, not a tidy street. Rolling ~19-day
    // window — expired pins never render as current.
    case "fixit":
      return "Teated lähedal (annateada väljavõte: 300 teadet, sh 120 lahendatud) · IGA täpp ÜKS teade (libisev 19 päeva aken; tihedus = teatamine, MITTE elukvaliteet — tühi kaart pole kiitus)";
    // SEVESO-HOOK (#613): seveso danger-class fills (Päästeamet
    // ohualad) — inside a named polygon reads by class color, outside
    // every polygon is unknown (never safe): an unregistered hazard is
    // not a ruled-out one.
    case "seveso":
      return "Seveso ohualad (Päästeameti register: 235 ohuala, sh 95 Harjumaal) · tsoonis = ohuala (mürkpunane / kuumusoranž, hinnang — tutvu infovoldikuga; väljaspool = teadmata, mitte ohutu)";
    // ASUMEDIA-HOOK (#495): asumedia (own-snapshot asking medians) —
    // the dated negative rides along: 0/84 asums reach MIN_N=5, so
    // the field is unknown everywhere until the reopen lands real
    // per-asum N (no bands, no fills, never a faked median).
    case "asumedia":
      return "Asumite küsi-mediaanid oma snapshotitest (ootel-hinnang: 2026-09-14 loendus 30 kirjet, 0 asumivõtmega, 0/84 asumi MIN_N=5 täis — õhukese N-iga asumeid EI FEIGITA; korduskontroll: geokodeeritud snapshotid + asumiliide)";
    // PAASTE-HOOK (#493): paaste (P4-012) — komando coverage, honestly
    // empty until a machine feed exists (see layers_paaste.ts).
    case "paaste":
      return "Päästekomandod (P4-012) · kaetud ≤5 km (hinnang 60, sõiduaeg mõõtmata — EI OLE masinloetavat komandode asukoha-voogu, asukohad rescue.ee kontaktidest)";
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
