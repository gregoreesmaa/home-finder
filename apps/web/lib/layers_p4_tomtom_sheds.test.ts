import { describe, expect, it } from "vitest";
import {
  SHED_ATTRIBUTION,
  SHED_DEFS,
  SHED_FILL,
  SHED_HOOK,
  SHED_LAYER_IDS,
  SHED_LAYER_SPEC,
  SHED_UNMEASURED_FILL,
  isShedLayerId,
  isShedPolygon,
  shedCoversPoint,
  shedPolygonsForLayer,
  type ShedPolygon,
} from "./layers_p4_tomtom_sheds";

const FIXTURE_SNAPSHOT = {
  polygons: [
    {
      hub: "city-center",
      budgetS: 1800,
      band: "rush",
      ring: [
        [59.4, 24.7],
        [59.4, 24.8],
        [59.47, 24.8],
        [59.47, 24.7],
      ],
    },
    {
      hub: "city-center",
      budgetS: 900,
      band: "rush",
      ring: [
        [59.42, 24.73],
        [59.42, 24.77],
        [59.45, 24.77],
        [59.45, 24.73],
      ],
    },
    { hub: "port", budgetS: 1800, band: "offpeak", ring: [] },
    { hub: "broken", budgetS: 1800, band: "rush", ring: "nope" },
  ],
};

describe("shed overlay (#670)", () => {
  it("ships four layers: 15/30 min x peak/off-peak", () => {
    expect(SHED_LAYER_IDS).toEqual([
      "shed-15-peak",
      "shed-15-offpeak",
      "shed-30-peak",
      "shed-30-offpeak",
    ]);
    expect(SHED_DEFS.map((d) => d.id)).toEqual(SHED_LAYER_IDS);
    expect(SHED_LAYER_SPEC["shed-30-peak"]).toEqual({
      budgetS: 1800,
      band: "rush",
    });
    expect(SHED_HOOK).toMatch(/SHED-HOOK \(#670\)/);
  });

  it("labels every layer short-cache-never-live in Estonian", () => {
    for (const def of SHED_DEFS) {
      expect(def.hubCount).toBe(5);
      expect(`${def.title} ${def.source}`).toMatch(
        /mõõtmik lühiajalisest puhvrist, mitte reaalajas/,
      );
    }
    expect(SHED_ATTRIBUTION).toMatch(/mitte reaalajas/);
  });

  it("selects only matching-budget/band polygons with real rings", () => {
    const polys = shedPolygonsForLayer(FIXTURE_SNAPSHOT, "shed-30-peak");
    expect(polys.map((p) => p.hub)).toEqual(["city-center"]);
    expect(shedPolygonsForLayer(FIXTURE_SNAPSHOT, "shed-15-peak")).toHaveLength(
      1,
    );
    expect(shedPolygonsForLayer(FIXTURE_SNAPSHOT, "shed-30-offpeak")).toEqual(
      [],
    );
    expect(shedPolygonsForLayer({ polygons: [] }, "shed-30-peak")).toEqual([]);
    expect(shedPolygonsForLayer(null, "shed-30-peak")).toEqual([]);
  });

  it("covers points by ray casting (scorer parity)", () => {
    const poly = shedPolygonsForLayer(
      FIXTURE_SNAPSHOT,
      "shed-30-peak",
    )[0] as ShedPolygon;
    expect(shedCoversPoint(poly, 59.44, 24.75)).toBe(true);
    expect(shedCoversPoint(poly, 59.5, 24.9)).toBe(false);
    expect(
      shedCoversPoint({ ...poly, ring: [[59.4, 24.7]] }, 59.44, 24.75),
    ).toBe(false);
  });

  it("validates ids, polygons and unmeasured paint", () => {
    expect(isShedLayerId("shed-30-peak")).toBe(true);
    expect(isShedLayerId("delay-morning")).toBe(false);
    expect(isShedPolygon(FIXTURE_SNAPSHOT.polygons[0])).toBe(true);
    expect(isShedPolygon(FIXTURE_SNAPSHOT.polygons[3])).toBe(false);
    expect(SHED_UNMEASURED_FILL).toBe("#94a3b8");
    expect(Object.keys(SHED_FILL)).toEqual([...SHED_LAYER_IDS]);
  });
});
