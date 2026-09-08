import { describe, expect, it } from "vitest";
import { combinedScore, dealNorm, sortListings } from "./sort";
import { MOCK_LISTINGS } from "./mockListings";

describe("ranking contract (mirrors GET /listings?sort= + scoring API)", () => {
  it("dealNorm maps [-15,+25] onto [0,1] clamped", () => {
    expect(dealNorm(-15)).toBe(0);
    expect(dealNorm(25)).toBe(1);
    expect(dealNorm(-99)).toBe(0);
    expect(dealNorm(99)).toBe(1);
    expect(dealNorm(5)).toBeCloseTo(0.5);
  });

  it("combined = 0.6*livability + 0.4*deal", () => {
    // liv 80, discount +5 (norm 0.5) -> 100*(0.48+0.20) = 68
    expect(combinedScore(80, 5)).toBe(68);
  });

  it("sorts best-to-worst per mode; each mode has its own winner (mock data)", () => {
    const byCombined = sortListings(MOCK_LISTINGS, "combined");
    const byLiv = sortListings(MOCK_LISTINGS, "livability");
    const byDeal = sortListings(MOCK_LISTINGS, "deal");
    for (const arr of [byCombined, byLiv, byDeal]) {
      expect(arr.map((l) => l.id)).toHaveLength(MOCK_LISTINGS.length);
    }
    expect(byLiv[0].id).toBe("parnu-rannarajoon"); // liv 95
    expect(byDeal[0].id).toBe("tartu-karlova"); // discount +18 (steal first)
    expect(byCombined[0].id).toBe("tallinn-kalamaja"); // best balance
    // strictly descending keys
    expect(byLiv[0].score_livability).toBeGreaterThan(byLiv[1].score_livability);
    expect(byDeal[0].discount_pct).toBeGreaterThan(byDeal[1].discount_pct);
    expect(byCombined[0].score_combined!).toBeGreaterThan(byCombined[1].score_combined!);
  });

  it("falls back to computing combined when score_combined missing", () => {
    const rows = MOCK_LISTINGS.map(({ score_combined, ...r }) => r);
    const sorted = sortListings(rows, "combined");
    expect(sorted[0].id).toBe("tallinn-kalamaja");
  });

  it("sorts discount % descending (steal-first) for deal mode", () => {
    const rows = [
      { score_livability: 10, discount_pct: -5 },
      { score_livability: 99, discount_pct: 20 },
      { score_livability: 50, discount_pct: 0 },
    ];
    expect(sortListings(rows, "deal").map((r) => r.discount_pct)).toEqual([20, 0, -5]);
  });

  it("sorts livability descending for livability mode", () => {
    const rows = [
      { score_livability: 40, discount_pct: 25 },
      { score_livability: 90, discount_pct: -15 },
      { score_livability: 70, discount_pct: 0 },
    ];
    expect(sortListings(rows, "livability").map((r) => r.score_livability)).toEqual([90, 70, 40]);
  });

  it("composite weights are 0.6 livability + 0.4 deal", () => {
    expect(combinedScore(100, -15)).toBe(60); // pure livability end
    expect(combinedScore(0, 25)).toBe(40); // pure deal end
    expect(combinedScore(100, 25)).toBe(100);
    expect(combinedScore(0, -15)).toBe(0);
  });

  it("keeps ties stable (input order) in every mode", () => {
    const tied = [
      { id: "a", score_livability: 70, discount_pct: 5, score_combined: 62 },
      { id: "b", score_livability: 70, discount_pct: 5, score_combined: 62 },
      { id: "c", score_livability: 70, discount_pct: 5, score_combined: 62 },
    ];
    for (const mode of ["combined", "livability", "deal"] as const) {
      expect(sortListings(tied, mode).map((r) => r.id)).toEqual(["a", "b", "c"]);
    }
    // mixed: tied pair stays ordered behind the winner
    const mixed = [
      { id: "x", score_livability: 70, discount_pct: 5, score_combined: 62 },
      { id: "win", score_livability: 99, discount_pct: 25, score_combined: 99 },
      { id: "y", score_livability: 70, discount_pct: 5, score_combined: 62 },
    ];
    expect(sortListings(mixed, "combined").map((r) => r.id)).toEqual(["win", "x", "y"]);
  });

  it("does not mutate the input array", () => {
    const rows = [
      { score_livability: 10, discount_pct: 0 },
      { score_livability: 90, discount_pct: 0 },
    ];
    const snapshot = rows.map((r) => ({ ...r }));
    sortListings(rows, "livability");
    expect(rows).toEqual(snapshot);
  });
});
