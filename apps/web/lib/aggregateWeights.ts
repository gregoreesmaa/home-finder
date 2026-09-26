// Aggregate view weight categories (#819).
//
// Layers grouped into fixed categories, each with its own multiplier:
//   effective weight = layer weight x category multiplier.
//
// CALIBRATION: DEFAULT_WEIGHTS and DEFAULT_CATEGORY_MULTIPLIERS ship
// NEUTRAL (every layer 1, every multiplier 1) with best-guess category
// assignments. Applying calibrated values later is a pure data edit to
// the two DEFAULT_* maps below — no logic changes needed. Reset in the
// UI restores these shipped defaults.

import type { LayerId } from "./layers";

/** Fixed category set for the aggregate view (#819). */
export const CATEGORIES = [
  "nature",
  "stores",
  "transport",
  "health",
  "safety",
  "education",
  "leisure",
  "housing",
  "environment",
  "utilities",
  "community",
] as const;

export type AggregateCategory = (typeof CATEGORIES)[number];

/** Human one-liners for the category sliders (Estonian, like the UI). */
export const CATEGORY_LABEL: Record<AggregateCategory, string> = {
  nature: "Loodus ja rohealad",
  stores: "Poed ja teenused",
  transport: "Transport ja liikuvus",
  health: "Tervis",
  safety: "Turvalisus",
  education: "Haridus",
  leisure: "Vaba aeg",
  housing: "Eluase ja kinnisvara",
  environment: "Keskkond ja riskid",
  utilities: "Tehnovõrgud",
  community: "Kogukond",
};

/**
 * Best-guess category per layer (neutral scaffolding for #819; final
 * calibrated weights arrive separately as a data edit). Every LayerId
 * must appear exactly once.
 */
export const LAYER_CATEGORY: Record<LayerId, AggregateCategory> = {
  // nature
  parks: "nature",
  forage: "nature",
  wildcorr: "nature",
  eeliskaitse: "nature",
  eelisniit: "nature",
  kalmistu: "nature",
  trailprivacy: "nature",
  relief: "nature",
  canopy: "nature",
  // stores
  grocery: "stores",
  dailyshop: "stores",
  lastshop: "stores",
  antiques: "stores",
  // transport (pins layers ride along; they never combine, kind "pins")
  transit: "transport",
  busmesh: "transport",
  "busmesh-sat": "transport",
  "busmesh-sun": "transport",
  gtfsstops: "transport",
  cycling: "transport",
  walkability: "transport",
  blockwalk: "transport",
  pedinfra: "transport",
  alley: "transport",
  parking: "transport",
  schoolbus: "transport",
  gbfs: "transport",
  "shed-15-peak": "transport",
  "shed-15-offpeak": "transport",
  "shed-30-peak": "transport",
  "shed-30-offpeak": "transport",
  "delay-morning": "transport",
  "delay-midday": "transport",
  "delay-evening": "transport",
  "delay-offpeak": "transport",
  "delay-worst": "transport",
  "datex-cameras": "transport",
  "datex-counters": "transport",
  "datex-restrictions": "transport",
  "datex-srti": "transport",
  "datex-truckpark": "transport",
  "datex-weather": "transport",
  incidents: "transport",
  fixit: "transport",
  // health
  healthcare: "health",
  medspecial: "health",
  medre_gp: "health",
  medre_clinic: "health",
  poi_pharmacy: "health",
  aed: "health",
  tervise: "health",
  // safety
  safety: "safety",
  emergency: "safety",
  hydrants: "safety",
  dispatch: "safety",
  evac: "safety",
  paaste: "safety",
  roadsafety: "safety",
  accblack: "safety",
  seveso: "safety",
  woodfire: "safety",
  wildfire: "safety",
  // education
  schools: "education",
  ehis_school: "education",
  ehis_kindergarten: "education",
  ehis_hobby: "education",
  harno: "education",
  libraries: "education",
  poi_library: "education",
  raamatukapid: "education",
  // leisure
  culture: "leisure",
  sport_pool: "leisure",
  sport_hall: "leisure",
  sport_field: "leisure",
  recspecial: "leisure",
  equestrian: "leisure",
  manguvaljakud: "leisure",
  tanavasport: "leisure",
  talisuplus: "leisure",
  skis: "leisure",
  saunad: "leisure",
  moorage: "leisure",
  koertepargid: "leisure",
  vesi: "leisure",
  viewshed: "leisure",
  activity: "leisure",
  nightlife: "leisure",
  harbour: "leisure",
  // housing
  korterstock: "housing",
  liftproxy: "housing",
  plaster: "housing",
  maaparcel: "housing",
  planktpr: "housing",
  stateland: "housing",
  kovedas: "housing",
  kovkaive: "housing",
  kovkasv: "housing",
  kovkiirus: "housing",
  asumedia: "housing",
  rentbleed: "housing",
  commbleed: "housing",
  upcycle: "housing",
  privroad: "housing",
  taxidoor: "housing",
  kpo: "housing",
  buildout: "housing",
  ehitus: "housing",
  kovehit: "housing",
  buildings: "housing",
  density: "housing",
  strsat: "housing",
  // environment
  noise: "environment",
  floodzone: "environment",
  quarry: "environment",
  soil: "environment",
  brownsoil: "environment",
  etak: "environment",
  maaparandus: "environment",
  drainage: "environment",
  eelisraie: "environment",
  forest: "environment",
  industprox: "environment",
  odorsrc: "environment",
  oiltank: "environment",
  senscom: "environment",
  ohuseire: "environment",
  kliima_frost: "environment",
  kliima_wet: "environment",
  viirs: "environment",
  daylight: "environment",
  dayopen: "environment",
  glassglare: "environment",
  fishbowl: "environment",
  mossrisk: "environment",
  saltspray: "environment",
  slidebuf: "environment",
  surgeroad: "environment",
  shoredist: "environment",
  vernalpool: "environment",
  vectorhabitat: "environment",
  windsolar: "environment",
  windtunnel: "environment",
  agrifield: "environment",
  agriland: "environment",
  kirikukellad: "environment",
  kajakad: "environment",
  // utilities
  fiber: "utilities",
  mobile: "utilities",
  ookla_fixed: "utilities",
  ookla_mobile: "utilities",
  water: "utilities",
  waste: "utilities",
  compost: "utilities",
  outage: "utilities",
  skyview: "utilities",
  darkness: "utilities",
  droneclear: "utilities",
  droneviab: "utilities",
  // community
  community: "community",
  heritage: "community",
  worship: "community",
  thirdplace: "community",
  herd: "community",
  postal: "community",
  mailbox: "community",
  poi_post: "community",
  leafdrop: "community",
  gritbin: "community",
  lawncare: "community",
  pets: "community",
  wc: "community",
  gardens: "community",
  kovmigr: "community",
  kovfisc: "community",
};

/**
 * Shipped per-layer default weights (#819). NEUTRAL: every layer 1.
 * Calibrators edit values here (0..2); Reset restores this map.
 */
export const DEFAULT_WEIGHTS: Record<LayerId, number> = {
  parks: 1,
  forage: 1,
  wildcorr: 1,
  eeliskaitse: 1,
  eelisniit: 1,
  kalmistu: 1,
  trailprivacy: 1,
  relief: 1,
  canopy: 1,
  grocery: 1,
  dailyshop: 1,
  lastshop: 1,
  antiques: 1,
  transit: 1,
  busmesh: 1,
  "busmesh-sat": 1,
  "busmesh-sun": 1,
  gtfsstops: 1,
  cycling: 1,
  walkability: 1,
  blockwalk: 1,
  pedinfra: 1,
  alley: 1,
  parking: 1,
  schoolbus: 1,
  gbfs: 1,
  "shed-15-peak": 1,
  "shed-15-offpeak": 1,
  "shed-30-peak": 1,
  "shed-30-offpeak": 1,
  "delay-morning": 1,
  "delay-midday": 1,
  "delay-evening": 1,
  "delay-offpeak": 1,
  "delay-worst": 1,
  "datex-cameras": 1,
  "datex-counters": 1,
  "datex-weather": 1,
  "datex-restrictions": 1,
  "datex-srti": 1,
  "datex-truckpark": 1,
  incidents: 1,
  fixit: 1,
  healthcare: 1,
  medspecial: 1,
  medre_gp: 1,
  medre_clinic: 1,
  poi_pharmacy: 1,
  aed: 1,
  tervise: 1,
  safety: 1,
  emergency: 1,
  hydrants: 1,
  dispatch: 1,
  evac: 1,
  paaste: 1,
  roadsafety: 1,
  accblack: 1,
  seveso: 1,
  woodfire: 1,
  wildfire: 1,
  schools: 1,
  ehis_school: 1,
  ehis_kindergarten: 1,
  ehis_hobby: 1,
  harno: 1,
  libraries: 1,
  poi_library: 1,
  raamatukapid: 1,
  culture: 1,
  sport_pool: 1,
  sport_hall: 1,
  sport_field: 1,
  recspecial: 1,
  equestrian: 1,
  manguvaljakud: 1,
  tanavasport: 1,
  talisuplus: 1,
  skis: 1,
  saunad: 1,
  moorage: 1,
  koertepargid: 1,
  vesi: 1,
  viewshed: 1,
  activity: 1,
  nightlife: 1,
  harbour: 1,
  korterstock: 1,
  liftproxy: 1,
  plaster: 1,
  maaparcel: 1,
  planktpr: 1,
  stateland: 1,
  kovedas: 1,
  kovkaive: 1,
  kovkasv: 1,
  kovkiirus: 1,
  asumedia: 1,
  rentbleed: 1,
  commbleed: 1,
  upcycle: 1,
  privroad: 1,
  taxidoor: 1,
  kpo: 1,
  buildout: 1,
  ehitus: 1,
  kovehit: 1,
  buildings: 1,
  density: 1,
  strsat: 1,
  noise: 1,
  floodzone: 1,
  quarry: 1,
  soil: 1,
  brownsoil: 1,
  etak: 1,
  maaparandus: 1,
  drainage: 1,
  eelisraie: 1,
  forest: 1,
  industprox: 1,
  odorsrc: 1,
  oiltank: 1,
  senscom: 1,
  ohuseire: 1,
  kliima_frost: 1,
  kliima_wet: 1,
  viirs: 1,
  daylight: 1,
  dayopen: 1,
  glassglare: 1,
  fishbowl: 1,
  mossrisk: 1,
  saltspray: 1,
  slidebuf: 1,
  surgeroad: 1,
  shoredist: 1,
  vernalpool: 1,
  vectorhabitat: 1,
  windsolar: 1,
  windtunnel: 1,
  agrifield: 1,
  agriland: 1,
  kirikukellad: 1,
  kajakad: 1,
  fiber: 1,
  mobile: 1,
  ookla_fixed: 1,
  ookla_mobile: 1,
  water: 1,
  waste: 1,
  compost: 1,
  outage: 1,
  skyview: 1,
  darkness: 1,
  droneclear: 1,
  droneviab: 1,
  community: 1,
  heritage: 1,
  worship: 1,
  thirdplace: 1,
  herd: 1,
  postal: 1,
  mailbox: 1,
  poi_post: 1,
  leafdrop: 1,
  gritbin: 1,
  lawncare: 1,
  pets: 1,
  wc: 1,
  gardens: 1,
  kovmigr: 1,
  kovfisc: 1,
};

/**
 * Shipped per-category default multipliers (#819). NEUTRAL: every
 * category 1. Calibrators edit values here (0..2).
 */
export const DEFAULT_CATEGORY_MULTIPLIERS: Record<AggregateCategory, number> = {
  nature: 1,
  stores: 1,
  transport: 1,
  health: 1,
  safety: 1,
  education: 1,
  leisure: 1,
  housing: 1,
  environment: 1,
  utilities: 1,
  community: 1,
};

/** Slider bounds shared by layer weights and category multipliers. */
export const WEIGHT_MIN = 0;
export const WEIGHT_MAX = 2;
export const WEIGHT_STEP = 0.25;

function saneFactor(v: unknown, fallback: number): number {
  return typeof v === "number" && Number.isFinite(v)
    ? Math.min(WEIGHT_MAX, Math.max(WEIGHT_MIN, v))
    : fallback;
}

/**
 * Effective combine weight for one layer: layer weight x its category
 * multiplier. Missing entries fall back to shipped defaults; a 0 on
 * either side excludes the layer (combine skips weight <= 0).
 */
export function effectiveWeight(
  layer: LayerId,
  layerWeights: Partial<Record<LayerId, number>>,
  categoryMultipliers: Partial<Record<AggregateCategory, number>>,
): number {
  const lw = saneFactor(layerWeights[layer], DEFAULT_WEIGHTS[layer] ?? 1);
  const cat = LAYER_CATEGORY[layer];
  const cm = saneFactor(
    categoryMultipliers[cat],
    DEFAULT_CATEGORY_MULTIPLIERS[cat] ?? 1,
  );
  return lw * cm;
}

/** Persisted aggregate-view state (v2 store). */
export interface StoredAggregateState {
  weights: Record<string, number>;
  multipliers: Record<string, number>;
  mode: string;
}

/** Local-storage key for weights + multipliers + mode (#819). */
export const STORE_KEY = "hf-aggregate-v2";

/**
 * Legacy v1 key (weights + mode only, no multipliers). Never read:
 * a v1 blob carries no category multipliers, so it cannot express v2
 * state — fall back to shipped defaults instead of half-migrating it.
 */
export const LEGACY_STORE_KEY = "hf-aggregate-v1";

/**
 * Parse a v2 store blob; null when unreadable (missing, corrupt, or
 * wrong shape) so the caller falls back to shipped defaults. Unknown
 * layer/category keys are dropped; numerics are clamped to slider
 * bounds.
 */
export function parseStoredAggregate(raw: unknown): StoredAggregateState | null {
  if (!raw || typeof raw !== "object") return null;
  const body = raw as {
    weights?: unknown;
    multipliers?: unknown;
    mode?: unknown;
  };
  if (
    body.weights !== undefined &&
    (typeof body.weights !== "object" ||
      body.weights === null ||
      Array.isArray(body.weights))
  ) {
    return null;
  }
  if (
    body.multipliers !== undefined &&
    (typeof body.multipliers !== "object" ||
      body.multipliers === null ||
      Array.isArray(body.multipliers))
  ) {
    return null;
  }
  const weights: Record<string, number> = {};
  for (const [k, v] of Object.entries(
    (body.weights ?? {}) as Record<string, unknown>,
  )) {
    if (typeof v === "number" && Number.isFinite(v)) {
      weights[k] = Math.min(WEIGHT_MAX, Math.max(WEIGHT_MIN, v));
    }
  }
  const multipliers: Record<string, number> = {};
  for (const [k, v] of Object.entries(
    (body.multipliers ?? {}) as Record<string, unknown>,
  )) {
    if (typeof v === "number" && Number.isFinite(v)) {
      multipliers[k] = Math.min(WEIGHT_MAX, Math.max(WEIGHT_MIN, v));
    }
  }
  const mode = typeof body.mode === "string" ? body.mode : "average";
  return { weights, multipliers, mode };
}
