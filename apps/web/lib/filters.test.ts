import { describe, expect, it } from "vitest";
import {
  applyFilters,
  countiesIn,
  EMPTY_FILTERS,
  isFiltered,
  parseFilterParams,
} from "./filters";
import { MOCK_LISTINGS } from "./mockListings";

describe("filters (D4: shareable URL params on live data)", () => {
  it("empty filters pass everything through", () => {
    expect(applyFilters(MOCK_LISTINGS, EMPTY_FILTERS)).toHaveLength(
      MOCK_LISTINGS.length,
    );
    expect(isFiltered(EMPTY_FILTERS)).toBe(false);
  });

  it("parses params, ignoring garbage numbers", () => {
    const f = parseFilterParams(
      new URLSearchParams("county=Harju+maakond&maxPrice=200000&minRooms=abc&minLiv=-5"),
    );
    expect(f.county).toBe("Harju maakond");
    expect(f.maxPrice).toBe(200000);
    expect(f.minRooms).toBeNull();
    expect(f.minLiv).toBeNull();
    expect(isFiltered(f)).toBe(true);
  });

  it("county + price + rooms + livability combine", () => {
    const f = {
      county: "Harju maakond",
      maxPrice: 300000,
      minRooms: 3,
      minLiv: 80,
    };
    const out = applyFilters(MOCK_LISTINGS, f);
    expect(out.map((l) => l.id)).toEqual(["tallinn-kalamaja"]);
  });

  it("impossible combo yields [] (empty state with reset)", () => {
    expect(
      applyFilters(MOCK_LISTINGS, { ...EMPTY_FILTERS, minLiv: 101 }),
    ).toEqual([]);
  });

  it("countiesIn lists distinct counties", () => {
    expect(countiesIn(MOCK_LISTINGS)).toEqual([
      "Harju maakond",
      "Pärnu maakond",
      "Tartu maakond",
    ]);
  });
});
