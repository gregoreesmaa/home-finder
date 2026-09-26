import { describe, expect, it } from "vitest";
import {
  CARFRICTION_BONUS,
  CARFRICTION_CAL,
  CARFRICTION_DECAY,
  CARFRICTION_DEFS,
  CARFRICTION_HOOK,
  CARFRICTION_LAYER_IDS,
  CARFRICTION_RASTER_FILE,
  CARFRICTION_TAGS,
  bonusSpecForCarfriction,
  carfrictionAt,
  carfrictionHavKm,
  carfrictionSparseScore,
  isCarfrictionLayerId,
} from "./layers_p4_carfriction";
import {
  LAYERS,
  bonusSpecFor,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { matchesContract } from "./server/snapshot";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("carfriction registry (#829)", () => {
  it("defines exactly the one OSM restriction-friction layer", () => {
    expect(CARFRICTION_LAYER_IDS).toEqual(["carfriction"]);
    expect(CARFRICTION_DEFS.map((d) => d.id)).toEqual(CARFRICTION_LAYER_IDS);
    expect(CARFRICTION_HOOK).toContain("CARFRICTION-HOOK (#829)");
  });

  it("carries no parameters3 id (parameters4 namespace, quarry precedent)", () => {
    for (const d of CARFRICTION_DEFS) {
      expect(d.paramIds).toEqual([]);
      expect(d.paramLabel).toBe("P4-auto");
    }
  });

  it("merges into LAYERS via the CARFRICTION-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    expect(ids).toContain("carfriction");
    // Order: right after the P4 parking sibling (same source family).
    expect(ids.indexOf("carfriction")).toBe(ids.indexOf("parking") + 1);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of CARFRICTION_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source).toContain("2026-09-12");
      expect(d.fallbackPoints.length).toBeGreaterThan(0);
    }
  });
});

describe("carfriction honesty (#829)", () => {
  it("says piirang + hinnang in the title, never measured difficulty or paid zones", () => {
    const cf = CARFRICTION_DEFS.find((d) => d.id === "carfriction");
    expect(cf?.title).toContain("piirang");
    expect(cf?.title).toMatch(/hinnang|proksi/);
    expect(cf?.title).not.toMatch(/tasuline|mõõdetud|ummik/i);
  });

  it("names the missing paid-zone / congestion facts in the source (nodata honesty)", () => {
    const cf = CARFRICTION_DEFS.find((d) => d.id === "carfriction");
    // Paid zones ship as a documented gap, never inferred.
    expect(cf?.source).toMatch(/TASULISED TSOONID EI OLE/);
    expect(cf?.source).toMatch(/tsoonirežiim/);
    expect(cf?.source).toMatch(/tuletamata/);
    // Congestion stays in the delay-* layers, never duplicated here.
    expect(cf?.source).toMatch(/VIIVITUS EI OLE/);
    expect(cf?.source).toMatch(/delay-\*/);
  });

  it("keeps the labels honest about what the map does not show", () => {
    const cf = CARFRICTION_DEFS.find((d) => d.id === "carfriction");
    expect(cf?.goodLabel).toContain("hinnang");
    expect(cf?.badLabel).toContain("hinnang");
    expect(cf?.badLabel).toMatch(/ummikuid ega tasulisi tsoone kaart ei näita/);
  });
});

describe("carfriction scoring contract (#829)", () => {
  it("locks radius and bonus spec (raster contract + Euclidean fallback)", () => {
    // CARFRICTION_CAL is the single source (mirrored by the Python
    // builder — parsed by scripts/build/test_batch_carfriction.py).
    expect(CARFRICTION_CAL).toEqual({ carfriction: { half: 60, sigma: 0.3 } });
    expect(CARFRICTION_DECAY).toEqual({ carfriction: 0.3 });
    expect(CARFRICTION_BONUS).toEqual({ carfriction: { kind: "sparse", half: 60 } });
    expect(radiusKmFor("carfriction")).toBeCloseTo(0.3, 5);
    expect(bonusSpecFor("carfriction")).toEqual({ kind: "sparse", half: 60 });
  });

  it("guards and lookups answer carfriction and ignore other layers", () => {
    expect(isCarfrictionLayerId("carfriction")).toBe(true);
    expect(isCarfrictionLayerId("parking")).toBe(false);
    expect(bonusSpecForCarfriction("carfriction")).toEqual({ kind: "sparse", half: 60 });
    expect(bonusSpecForCarfriction("parks")).toBeUndefined();
  });

  it("names the raster master the snapshot serves under the contract", () => {
    expect(CARFRICTION_RASTER_FILE).toEqual({ carfriction: "carfriction-walk-raster.json" });
  });

  it("raster docs bake matching calibration (matchesContract)", () => {
    expect(matchesContract({ half: 60, sigma: 0.3, per: 0, cap: 0 }, "carfriction")).toBe(true);
    // Stale half is rejected, never silently rendered.
    expect(matchesContract({ half: 999, sigma: 0.3, per: 0, cap: 0 }, "carfriction")).toBe(false);
    // Wrong sigma is rejected too (the street-scale kernel is load-bearing).
    expect(matchesContract({ half: 60, sigma: 0.8, per: 0, cap: 0 }, "carfriction")).toBe(false);
  });

  it("scores INVERTED: a lone barrier reads ~open, a dense pocket reads bad", () => {
    // One barrier on the cell: S=1 -> 100*60/61 = 98.36 -> 98.
    const one = carfrictionAt(59.44, 24.75, [{ lat: 59.44, lon: 24.75 }]);
    expect(one).toBe(98);
    // Empty input is unknown (never a faked open 100)...
    expect(carfrictionAt(59.44, 24.75, [])).toBeNull();
    // ...but a loaded set with nothing in range reads measured-open 100.
    expect(carfrictionAt(59.44, 24.75, [{ lat: 59.5, lon: 24.9 }])).toBe(100);
    // A closure-lined pocket (200 samples on one cell) reads red.
    const dense = new Array(200).fill({ lat: 59.44, lon: 24.75 });
    expect(carfrictionAt(59.44, 24.75, dense)).toBeLessThan(50);
    expect(carfrictionHavKm(24.75, 59.44, 24.75, 59.44)).toBe(0);
  });

  it("reads Vanalinn red and open suburbs green off the built signal shape", () => {
    // Unit-level acceptance proof (criterion 1): half-count scores 50,
    // the Vanalinn-scale count (~150) scores red, empty reads 100.
    expect(carfrictionSparseScore(0, 60)).toBe(100);
    expect(carfrictionSparseScore(60, 60)).toBe(50);
    expect(carfrictionSparseScore(150, 60)).toBeLessThan(50);
  });
});

describe("carfriction queries and tags (#829)", () => {
  it("documents the verified snapshot tags (motor-vehicle access keys)", () => {
    expect(CARFRICTION_TAGS.carfriction).toContain("motor_vehicle");
    expect(CARFRICTION_TAGS.carfriction).toContain("motorcar");
  });

  it("builds a bbox-scoped Overpass QL query covering nodes and ways", () => {
    const q = overpassQueryFor("carfriction", TALLINN_BBOX);
    expect(q).toContain("motor_vehicle");
    expect(q).toContain("24.5");
  });
});
