// Hermetic tests for the micromobility GBFS layer (issue #688).
// No network: the 2026-09-19 probe verdict lives in GBFS_PROBE
// (probed live, /tmp only, never at runtime); the layer ships
// honestly empty (paaste #493 precedent) until a keyless feed
// verifies. Fixtures fully synthetic where marked. No secrets.

import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  GBFS_FAR_M,
  GBFS_HOOK,
  GBFS_LAYER_IDS,
  GBFS_PROBE,
  gbfsBandForCount,
  gbfsBonusSpecFor,
  gbfsCoveredAt,
  gbfsNearby,
  isGbfsLayerId,
} from "./layers_p4_gbfs";

describe("gbfs registry", () => {
  it("registers the honest-empty bike-share layer", () => {
    expect(GBFS_LAYER_IDS).toEqual(["gbfs"]);
    expect(LAYERS.find((l) => l.id === "gbfs")).toBeTruthy();
  });

  it("wires the bands spec through the shared hooks", () => {
    expect(isGbfsLayerId("gbfs")).toBe(true);
    expect(isGbfsLayerId("fixit")).toBe(false);
    expect(gbfsBonusSpecFor("gbfs")).toEqual({
      kind: "bands",
      radiusM: GBFS_FAR_M,
      one: 60,
      twoThree: 70,
      fourPlus: 80,
    });
    expect(bonusSpecFor("gbfs")).toEqual(gbfsBonusSpecFor("gbfs"));
    expect(radiusKmFor("gbfs")).toBe(0.5);
  });

  it("pins the negative probe verdict (no keyless feed, never faked)", () => {
    expect(GBFS_PROBE.date).toBe("2026-09-19");
    expect(GBFS_PROBE.registryEstonianSystems).toBe(0);
    expect(GBFS_PROBE.tartuBundleGbfsRefs).toBe(0);
    expect(GBFS_PROBE.dottTallinn).toBe("ERR_REGION_NOT_FOUND");
    expect(GBFS_PROBE.dottTartu).toBe("ERR_REGION_NOT_FOUND");
    expect(GBFS_PROBE.tartuMapApi).toBe("Wrong request!");
  });

  it("explains the gap in Estonian with zero markers", () => {
    const def = LAYERS.find((l) => l.id === "gbfs")!;
    expect(def.title.length).toBeGreaterThan(0);
    expect(def.goodLabel.length).toBeGreaterThan(0);
    expect(def.badLabel).toContain("EI OLE");
    expect(def.source).toContain("EI OLE");
    expect(def.paramIds).toEqual([]);
    expect(def.fallbackPoints).toEqual([]);
    expect(def.paramLabel).toBe("P4-GBFS");
  });

  it("serves an Estonian legend and a registry-unique color", () => {
    expect(overlayLegendFor("gbfs")).toContain("EI OLE");
    expect(overlayColorFor("gbfs")).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("keeps the hook marker greppable", () => {
    expect(GBFS_HOOK).toContain("GBFS-HOOK (#688)");
  });
});

describe("gbfs kernel (dormant until a feed verifies)", () => {
  const raekoja = { lat: 58.3806, lon: 26.7225 };

  it("reads empty as unknown, never zero", () => {
    expect(gbfsBandForCount(0)).toBeNull();
    expect(gbfsCoveredAt(raekoja.lat, raekoja.lon, [])).toBeNull();
  });

  it("grades station counts when a feed lands", () => {
    expect(gbfsBandForCount(1)).toBe(60);
    expect(gbfsBandForCount(3)).toBe(70);
    expect(gbfsBandForCount(9)).toBe(80);
    const pts = [
      raekoja,
      { lat: 58.3798, lon: 26.7265 }, // ~245 m
      { lat: 58.3812, lon: 26.7192 }, // ~200 m
    ];
    expect(gbfsNearby(raekoja.lat, raekoja.lon, pts)).toHaveLength(3);
    expect(gbfsCoveredAt(raekoja.lat, raekoja.lon, pts)).toBe(70);
    // Far away (Tallinn) stays unknown on Tartu fixtures.
    expect(gbfsCoveredAt(59.437, 24.745, pts)).toBeNull();
  });
});
