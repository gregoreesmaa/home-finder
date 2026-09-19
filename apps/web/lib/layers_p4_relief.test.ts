import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  RELIEF_ALPHA,
  RELIEF_ATTRIBUTION,
  RELIEF_BONUS,
  RELIEF_DECAY,
  RELIEF_DEFS,
  RELIEF_HOOK,
  RELIEF_LUT,
  RELIEF_NO_METRO,
  RELIEF_NO_RASTER,
  RELIEF_RASTER_FILE,
  RELIEF_TAGS,
  bonusSpecForRelief,
  decodeReliefGrid,
  fetchReliefTint,
  isReliefLayerId,
  isReliefTasteOnlyLayer,
  isReliefTintGrid,
  reliefColorFor,
  renderReliefTint,
  type ReliefTintGrid,
} from "./layers_p4_relief";

const GRID: ReliefTintGrid = {
  cols: 3,
  rows: 2,
  bbox: { minlon: 24.6, minlat: 59.28, maxlon: 24.7, maxlat: 59.33 },
  vintage: "2026-09-17",
  heights: [0, 20, 120, NaN, -5, 45],
};

describe("relief tint renderer (#619)", () => {
  it("paints lowland/highland bands, never numbers", () => {
    const low = reliefColorFor(5);
    const high = reliefColorFor(110);
    expect(low).not.toBeNull();
    expect(high).not.toBeNull();
    expect(low).not.toEqual(high);
    expect(low![3]).toBe(RELIEF_ALPHA);
    // Deliberately NOT green/red: the tint must never read as good/bad.
    for (const c of [low!, high!]) {
      const [r, g] = c;
      expect(r > 200 && g < 80).toBe(false); // no pure red
      expect(g > 200 && r < 80).toBe(false); // no pure green
    }
  });
  it("renders missing cells transparent (never faked as lowland)", () => {
    expect(reliefColorFor(NaN)).toBeNull();
    const { rgba } = renderReliefTint(GRID);
    expect(rgba.length).toBe(3 * 2 * 4);
    expect(rgba[3 * 4 + 3]).toBe(0); // NaN cell alpha
    expect(rgba[0 * 4 + 3]).toBe(RELIEF_ALPHA); // 0 m lowland paints
  });
  it("keeps the LUT sorted (band edges monotonic)", () => {
    for (let i = 1; i < RELIEF_LUT.length; i++) {
      expect(RELIEF_LUT[i][0]).toBeGreaterThan(RELIEF_LUT[i - 1][0]);
    }
  });
});

describe("relief grid guard + fetch (#619)", () => {
  it("accepts well-formed grids, rejects malformed (never faked)", () => {
    expect(isReliefTintGrid(GRID)).toBe(true);
    expect(isReliefTintGrid({ ...GRID, heights: [1, 2] })).toBe(false);
    expect(isReliefTintGrid({ ...GRID, cols: 0 })).toBe(false);
    expect(isReliefTintGrid(null)).toBe(false);
  });
  it("decodes the sidecar doc, refuses corrupt grids", () => {
    // 2x1 grid: 10.0 m + missing.
    const raw = Buffer.from([100, 0, 0, 128]).toString("base64");
    const grid = decodeReliefGrid({
      cols: 2,
      rows: 1,
      bbox: GRID.bbox,
      vintage: "2026-09-17",
      encoding: "base64-int16-le",
      data: raw,
    });
    expect(grid?.heights).toEqual([10, NaN]);
    expect(decodeReliefGrid({ cols: 2, rows: 1 })).toBeNull();
    expect(decodeReliefGrid({ ...{ cols: 2, rows: 1, bbox: GRID.bbox, encoding: "x", data: raw } })).toBeNull();
  });
  it("fetches the grid from the relief areas endpoint", async () => {
    const raw = Buffer.from([100, 0, 0, 128]).toString("base64");
    const fetchImpl = (async () => ({
      ok: true,
      json: async () => ({
        grid: { cols: 2, rows: 1, bbox: GRID.bbox, vintage: null, encoding: "base64-int16-le", data: raw },
      }),
    })) as unknown as typeof fetch;
    const grid = await fetchReliefTint(fetchImpl);
    expect(grid?.heights).toEqual([10, NaN]);
  });
  it("is null on any transport failure (errors never cached as data)", async () => {
    const down = (async () => {
      throw new Error("down");
    }) as unknown as typeof fetch;
    await expect(fetchReliefTint(down)).resolves.toBeNull();
  });
});

describe("relief registry (#619)", () => {
  it("merges into LAYERS via the RELIEF-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 124 shipped + seveso + stateland + quarry + maaparandus + soil +
    // etak + 1 relief overlay (RELIEF-HOOK #619, 129 + 1) + 1 canopy overlay
    // (CANOPY-HOOK #620, 130 + 1) + 1 buildings overlay
    // (BUILDINGS-HOOK #621, 131 + 1) + 1 density overlay
    // (DENSITY-HOOK #622, 132 + 1) + 1 forest overlay
    // (FOREST-HOOK #624, 133 + 1 = 134).....
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    // HARNO-HOOK (#687): +1 harno school layer (156 + 1 = 157).
    // VIIRS-HOOK (#719): +1 viirs brightness layer (157 + 1 = 158).
    expect(ids.length).toBe(158); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    expect(ids).toContain("relief");
  });
  it("rides paramLabel with empty paramIds (tint only, no parameters3 number)", () => {
    expect(RELIEF_DEFS[0]?.paramIds).toEqual([]);
    expect(RELIEF_DEFS[0]?.paramLabel).toBe("P4-reljeef");
    expect(RELIEF_DEFS[0]?.fallbackPoints).toEqual([]);
  });
  it("guards by id, never by literal", () => {
    expect(isReliefLayerId("relief")).toBe(true);
    expect(isReliefLayerId("soil")).toBe(false);
    expect(isReliefTasteOnlyLayer("relief")).toBe(true);
    expect(isReliefTasteOnlyLayer("parks")).toBe(false);
    expect(bonusSpecForRelief("relief")).toEqual(RELIEF_BONUS.relief);
    expect(bonusSpecForRelief("parks")).toBeUndefined();
  });
  it("pins inert placeholders + attribution + hook marker", () => {
    expect(RELIEF_DECAY.relief).toBe(0.5);
    expect(RELIEF_NO_RASTER).toBe(true);
    expect(RELIEF_NO_METRO).toBe(true);
    expect(RELIEF_RASTER_FILE.relief).toContain("relief");
    expect(RELIEF_TAGS.relief).not.toContain("node(");
    expect(RELIEF_ATTRIBUTION).toContain("CC BY 4.0");
    expect(RELIEF_HOOK).toContain("RELIEF-HOOK (#619)");
  });
});

describe("relief wiring (#619)", () => {
  it("locks the inert decay/bonus placeholders through layers.ts (never evaluated)", () => {
    expect(radiusKmFor("relief")).toBeCloseTo(0.5, 5);
    expect(bonusSpecFor("relief")).toEqual({ kind: "area", half: 60 });
  });
  it("states taste-only in the legend (never a score)", () => {
    expect(overlayLegendFor("relief")).toContain("maitse, mitte hinne");
    expect(overlayLegendFor("relief").length).toBeGreaterThan(10);
  });
  it("paints a distinct toggle-dot color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("relief")).toBe("#292524");
  });
});
