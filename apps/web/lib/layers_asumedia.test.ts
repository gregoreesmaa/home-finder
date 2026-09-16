import { describe, expect, it } from "vitest";
import {
  ASUMEDIA_BONUS,
  ASUMEDIA_DECAY,
  ASUMEDIA_DEFS,
  ASUMEDIA_HOOK,
  ASUMEDIA_LAYER_IDS,
  ASUMEDIA_MEASURED,
  ASUMEDIA_MIN_N,
  ASUMEDIA_NO_METRO,
  ASUMEDIA_NO_RASTER,
  ASUMEDIA_RASTER_FILE,
  ASUMEDIA_REOPEN,
  ASUMEDIA_TALLINN_ASUMS,
  ASUMEDIA_VERDICT,
  asumediaGatedMedian,
  asumediaMedianEurM2,
  bonusSpecForAsumedia,
  isAsumediaLayerId,
} from "./layers_asumedia";
import {
  LAYERS,
  bonusSpecFor,
  radiusKmFor,
} from "./layers";

describe("asumedia registry (#495)", () => {
  it("defines exactly the one own-snapshot asumedian layer", () => {
    expect(ASUMEDIA_LAYER_IDS).toEqual(["asumedia"]);
    expect(ASUMEDIA_DEFS.map((d) => d.id)).toEqual(ASUMEDIA_LAYER_IDS);
    expect(ASUMEDIA_HOOK).toContain("ASUMEDIA-HOOK (#495)");
    // No parameters3 number claimed (namespace lock — the asking-median
    // leg is distinct from P4-002 closed medians and P4-038 gap).
    for (const d of ASUMEDIA_DEFS) expect(d.paramIds).toEqual([]);
  });

  it("merges into LAYERS via the ASUMEDIA-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 106 shipped layers on main (#511 tervise) + 1 asumedia layer (106 + 1).
    // ASUMEDIA-HOOK (#495): asumedia joins the registry (106 + 1).
    // PAASTE-HOOK (#493): +1 komando overlay (107 + 1).
    expect(ids.length).toBe(119); // SPORT-HOOK (#607): +3 sport slices (108 + 3); EHIS-HOOK (#608): +3 school slices (111 + 3); MEDRE-HOOK (#609): +2 care slices (114 + 2); OHUSEIRE-HOOK (#610): +1 station dots (116 + 1); KLIIMA-HOOK (#611): +2 climate slices (117 + 2)
    expect(ids).toContain("asumedia");
  });

  it("labels the dated negative in Estonian with demo-free honesty", () => {
    for (const d of ASUMEDIA_DEFS) {
      expect(d.title).toMatch(/ootel/);
      expect(d.title).toMatch(/hinnang/);
      expect(d.goodLabel).toMatch(/teadmata/);
      expect(d.badLabel).toMatch(/EI OLE/);
      expect(d.source).toMatch(/EI FEIGITA/);
      expect(d.source).toContain(ASUMEDIA_VERDICT.date);
      // EMPTY by decision (planktpr #492 precedent): demo points would
      // paint a fake gradient splat on a future exact-fill choropleth.
      expect(d.fallbackPoints).toEqual([]);
    }
  });

  it("pins the verify-first tally (re-tally forces an intentional edit)", () => {
    expect(ASUMEDIA_MIN_N).toBe(5);
    expect(ASUMEDIA_TALLINN_ASUMS).toBe(84);
    expect(ASUMEDIA_VERDICT).toEqual({
      date: "2026-09-14",
      fixtureRecords: 30,
      fixtureUsable: 26,
      fixtureWithAsumKey: 0,
      fixtureTallinnUsable: 13,
      asumsAtMinN: 0,
    });
    expect(ASUMEDIA_MEASURED).toEqual([]);
    expect(ASUMEDIA_REOPEN).toMatch(/Taasavamise latt/);
  });
});

describe("asumedia honesty (#495)", () => {
  it("never claims measured truth and names the missing join", () => {
    for (const d of ASUMEDIA_DEFS) {
      expect(d.title + d.source).not.toMatch(/mõõdetud|tegelik arv|täpne arv/);
      expect(d.source).toMatch(/asumivõtit/);
      expect(d.source).toMatch(/polügoone repos/);
    }
  });

  it("documents the reopen bar in the hook marker", () => {
    expect(ASUMEDIA_HOOK).toMatch(/dated negative/);
    expect(ASUMEDIA_HOOK).toMatch(/empty-on-purpose/);
  });
});

describe("asumedia median kernel (#495)", () => {
  it("takes the middle value on odd groups", () => {
    expect(asumediaMedianEurM2([4000, 4000, 4545.45, 4727.27, 4838.71])).toBe(4545.45);
  });

  it("averages the middle pair on even groups", () => {
    expect(asumediaMedianEurM2([4000, 4545.45, 4727.27, 5000])).toBe(
      (4545.45 + 4727.27) / 2,
    );
  });

  it("returns null on empty or unusable groups (unknown, never zero)", () => {
    expect(asumediaMedianEurM2([])).toBeNull();
    expect(asumediaMedianEurM2([0, -5, NaN, Infinity])).toBeNull();
  });

  it("gates medians behind ASUMEDIA_MIN_N (thin stays null, n labeled)", () => {
    expect(asumediaGatedMedian([4545.45, 4727.27])).toEqual({ median: null, n: 2 });
    expect(asumediaGatedMedian([4000])).toEqual({ median: null, n: 1 });
    expect(
      asumediaGatedMedian([4000, 4000, 4545.45, 4727.27, 4838.71]),
    ).toEqual({ median: 4545.45, n: 5 });
  });
});

describe("asumedia calibration (#495)", () => {
  it("locks the inert cover spec + decay (drift guard vs Python MIN_N)", () => {
    expect(ASUMEDIA_BONUS).toEqual({ asumedia: { kind: "cover", sigma: 0.5 } });
    expect(ASUMEDIA_DECAY).toEqual({ asumedia: 0.5 });
    expect(bonusSpecFor("asumedia")).toEqual({ kind: "cover", sigma: 0.5 });
    expect(radiusKmFor("asumedia")).toBe(0.5);
    expect(bonusSpecForAsumedia("asumedia")).toEqual({ kind: "cover", sigma: 0.5 });
    expect(isAsumediaLayerId("asumedia")).toBe(true);
    expect(isAsumediaLayerId("parking")).toBe(false);
    expect(bonusSpecForAsumedia("parking")).toBeUndefined();
  });

  it("names the raster master that is intentionally never built", () => {
    expect(ASUMEDIA_RASTER_FILE).toEqual({
      asumedia: "asumedia-walk-raster.json",
    });
    expect(ASUMEDIA_NO_RASTER).toBe(true);
    expect(ASUMEDIA_NO_METRO).toBe(true);
  });
});
