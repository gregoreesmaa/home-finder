// Hermetic tests for the outage latest-observed layer (issue #729;
// wording per #783 slice 2: surfaces say "viimane vaatlus", never
// "hetkeseis" — the #780 history-vs-observation side-by-side contract
// is unchanged, only the observed-side label is renamed).
// No network: the 2026-09-19 live verification (GetApplicationData
// 200 + configuration.js field pins) lives in OUTAGE_PROBE + the
// harvester (pulled live, /tmp only, never at runtime); the layer
// ships honestly empty until the operator pull, and the band kernel
// is byte parity with dim_outage_now (drift = failing test). The
// fixture Tallinn row repeats the observed live counters (facts,
// tiny). No secrets.

import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  OUTAGE_BANDS,
  OUTAGE_HOOK,
  OUTAGE_LAYER_IDS,
  OUTAGE_POLE_DATASET,
  OUTAGE_PROBE,
  OUTAGE_RADIUS_M,
  OUTAGE_RELIABILITY_METRIC,
  OUTAGE_RELIABILITY_POLE_DATASET,
  OUTAGE_RELIABILITY_TTL_S,
  OUTAGE_RELIABILITY_WINDOW_DAYS,
  OUTAGE_TALLINN,
  OUTAGE_TTL_S,
  outageBandAt,
  outageBandForRow,
  outageBonusSpecFor,
  outageCountOf,
  outageHistoryStatus,
  outageNearby,
  outagePointsIn,
  isOutageLayerId,
} from "./layers_p4_outage";

const LIVE_TALLINN = { lat: OUTAGE_TALLINN.lat, lon: OUTAGE_TALLINN.lon };

describe("outage registry", () => {
  it("registers the honest-empty latest-observed layer", () => {
    expect(OUTAGE_LAYER_IDS).toEqual(["outage"]);
    expect(LAYERS.find((l) => l.id === "outage")).toBeTruthy();
  });

  it("wires the qbands spec through the shared hooks", () => {
    expect(isOutageLayerId("outage")).toBe(true);
    expect(isOutageLayerId("tervise")).toBe(false);
    expect(outageBonusSpecFor("outage")).toEqual({
      kind: "qbands",
      radiusM: OUTAGE_RADIUS_M,
    });
    expect(bonusSpecFor("outage")).toEqual(outageBonusSpecFor("outage"));
    expect(radiusKmFor("outage")).toBe(15.0);
    expect(OUTAGE_RADIUS_M).toBe(15000);
    expect(OUTAGE_TTL_S).toBe(300);
    expect(OUTAGE_BANDS).toEqual({ fault: 30, planned: 55, upcoming: 70, clean: 80 });
  });

  it("pins the live-verified, uncommitted-sidecar verdict", () => {
    expect(OUTAGE_PROBE.date).toBe("2026-09-19");
    expect(OUTAGE_PROBE.liveVerified).toBe(true);
    expect(OUTAGE_PROBE.sidecarCommitted).toBe(false);
  });

  it("explains the latest observation in Estonian with zero markers", () => {
    const def = LAYERS.find((l) => l.id === "outage")!;
    expect(def.title).toContain("katkestused");
    expect(def.badLabel).toContain("EI OLE");
    expect(def.source).toContain("viimane vaatlus");
    expect(def.source).not.toContain("hetkeseis");
    expect(def.paramIds).toEqual([]);
    expect(def.fallbackPoints).toEqual([]);
    expect(def.paramLabel).toBe("P4-009");
  });

  it("serves an Estonian legend and a registry-unique color", () => {
    expect(overlayLegendFor("outage")).toContain("viimane vaatlus");
    expect(overlayLegendFor("outage")).not.toContain("hetkeseis");
    expect(overlayColorFor("outage")).toMatch(/^#[0-9a-f]{6}$/);
    expect(overlayColorFor("outage")).toBe("#e65100");
    expect(overlayColorFor("outage")).not.toBe(overlayColorFor("tervise"));
  });

  it("keeps the hook marker greppable", () => {
    expect(OUTAGE_HOOK).toContain("OUTAGE-HOOK (#729)");
  });

  it("names the pole live-table dataset for the route (#775)", () => {
    expect(OUTAGE_POLE_DATASET).toBe("outage");
  });
});

describe("outage kernel (parity with dim_outage_now)", () => {
  const live = { ...LIVE_TALLINN, q: 70 };

  it("bands fault/planned/upcoming/clean off counters, missing stays null", () => {
    // Live Tallinn row 2026-09-19: uc=27/ucc=3169, rest 0 -> upcoming 70.
    expect(outageBandForRow({ fc: 0, fcc: 0, pc: 0, pcc: 0, uc: 27, ucc: 3169 })).toBe(70);
    expect(outageBandForRow({ fc: 2, fcc: 410, pc: 0, pcc: 0, uc: 0, ucc: 0 })).toBe(30);
    expect(outageBandForRow({ fc: 0, fcc: 0, pc: 1, pcc: 55, uc: 0, ucc: 0 })).toBe(55);
    expect(outageBandForRow({ fc: 0, fcc: 0, pc: 0, pcc: 0, uc: 0, ucc: 0 })).toBe(80);
    // Missing counts never zero-fill into calm.
    expect(outageBandForRow({ fc: null, fcc: 0, pc: 0, pcc: 0, uc: 0, ucc: 0 })).toBeNull();
    expect(outageBandForRow({})).toBeNull();
  });

  it("reads empty as unknown, never zero", () => {
    expect(outageBandAt(59.437, 24.745, [])).toBeNull();
    expect(outageNearby(59.437, 24.745, [])).toEqual([]);
  });

  it("reads the city point inside 15 km, unknown past it", () => {
    expect(outageBandAt(59.437, 24.745, [live])).toBe(70);
    expect(outageBandAt(59.437, 24.745, [{ ...LIVE_TALLINN }])).toBeNull();
    // Tartu stays unknown on a Tallinn point.
    expect(outageBandAt(58.38, 26.72, [live])).toBeNull();
  });

  it("reads counters off served tags", () => {
    const tags = { uc: "27", ucc: "3169" };
    expect(outageCountOf(tags, "uc")).toBe(27);
    expect(outageCountOf(tags, "ucc")).toBe(3169);
    expect(outageCountOf(tags, "fc")).toBeNull();
    expect(outageCountOf(undefined, "uc")).toBeNull();
  });

  it("clips the city point to the view bbox", () => {
    const bbox = { minlon: 24.5, maxlon: 25.0, minlat: 59.3, maxlat: 59.6 };
    expect(outagePointsIn([live], bbox)).toHaveLength(1);
    expect(outagePointsIn([{ lat: 58.38, lon: 26.72, q: 30 }], bbox)).toHaveLength(0);
  });
});

describe("outage observed reliability (#780)", () => {
  it("pins the pole dataset, window and freshness ceiling", () => {
    expect(OUTAGE_RELIABILITY_POLE_DATASET).toBe("outage-reliability");
    expect(OUTAGE_RELIABILITY_WINDOW_DAYS).toBe(28);
    expect(OUTAGE_RELIABILITY_TTL_S).toBe(86400);
    expect(OUTAGE_RELIABILITY_METRIC).toContain("MITTE garantii");
  });

  it("names the window and labels history vs latest observation on every surface", () => {
    const def = LAYERS.find((l) => l.id === "outage")!;
    expect(def.title).toContain("28 pv");
    expect(def.title).toContain("viimane vaatlus");
    expect(def.source).toContain("28 päeva");
    expect(def.source).toContain("punkt on viimane vaatlus");
    expect(def.source).toContain("ajalugu on pooluse");
    expect(def.goodLabel).toContain("viimase vaatluse hinnang");
    expect(def.goodLabel).toContain("ajalugu: 28 päeva");
    expect(overlayLegendFor("outage")).toContain("28 pv");
    expect(overlayLegendFor("outage")).toContain("ajalugu");
    expect(overlayLegendFor("outage")).toContain("viimane vaatlus");
    expect(OUTAGE_HOOK).toContain("#780");
  });

  it("formats the history line off the served window, null otherwise", () => {
    const rel = {
      builtAt: "2026-09-20T11:55:00Z",
      windowDays: 28,
      tallinn: {
        nObs: 100, faultObs: 3, plannedObs: 5, upcomingObs: 40,
        faultCustomers: 210, plannedCustomers: 90, coverage: 0.0124,
      },
      nObsTotal: 100,
    };
    const line = outageHistoryStatus(rel);
    expect(line).toContain("ajalugu 28 pv");
    expect(line).toContain("3 rikke-");
    expect(line).toContain("MITTE garantii");
    // Absent/unshaped/wrong-window payloads never fake a window.
    expect(outageHistoryStatus(null)).toBeNull();
    expect(outageHistoryStatus(undefined)).toBeNull();
    expect(outageHistoryStatus({ windowDays: 28 })).toBeNull();
    expect(outageHistoryStatus({ ...rel, windowDays: 7 })).toBeNull();
  });
});
