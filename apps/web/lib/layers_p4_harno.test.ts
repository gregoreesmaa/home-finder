// Hermetic tests for the Harno school-quality layer (issue #687).
// No network: the 2026-09-19 no-export verdict lives in HARNO_PROBE
// (probed live, /tmp only, never at runtime); the layer ships
// honestly empty (paaste #493 precedent) until the first verified
// annual snapshot. No secrets.

import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  HARNO_BANDS,
  HARNO_HOOK,
  HARNO_LAYER_IDS,
  HARNO_PROBE,
  HARNO_RADIUS_M,
  HARNO_VINTAGE,
  harnoBandAt,
  harnoBonusSpecFor,
  harnoNearby,
  harnoPointsIn,
  isHarnoLayerId,
} from "./layers_p4_harno";

describe("harno registry", () => {
  it("registers the honest-empty school-quality layer", () => {
    expect(HARNO_LAYER_IDS).toEqual(["harno"]);
    expect(LAYERS.find((l) => l.id === "harno")).toBeTruthy();
  });

  it("wires the qbands spec through the shared hooks", () => {
    expect(isHarnoLayerId("harno")).toBe(true);
    expect(isHarnoLayerId("tervise")).toBe(false);
    expect(harnoBonusSpecFor("harno")).toEqual({
      kind: "qbands",
      radiusM: HARNO_RADIUS_M,
    });
    expect(bonusSpecFor("harno")).toEqual(harnoBonusSpecFor("harno"));
    expect(radiusKmFor("harno")).toBe(1.0);
    expect(HARNO_RADIUS_M).toBe(1000);
    expect(HARNO_BANDS).toEqual([80, 70, 60, 45, 30]);
  });

  it("pins the no-snapshot verdict (never invented schools)", () => {
    expect(HARNO_PROBE.date).toBe("2026-09-19");
    expect(HARNO_PROBE.snapshot).toBe(false);
    expect(HARNO_PROBE.machineExport).toBe(false);
    expect(HARNO_VINTAGE).toBeNull();
  });

  it("explains the gap in Estonian with zero markers", () => {
    const def = LAYERS.find((l) => l.id === "harno")!;
    expect(def.title).toContain("Koolide");
    expect(def.badLabel).toContain("EI OLE");
    expect(def.source).toContain("EI OLE");
    expect(def.paramIds).toEqual([]);
    expect(def.fallbackPoints).toEqual([]);
    expect(def.paramLabel).toBe("P4-harno");
  });

  it("serves an Estonian legend and a registry-unique color", () => {
    expect(overlayLegendFor("harno")).toContain("EI OLE");
    expect(overlayColorFor("harno")).toMatch(/^#[0-9a-f]{6}$/);
    expect(overlayColorFor("harno")).not.toBe(overlayColorFor("tervise"));
  });

  it("keeps the hook marker greppable", () => {
    expect(HARNO_HOOK).toContain("HARNO-HOOK (#687)");
  });
});

describe("harno kernel (dormant until the first snapshot)", () => {
  const school = { lat: 59.437, lon: 24.745, q: 80 };

  it("reads empty as unknown, never zero", () => {
    expect(harnoBandAt(59.437, 24.745, [])).toBeNull();
    expect(harnoNearby(59.437, 24.745, [])).toEqual([]);
  });

  it("reads the nearest school's band, NULL stays NULL", () => {
    expect(harnoBandAt(59.437, 24.745, [school])).toBe(80);
    expect(
      harnoBandAt(59.437, 24.745, [{ lat: 59.437, lon: 24.745 }]),
    ).toBeNull();
    // Far away (Tartu) stays unknown on Tallinn fixtures.
    expect(harnoBandAt(58.38, 26.72, [school])).toBeNull();
  });

  it("clips points to the view bbox", () => {
    const bbox = { minlon: 24.5, maxlon: 25.0, minlat: 59.3, maxlat: 59.6 };
    expect(harnoPointsIn([school], bbox)).toHaveLength(1);
    expect(harnoPointsIn([{ lat: 58.38, lon: 26.72, q: 60 }], bbox)).toHaveLength(0);
  });
});
