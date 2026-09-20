// 808-HOOK (#808): walk-graph vs bird-flight distance audit (issue #808).
//
// For every id in LAYERS this module records which distance the map
// field and the per-listing scorer each use, plus a verdict (reasonable
// / change) with a rationale citing the layer's semantics (what
// good/bad means there), not just the current implementation.
//
// Survey method (2026-09-20, read from code, not summaries):
// * Map side: scripts/build/batch_*.py kernels (foot-graph load_graph
//   vs exact full-grid 8-connectivity Dijkstra vs Euclidean count
//   kernels vs *_NO_RASTER decisions), loadLayerRaster labels
//   (server/snapshot.ts, shared via rasterDistanceLabel), the
//   bonusSpecFor kernel kinds (bands/tileband/qbands/dbands/pins),
//   and the polygon/tint/district predicates.
// * Scorer side: services/scoring/dims_*.py + livability.py. Universal
//   finding: every per-listing distance is bird-flight haversine
//   ("bird-flight at 75 m/min, never routed" — dims_p4_peatus.py;
//   walk_min = haversine/75 in dims_group12.py; livability._nearest_m).
//   No scorer leg routes on the foot graph.
//
// verdict "change" is reserved for behavior this PR changes (the
// G07-family relabel below); contested re-tunes are verdict
// "reasonable" with a followUp note, implemented as follow-up issues.

import { bonusSpecFor, LAYERS, type LayerDef, type LayerId } from "../layers";
import { rasterDistanceLabel } from "./snapshot";
import { isPolygonOnlyLayer } from "../layers_flood";
import { isPolygonOnlyMaaLayer } from "../layers_maaparcel";
import { isEelisPolygonOnlyLayer } from "../layers_eelis";
import { isStatelandPolygonOnlyLayer } from "../layers_p4_stateland";
import { isSevesoPolygonOnlyLayer } from "../layers_p4_seveso";
import { isQuarryPolygonOnlyLayer } from "../layers_p4_quarry";
import { isMaaparandusPolygonOnlyLayer } from "../layers_p4_maaparandus";
import { isSoilPolygonOnlyLayer } from "../layers_p4_soil";
import { isEtakPolygonOnlyLayer } from "../layers_p4_etak";
import { isReliefTasteOnlyLayer } from "../layers_p4_relief";
import { isCanopyTasteOnlyLayer } from "../layers_p4_canopy";
import { isBuildingsTasteOnlyLayer } from "../layers_p4_buildings";
import { isDensityTasteOnlyLayer } from "../layers_p4_density";
import { isForestPolygonOnlyLayer } from "../layers_p4_forest";
import { isNoisePolygonOnlyLayer } from "../layers_p4_noise";
import { isHarbourLayerId } from "../layers_p4_harbour";
import { isKpoPolygonOnlyLayer } from "../layers_p4_kpo";
import { isDelayPolygonOnlyLayer } from "../layers_p4_delay";
import { isStatKovLayerId } from "../layers_statkov";
import { isMaruKovLayerId } from "../layers_maru";
import { isAsumediaLayerId } from "../layers_asumedia";
import { isAccBlackLayerId } from "../layers_accblack";
import { isPlanktprLayerId } from "../layers_planktpr";
import { isOutageLayerId } from "../layers_p4_outage";
import { GTFSSTOPS_LAYER_IDS } from "../layers_gtfsstops";
import { BUSMESH_LAYER_IDS } from "../layers_busmesh";
import { OSMDAILY_LAYER_IDS } from "../layers_osmdaily";
import { B1_LAYER_IDS } from "../layers_batch1";
import { BATCH5_LAYER_IDS } from "../layers_batch5";
import { G11C_LAYER_IDS } from "../layers_group11c";

/** Map-field distance vocabulary (issue #808 §Scope.1). */
export type AuditMapDistance =
  | "walk-raster"
  | "euclidean-raster"
  | "euclidean-fallback"
  | "hard-cutoff-join"
  | "markers"
  | "na";

/** Per-listing scorer distance vocabulary (same buckets). */
export type AuditScorerDistance =
  | "haversine"
  | "haversine-bands"
  | "haversine-join"
  | "polygon"
  | "district"
  | "attribute"
  | "none";

export type AuditVerdict = "reasonable" | "change";

export interface AuditRow {
  id: LayerId;
  title: string;
  map: AuditMapDistance;
  scorer: AuditScorerDistance;
  /** Scorer file(s) the scorer column was read from. */
  scorerRef: string;
  verdict: AuditVerdict;
  /** Cites layer semantics (what good/bad means), not just the code. */
  rationale: string;
  /** Follow-up issue topic when a contested re-tune is proposed. */
  followUp?: string;
}

const WALK_SCORER_FOLLOW_UP =
  "Walk-graph scorer legs for pedestrian-access layers (map is walk-graph, " +
  "scorer is bird-flight minutes): contested re-tune, needs foot-graph " +
  "lookup at score time on both sides plus recalibration.";

function defOf(id: LayerId): LayerDef {
  const def = LAYERS.find((l) => l.id === id);
  if (!def) throw new Error(`808 audit: unknown layer ${id}`);
  return def;
}

function row(
  id: LayerId,
  map: AuditMapDistance,
  scorer: AuditScorerDistance,
  scorerRef: string,
  verdict: AuditVerdict,
  rationale: string,
  followUp?: string,
): AuditRow {
  return { id, title: defOf(id).title, map, scorer, scorerRef, verdict, rationale, followUp };
}

// Ownership sets (batch-owned id lists; the completeness test pins that
// every LAYERS id lands in exactly one family below).
const CORE_WALK: ReadonlySet<string> = new Set([
  "parks",
  "transit",
  "schools",
  "walkability",
  "pedinfra",
  "cycling",
  "grocery",
  "healthcare",
]);
const B1 = new Set<string>(B1_LAYER_IDS);
const B5 = new Set<string>(BATCH5_LAYER_IDS);
const G11C = new Set<string>(G11C_LAYER_IDS);
// G11D area legs (mailbox/postal/alley); trailprivacy is quiet-kind.
const G11D_AREA: ReadonlySet<string> = new Set(["mailbox", "postal", "alley"]);
const G06B_AREA: ReadonlySet<string> = new Set(["plaster", "antiques"]);
// 808 audit: G07-family masters are grid-Dijkstra Euclidean (see the
// G07*_EUCLIDEAN_MASTER sets in snapshot.ts); the label fix rides in
// this PR, so these rows carry verdict "change".
const G07_CHANGE: ReadonlySet<string> = new Set([
  "industprox",
  "odorsrc",
  "brownsoil",
  "oiltank",
  "agriland",
  "vectorhabitat",
  "agrifield",
  "wildcorr",
]);
const AIR: ReadonlySet<string> = new Set(["droneclear", "droneviab", "mobile"]);
const GRID: ReadonlySet<string> = new Set([
  "drainage",
  "shoredist",
  "wildfire",
  "vernalpool",
  "surgeroad",
  "slidebuf",
  "windtunnel",
  "saltspray",
  "skyview",
  "dayopen",
  "glassglare",
  "commbleed",
  "windsolar",
  "privroad",
  "strsat",
  "rentbleed",
]);
const COUNT: ReadonlySet<string> = new Set([
  "gardens",
  "buildout",
  "ehitus",
  "korterstock",
  "viewshed",
  "equestrian",
  "upcycle",
  "compost",
  "gritbin",
  "leafdrop",
  "lawncare",
  "fishbowl",
  "mossrisk",
  "daylight",
  "moorage",
  "roadsafety",
  "parking",
  "blockwalk",
  "darkness",
]);
const UTIL_WALK: ReadonlySet<string> = new Set(["fiber", "waste", "water"]);
const NO_MASTER_FALLBACK = new Set<string>([...GTFSSTOPS_LAYER_IDS, ...BUSMESH_LAYER_IDS]);
const OSMDAILY = new Set<string>(OSMDAILY_LAYER_IDS);

function isPolygonFamily(layer: string): boolean {
  return (
    isPolygonOnlyLayer(layer) ||
    isPolygonOnlyMaaLayer(layer) ||
    isEelisPolygonOnlyLayer(layer) ||
    isStatelandPolygonOnlyLayer(layer) ||
    isSevesoPolygonOnlyLayer(layer) ||
    isQuarryPolygonOnlyLayer(layer) ||
    isMaaparandusPolygonOnlyLayer(layer) ||
    isSoilPolygonOnlyLayer(layer) ||
    isEtakPolygonOnlyLayer(layer) ||
    isForestPolygonOnlyLayer(layer) ||
    isNoisePolygonOnlyLayer(layer) ||
    isHarbourLayerId(layer) ||
    isKpoPolygonOnlyLayer(layer) ||
    isDelayPolygonOnlyLayer(layer)
  );
}

function isTintFamily(layer: string): boolean {
  return (
    isReliefTasteOnlyLayer(layer) ||
    isCanopyTasteOnlyLayer(layer) ||
    isBuildingsTasteOnlyLayer(layer) ||
    isDensityTasteOnlyLayer(layer)
  );
}

/**
 * Audit row for one layer. Classification order is load-bearing:
 * kernel kind (pins/bands/...) first, then polygon/tint/district/empty
 * overlays (never a distance), then documented no-master fallbacks,
 * then the raster label shared with loadLayerRaster.
 */
export function auditRowFor(layer: LayerId): AuditRow {
  const kind = bonusSpecFor(layer).kind;

  // Markers-only: pins measure reporting activity, not place quality
  // (FIXIT-HOOK #623) — no distance anywhere, both sides.
  if (kind === "pins") {
    return row(
      layer,
      "markers",
      "none",
      "n/a (markers-only by decision; feeds live in pole/api.py + operator caches)",
      "reasonable",
      "Green/red is pin presence and status, never distance decay: " +
        "complaint/report/sensor pins (fixit), live DATEX/shed/incident " +
        "markers, leisure pins (silly). Bird-flight vs walk never enters " +
        "because nothing is scored by proximity.",
    );
  }
  // Hard-cutoff haversine joins with byte parity to the scorer bands.
  if (kind === "bands") {
    const ref =
      layer === "senscom"
        ? "services/scoring/dims_p4_senscom.py (haversine witness count, SENSCOM_BANDS parity)"
        : layer === "paaste"
          ? "services/scoring/dims_p4_paaste.py (haversine station bands)"
          : "services/scoring/dims_gbfs.py (honest-empty per-listing station check)";
    return row(
      layer,
      "hard-cutoff-join",
      layer === "gbfs" ? "none" : "haversine",
      ref,
      "reasonable",
      layer === "senscom"
        ? "Green = 4+ DIY witnesses within 500 m (air-sensor coverage, " +
          "not access): counting witnesses in a hard Euclidean radius is " +
          "the honest metric — air does not walk footpaths, and a " +
          "smoothed walk kernel would fake gradients between sensors."
        : layer === "paaste"
          ? "Green = komando station within the hard band (rescue " +
            "response drives; Euclidean bands are the honest proxy, " +
            "and map/scorer share the band table)."
          : "Green = bike-share station nearby in the snapshot bands; " +
            "the per-listing scorer deliberately refuses faked counts " +
            "(honest-empty). Snapshot proximity bands for orientation " +
            "plus an honest listing check is the reviewable split.",
    );
  }
  if (kind === "tileband") {
    return row(
      layer,
      "hard-cutoff-join",
      "haversine-join",
      "services/scoring/dims_p4_ookla.py (haversine tile join, OOKLA_BANDS parity)",
      "reasonable",
      "Green = fast Ookla tile (fixed/mobile download bands): radio " +
        "throughput radiates through air, so the nearest-tile Euclidean " +
        "join is the physical metric — walk routing a radio cell would " +
        "be fake precision. Map and scorer share the band table.",
    );
  }
  if (kind === "qbands") {
    if (isOutageLayerId(layer)) {
      return row(
        layer,
        "hard-cutoff-join",
        "haversine",
        "services/scoring/dims_p4_outage.py (city-grain window, no routing)",
        "reasonable",
        "Green = no live outage in the city-grain window (power " +
          "reliability is a window/state reading, not access distance): " +
          "the window join is the metric on both sides by decision.",
      );
    }
    return row(
      layer,
      "hard-cutoff-join",
      "haversine-join",
      "scripts/build/batch_tervise.py quality bands + services/scoring/dims_p4_kliima_stations.py " +
        "(haversine) + dims_harno.py (nearest-school quality)",
      "reasonable",
      "Green = good bathing water / school quality / climate normal / " +
        "brightness proxy at the nearest point: QUALITY rides the join, " +
        "distance only selects which point speaks. Euclidean nearest is " +
        "correct — water quality and normals do not walk footpaths.",
    );
  }
  if (kind === "dbands") {
    return row(
      layer,
      "hard-cutoff-join",
      "haversine-bands",
      "services/scoring/dims_p4_sportreg.py PROX_BANDS + dims_p4_ehis_map.py + " +
        "dims_p4_medre.py + dims_p4_poi.py + dims_p4_ohuseire.py (all haversine, byte parity)",
      "reasonable",
      "Green = venue/school/clinic/library/post/pharmacy/station within " +
        "the distance bands (access!). Bird-flight bands are the honest " +
        "documented approximation on BOTH sides with byte parity — but " +
        "these are pedestrian-access layers, so a walk-graph upgrade " +
        "would be more physical.",
      WALK_SCORER_FOLLOW_UP,
    );
  }
  // Polygon/tint/district/empty overlays: never a distance, both sides.
  if (isPolygonFamily(layer)) {
    return row(
      layer,
      "na",
      "polygon",
      "services/scoring/dims_overturn_flood.py + dims_p4_eelis.py + dims_p4_seveso.py " +
        "(zone membership) + dims_p4_maavara_extract.py + dims_p4_kitsendus.py + " +
        "dims_p4_noisemap.py + dims_p4_forestchange.py + dims_p4_harbour.py + " +
        "dims_p4_typical_delay.py + dims_soil_map.py + dims_group18etak.py + " +
        "dims_p4_maaparandus.py + dims_p4_riigimaa.py + dims_overturn_maa.py",
      "reasonable",
      "Green/red is polygon membership (flood zone, nature zone, danger " +
        "area, quarry permit, kitsendus zone, noise band, forest change, " +
        "harbour fill, delay corridor, soil/etak contour, drainage " +
        "network, state land, kataster class): buffer/zone semantics on " +
        "both sides — walk vs bird-flight never enters.",
    );
  }
  if (isTintFamily(layer)) {
    return row(
      layer,
      "na",
      "none",
      "n/a (taste-only by decision, no parameters3 id, never evaluated)",
      "reasonable",
      "Relief/canopy/buildings/density are taste tints, not scores: no " +
        "distance kernel and no per-listing leg — nothing to route.",
    );
  }
  if (isStatKovLayerId(layer) || isMaruKovLayerId(layer)) {
    return row(
      layer,
      "na",
      "district",
      "services/scoring/dims_p4_emta_kov.py + dims_overturn_maru.py (per-KOV joins)",
      "reasonable",
      "Green = good KOV aggregate (migration, construction, fiscal, " +
        "growth): exact KOV fills on the map, district join in the " +
        "scorer — aggregates have no distance metric by construction.",
    );
  }
  if (isAsumediaLayerId(layer)) {
    return row(
      layer,
      "na",
      "district",
      "services/scoring/dims_p4_own_asum.py (per-asum join; layer empty-on-purpose)",
      "reasonable",
      "Per-asum medians, empty-on-purpose on the map: no field, no " +
        "distance, both sides.",
    );
  }
  if (isPlanktprLayerId(layer)) {
    return row(
      layer,
      "na",
      "polygon",
      "services/scoring/dims_overturn_planktpr.py (parcel designated-use join)",
      "reasonable",
      "Green = matching designated use (exact parcel fills): parcel-join " +
        "semantics on both sides — distance never enters.",
    );
  }
  if (isAccBlackLayerId(layer)) {
    return row(
      layer,
      "na",
      "none",
      "n/a (honest-empty overlay until the L-EST97 projection reopens; scorer likewise NULL)",
      "reasonable",
      "Accident blackspots stay empty (projecting L-EST97 as WGS84 would " +
        "be fake precision): no field, no distance, both sides.",
    );
  }
  // Documented no-master fallbacks: honest Euclidean splat.
  if (NO_MASTER_FALLBACK.has(layer)) {
    return row(
      layer,
      "euclidean-fallback",
      "haversine",
      layer === "gtfsstops"
        ? "services/scoring/dims_p4_peatus.py (haversine windows; ridership dims honest-empty)"
        : "services/scoring/dims_p4_busmesh.py (transfer richness)",
      "reasonable",
      layer === "gtfsstops"
        ? "Green = stops with departures nearby (point overlay + trips " +
          "spec, deliberately no frequency kernel or walk raster): the " +
          "Euclidean fallback splat is the documented honest metric " +
          "until a master exists."
        : "Green = transfer-rich nodes nearby (deliberately no walk " +
          "raster): the Euclidean fallback splat with the transfer spec " +
          "is the documented honest metric.",
    );
  }
  if (OSMDAILY.has(layer)) {
    return row(
      layer,
      "euclidean-fallback",
      "haversine",
      "services/scoring/dims_p4_osm.py (around:500 Euclidean tiers + haversine)",
      "reasonable",
      "Green = daily shop/activity/herd/third-place/taxi-door/last-shop " +
        "nearby (everyday pedestrian access!): the Euclidean fallback is " +
        "honest but walk would be more physical — walk masters are the " +
        "documented follow-up in layers_osmdaily.ts.",
      "Build OSMDAILY walk masters (documented follow-up in " +
        "layers_osmdaily.ts: rasters are follow-up, none built).",
    );
  }
  // G07-family: Euclidean-by-construction grid masters, relabeled here.
  if (G07_CHANGE.has(layer)) {
    const ref =
      layer === "industprox" || layer === "odorsrc"
        ? "services/scoring/dims_group07.py (haversine bands, õhu proksi)"
        : layer === "brownsoil" || layer === "oiltank" || layer === "agriland"
          ? "services/scoring/dims_group07b.py (haversine)"
          : layer === "vectorhabitat"
            ? "services/scoring/dims_group07c.py (haversine)"
            : "services/scoring/dims_group07d.py (haversine)";
    return row(
      layer,
      "euclidean-raster",
      "haversine-bands",
      ref,
      "change",
      "Green = far from the source (industrial/odor/soil/tank/field/" +
        "habitat/corridor exposure, inverted quiet): exposure disperses " +
        "through air/soil, NOT along footpaths, so the grid-Dijkstra " +
        "Euclidean master is the physical metric — and the scorer " +
        "already measures bird-flight. This PR fixes the label " +
        "walk→euclidean so the otsekaugus disclaimer shows.",
    );
  }
  // Euclidean-by-construction raster families (label already euclidean).
  if (AIR.has(layer)) {
    return row(
      layer,
      "euclidean-raster",
      "haversine-bands",
      layer === "mobile"
        ? "services/scoring/dims_group10c.py dim_internet (_haversine_m)"
        : "services/scoring/dims_group13.py (CLEARANCE/VIABILITY/YARD_BANDS) + " +
          "dims_batch6.py p386 (100·d/(d+800) campus pressure)",
      "reasonable",
      layer === "mobile"
        ? "Green = strong measured mobile coverage (self-scaling discs): " +
          "radio cells radiate through air — Euclidean is the physical " +
          "metric on both sides."
        : "Green = clear/viable/calm airspace (droneclear/droneviab) or " +
          "far from campus pressure (rentbleed): drones fly, they do not " +
          "walk, and pressure radiates — Euclidean on both sides is " +
          "correct (the drone precedent).",
    );
  }
  if (GRID.has(layer)) {
    return row(
      layer,
      "euclidean-raster",
      "haversine",
      "services/scoring/dims_group03.py + dims_group03d.py + dims_group05a-f.py + " +
        "dims_group08a-d.py + dims_group10rest.py + dims_group17rest.py + " +
        "dims_group18resta.py + dims_batch6.py (all haversine; moorage/drainage " +
        "documented Euclidean-by-construction in snapshot.ts)",
      "reasonable",
      "Green = good drainage/shore/wildfire/vernal/surge/slide/wind/salt/" +
        "sky/day/glare/bleed/solar/privroad/strsat/rentbleed " +
        "field value: exact-grid Dijkstra / smooth Euclidean fields by " +
        "construction (foot graph has no vertices at marinas, pits, " +
        "gardens — walk stamping would leave holes AT the facilities). " +
        "Euclidean on both sides is correct.",
    );
  }
  if (COUNT.has(layer)) {
    return row(
      layer,
      "euclidean-raster",
      "haversine",
      "services/scoring/dims_group05a.py + dims_group05b.py + dims_group05c.py + " +
        "dims_group05e.py + dims_group05f.py + dims_group17a.py + dims_group17b.py + " +
        "dims_group18restb.py + dims_p4_osm.py (blackspots/parking/walkway/darkness) " +
        "(all haversine / around-radius)",
      "reasonable",
      "Green = dense facility counts nearby (gardens, ehitus, compost, " +
        "roadsafety, parking, blockwalk, daylight openness...): Euclidean " +
        "count kernels by construction on the map, around-radius + " +
        "haversine in the scorer. Euclidean on both sides is correct " +
        "(counts, not routes).",
    );
  }
  // True walk-graph raster families (foot-graph-stamped masters).
  if (CORE_WALK.has(layer) || B1.has(layer) || B5.has(layer) || G11C.has(layer)) {
    return row(
      layer,
      "walk-raster",
      "haversine",
      "services/scoring/dims_group12.py (walk_min = haversine/75 + wait + ride) + " +
        "dims_p4_peatus.py (bird-flight at 75 m/min, never routed) + " +
        "livability._nearest_m haversine (dims_group11.py) + dims_group10b.py " +
        "dim_emergency (haversine) + dims_group11c.py",
      "reasonable",
      "Green = short walk to the amenity/safety feature (parks area, " +
        "transit frequency, school variety, network density, food, care, " +
        "pets/culture/nightlife, safety stations, schoolbus/worship): " +
        "pedestrian access, so the foot-graph map kernel is the honest " +
        "metric. The scorer approximates with bird-flight minutes " +
        "(documented, calibrated) — a walk-graph scorer is the " +
        "contested re-tune.",
      WALK_SCORER_FOLLOW_UP,
    );
  }
  if (G11D_AREA.has(layer)) {
    return row(
      layer,
      "walk-raster",
      "haversine",
      "services/scoring/dims_group11b.py (_haversine_m 500 m / 1500 m windows)",
      "reasonable",
      "Green = mailbox/postal/alley access nearby (pedestrian errands): " +
        "foot-graph map kernel is honest; the scorer uses haversine " +
        "windows (documented approximation).",
      WALK_SCORER_FOLLOW_UP,
    );
  }
  if (G06B_AREA.has(layer)) {
    return row(
      layer,
      "walk-raster",
      "haversine",
      "services/scoring/dims_group06b.py (_count_within_m / _nearest haversine)",
      "reasonable",
      "Green = plaster/antiques building stock nearby (heritage " +
        "density hinnang): foot-graph count kernel on the map, " +
        "haversine counts in the scorer (documented approximation).",
      WALK_SCORER_FOLLOW_UP,
    );
  }
  if (layer === "heritage") {
    return row(
      layer,
      "walk-raster",
      "haversine",
      "services/scoring/dims_group06.py (haversine counts)",
      "reasonable",
      "Green = mapped heritage objects nearby (proximity hinnang, never " +
        "a conservation decision): foot-graph density on the map, " +
        "haversine in the scorer (documented approximation).",
      WALK_SCORER_FOLLOW_UP,
    );
  }
  if (layer === "liftproxy") {
    return row(
      layer,
      "walk-raster",
      "attribute",
      "services/scoring/dims_group02b.py dim_elevators (per-building EHR registry count, no distance)",
      "reasonable",
      "Green = high-rise (likely-lift) stock nearby: area likelihood on " +
        "the map vs the building's own registry lift count in the " +
        "scorer — different aspects (area prior vs building fact), so " +
        "the metric differs by design, not by drift.",
    );
  }
  if (layer === "woodfire") {
    return row(
      layer,
      "walk-raster",
      "haversine",
      "services/scoring/dims_group06b.py (haversine)",
      "reasonable",
      "Green = far from mapped wooden houses (fire-spread attention, " +
        "inverted avoid): the scorer's bird-flight is arguably MORE " +
        "physical (fire spreads through air, not footpaths) while the " +
        "map walks — noted, no change: retuning the kernel shape is " +
        "contested.",
      WALK_SCORER_FOLLOW_UP,
    );
  }
  if (layer === "trailprivacy") {
    return row(
      layer,
      "walk-raster",
      "haversine",
      "services/scoring/dims_group11b.py dim_trail_privacy (haversine 500 m window)",
      "reasonable",
      "Green = private (far from dense paths): foot-graph quiet on the " +
        "map, haversine window in the scorer (documented approximation).",
      WALK_SCORER_FOLLOW_UP,
    );
  }
  if (UTIL_WALK.has(layer)) {
    return row(
      layer,
      "walk-raster",
      "haversine",
      "services/scoring/dims_group10c.py dim_water/dim_waste " +
        "(_nearest_m/_count_within_m haversine)",
      "reasonable",
      "Green = water/waste/fiber access nearby (utility access): " +
        "foot-graph map kernel is honest; the scorer uses haversine " +
        "(documented approximation).",
      WALK_SCORER_FOLLOW_UP,
    );
  }
  // Anything left must be a raster-labeled id: report its label so a
  // new family fails review loudly instead of silently joining one.
  const label = rasterDistanceLabel(layer);
  return row(
    layer,
    label === "walk" ? "walk-raster" : "euclidean-raster",
    "haversine",
    "services/scoring (bird-flight convention; exact leg unverified for this id)",
    "reasonable",
    `Unclassified id fell through to the raster label (${label}): review ` +
      `before trusting this row — the completeness test pins the family ` +
      `sets above, so update them, not this fallback.`,
  );
}

/** Full audit table, generated from the LAYERS registry (never hand-enumerated). */
export function buildAuditTable(): AuditRow[] {
  return LAYERS.map((l) => auditRowFor(l.id));
}

/** Pipe table for the PR/issue body. */
export function toMarkdownTable(rows: AuditRow[]): string {
  const head =
    "| id | map | scorer | verdict | rationale |\n|---|---|---|---|---|";
  const esc = (s: string) => s.replace(/\|/g, "\\|").replace(/\n/g, " ");
  return [head, ...rows.map((r) => `| ${r.id} | ${r.map} | ${r.scorer} | ${r.verdict} | ${esc(r.rationale)} |`)].join(
    "\n",
  );
}

