// Buyer-adjustable livability weights (#74) + per-dim metadata.
//
// The API serves each listing's `dims` (per-dimension 0..100 scores, null
// when missing) computed with the DEFAULT registry weights in
// services/scoring/livability.py (WEIGHTS — keep DIMS in sync with it).
// Here the buyer multiplies dimensions (sliders, URL-shared) and the list
// re-sorts client-side; untouched sliders reproduce the base score exactly.

export interface DimMeta {
  key: string;
  /** Estonian label shown next to the slider. */
  label: string;
  /** Registry default weight (informational; mirrors livability.WEIGHTS). */
  weight: number;
  /**
   * Estonian tooltip copy: what quantity is scored, how it maps to
   * points, and what moving the slider changes in the ranking.
   * Must stay honest with the dim_* scorers in livability.py.
   */
  hint: string;
}

/** Must match livability.WEIGHTS keys; weights must sum to 1. */
export const DIMS: DimMeta[] = [
  {
    key: "schools",
    label: "Koolid",
    weight: 0.18,
    hint: "Mõõdab kaugust lähima kooli või lasteaiateni (OpenStreetMap). Kuni 300 m annab 100 punkti, umbes 1 km 70 punkti, üle 2,5 km 30 või vähem. Tõstmisel kerkivad koolide-lähedased kuulutused ettepoole; 0% jätab mõõdiku arvestusest välja.",
  },
  {
    key: "transit",
    label: "Ühistransport",
    weight: 0.12,
    hint: "Loeb bussipeatusi 500 m raadiuses (OpenStreetMap). 5 või enam peatust annab 100 punkti, üks peatus 60, üle 1 km kaugusel peatus 15. Tõstmisel kerkivad hea ühistranspordiga kuulutused ettepoole; 0% jätab mõõdiku arvestusest välja.",
  },
  {
    key: "services",
    label: "Teenused",
    weight: 0.12,
    hint: "Mõõdab kaugust lähima poe, apteegi või kliinikuni (OpenStreetMap). Kuni 400 m annab 100 punkti, umbes 800 m 80, umbes 1,2 km 60. Tõstmisel kerkivad teenuste-lähedased kuulutused ettepoole; 0% jätab mõõdiku arvestusest välja.",
  },
  {
    key: "green",
    label: "Haljastus",
    weight: 0.1,
    hint: "Mõõdab kaugust lähima pargi, metsa või rannani (OpenStreetMap). Kuni 400 m annab 100 punkti, kuni 800 m 80, kuni 1,2 km 60; huvipunkti puudumisel madal. Tõstmisel kerkivad roheluse-lähedased kuulutused ettepoole; 0% jätab mõõdiku arvestusest välja.",
  },
  {
    key: "water",
    label: "Vesi",
    weight: 0.08,
    hint: "Mõõdab kaugust lähima mere või järveni (OpenStreetMap). Kuni 500 m annab 100 punkti, kuni 1 km 75, kuni 2 km 50, kaugemal madal. Tõstmisel kerkivad veekogu-lähedased kuulutused ettepoole; 0% jätab mõõdiku arvestusest välja.",
  },
  {
    key: "rail",
    label: "Rong",
    weight: 0.07,
    hint: "Mõõdab kaugust lähima rongipeatuseni (OpenStreetMap, 2 km aken). Kuni 800 m annab 100 punkti, kuni 1,5 km 80, kuni 2 km 60, kaugemal 20. Tõstmisel kerkivad rongiühendusega kuulutused ettepoole; 0% jätab mõõdiku arvestusest välja.",
  },
  {
    key: "urban",
    label: "Melu (rahulik↔sagiv)",
    weight: 0.03,
    hint: "Maitse-telg, mitte üldine heaolu: loeb huvipunkte 1,5 km raadiuses. Tühi maa saab 10 punkti, tihe linn kuni 80 punkti. Tõstmisel kerkivad sagivad linnapiirkonnad ettepoole, langetamisel rahulikud maapiirkonnad; 0% jätab telje arvestusest välja.",
  },
  {
    key: "safety",
    label: "Turvalisus",
    weight: 0.15,
    hint: "Maakonna jäme turvatase riiklike kuritegevusülevaadete põhjal: saartel kõrgeim (umbes 90 punkti), Ida-Virumaal madalaim (30). Alla maakonnataseme andmeid pole; hinnanguta maakondades skoori pole ja liugur neid kuulutusi ei mõjuta. Tõstmisel kerkivad turvalisemate maakondade kuulutused ettepoole; 0% jätab mõõdiku arvestusest välja.",
  },
  {
    key: "connect",
    label: "Ühendus",
    weight: 0.15,
    hint: "Parim hinnanguline sõiduaeg: kesklinna autoga (Tallinn, Tartu, Pärnu, Narva ja lähiomavalitsused), rongipeatusse jalgsi ning poodi jalgsi või rattaga. Linnulennu-kaugusest keskmiste kiirustega arvutatud hinnang, mitte mõõdetud marsruut: kuni 10 min annab 100 punkti, kuni 30 min 70, üle tunni 25. Tõstmisel kerkivad hästi ühendatud kuulutused ettepoole; 0% jätab mõõdiku arvestusest välja.",
  },
];

/** Tooltip copy for the price-vs-quality balance slider. */
export const BALANCE_HINT =
  "Määrab, mitu protsenti lõppskoorist tuleb elamiskvaliteedist ja mitu soodsast hinnast. 100% arvestab ainult kvaliteeti, 0% ainult hinda; vaikesäte on 60% kvaliteet.";

export interface UnconfigurableDim {
  key: string;
  /** Estonian label shown in the "cannot change" section. */
  label: string;
  /** Estonian explanation of why there is no slider for it. */
  why: string;
}

/**
 * Dims that exist in livability.py but have no slider: dim_air is an
 * explicit always-None stub kept out of WEIGHTS until an open data source
 * exists — no slider, so the UI never fakes precision for it.
 */
export const UNCONFIGURABLE_DIMS: UnconfigurableDim[] = [
  {
    key: "air",
    label: "Õhk ja valgus",
    why: "Valguse ja õhukvaliteedi kohta pole avatud andmeallikat, seetõttu on teenuse väärtus alati teadmata ja mõõdik jääb kaaludest välja. Liugurit pole, et mitte näidata väljamõeldud täpsust.",
  },
];

/** Slider percent per dim (100 = registry default). */
export type Multipliers = Partial<Record<string, number>>;

export const DEFAULT_BALANCE = 60; // % livability in the combined score

/**
 * Weighted livability: renormalized mean of available dims times their
 * multipliers. Null when the listing has no usable dims (caller falls back
 * to the base score). All-100 multipliers reproduce combine() exactly.
 */
export function weightedLivability(
  dims: Record<string, number | null> | null | undefined,
  multipliers: Multipliers,
): number | null {
  if (!dims) return null;
  let num = 0;
  let den = 0;
  for (const d of DIMS) {
    const v = dims[d.key];
    if (typeof v !== "number" || !Number.isFinite(v)) continue;
    const m = multipliers[d.key] ?? 100;
    num += d.weight * (m / 100) * v;
    den += d.weight * (m / 100);
  }
  if (den <= 0) return null;
  return Math.round(num / den);
}

/** True when every slider sits at its default (base scores apply). */
export function isDefaultWeights(multipliers: Multipliers, balance: number): boolean {
  if (balance !== DEFAULT_BALANCE) return false;
  return Object.values(multipliers).every((m) => m === 100 || m === undefined);
}

/** Parse `?w=green:200,schools:0` (percent ints, clamped 0..200). */
export function parseWeightsParam(value: unknown): Multipliers {
  const out: Multipliers = {};
  if (typeof value !== "string") return out;
  for (const part of value.split(",")) {
    const [k, v] = part.split(":");
    if (!k || v === undefined) continue;
    if (!DIMS.some((d) => d.key === k)) continue;
    const n = Number(v);
    if (!Number.isFinite(n)) continue;
    out[k] = Math.min(200, Math.max(0, Math.round(n)));
  }
  return out;
}

/** Serialize non-default multipliers back to `?w=…` ("" when default). */
export function weightsToParam(multipliers: Multipliers): string {
  return DIMS.filter((d) => {
    const m = multipliers[d.key];
    return m !== undefined && m !== 100;
  })
    .map((d) => `${d.key}:${multipliers[d.key]}`)
    .join(",");
}

/** Parse `?bal=35` (0..100), defaulting to DEFAULT_BALANCE. */
export function parseBalanceParam(value: unknown): number {
  const n = typeof value === "string" ? Number(value) : NaN;
  if (!Number.isFinite(n)) return DEFAULT_BALANCE;
  return Math.min(100, Math.max(0, Math.round(n)));
}
