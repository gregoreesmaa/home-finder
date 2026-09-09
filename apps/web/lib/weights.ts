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
}

/** Must match livability.WEIGHTS keys; weights must sum to 1. */
export const DIMS: DimMeta[] = [
  { key: "schools", label: "Koolid", weight: 0.18 },
  { key: "transit", label: "Ühistransport", weight: 0.12 },
  { key: "services", label: "Teenused", weight: 0.12 },
  { key: "green", label: "Haljastus", weight: 0.1 },
  { key: "water", label: "Vesi", weight: 0.08 },
  { key: "rail", label: "Rong", weight: 0.07 },
  { key: "urban", label: "Melu (rahulik↔sagiv)", weight: 0.03 },
  { key: "safety", label: "Turvalisus", weight: 0.15 },
  { key: "connect", label: "Ühendus", weight: 0.15 },
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
