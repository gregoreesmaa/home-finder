// Hermetic tests for the VIIRS brightness-proxy layer (issue #719).
// No network: the 2026-09-19 tile harvest lives in VIIRS_PROBE and
// the 96 sampled cells in VIIRS_CELLS (built offline by
// scripts/build/batch_viirs.py from the /tmp harvest — never live).
// Spot-check anchors (saturated centre 255.0 vs dark bog 11.6) pin
// the proxy premise. No secrets.

import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  VIIRS_CELLS,
  VIIRS_HOOK,
  VIIRS_LAYER_IDS,
  VIIRS_PROBE,
  VIIRS_RADIUS_M,
  VIIRS_VINTAGE,
  isViirsLayerId,
  viirsBandAt,
  viirsBonusSpecFor,
  viirsNearby,
  viirsPointsIn,
} from "./layers_p4_viirs";

describe("viirs registry", () => {
  it("registers the brightness-proxy layer", () => {
    expect(VIIRS_LAYER_IDS).toEqual(["viirs"]);
    expect(LAYERS.find((l) => l.id === "viirs")).toBeTruthy();
  });

  it("wires the qbands spec through the shared hooks", () => {
    expect(isViirsLayerId("viirs")).toBe(true);
    expect(isViirsLayerId("tervise")).toBe(false);
    expect(viirsBonusSpecFor("viirs")).toEqual({
      kind: "qbands",
      radiusM: VIIRS_RADIUS_M,
    });
    expect(bonusSpecFor("viirs")).toEqual(viirsBonusSpecFor("viirs"));
    expect(radiusKmFor("viirs")).toBe(3.0);
    expect(VIIRS_RADIUS_M).toBe(3000);
  });

  it("pins the live harvest basis and the 2016 vintage", () => {
    expect(VIIRS_PROBE.date).toBe("2026-09-19");
    expect(VIIRS_PROBE.tile).toBe("8/75/145");
    expect(VIIRS_PROBE.tileBytes).toBe(55225);
    expect(VIIRS_VINTAGE).toBe("2016");
  });

  it("pins the spot-check contrast before ranking", () => {
    expect(VIIRS_PROBE.centerMean).toBe(255.0);
    expect(VIIRS_PROBE.bogMean).toBe(11.6);
    expect(VIIRS_PROBE.centerMean).toBeGreaterThan(
      VIIRS_PROBE.bogMean * 10,
    );
  });

  it("ships the 96 sampled cells (regenerate, never hand-edit)", () => {
    expect(VIIRS_CELLS).toHaveLength(VIIRS_PROBE.cells);
    expect(VIIRS_PROBE.cells).toBe(96);
    const qs = VIIRS_CELLS.map((c) => c.q!);
    expect(Math.min(...qs)).toBe(10);
    expect(Math.max(...qs)).toBe(90);
    // Brightest sampled cell sits over the Mustamäe/Õismäe glow
    // (mean 255.0), darkest over the north-western outskirts
    // (mean 9.4, sea-adjacent — disclosed limitation).
    const glow = VIIRS_CELLS.find(
      (c) => Math.abs(c.lat - 59.4075) < 0.02 && Math.abs(c.lon - 24.675) < 0.03,
    );
    expect(glow?.q).toBe(10);
    const dark = VIIRS_CELLS.find(
      (c) => Math.abs(c.lat - 59.5075) < 0.02 && Math.abs(c.lon - 24.475) < 0.03,
    );
    expect(dark?.q).toBe(90);
  });

  it("labels the proxy on every user surface (never radiometry)", () => {
    const def = LAYERS.find((l) => l.id === "viirs")!;
    expect(def.title).toContain("proksi");
    expect(def.badLabel).toContain("mitte mõõdetud radiomeetria");
    expect(def.source).toContain("MITTE radiomeetria");
    expect(def.source).toContain("2016");
    expect(def.paramIds).toEqual([]);
    expect(def.paramLabel).toBe("P4-035");
  });

  it("serves an Estonian legend and a registry-unique color", () => {
    expect(overlayLegendFor("viirs")).toContain("heledusproksi");
    expect(overlayLegendFor("viirs")).toContain("2016");
    expect(overlayColorFor("viirs")).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("keeps the hook marker greppable", () => {
    expect(VIIRS_HOOK).toContain("VIIRS-HOOK (#719)");
  });
});

describe("viirs kernel (sampled cells)", () => {
  it("reads the nearest cell's band at the centre", () => {
    expect(viirsBandAt(59.437, 24.745, VIIRS_CELLS)).toBe(10);
  });

  it("reads dark outskirts high, far outside stays unknown", () => {
    expect(viirsBandAt(59.5075, 24.475, VIIRS_CELLS)).toBe(90);
    expect(viirsBandAt(58.38, 26.72, VIIRS_CELLS)).toBeNull();
  });

  it("orders neighbours nearest-first", () => {
    const near = viirsNearby(59.437, 24.745, VIIRS_CELLS);
    expect(near.length).toBeGreaterThan(0);
    for (let i = 1; i < near.length; i++) {
      expect(near[i].distM).toBeGreaterThanOrEqual(near[i - 1].distM);
    }
  });

  it("clips points to the view bbox", () => {
    const bbox = { minlon: 24.5, maxlon: 25.0, minlat: 59.3, maxlat: 59.6 };
    const inside = viirsPointsIn(VIIRS_CELLS, bbox);
    expect(inside.length).toBeGreaterThan(0);
    expect(inside.length).toBeLessThan(VIIRS_CELLS.length);
  });
});
