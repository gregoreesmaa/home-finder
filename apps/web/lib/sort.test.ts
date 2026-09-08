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
});
