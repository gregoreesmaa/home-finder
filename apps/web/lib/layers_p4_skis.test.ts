// Hermetic tests for the seasonal ski-track layer (issue #692).
// No network: the 2026-09-19 off-season verdict lives in SKIS_PROBE
// (probed live, /tmp only, never at runtime); the layer ships
// honestly empty (DATEX SRTI pattern) with the in-season mechanism
// proven by fixture. No secrets.

import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  SKIS_HOOK,
  SKIS_LAYER_IDS,
  SKIS_PROBE,
  SKIS_RADIUS_M,
  isSkisLayerId,
  skisBonusSpecFor,
  skisNearby,
} from "./layers_p4_skis";

describe("skis registry", () => {
  it("registers the honest off-season track layer", () => {
    expect(SKIS_LAYER_IDS).toEqual(["skis"]);
    expect(LAYERS.find((l) => l.id === "skis")).toBeTruthy();
  });

  it("wires the dormant dbands spec through the shared hooks (#807)", () => {
    expect(isSkisLayerId("skis")).toBe(true);
    expect(isSkisLayerId("fixit")).toBe(false);
    expect(skisBonusSpecFor("skis")).toEqual({ kind: "dbands", radiusM: 1000, edges: [[1000, 75]] });
    expect(bonusSpecFor("skis")).toEqual({ kind: "dbands", radiusM: 1000, edges: [[1000, 75]] });
    expect(radiusKmFor("skis")).toBe(1.0);
    expect(SKIS_RADIUS_M).toBe(1000);
  });

  it("pins the live off-season verdict (never carried-over tracks)", () => {
    expect(SKIS_PROBE.date).toBe("2026-09-19");
    expect(SKIS_PROBE.season).toBe("off");
    expect(SKIS_PROBE.machineFeed).toBe(false);
    expect(SKIS_PROBE.quote).toContain("suusahooaeg");
  });

  it("explains the season in Estonian with zero markers", () => {
    const def = LAYERS.find((l) => l.id === "skis")!;
    expect(def.title).toContain("suusarajad");
    expect(def.badLabel).toContain("hooaeg");
    expect(def.source).toContain("EI OLE");
    expect(def.paramIds).toEqual([]);
    expect(def.fallbackPoints).toEqual([]);
    expect(def.paramLabel).toBe("P4-skis");
  });

  it("serves an Estonian legend and a registry-unique color", () => {
    expect(overlayLegendFor("skis")).toContain("EI OLE");
    expect(overlayColorFor("skis")).toMatch(/^#[0-9a-f]{6}$/);
    expect(overlayColorFor("skis")).not.toBe(overlayColorFor("paaste"));
  });

  it("keeps the hook marker greppable", () => {
    expect(SKIS_HOOK).toContain("SKIS-HOOK (#692)");
  });
});

describe("skis kernel (dormant off-season)", () => {
  it("reads empty as no entries, never faked snow", () => {
    expect(skisNearby(59.4711, 24.8711, [])).toEqual([]);
  });

  it("finds groomed entries nearest-first inside 1 km (fixture)", () => {
    const pts = [
      { lat: 59.4711, lon: 24.8711 },
      { lat: 59.472, lon: 24.873 },
    ];
    const near = skisNearby(59.4711, 24.8711, pts);
    expect(near).toHaveLength(2);
    expect(near[0].distM).toBeLessThanOrEqual(near[1].distM);
    // Far away (city centre) stays empty on track fixtures.
    expect(skisNearby(59.437, 24.745, pts)).toEqual([]);
  });
});
