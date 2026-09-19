import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  CANOPY_ALPHA,
  CANOPY_ATTRIBUTION,
  CANOPY_BONUS,
  CANOPY_CLASSES,
  CANOPY_DECAY,
  CANOPY_DEFS,
  CANOPY_HOOK,
  CANOPY_LUT,
  CANOPY_NO_METRO,
  CANOPY_NO_RASTER,
  CANOPY_RASTER_FILE,
  CANOPY_TAGS,
  bonusSpecForCanopy,
  decodeCanopyGrid,
  fetchCanopyTint,
  isCanopyLayerId,
  isCanopyTasteOnlyLayer,
  isCanopyTintGrid,
  renderCanopyTint,
  type CanopyTintGrid,
} from "./layers_p4_canopy";

const GRID: CanopyTintGrid = {
  cols: 3,
  rows: 2,
  bbox: { minlon: 24.6, minlat: 59.28, maxlon: 24.7, maxlat: 59.33 },
  vintage: "2022-suvi",
  classes: [0, 1, 5, 3, 9, 2],
};

describe("canopy tint renderer (#620)", () => {
  it("paints publisher classes, missing stays transparent", () => {
    const { rgba } = renderCanopyTint({ ...GRID, classes: [0, 1, 5, 3, 2, 4] });
    expect(rgba.length).toBe(3 * 2 * 4);
    expect(rgba[0 * 4 + 3]).toBe(0); // <1m transparent
    expect(rgba[1 * 4]).toBe(0x25); // 1-4 m legend-exact
    expect(rgba[2 * 4]).toBe(0xe0); // >30 m legend-exact
    expect(rgba[1 * 4 + 3]).toBe(CANOPY_ALPHA);
  });
  it("refuses out-of-range classes in the guard (never painted)", () => {
    expect(isCanopyTintGrid(GRID)).toBe(false); // 9 is not a class
    expect(isCanopyTintGrid({ ...GRID, classes: [0, 1, 5, 3, 2, 4] })).toBe(true);
  });
  it("keeps six classes with a LUT entry each", () => {
    expect(CANOPY_CLASSES).toHaveLength(6);
    expect(CANOPY_LUT).toHaveLength(6);
  });
});

describe("canopy grid guard + fetch (#620)", () => {
  it("decodes the sidecar doc, refuses corrupt grids", () => {
    const raw = Buffer.from([0, 3, 5]).toString("base64");
    const grid = decodeCanopyGrid({
      cols: 3,
      rows: 1,
      bbox: GRID.bbox,
      vintage: "2022-suvi",
      encoding: "base64-uint8",
      data: raw,
    });
    expect(grid?.classes).toEqual([0, 3, 5]);
    expect(decodeCanopyGrid({ cols: 3, rows: 1 })).toBeNull();
    expect(decodeCanopyGrid({ cols: 3, rows: 1, bbox: GRID.bbox, encoding: "x", data: raw })).toBeNull();
    const bad = Buffer.from([0, 3, 9]).toString("base64");
    expect(
      decodeCanopyGrid({ cols: 3, rows: 1, bbox: GRID.bbox, encoding: "base64-uint8", data: bad }),
    ).toBeNull();
  });
  it("fetches the grid from the canopy areas endpoint", async () => {
    const raw = Buffer.from([0, 3]).toString("base64");
    const fetchImpl = (async () => ({
      ok: true,
      json: async () => ({
        grid: { cols: 2, rows: 1, bbox: GRID.bbox, vintage: null, encoding: "base64-uint8", data: raw },
      }),
    })) as unknown as typeof fetch;
    const grid = await fetchCanopyTint(fetchImpl);
    expect(grid?.classes).toEqual([0, 3]);
  });
  it("is null on any transport failure (errors never cached as data)", async () => {
    const down = (async () => {
      throw new Error("down");
    }) as unknown as typeof fetch;
    await expect(fetchCanopyTint(down)).resolves.toBeNull();
  });
});

describe("canopy registry (#620)", () => {
  it("merges into LAYERS via the CANOPY-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 124 shipped + seveso + stateland + quarry + maaparandus + soil +
    // etak + relief + 1 canopy overlay (CANOPY-HOOK #620, 130 + 1) + 1 buildings overlay
    // (BUILDINGS-HOOK #621, 131 + 1) + 1 density overlay
    // (DENSITY-HOOK #622, 132 + 1) + 1 forest overlay
    // (FOREST-HOOK #624, 133 + 1 = 134)....
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    // HARNO-HOOK (#687): +1 harno school layer (156 + 1 = 157).
    // VIIRS-HOOK (#719): +1 viirs brightness layer (157 + 1 = 158).
    // OUTAGE-HOOK (#729): +1 outage hetkeseis layer (158 + 1 = 159).
    // BUSMESH-HOOK (#769): +3 transfer-node window layers (159 + 3 = 162).
    // SHED-HOOK (#763) + DATEX-HOOK (#763) + INCIDENTS-HOOK (#763): +4 sheds +6 datex +1 incidents (162 + 11 = 173).
    expect(ids.length).toBe(173); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    expect(ids).toContain("canopy");
  });
  it("rides paramLabel with empty paramIds (tint only, no parameters3 number)", () => {
    expect(CANOPY_DEFS[0]?.paramIds).toEqual([]);
    expect(CANOPY_DEFS[0]?.paramLabel).toBe("P4-võra");
    expect(CANOPY_DEFS[0]?.fallbackPoints).toEqual([]);
  });
  it("guards by id, never by literal", () => {
    expect(isCanopyLayerId("canopy")).toBe(true);
    expect(isCanopyLayerId("relief")).toBe(false);
    expect(isCanopyTasteOnlyLayer("canopy")).toBe(true);
    expect(isCanopyTasteOnlyLayer("parks")).toBe(false);
    expect(bonusSpecForCanopy("canopy")).toEqual(CANOPY_BONUS.canopy);
    expect(bonusSpecForCanopy("parks")).toBeUndefined();
  });
  it("pins inert placeholders + attribution + hook marker", () => {
    expect(CANOPY_DECAY.canopy).toBe(0.5);
    expect(CANOPY_NO_RASTER).toBe(true);
    expect(CANOPY_NO_METRO).toBe(true);
    expect(CANOPY_RASTER_FILE.canopy).toContain("canopy");
    expect(CANOPY_TAGS.canopy).not.toContain("node(");
    expect(CANOPY_ATTRIBUTION).toContain("CC BY 4.0");
    expect(CANOPY_HOOK).toContain("CANOPY-HOOK (#620)");
  });
});

describe("canopy wiring (#620)", () => {
  it("locks the inert decay/bonus placeholders through layers.ts (never evaluated)", () => {
    expect(radiusKmFor("canopy")).toBeCloseTo(0.5, 5);
    expect(bonusSpecFor("canopy")).toEqual({ kind: "area", half: 60 });
  });
  it("states taste-only + vintage in the legend (never a score)", () => {
    expect(overlayLegendFor("canopy")).toContain("maitse, mitte hinne");
    expect(overlayLegendFor("canopy")).toContain("2022");
    expect(overlayLegendFor("canopy").length).toBeGreaterThan(10);
  });
  it("paints a distinct toggle-dot color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("canopy")).toBe("#042f2e");
  });
});
