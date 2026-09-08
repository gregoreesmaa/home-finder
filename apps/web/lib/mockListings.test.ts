import { describe, expect, it } from "vitest";
import { formatFacts, type MockListing } from "./mockListings";

const base: MockListing = {
  id: "x",
  address: "A 1, Tallinn",
  county: "Harju maakond",
  price: 285000,
  price_per_m2: 4200,
  rooms: 3,
  area_m2: 68,
  score_livability: 50,
  discount_pct: 0,
  score_combined: 55,
  reasons: [],
};

/** et-EE grouping emits NBSP (U+00A0); normalize so expectations stay ASCII. */
const plain = (s: string): string => s.replace(/ /g, " ");

describe("formatFacts (card facts line, null-tolerant for live rows)", () => {
  it("formats full rows with Estonian number grouping", () => {
    expect(plain(formatFacts(base))).toBe(
      "285 000 € · 4200 €/m² · 3 tuba · 68 m²",
    );
  });

  it("renders missing live fields as dashes instead of crashing", () => {
    expect(
      plain(
        formatFacts({ ...base, price_per_m2: null, rooms: null, area_m2: null }),
      ),
    ).toBe("285 000 € · – · – · –");
  });

  it("handles partially missing fields", () => {
    expect(plain(formatFacts({ ...base, rooms: null }))).toContain("–");
    expect(plain(formatFacts({ ...base, rooms: null }))).toContain(
      "4200 €/m²",
    );
  });
});
