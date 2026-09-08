// Canonical ranking contract — mirrored by services/scoring (Python).
// discountPct: % below predicted market price (POSITIVE = steal / good deal).
// Display convention (ListingCard): steal shows as e.g. "STEAL -12%".

export type SortMode = "combined" | "livability" | "deal";

export interface Rankable {
  score_livability: number; // 0..100
  discount_pct: number; // % below predicted market, positive = steal
  score_combined?: number;
}

/** Map discount_pct in [-15, +25] onto [0, 1]. Clamped. */
export function dealNorm(discountPct: number): number {
  return Math.min(1, Math.max(0, (discountPct + 15) / 40));
}

/** 0.6 * livability_norm + 0.4 * deal_norm, scaled to 0..100 integer. */
export function combinedScore(livability: number, discountPct: number): number {
  return Math.round(100 * (0.6 * (livability / 100) + 0.4 * dealNorm(discountPct)));
}

export function withCombined<T extends Rankable>(l: T): T {
  return { ...l, score_combined: combinedScore(l.score_livability, l.discount_pct) };
}

/** Best-to-worst sort. combined/deal DESC steal-first, livability DESC. Stable. */
export function sortListings<T extends Rankable>(listings: T[], sort: SortMode): T[] {
  const key =
    sort === "livability"
      ? (l: T) => l.score_livability
      : sort === "deal"
        ? (l: T) => l.discount_pct
        : (l: T) => l.score_combined ?? combinedScore(l.score_livability, l.discount_pct);
  return listings
    .map((l, i) => ({ l, i }))
    .sort((a, b) => key(b.l) - key(a.l) || a.i - b.i)
    .map(({ l }) => l);
}
