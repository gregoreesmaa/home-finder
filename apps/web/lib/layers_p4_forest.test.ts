import { describe, expect, it, vi } from "vitest";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  FOREST_ATTRIBUTION,
  FOREST_BONUS,
  FOREST_CLASS_FILL,
  FOREST_CLASSES,
  FOREST_DECAY,
  FOREST_DEFS,
  FOREST_HOOK,
  FOREST_NO_METRO,
  FOREST_NO_RASTER,
  FOREST_RASTER_FILE,
  FOREST_TAGS,
  bonusSpecForForest,
  fetchForestAreas,
  forestFillColor,
  isForestArea,
  isForestLayerId,
  isForestPolygonOnlyLayer,
} from "./layers_p4_forest";

const AREA = {
  change_id: "kevad-0",
  season: "kevad",
  first: "2022-06-16",
  second: "2024-05-04",
  area_ha: 0.6,
  cls: 3,
  b: [24.88, 59.1, 24.9, 59.11],
  r: [
    [
      [24.88, 59.1],
      [24.88, 59.11],
      [24.9, 59.11],
      [24.9, 59.1],
      [24.88, 59.1],
    ],
  ],
};

describe("forest areas (#624)", () => {
  it("accepts well-formed changes, refuses undatable/degenerate ones", () => {
    expect(isForestArea(AREA)).toBe(true);
    expect(isForestArea({ ...AREA, cls: 0 })).toBe(false); // undatable, never painted
    expect(isForestArea({ ...AREA, cls: 4 })).toBe(false);
    expect(isForestArea({ ...AREA, r: [[[24.7]]] })).toBe(false);
    expect(isForestArea(null)).toBe(false);
  });
  it("maps every class to a warning fill (unknown degrades oldest)", () => {
    expect(Object.keys(FOREST_CLASS_FILL)).toHaveLength(4); // 1-3 + unknown
    for (let c = 1; c <= 3; c++) {
      expect(forestFillColor(c)).toBe(FOREST_CLASS_FILL[String(c)]);
      expect(forestFillColor(c)).toMatch(/^#[0-9a-f]{6}$/);
    }
    expect(forestFillColor(9)).toBe(FOREST_CLASS_FILL["1"]);
    expect(FOREST_CLASSES).toHaveLength(4);
  });
  it("fetches changes from the forest areas endpoint", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA] }),
    });
    const areas = await fetchForestAreas(fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0])).toBe("/api/layers/forest/areas");
    expect(areas).toHaveLength(1);
    expect(areas?.[0].change_id).toBe("kevad-0");
    expect(areas?.[0].cls).toBe(3);
  });
  it("drops malformed changes and fails null (never faked)", async () => {
    const bad = { ...AREA, cls: 0, r: [[[24.7]]] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA, bad, null, 7] }),
    });
    expect(await fetchForestAreas(fetchImpl)).toHaveLength(1);
    const failImpl = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchForestAreas(failImpl)).toBeNull();
  });
});

describe("forest registry (#624)", () => {
  it("merges into LAYERS via the FOREST-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 124 shipped + seveso + stateland + quarry + maaparandus + soil +
    // etak + relief + canopy + buildings + density + 1 forest overlay
    // (FOREST-HOOK #624, 133 + 1 = 134).
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    expect(ids.length).toBe(156); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    expect(ids).toContain("forest");
  });
  it("rides paramLabel with empty paramIds (polygons only, no parameters3 number)", () => {
    expect(FOREST_DEFS[0]?.paramIds).toEqual([]);
    expect(FOREST_DEFS[0]?.paramLabel).toBe("P4-mets");
    expect(FOREST_DEFS[0]?.fallbackPoints).toEqual([]);
  });
  it("guards by id, never by literal", () => {
    expect(isForestLayerId("forest")).toBe(true);
    expect(isForestLayerId("density")).toBe(false);
    expect(isForestPolygonOnlyLayer("forest")).toBe(true);
    expect(isForestPolygonOnlyLayer("parks")).toBe(false);
    expect(bonusSpecForForest("forest")).toEqual(FOREST_BONUS.forest);
    expect(bonusSpecForForest("parks")).toBeUndefined();
  });
  it("pins inert placeholders + attribution + hook marker", () => {
    expect(FOREST_DECAY.forest).toBe(0.5);
    expect(FOREST_NO_RASTER).toBe(true);
    expect(FOREST_NO_METRO).toBe(true);
    expect(FOREST_RASTER_FILE.forest).toContain("forest");
    expect(FOREST_TAGS.forest).not.toContain("node(");
    expect(FOREST_ATTRIBUTION).toContain("ETAK");
    expect(FOREST_HOOK).toContain("FOREST-HOOK (#624)");
  });
});

describe("forest wiring (#624)", () => {
  it("locks the inert decay/bonus placeholders through layers.ts (never evaluated)", () => {
    expect(radiusKmFor("forest")).toBeCloseTo(0.5, 5);
    expect(bonusSpecFor("forest")).toEqual({ kind: "area", half: 60 });
  });
  it("states bands + vintage + caveat in the legend (warning, never safe)", () => {
    expect(overlayLegendFor("forest")).toContain("2024");
    expect(overlayLegendFor("forest")).toContain("turvaline mets");
    expect(overlayLegendFor("forest").length).toBeGreaterThan(10);
  });
  it("paints a distinct toggle-dot color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("forest")).toBe("#5c4033");
  });
});
