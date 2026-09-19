import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  BUILDINGS_ALPHA,
  BUILDINGS_ATTRIBUTION,
  BUILDINGS_BONUS,
  BUILDINGS_CLASSES,
  BUILDINGS_DECAY,
  BUILDINGS_DEFS,
  BUILDINGS_HOOK,
  BUILDINGS_LUT,
  BUILDINGS_NO_METRO,
  BUILDINGS_NO_RASTER,
  BUILDINGS_RASTER_FILE,
  BUILDINGS_TAGS,
  bonusSpecForBuildings,
  decodeBuildingsGrid,
  fetchBuildingsTint,
  isBuildingsLayerId,
  isBuildingsTasteOnlyLayer,
  isBuildingsTintGrid,
  renderBuildingsTint,
  type BuildingsTintGrid,
} from "./layers_p4_buildings";

const GRID: BuildingsTintGrid = {
  cols: 3,
  rows: 2,
  bbox: { minlon: 24.6, minlat: 59.28, maxlon: 24.7, maxlat: 59.33 },
  vintage: "2025",
  classes: [0, 1, 5, 3, 9, 2],
};

describe("buildings tint renderer (#621)", () => {
  it("paints our height bins, missing stays transparent", () => {
    const { rgba } = renderBuildingsTint({ ...GRID, classes: [0, 1, 5, 3, 2, 4] });
    expect(rgba.length).toBe(3 * 2 * 4);
    expect(rgba[0 * 4 + 3]).toBe(0); // missing transparent
    expect(rgba[1 * 4]).toBe(0xd9); // 0-3 m pale stone
    expect(rgba[2 * 4]).toBe(0x45); // >25 m deep indigo
    expect(rgba[1 * 4 + 3]).toBe(BUILDINGS_ALPHA);
  });
  it("refuses out-of-range classes in the guard (never painted)", () => {
    expect(isBuildingsTintGrid(GRID)).toBe(false); // 9 is not a class
    expect(isBuildingsTintGrid({ ...GRID, classes: [0, 1, 5, 3, 2, 4] })).toBe(true);
  });
  it("keeps six classes with a LUT entry each", () => {
    expect(BUILDINGS_CLASSES).toHaveLength(6);
    expect(BUILDINGS_LUT).toHaveLength(6);
  });
});

describe("buildings grid guard + fetch (#621)", () => {
  it("decodes the sidecar doc, refuses corrupt grids", () => {
    const raw = Buffer.from([0, 3, 5]).toString("base64");
    const grid = decodeBuildingsGrid({
      cols: 3,
      rows: 1,
      bbox: GRID.bbox,
      vintage: { 2025: 100 },
      encoding: "base64-uint8",
      data: raw,
    });
    expect(grid?.classes).toEqual([0, 3, 5]);
    expect(grid?.vintage).toBe("2025"); // majority year object -> string
    expect(decodeBuildingsGrid({ cols: 3, rows: 1 })).toBeNull();
    expect(decodeBuildingsGrid({ cols: 3, rows: 1, bbox: GRID.bbox, encoding: "x", data: raw })).toBeNull();
    const bad = Buffer.from([0, 3, 9]).toString("base64");
    expect(
      decodeBuildingsGrid({ cols: 3, rows: 1, bbox: GRID.bbox, encoding: "base64-uint8", data: bad }),
    ).toBeNull();
  });
  it("fetches the grid from the buildings areas endpoint", async () => {
    const raw = Buffer.from([0, 3]).toString("base64");
    const fetchImpl = (async () => ({
      ok: true,
      json: async () => ({
        grid: { cols: 2, rows: 1, bbox: GRID.bbox, vintage: null, encoding: "base64-uint8", data: raw },
      }),
    })) as unknown as typeof fetch;
    const grid = await fetchBuildingsTint(fetchImpl);
    expect(grid?.classes).toEqual([0, 3]);
  });
  it("is null on any transport failure (errors never cached as data)", async () => {
    const down = (async () => {
      throw new Error("down");
    }) as unknown as typeof fetch;
    await expect(fetchBuildingsTint(down)).resolves.toBeNull();
  });
});

describe("buildings registry (#621)", () => {
  it("merges into LAYERS via the BUILDINGS-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 124 shipped + seveso + stateland + quarry + maaparandus + soil +
    // etak + relief + canopy + 1 buildings overlay
    // (BUILDINGS-HOOK #621, 131 + 1) + 1 density overlay
    // (DENSITY-HOOK #622, 132 + 1) + 1 forest overlay
    // (FOREST-HOOK #624, 133 + 1 = 134)..
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    // HARNO-HOOK (#687): +1 harno school layer (156 + 1 = 157).
    // VIIRS-HOOK (#719): +1 viirs brightness layer (157 + 1 = 158).
    // OUTAGE-HOOK (#729): +1 outage hetkeseis layer (158 + 1 = 159).
    expect(ids.length).toBe(159); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    expect(ids).toContain("buildings");
  });
  it("rides paramLabel with empty paramIds (tint only, no parameters3 number)", () => {
    expect(BUILDINGS_DEFS[0]?.paramIds).toEqual([]);
    expect(BUILDINGS_DEFS[0]?.paramLabel).toBe("P4-hooned");
    expect(BUILDINGS_DEFS[0]?.fallbackPoints).toEqual([]);
  });
  it("guards by id, never by literal", () => {
    expect(isBuildingsLayerId("buildings")).toBe(true);
    expect(isBuildingsLayerId("canopy")).toBe(false);
    expect(isBuildingsTasteOnlyLayer("buildings")).toBe(true);
    expect(isBuildingsTasteOnlyLayer("parks")).toBe(false);
    expect(bonusSpecForBuildings("buildings")).toEqual(BUILDINGS_BONUS.buildings);
    expect(bonusSpecForBuildings("parks")).toBeUndefined();
  });
  it("pins inert placeholders + attribution + hook marker", () => {
    expect(BUILDINGS_DECAY.buildings).toBe(0.5);
    expect(BUILDINGS_NO_RASTER).toBe(true);
    expect(BUILDINGS_NO_METRO).toBe(true);
    expect(BUILDINGS_RASTER_FILE.buildings).toContain("buildings");
    expect(BUILDINGS_TAGS.buildings).not.toContain("node(");
    expect(BUILDINGS_ATTRIBUTION).toContain("CC BY 4.0");
    expect(BUILDINGS_HOOK).toContain("BUILDINGS-HOOK (#621)");
  });
});

describe("buildings wiring (#621)", () => {
  it("locks the inert decay/bonus placeholders through layers.ts (never evaluated)", () => {
    expect(radiusKmFor("buildings")).toBeCloseTo(0.5, 5);
    expect(bonusSpecFor("buildings")).toEqual({ kind: "area", half: 60 });
  });
  it("states taste-only + vintage in the legend (never a score)", () => {
    expect(overlayLegendFor("buildings")).toContain("maitse, mitte hinne");
    expect(overlayLegendFor("buildings")).toContain("2025");
    expect(overlayLegendFor("buildings").length).toBeGreaterThan(10);
  });
  it("paints a distinct toggle-dot color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("buildings")).toBe("#3730a3");
  });
});
