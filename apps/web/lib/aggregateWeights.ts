// Aggregate view weight categories (#819).
//
// Layers grouped into fixed categories, each with its own multiplier:
//   effective weight = layer weight x category multiplier.
//
// CALIBRATION (#819): DEFAULT_WEIGHTS ships CALIBRATED — 151 layer
// defaults from 4 calibrator subagents (/tmp/calib_tables.json, rationale
// preserved as trailing comments below) plus 22 explicit applier gap
// defaults for registered layers with no calib entry (marked "gap").
// 20 further calib entries target layers not yet in the LayerId registry
// (batch4/group09/genv/group15); they land when those layers register.
// Category multipliers stay NEUTRAL (1) — calibrators set layer weights
// only. Reset in the UI restores these shipped defaults.

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
 * Category per layer (#819): calibrated assignments where a calib entry
 * exists, scaffolding guess otherwise (gap layers keep their guess —
 * all 22 sit in the sibling-plausible category). Every LayerId must
 * appear exactly once.
 */
export const LAYER_CATEGORY: Record<LayerId, AggregateCategory> = {
  // nature (7 calibrated)
  parks: "nature",
  forage: "nature",
  wildcorr: "nature",
  relief: "nature",
  canopy: "nature",
  forest: "nature",
  lawncare: "nature",
  // stores (4 calibrated)
  grocery: "stores",
  dailyshop: "stores",
  lastshop: "stores",
  antiques: "stores",
  // transport (15 calibrated + 13 applier gap)
  transit: "transport",
  busmesh: "transport", // gap default (no calib entry)
  "busmesh-sat": "transport", // gap default (no calib entry)
  "busmesh-sun": "transport", // gap default (no calib entry)
  gtfsstops: "transport",
  cycling: "transport",
  walkability: "transport",
  blockwalk: "transport",
  pedinfra: "transport",
  alley: "transport",
  parking: "transport",
  carfriction: "transport", // gap default (no calib entry)
  gbfs: "transport",
  "shed-15-peak": "transport", // gap default (no calib entry)
  "shed-15-offpeak": "transport", // gap default (no calib entry)
  "shed-30-peak": "transport", // gap default (no calib entry)
  "shed-30-offpeak": "transport", // gap default (no calib entry)
  "delay-morning": "transport",
  "delay-midday": "transport",
  "delay-evening": "transport",
  "delay-offpeak": "transport",
  "delay-worst": "transport",
  "datex-cameras": "transport", // gap default (no calib entry)
  "datex-counters": "transport", // gap default (no calib entry)
  "datex-restrictions": "transport", // gap default (no calib entry)
  "datex-srti": "transport", // gap default (no calib entry)
  "datex-truckpark": "transport", // gap default (no calib entry)
  "datex-weather": "transport", // gap default (no calib entry)
  incidents: "transport",
  // health (7 calibrated + 1 applier gap)
  healthcare: "health",
  medspecial: "health",
  medre_gp: "health",
  medre_clinic: "health",
  poi_pharmacy: "health", // gap default (no calib entry)
  industprox: "health",
  vectorhabitat: "health",
  agriland: "health",
  // safety (16 calibrated)
  aed: "safety",
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
  oiltank: "safety",
  slidebuf: "safety",
  surgeroad: "safety",
  darkness: "safety",
  // education (4 calibrated + 4 applier gap)
  schoolbus: "education",
  schools: "education",
  ehis_school: "education", // gap default (no calib entry)
  ehis_kindergarten: "education", // gap default (no calib entry)
  ehis_hobby: "education", // gap default (no calib entry)
  harno: "education",
  libraries: "education",
  poi_library: "education", // gap default (no calib entry)
  // leisure (20 calibrated + 3 applier gap)
  trailprivacy: "leisure",
  tervise: "leisure",
  culture: "leisure",
  sport_pool: "leisure", // gap default (no calib entry)
  sport_hall: "leisure", // gap default (no calib entry)
  sport_field: "leisure", // gap default (no calib entry)
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
  droneclear: "leisure",
  droneviab: "leisure",
  herd: "leisure",
  // housing (25 calibrated)
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
  upcycle: "housing",
  privroad: "housing",
  taxidoor: "housing",
  kpo: "housing",
  buildout: "housing",
  ehitus: "housing",
  kovehit: "housing",
  buildings: "housing",
  density: "housing",
  soil: "housing",
  fishbowl: "housing",
  mossrisk: "housing",
  saltspray: "housing",
  // environment (27 calibrated)
  eeliskaitse: "environment",
  eelisniit: "environment",
  kalmistu: "environment",
  commbleed: "environment",
  noise: "environment",
  floodzone: "environment",
  quarry: "environment",
  brownsoil: "environment",
  etak: "environment",
  maaparandus: "environment",
  drainage: "environment",
  eelisraie: "environment",
  odorsrc: "environment",
  senscom: "environment",
  ohuseire: "environment",
  kliima_frost: "environment",
  kliima_wet: "environment",
  viirs: "environment",
  daylight: "environment",
  dayopen: "environment",
  glassglare: "environment",
  shoredist: "environment",
  vernalpool: "environment",
  windtunnel: "environment",
  agrifield: "environment",
  kirikukellad: "environment",
  kajakad: "environment",
  // utilities (14 calibrated + 1 applier gap)
  windsolar: "utilities",
  fiber: "utilities",
  mobile: "utilities",
  ookla_fixed: "utilities",
  ookla_mobile: "utilities",
  water: "utilities",
  waste: "utilities",
  compost: "utilities",
  outage: "utilities",
  skyview: "utilities",
  postal: "utilities",
  mailbox: "utilities",
  poi_post: "utilities", // gap default (no calib entry)
  leafdrop: "utilities",
  gritbin: "utilities",
  // community (12 calibrated)
  fixit: "community",
  raamatukapid: "community",
  strsat: "community",
  community: "community",
  heritage: "community",
  worship: "community",
  thirdplace: "community",
  pets: "community",
  wc: "community",
  gardens: "community",
  kovmigr: "community",
  kovfisc: "community",
};

/**
 * Shipped per-layer default weights (#819). Calibrated 0..2 in 0.25
 * steps; Reset restores this map. Trailing comments are the calibrator
 * rationale (shortened); "gap" marks applier defaults for layers with
 * no calib entry.
 */
export const DEFAULT_WEIGHTS: Record<LayerId, number> = {
  // ---- nature ----
  parks: 1.5, // Green-area proximity is a top stated buyer criterion (families, dog owners, runners).
  forage: 0.5, // Berry/mushroom forest proximity is a beloved but non-decisive hobby perk.
  wildcorr: 0.5, // Wildlife-corridor encounters are occasional curiosity, rarely decision-relevant.
  relief: 0, // Unscored taste tint (hinnanguta); off by default.
  canopy: 0, // Taste-only canopy tint with no rating; off by default in aggregate.
  forest: 0.5, // Detected canopy change is background greenery context, weakly decision-linked.
  lawncare: 0.5, // Mowed-green upkeep signal; streetscape upkeep, not a core need.
  // ---- stores ----
  grocery: 1.75, // Walkable food shopping is the single most-used everyday convenience.
  dailyshop: 2, // Daily grocery proximity is a universal top buyer/renter priority.
  lastshop: 1.5, // Last-shop desert warning flags genuine everyday-viability risk.
  antiques: 0.25, // Antique-shop proximity is niche retail, irrelevant to almost all movers.
  // ---- transport ----
  transit: 2, // Frequent-transit walk access drives daily commute for car-free and one-car households.
  busmesh: 1.5, // Weekday transfer-node depth refines base transit access; below transit/gtfsstops 2.0.
  "busmesh-sat": 1, // Saturday transfer service thinner; secondary to weekday mesh.
  "busmesh-sun": 1, // Sunday transfer service thinner; secondary to weekday mesh.
  gtfsstops: 2, // Scheduled transit access is the single most decision-relevant mobility layer.
  cycling: 1.25, // Bike-lane density matters to commuters/casual riders; secondary to transit and walking.
  walkability: 1.5, // Dense connected street grid underpins car-light everyday life for almost all buyers.
  blockwalk: 1.5, // Everyday sidewalk/paving walkability is core livability.
  pedinfra: 1.25, // Sidewalk density matters daily on foot, but largely overlaps walkability signal.
  alley: 0.25, // Back-alley proximity is cartographic trivia with no plausible buyer demand.
  parking: 1.5, // Mapped parking density is daily convenience for car owners.
  carfriction: 1, // Driving-restriction density is a real car-hardship signal; moderate until calibrated.
  gbfs: 1, // Bikeshare station access is a real everyday mobility option.
  "shed-15-peak": 1.5, // Peak 15-min catchment decides commute feasibility (delay-morning parity).
  "shed-15-offpeak": 0.5, // Free-flow reference catchment; small residual so off-peak reachability still counts.
  "shed-30-peak": 1.25, // Peak 30-min catchment; wide-radius commute option (delay-worst parity).
  "shed-30-offpeak": 0.5, // Free-flow reference catchment; small residual so off-peak reachability still counts.
  "delay-morning": 1.5, // Morning peak delay hits the daily commute directly.
  "delay-midday": 0.75, // Midday delay matters less; few buyers drive midday daily.
  "delay-evening": 1.5, // Evening peak delay mirrors morning commute pain.
  "delay-offpeak": 0, // Free-flow baseline is a reference level, not a decision signal; off by default.
  "delay-worst": 1.25, // Worst-peak robustness captures commute worst-case stress.
  "datex-cameras": 0.5, // Pins-only traffic overlay; inert in combine, fixit-parity small default.
  "datex-counters": 0.5, // Pins-only traffic overlay; inert in combine, fixit-parity small default.
  "datex-restrictions": 0.5, // Pins-only traffic overlay; inert in combine, fixit-parity small default.
  "datex-srti": 0.5, // Pins-only traffic overlay; inert in combine, fixit-parity small default.
  "datex-truckpark": 0.5, // Pins-only traffic overlay; inert in combine, fixit-parity small default.
  "datex-weather": 0.5, // Pins-only traffic overlay; inert in combine, fixit-parity small default.
  incidents: 0.75, // 6h TomTom traffic snapshot rarely decides a home purchase.
  // ---- health ----
  healthcare: 1.75, // Pharmacy/doctor proximity is high-stakes for elderly, families, chronic care.
  medspecial: 1.5, // Hospital/dentist access is a high-priority healthcare need across ages.
  medre_gp: 1.75, // Everyday GP access is core for family buyers/renters.
  medre_clinic: 1.5, // Clinic proximity matters slightly less than own GP list.
  poi_pharmacy: 1.5, // Pharmacy slice; just below full healthcare (1.75).
  industprox: 1.5, // Industrial air-quality proximity is a top-tier health concern for families.
  vectorhabitat: 1.25, // Tick/mosquito habitat is a widely felt health nuisance in a forest-rich region.
  agriland: 1, // Pesticide drift from arable fields is a real health/nuisance factor at the suburban fringe.
  // ---- safety ----
  aed: 0.25, // Only 11 mapped defibrillators; too sparse to score by default.
  safety: 1.5, // Police-proximity estimate proxies felt security, a core common-buyer concern.
  emergency: 1.5, // Fire-station/hospital proximity is the highest-stakes safety signal for most buyers.
  hydrants: 0.5, // Hydrant proximity is firefighter infrastructure, invisible to buyer decisions.
  dispatch: 1.25, // Combined 112-services proximity restates safety/emergency; moderate to limit overlap.
  evac: 0.5, // Trunk-road proxy, not an official evacuation plan — background resilience only.
  paaste: 1.25, // Rescue-command coverage is reassurance-level safety.
  roadsafety: 1.25, // Crossing/calming density proxies child/pedestrian safety.
  accblack: 1.5, // Measured severe-crash blackspots are hard road-danger data buyers act on.
  seveso: 1.75, // Major-accident hazard zones are a hard avoidance factor.
  woodfire: 1.25, // Wooden-house fire-spread risk is a genuine safety factor in timber districts (e.g. Kalamaja).
  wildfire: 1.25, // Forest-fire buffer/defensible space is a material safety factor for forest-edge homes.
  oiltank: 1, // Fuel-tank proximity is a moderate hazard/nuisance flag worth a default point.
  slidebuf: 0.75, // Cliff/rockfall collapse proximity is a real but highly localized geohazard.
  surgeroad: 1, // Storm-surge street impassability is a concrete access/safety risk on coastal roads.
  darkness: 1.25, // Street lighting drives perceived evening safety.
  // ---- education ----
  schoolbus: 1.25, // Walkable school-with-stop access is a core family criterion.
  schools: 1.5, // School/kindergarten walk distance decides family purchases; irrelevant only to child-free buyers.
  ehis_school: 1.5, // Measured-school slice of the schools (1.5) walk-distance signal.
  ehis_kindergarten: 1.5, // Kindergarten walk distance decides family purchases like schools (1.5).
  ehis_hobby: 1, // Hobby-school plus; active-lifestyle convenience at recspecial parity (1.0).
  harno: 1.75, // School exam quality is a top family-buyer decision factor.
  libraries: 0.75, // Library proximity a steady family/student plus, weaker than schools themselves.
  poi_library: 0.75, // Long-tail slice of libraries (0.75).
  // ---- leisure ----
  trailprivacy: 0.5, // Hiking-trail privacy cuts both ways (access vs seclusion); low default either way.
  tervise: 1, // Monitored swimming-water quality is a summer plus.
  culture: 1, // Theatre/museum proximity valued by urban buyers; city-level amenity, not daily need.
  sport_pool: 1.25, // Pools scarce with strong family/fitness demand (manguvaljakud parity).
  sport_hall: 1, // Standard active-lifestyle convenience (recspecial parity).
  sport_field: 1, // Standard active-lifestyle convenience (recspecial parity).
  recspecial: 1, // Stadium/pool/hall proximity is a standard active-lifestyle convenience.
  equestrian: 0.25, // Horse-riding access is a rare hobby filter, not a common decision factor.
  manguvaljakud: 1.25, // Playground in walking distance matters to family buyers.
  tanavasport: 0.75, // Outdoor gyms/skate/disc-golf appeal to active buyers.
  talisuplus: 0.5, // Winter-swimming spots serve a niche hobby.
  skis: 1, // Groomed ski-trail access is a real winter plus in Estonia.
  saunad: 0.75, // Public sauna nearby is everyday convenience in Estonia.
  moorage: 0.25, // Harbour/berth proximity is pure boating-niche signal.
  koertepargid: 0.5, // Barking-avoidance; relevant only to sensitive buyers/owners.
  vesi: 0.5, // Fountains/drinking water are micro-amenities.
  viewshed: 0.5, // Protected-view proximity is an aesthetic bonus, rarely a purchase criterion.
  activity: 1, // Evening-use venue density signals a lively, walkable neighbourhood.
  nightlife: 0.5, // Bars/cinema nearby is a lifestyle plus — and noise-adjacent, so keep modest.
  harbour: 0.5, // Harbour/boating recreation amenity for a small buyer segment.
  droneclear: 0.25, // Hobby-drone airspace proxy relevant to a tiny enthusiast niche.
  droneviab: 0.25, // Speculative drone-delivery proxy; no buyer shops for this today.
  herd: 0.5, // Gallery/museum taste layer; cultural amenity for a minority of buyers.
  // ---- housing ----
  korterstock: 0.75, // Apartment density / rental liquidity matters to investors and renters, less to owner-occupiers.
  liftproxy: 0.5, // Tall-building proximity as lift proxy matters to elderly/mobility buyers only.
  plaster: 0.25, // Plaster-facade craftsmanship proxy is an enthusiast aesthetic, not a market driver.
  maaparcel: 0.75, // Ownership-form cadastre info is useful context, not a quality score.
  planktpr: 1.5, // Planned land use shapes future neighbours and value.
  stateland: 0.5, // State-land/auction adjacency is niche buyer trivia.
  kovedas: 1.25, // Resale attractiveness composite is core buyer downside protection.
  kovkaive: 1, // Market depth signals resale liquidity risk.
  kovkasv: 1.25, // Municipal price trend directly informs buyer value/investment judgement.
  kovkiirus: 0.5, // Turnover-change layer is explicitly weak and capped; low trust weight.
  asumedia: 0, // Pending estimate with empty field (no subdistricts meet MIN_N) — keep off until data exists.
  rentbleed: 0.75, // Student-rent pressure proxy matters to renters/peace-seekers near universities.
  upcycle: 0.5, // Abandoned-building redevelopment potential is investor-niche, not owner-occupier relevant.
  privroad: 1.25, // Private-road maintenance burden is a real hidden cost risk for buyers.
  taxidoor: 0.25, // Mapped-entrance findability is an explicitly weak proxy, near-noise.
  kpo: 1.75, // Building bans/conditions directly constrain what owners can do.
  buildout: 0.75, // Future-densification pressure is worth a mild default signal, mostly for long-horizon buyers.
  ehitus: 1, // Nearby construction signals a developing area but also years of disturbance; moderate everyday relevance.
  kovehit: 1, // Local oversupply flags price-drop risk.
  buildings: 0, // Taste-only height tint with no rating; off by default in aggregate.
  density: 0, // Taste-only settlement tint with no rating; off by default in aggregate.
  soil: 1, // Soil/foundation conditions matter to house builders/buyers.
  fishbowl: 0.5, // Corner-lot exposure/privacy; matters to some buyers, invisible to most.
  mossrisk: 0.5, // Roof moss/moisture risk near forest; a maintenance note, not a dealbreaker.
  saltspray: 0.5, // Sea salt-spray facade wear is a coastal maintenance footnote, not a buying criterion.
  // ---- environment ----
  eeliskaitse: 0.5, // Protected-area restriction flag: important when it bites, inert for most addresses.
  eelisniit: 0.5, // Coarse tick-habitat meadow proxy; health-adjacent but too rough to steer buying.
  kalmistu: 0.5, // Cemetery-green quiet is a soft plus, neutral overall.
  commbleed: 1, // Commercial-zone traffic/noise spillover affects residential calm in mixed districts.
  noise: 2, // Chronic strategic noise is the most common home dealbreaker.
  floodzone: 1.5, // Flood-zone membership is catastrophic-risk info buyers pay for despite thin Tallinn data.
  quarry: 1.25, // Quarry/blasting proximity is a strong but rare local negative.
  brownsoil: 1.25, // Former-industrial soil contamination risk matters to families and gardeners.
  etak: 1, // Wetland/water/yard zone overlay flags moisture and drainage context.
  maaparandus: 0.75, // Drainage/moisture risk matters mostly to suburban house buyers.
  drainage: 1, // Open-water/wetland drainage proxy flags damp-basement risk worth a full point.
  eelisraie: 0.25, // Single-record logging change flag, not a livability gradient.
  odorsrc: 1.5, // Treatment-plant/landfill odor ruins livability where present; high avoidance weight.
  senscom: 0.5, // Uncalibrated DIY sensor density is a weak signal.
  ohuseire: 0.5, // Only 3 official stations; weak proxy, curiosity value.
  kliima_frost: 0.5, // 70 km climate cell is far too coarse to differentiate homes.
  kliima_wet: 0.5, // Same coarse-cell caveat as frost; background context only.
  viirs: 0.5, // Night-sky brightness (2016 composite) is stargazer niche.
  daylight: 1, // Building-density daylight spaciousness shapes daily comfort.
  dayopen: 1, // Sky openness/daylight overshadowing affects everyday living quality.
  glassglare: 0.25, // Facade glare is a rare micro-nuisance, almost never decision-relevant.
  shoredist: 0.75, // Shore building-restriction estimate matters only coastally / for builders, not the typical buyer.
  vernalpool: 0.5, // Ephemeral-pool spring dampness is a minor moisture footnote for few parcels.
  windtunnel: 0.75, // High-rise wind-canyon discomfort affects dense districts but is second-order comfort.
  agrifield: 0.75, // Broader farm-proximity layer overlapping agriland drift; kept lower to avoid double counting.
  kirikukellad: 0.5, // Sunday bell nuisance affects only a few streets.
  kajakad: 0.5, // Gull noise/litter is a hyper-local nuisance.
  // ---- utilities ----
  windsolar: 0.5, // Wind/solar-farm noise and shadowing concern mainly rural-edge buyers; irrelevant in the city.
  fiber: 1.5, // Reported >=1000 Mbit/s coverage is decisive for remote workers, table stakes otherwise.
  mobile: 1, // Measured LTE coverage mostly saturated; differentiates only dead-zone edges.
  ookla_fixed: 1.25, // Home-office fixed internet speed matters to many buyers.
  ookla_mobile: 1, // Mobile speed is less decision-relevant than fixed line.
  water: 0.25, // Public taps/wells serve hikers and dog walkers only — not a housing decision factor.
  waste: 1, // Bottle/recycling drop-off proximity is routine Estonian everyday logistics.
  compost: 0.5, // Waste-station proximity is a convenience, rarely decision-driving.
  outage: 1.25, // Power reliability matters; grid mostly reliable so moderate.
  skyview: 0.25, // Open-sky satellite-internet suitability is a rare tech edge case.
  postal: 1, // Post office/parcel-locker access is a genuine everyday errand factor.
  mailbox: 0.5, // Post-box proximity is trivial daily convenience in the parcel-locker era.
  poi_post: 1, // Long-tail slice of postal (1.0); moved to utilities for sibling parity.
  leafdrop: 0.5, // Garden-waste collection point; niche convenience for house owners.
  gritbin: 0.75, // Winter maintenance proxy matters for walkability/safety in Estonian winters.
  // ---- community ----
  fixit: 0.5, // Complaint density measures reporting behaviour, not liveability; low trust.
  raamatukapid: 0.25, // 18 bookcases; charming but not decision-relevant.
  strsat: 1, // Short-term-rental saturation drives noise and turnover in tourist cores; moderate default weight.
  community: 0.75, // Community rooms nice for belonging; rarely a purchase dealbreaker.
  heritage: 0.5, // Heritage proximity adds charm but seldom decides a purchase.
  worship: 0.5, // Churches matter deeply to some buyers but not to the common default profile.
  thirdplace: 1.25, // Cafes/sauna/library nearby underpin daily social life and belonging.
  pets: 0.5, // Dog-park/vet proximity matters strongly but only to pet-owning subset.
  wc: 0.5, // Public toilets are convenience, not a home-decision factor.
  gardens: 0.5, // Community gardens are a nice-to-have hobby amenity for a small minority.
  kovmigr: 1, // Municipal inflow signals area vitality and demand.
  kovfisc: 1.25, // Municipal fiscal health underpins taxes and services.
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

/**
 * Sanitize an unknown factor map from storage (toggle stash / expanded
 * extras, #825): finite non-negative numbers clamped to WEIGHT_MAX,
 * everything else dropped so old or hand-edited blobs stay loadable.
 */
export function cleanFactorMap(v: unknown): Record<string, number> {
  const out: Record<string, number> = {};
  if (!v || typeof v !== "object" || Array.isArray(v)) return out;
  for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
    if (typeof val === "number" && Number.isFinite(val) && val >= 0) {
      out[k] = Math.min(WEIGHT_MAX, val);
    }
  }
  return out;
}

/**
 * Quick-trial checkbox toggle with restore (#825). Uncheck stashes
 * the nonzero value and yields 0; re-check restores the stash (or
 * the shipped fallback, or 1 when both are non-positive).
 */
export function toggleFactor(
  current: number,
  stash: number | undefined,
  fallback: number,
): { value: number; stash: number | undefined } {
  if (current > 0) return { value: 0, stash: current };
  const back = stash ?? fallback;
  return { value: back > 0 ? back : 1, stash };
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
