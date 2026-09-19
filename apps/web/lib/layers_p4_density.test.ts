import { describe, expect, it, vi } from "vitest";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  DENSITY_ATTRIBUTION,
  DENSITY_BONUS,
  DENSITY_CLASS_FILL,
  DENSITY_CLASSES,
  DENSITY_DECAY,
  DENSITY_DEFS,
  DENSITY_HOOK,
  DENSITY_NO_METRO,
  DENSITY_NO_RASTER,
  DENSITY_RASTER_FILE,
  DENSITY_TAGS,
  bonusSpecForDensity,
  densityFillColor,
  fetchDensityAreas,
  isDensityArea,
  isDensityLayerId,
  isDensityTasteOnlyLayer,
} from "./layers_p4_density";

const AREA = {
  zone_id: "S-10018",
  value: 5,
  cls: 1,
  b: [24.27, 58.94, 24.3, 58.96],
  r: [
    [
      [24.27, 58.94],
      [24.27, 58.96],
      [24.3, 58.96],
      [24.3, 58.94],
      [24.27, 58.94],
    ],
  ],
};

describe("density areas (#622)", () => {
  it("accepts well-formed squares, bins masked-zero as class 0", () => {
    expect(isDensityArea(AREA)).toBe(true);
    expect(isDensityArea({ ...AREA, cls: 0, value: 0 })).toBe(true); // masked, never "empty"
    expect(isDensityArea({ ...AREA, cls: 6 })).toBe(false);
    expect(isDensityArea({ ...AREA, cls: 1.5 })).toBe(false);
    expect(isDensityArea({ ...AREA, r: [[[24.7]]] })).toBe(false);
    expect(isDensityArea(null)).toBe(false);
  });
  it("maps every class to a non-score fill (unknown degrades to class 0)", () => {
    expect(Object.keys(DENSITY_CLASS_FILL)).toHaveLength(7); // 0-5 + unknown
    for (let c = 0; c <= 5; c++) {
      expect(densityFillColor(c)).toBe(DENSITY_CLASS_FILL[String(c)]);
      expect(densityFillColor(c)).toMatch(/^#[0-9a-f]{6}$/);
    }
    expect(densityFillColor(9)).toBe(DENSITY_CLASS_FILL["0"]);
    expect(DENSITY_CLASSES).toHaveLength(6);
  });
  it("fetches squares from the density areas endpoint", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA] }),
    });
    const areas = await fetchDensityAreas(fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0])).toBe("/api/layers/density/areas");
    expect(areas).toHaveLength(1);
    expect(areas?.[0].zone_id).toBe("S-10018");
    expect(areas?.[0].cls).toBe(1);
  });
  it("drops malformed areas and fails null (never faked)", async () => {
    const bad = { ...AREA, cls: 9, r: [[[24.7]]] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA, bad, null, 7] }),
    });
    expect(await fetchDensityAreas(fetchImpl)).toHaveLength(1);
    const failImpl = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchDensityAreas(failImpl)).toBeNull();
  });
});

describe("density registry (#622)", () => {
  it("merges into LAYERS via the DENSITY-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 124 shipped + seveso + stateland + quarry + maaparandus + soil +
    // etak + relief + canopy + buildings + 1 density overlay
    // (DENSITY-HOOK #622, 132 + 1) + 1 forest overlay
    // (FOREST-HOOK #624, 133 + 1 = 134)..
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    expect(ids.length).toBe(156); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    expect(ids).toContain("density");
  });
  it("rides paramLabel with empty paramIds (tint only, no parameters3 number)", () => {
    expect(DENSITY_DEFS[0]?.paramIds).toEqual([]);
    expect(DENSITY_DEFS[0]?.paramLabel).toBe("P4-asustus");
    expect(DENSITY_DEFS[0]?.fallbackPoints).toEqual([]);
  });
  it("guards by id, never by literal", () => {
    expect(isDensityLayerId("density")).toBe(true);
    expect(isDensityLayerId("buildings")).toBe(false);
    expect(isDensityTasteOnlyLayer("density")).toBe(true);
    expect(isDensityTasteOnlyLayer("parks")).toBe(false);
    expect(bonusSpecForDensity("density")).toEqual(DENSITY_BONUS.density);
    expect(bonusSpecForDensity("parks")).toBeUndefined();
  });
  it("pins inert placeholders + attribution + hook marker", () => {
    expect(DENSITY_DECAY.density).toBe(0.5);
    expect(DENSITY_NO_RASTER).toBe(true);
    expect(DENSITY_NO_METRO).toBe(true);
    expect(DENSITY_RASTER_FILE.density).toContain("density");
    expect(DENSITY_TAGS.density).not.toContain("node(");
    expect(DENSITY_ATTRIBUTION).toContain("CC0");
    expect(DENSITY_HOOK).toContain("DENSITY-HOOK (#622)");
  });
});

describe("density wiring (#622)", () => {
  it("locks the inert decay/bonus placeholders through layers.ts (never evaluated)", () => {
    expect(radiusKmFor("density")).toBeCloseTo(0.5, 5);
    expect(bonusSpecFor("density")).toEqual({ kind: "area", half: 60 });
  });
  it("states taste-only + vintage + grain in the legend (never a score)", () => {
    expect(overlayLegendFor("density")).toContain("maitse, mitte hinne");
    expect(overlayLegendFor("density")).toContain("2024");
    expect(overlayLegendFor("density")).toContain("1 km");
    expect(overlayLegendFor("density").length).toBeGreaterThan(10);
  });
  it("paints a distinct toggle-dot color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("density")).toBe("#5b21b6");
  });
});
