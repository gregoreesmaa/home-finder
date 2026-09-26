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
  asumediaEmptyStatus,
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
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    // HARNO-HOOK (#687): +1 harno school layer (156 + 1 = 157).
    // VIIRS-HOOK (#719): +1 viirs brightness layer (157 + 1 = 158).
    // OUTAGE-HOOK (#729): +1 outage hetkeseis layer (158 + 1 = 159).
    // BUSMESH-HOOK (#769): +3 transfer-node window layers (159 + 3 = 162).
    // SHED-HOOK (#763) + DATEX-HOOK (#763) + INCIDENTS-HOOK (#763): +4 sheds +6 datex +1 incidents (162 + 11 = 173).
    // CARFRICTION-HOOK (#829): +1 carfriction restriction-friction layer (173 + 1 = 174).
    expect(ids.length).toBe(174); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
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

describe("asumedia empty state (#786)", () => {
  it("pins the honest ootel empty-state message", () => {
    expect(asumediaEmptyStatus()).toBe(
      "Ootel-hinnang (2026-09-14 loendus: 30 kirjet, 0 asumivõtmega, " +
        "0/84 asumi MIN_N=5 täis) — taasavab: geokodeeritud " +
        "snapshotid + Tallinna 84 asumi polügoonid; õhukese N-iga " +
        "asumeid EI FEIGITA",
    );
  });

  it("names the dated tally + reopen path, never bare no-data", () => {
    const status = asumediaEmptyStatus();
    // Dated tally: probe date + counts that match ASUMEDIA_VERDICT.
    expect(status).toContain(ASUMEDIA_VERDICT.date);
    expect(status).toContain(`${ASUMEDIA_VERDICT.fixtureRecords} kirjet`);
    expect(status).toContain(
      `${ASUMEDIA_VERDICT.asumsAtMinN}/${ASUMEDIA_TALLINN_ASUMS}`,
    );
    // Reopen path: geocoded snapshots + 84 asum polygons + MIN_N.
    expect(status).toMatch(/geokodeeritud snapshotid/);
    expect(status).toMatch(/84 asumi polügoonid/);
    expect(status).toContain(`MIN_N=${ASUMEDIA_MIN_N}`);
    // Thin asums stay unfaked, and this is not the generic
    // no-coverage copy ("...andmed puuduvad").
    expect(status).toMatch(/EI FEIGITA/);
    expect(status).not.toContain("andmed puuduvad");
    expect(status).not.toMatch(/€\/m²/);
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
