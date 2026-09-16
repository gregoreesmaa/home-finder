// Hermetic tests for the Keskkonnaagentuur climate-normals overlay
// (issue #611). Synthetic fixtures below are FULLY SYNTHETIC (clearly
// labelled); the REAL-DATA pins read the committed KLIIMA_CELLS
// extract (built offline by scripts/build/batch_kliima.py, vintage
// 2026-09-16 — fixtures only, never live). No network in tests.

import { describe, expect, it } from "vitest";
import {
  LAYERS,
  bonusSpecFor,
  fetchWindow,
  layerParamTag,
  radiusKmFor,
} from "./layers";
import { buildScoredField } from "./distanceField";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  KLIIMA_CELLS,
  KLIIMA_LAYERS,
  KLIIMA_PROBE,
  KLIIMA_RADIUS_M,
  isKliimaLayerId,
  kliimaBandAt,
  kliimaBonusSpecFor,
  kliimaPointsIn,
  kliimaSliceFor,
  type KliimaCell,
  type KliimaLayerId,
} from "./layers_kliima";

/** Synthetic Tallinn backyard + synthetic station cells. */
const HOME = { lat: 59.4374, lon: 24.7454 };
const M_PER_DEG_LAT = 111194.9;
function cellNorthOf(m: number, frostBand: number | null, wetBand: number | null): KliimaCell {
  return {
    code: "SYN",
    lat: HOME.lat + m / M_PER_DEG_LAT,
    lon: HOME.lon,
    frostDays: 120,
    precipMm: 700,
    frostBand,
    wetBand,
  };
}

describe("kliima normals kernel (builder parity)", () => {
  it("pins the radius to the batch_kliima harvest (drift = bug)", () => {
    expect(KLIIMA_RADIUS_M).toBe(70000);
    expect(kliimaBonusSpecFor("kliima_frost")).toEqual({ kind: "qbands", radiusM: 70000 });
    expect(kliimaBonusSpecFor("kliima_wet")).toEqual({ kind: "qbands", radiusM: 70000 });
    expect(radiusKmFor("kliima_frost")).toBe(70.0);
  });

  it("scores the nearest synthetic cell's band, unknown stays null (never zero)", () => {
    const cells = [cellNorthOf(0, 70, 40)];
    expect(kliimaBandAt(HOME.lat, HOME.lon, "frost", cells)).toBe(70);
    expect(kliimaBandAt(HOME.lat, HOME.lon, "wet", cells)).toBe(40);
    expect(kliimaBandAt(58.0, 22.0, "frost", cells)).toBeNull();
  });

  it("stays null where the nearest cell's slice band is NULL (never a faked middle)", () => {
    // Pakri-shape: frost ranked, wet missing.
    const cells = [cellNorthOf(0, 70, null)];
    expect(kliimaBandAt(HOME.lat, HOME.lon, "frost", cells)).toBe(70);
    expect(kliimaBandAt(HOME.lat, HOME.lon, "wet", cells)).toBeNull();
  });

  it("applies the HARD 70 km cutoff (an 80 km cell is not a cell)", () => {
    const cells = [cellNorthOf(80000, 70, 70)];
    expect(kliimaBandAt(HOME.lat, HOME.lon, "frost", cells)).toBeNull();
  });

  it("skips coordless junk instead of scoring absence", () => {
    const cells = [
      { code: "JUNK", lat: NaN, lon: NaN, frostDays: null, precipMm: null, frostBand: 70, wetBand: 70 },
    ];
    expect(kliimaBandAt(HOME.lat, HOME.lon, "frost", cells)).toBeNull();
  });

  it("maps layer ids to slices", () => {
    expect(kliimaSliceFor("kliima_frost")).toBe("frost");
    expect(kliimaSliceFor("kliima_wet")).toBe("wet");
    expect(isKliimaLayerId("kliima_frost")).toBe(true);
    expect(isKliimaLayerId("tervise")).toBe(false);
  });
});

describe("kliima registry wiring", () => {
  it("registers two slices with no parameters3 id + per-slice P4-kliima labels", () => {
    for (const layer of KLIIMA_LAYERS) {
      expect(layer.paramIds).toEqual([]);
    }
    expect(LAYERS.find((l) => l.id === "kliima_frost")?.paramLabel).toBe("P4-kliima talv");
    expect(LAYERS.find((l) => l.id === "kliima_wet")?.paramLabel).toBe("P4-kliima sademed");
  });

  it("tags the layer buttons (P4-kliima talv/sademed), leaving parameters3 tags untouched", () => {
    expect(layerParamTag(LAYERS.find((l) => l.id === "kliima_frost")!)).toBe("(P4-kliima talv)");
    expect(layerParamTag(LAYERS.find((l) => l.id === "kliima_wet")!)).toBe("(P4-kliima sademed)");
    expect(layerParamTag(LAYERS.find((l) => l.id === "parks")!)).toBe("(p19)");
  });

  it("locks the qbands spec + radius (map kernel == builder kernel)", () => {
    expect(bonusSpecFor("kliima_frost")).toEqual({ kind: "qbands", radiusM: KLIIMA_RADIUS_M });
    expect(bonusSpecFor("kliima_wet")).toEqual({ kind: "qbands", radiusM: KLIIMA_RADIUS_M });
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const id of ["kliima_frost", "kliima_wet"] as KliimaLayerId[]) {
      const def = LAYERS.find((l) => l.id === id)!;
      for (const f of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(f.length).toBeGreaterThan(0);
      }
      expect(def.fallbackPoints.length).toBeGreaterThan(0);
      expect(def.source).toContain("Keskkonnaagentuur");
    }
  });

  it("gives kliima legends naming the bands + the 3-cell thinness + the normals vintage", () => {
    const frost = overlayLegendFor("kliima_frost");
    expect(frost.length).toBeGreaterThan(10);
    expect(frost).toContain("70 km");
    expect(frost).toContain("1991-2020");
    expect(frost).toContain("interpolatsiooni pole");
    const wet = overlayLegendFor("kliima_wet");
    expect(wet).toContain("Pakri");
    expect(wet).toContain("teadmata");
  });

  it("paints kliima markers ice + dry-hay", () => {
    expect(overlayColorFor("kliima_frost")).toBe("#e0f2fe");
    expect(overlayColorFor("kliima_wet")).toBe("#fef3c7");
  });

  it("skips the raster window fetch (no master exists by decision)", async () => {
    const boom = () => {
      throw new Error("qbands layers must never fetch a window");
    };
    for (const id of ["kliima_frost", "kliima_wet"] as KliimaLayerId[]) {
      await expect(
        fetchWindow(id, { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 }, boom as unknown as typeof fetch),
      ).resolves.toBeNull();
    }
  });

  it("clips extract cells to the view bbox with per-slice q stamps (route contract)", () => {
    const bbox = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };
    const frost = kliimaPointsIn(KLIIMA_CELLS, "frost", bbox);
    // Only Harku sits inside this Tallinn bbox; Pakri + Kuusiku clip out.
    expect(frost).toHaveLength(1);
    expect(frost[0]).toMatchObject({ lat: 59.398122, q: 55 });
    const wide = { minlon: 23.9, minlat: 58.9, maxlon: 25.0, maxlat: 59.5 };
    const wet = kliimaPointsIn(KLIIMA_CELLS, "wet", wide);
    expect(wet).toHaveLength(3);
    // Pakri rides WITHOUT q on the wet slice (unranked: plotted, never scored).
    expect(wet.find((p) => p.lon === 24.0401)).not.toHaveProperty("q");
    expect(wet.find((p) => p.lon === 24.60287)).toMatchObject({ q: 70 });
  });
});

describe("kliima normals field (client render path)", () => {
  const bbox = { minlon: 24.73, minlat: 59.43, maxlon: 24.76, maxlat: 59.445 };
  const spec = kliimaBonusSpecFor("kliima_frost");
  if (spec.kind !== "qbands") throw new Error("kliima spec must be qbands");

  it("renders the cell band over the whole county-scale window (70 km covers the bbox)", () => {
    const pts = [{ lon: 24.7454, lat: 59.4375, q: 55 }];
    const field = buildScoredField(pts, bbox, 24, 12, 1.0, spec);
    expect(field.direct).not.toBeNull();
    // Every cell sits inside the 70 km county radius: all 55, none
    // unknown (the cutoff pins live in the kernel-parity tests above).
    expect(field.direct!).toHaveLength(24 * 12);
    for (const v of field.direct!) expect(v).toBe(55);
  });

  it("renders the nearest band where synthetic cells overlap (no blending)", () => {
    const cells = [
      { lon: 24.7454, lat: 59.4375, q: 40 },
      { lon: 24.7454, lat: 59.4395, q: 70 },
    ];
    const field = buildScoredField(cells, bbox, 24, 12, 1.0, spec);
    const vals = [...field.direct!].filter((v) => !Number.isNaN(v));
    expect(vals.length).toBeGreaterThan(0);
    for (const v of vals) expect([40, 70]).toContain(v);
  });

  it("renders all-unknown over a quality-NULL cell (never a faked middle)", () => {
    const pts = [{ lon: 24.7454, lat: 59.4375 }];
    const field = buildScoredField(pts, bbox, 8, 8, 1.0, spec);
    expect(field.direct).not.toBeNull();
    for (const v of field.direct!) expect(v).toBeNaN();
  });

  it("renders all-unknown when nothing loaded (never a faked field)", () => {
    const field = buildScoredField([], bbox, 8, 8, 1.0, spec);
    expect(field.direct).not.toBeNull();
    for (const v of field.direct!) expect(v).toBeNaN();
  });
});

describe("kliima committed extract (real-data pins, vintage 2026-09-16)", () => {
  it("carries 3 Harjumaa station cells (Harku/Pakri/Kuusiku)", () => {
    expect(KLIIMA_CELLS).toHaveLength(3);
    expect(KLIIMA_CELLS.map((c) => c.code).sort()).toEqual(["AJHARK01", "AJKUUS01", "AJPAKR01"]);
  });

  it("pins the harvested normals (builder parity — drift = bug)", () => {
    expect(KLIIMA_PROBE.frostHarkuDays).toBe(128.6);
    expect(KLIIMA_PROBE.frostPakriDays).toBe(106.5);
    expect(KLIIMA_PROBE.frostKuusikuDays).toBe(146.5);
    expect(KLIIMA_PROBE.precipHarkuMm).toBe(699.9);
    expect(KLIIMA_PROBE.precipKuusikuMm).toBe(730.1);
    const harku = KLIIMA_CELLS.find((c) => c.code === "AJHARK01")!;
    expect(harku.frostDays).toBe(128.6);
    expect(harku.precipMm).toBe(699.9);
    expect(harku.frostBand).toBe(55);
    expect(harku.wetBand).toBe(70);
  });

  it("ranks frost Pakri 70 / Harku 55 / Kuusiku 40 (mildest first)", () => {
    // Tallinn backyard -> Harku cell (frost 55, wet 70).
    expect(kliimaBandAt(59.4374, 24.7454, "frost", KLIIMA_CELLS)).toBe(55);
    expect(kliimaBandAt(59.4374, 24.7454, "wet", KLIIMA_CELLS)).toBe(70);
    // Paldiski backyard -> Pakri cell (frost 70, wet NULL by the
    // coverage rule — scorer parity: EI OLE on the same gap).
    expect(kliimaBandAt(59.32, 24.05, "frost", KLIIMA_CELLS)).toBe(70);
    expect(kliimaBandAt(59.32, 24.05, "wet", KLIIMA_CELLS)).toBeNull();
    // South-Harjumaa backyard -> Kuusiku cell (frost 40, wet 40).
    expect(kliimaBandAt(58.99, 24.74, "frost", KLIIMA_CELLS)).toBe(40);
    expect(kliimaBandAt(58.99, 24.74, "wet", KLIIMA_CELLS)).toBe(40);
  });

  it("keeps every band in the coarse ladder and every cell inside Harjumaa", () => {
    for (const c of KLIIMA_CELLS) {
      if (c.frostBand !== null) expect([40, 55, 70]).toContain(c.frostBand);
      if (c.wetBand !== null) expect([40, 55, 70]).toContain(c.wetBand);
      expect(c.lat).toBeGreaterThan(58.9);
      expect(c.lat).toBeLessThan(59.5);
      expect(c.lon).toBeGreaterThan(23.9);
      expect(c.lon).toBeLessThan(25.0);
    }
  });
});
