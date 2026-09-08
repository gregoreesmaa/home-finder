import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { hexesFromGeoJSON } from "./heatmap";
import { MOCK_LISTINGS } from "./mockListings";

const root = new URL("../../../contracts/", import.meta.url);
const listingsSchema = JSON.parse(
  readFileSync(new URL("listings.json", root), "utf-8"),
) as {
  $defs: { listing: { required: string[]; properties: Record<string, unknown> } };
};
const cellsSchema = JSON.parse(
  readFileSync(new URL("area-scores.json", root), "utf-8"),
) as { required: string[] };

const required: string[] = listingsSchema.$defs.listing.required;

describe("contract C2 (vitest side): TS shapes match contracts/*.json", () => {
  it("mock listings carry every required listing key", () => {
    expect(required.length).toBeGreaterThan(0);
    for (const l of MOCK_LISTINGS) {
      for (const key of required) {
        expect(l, `missing ${key}`).toHaveProperty(key);
      }
      expect(typeof l.id).toBe("string");
      expect(Array.isArray(l.reasons)).toBe(true);
    }
  });

  it("area-scores contract names the fields the map parses", () => {
    expect(cellsSchema.required).toContain("features");
    expect(cellsSchema.required).toContain("live");
  });

  it("malformed cells never reach the map (drift guard)", () => {
    expect(
      hexesFromGeoJSON({
        type: "FeatureCollection",
        features: [{ properties: { h3: 123 }, geometry: null }],
      }),
    ).toEqual([]);
  });
});
