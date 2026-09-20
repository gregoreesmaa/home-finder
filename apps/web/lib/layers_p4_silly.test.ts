// Hermetic tests for the trivial & silly amenity bundle (issue #711).
// No network: the held-extract counts live in SILLY_PROBE (probed
// 2026-09-19 from /private/tmp/estonia-260914.osm.pbf, never at
// runtime); fallbackPoints below are the real mapped points from that
// probe, fixtures fully synthetic where marked. No secrets.

import { describe, expect, it } from "vitest";
import {
  LAYERS,
  bonusSpecFor,
  radiusKmFor,
} from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  SILLY_HOOK,
  SILLY_LAYER_IDS,
  SILLY_PROBE,
  SILLY_VINTAGE,
  isSillyLayerId,
  sillyBonusSpecFor,
  sillyDemoStatus,
  sillyNearby,
  sillyPointsIn,
  sillySnapshotStatus,
} from "./layers_p4_silly";

describe("silly bundle registry", () => {
  it("registers every non-empty checkbox layer", async () => {
    const m = await import("./layers_p4_silly");
    expect(m.SILLY_LAYER_IDS.length).toBeGreaterThan(0);
    for (const id of m.SILLY_LAYER_IDS) {
      expect(LAYERS.find((l) => l.id === id)).toBeTruthy();
    }
  });

  it("ships twelve scored layers (dbands amenity + quiet nuisance, #807)", () => {
    expect(SILLY_LAYER_IDS).toHaveLength(12);
    for (const id of SILLY_LAYER_IDS) {
      expect(isSillyLayerId(id)).toBe(true);
      expect(sillyBonusSpecFor(id)).toEqual(bonusSpecFor(id));
      expect(["dbands", "quiet"]).toContain((sillyBonusSpecFor(id) as { kind: string }).kind);
      expect(radiusKmFor(id)).toBe(0.5);
    }
    expect(isSillyLayerId("fixit")).toBe(false);
  });

  it("drops the empty/unbuildable checkboxes (never fake points)", () => {
    const ids = SILLY_LAYER_IDS as string[];
    expect(ids).not.toContain("pingid"); // no smart-bench tag in OSM
    expect(ids).not.toContain("suve_hairikud"); // mosquitoes/STR sourceless
    expect(LAYERS.find((l) => l.id === ("pingid" as typeof l.id))).toBeFalsy();
  });

  it("locks the held-extract Tallinn counts (non-empty verdicts)", () => {
    expect(SILLY_PROBE.date).toBe("2026-09-19");
    for (const id of SILLY_LAYER_IDS) {
      expect(SILLY_PROBE[id]).toBeGreaterThan(0);
    }
    // Spot-check the probe table against the header verdicts.
    expect(SILLY_PROBE.manguvaljakud).toBe(1874);
    expect(SILLY_PROBE.wc).toBe(205);
    expect(SILLY_PROBE.aed).toBe(11);
  });

  it("explains every silly layer in Estonian with real demo points", () => {
    for (const id of SILLY_LAYER_IDS) {
      const def = LAYERS.find((l) => l.id === id)!;
      expect(def.title.length).toBeGreaterThan(0);
      expect(def.goodLabel.length).toBeGreaterThan(0);
      expect(def.badLabel.length).toBeGreaterThan(0);
      expect(def.source).toContain("väljavõte");
      expect(def.paramIds).toEqual([]);
      // Real mapped points in Tallinn (never invented, never empty).
      expect(def.fallbackPoints.length).toBeGreaterThan(0);
      for (const p of def.fallbackPoints) {
        expect(Number.isFinite(p.lat)).toBe(true);
        expect(Number.isFinite(p.lon)).toBe(true);
        expect(p.lat).toBeGreaterThan(59.3);
        expect(p.lat).toBeLessThan(59.6);
        expect(p.lon).toBeGreaterThan(24.4);
        expect(p.lon).toBeLessThan(25.1);
      }
      // Legend + distinct marker color (registry-wide uniqueness holds).
      expect(overlayLegendFor(id).length).toBeGreaterThan(0);
      expect(overlayColorFor(id)).toMatch(/^#[0-9a-f]{6}$/);
    }
    const colors = new Set(SILLY_LAYER_IDS.map(overlayColorFor));
    expect(colors.size).toBe(SILLY_LAYER_IDS.length);
  });

  it("keeps the wiring contract greppable", () => {
    expect(SILLY_HOOK).toContain("SILLY-HOOK (#711)");
  });

  it("labels demo-by-design as sample, never as failure (#774)", () => {
    for (const id of SILLY_LAYER_IDS) {
      const status = sillyDemoStatus(
        LAYERS.find((l) => l.id === id)!.fallbackPoints.length,
      );
      expect(status).toContain("DEMO-näidis");
      expect(status).toContain("mitte loendus");
      expect(status).not.toContain("ebaõnnestus");
    }
    expect(sillyDemoStatus(2)).toBe(
      "DEMO-näidis (näidispunktid, mitte loendus) · 2 punkti",
    );
  });

  it("names the served extract vintage, never live state (#774)", () => {
    expect(SILLY_VINTAGE).toBe("2026-09-14");
    expect(sillySnapshotStatus(1874)).toBe(
      "OSM väljavõte (Eesti 2026-09-14, hinnang) · 1874 punkti",
    );
    expect(sillySnapshotStatus(1874)).not.toContain("hetkeseis");
    expect(sillySnapshotStatus(1874)).not.toContain("hetktõmmis");
  });

  it("serves one layer slice from the shared sidecar (#774)", () => {
    const pts = [
      { lat: 59.44, lon: 24.75, slice: "wc" },
      { lat: 59.45, lon: 24.76, slice: "vesi" },
    ];
    const bbox = { minlon: 24.5, minlat: 59.35, maxlon: 25.0, maxlat: 59.5 };
    expect(sillyPointsIn(pts, bbox, "wc")).toEqual([{ lat: 59.44, lon: 24.75 }]);
    expect(sillyPointsIn(pts, bbox)).toHaveLength(2);
  });
});

describe("silly point helpers (synthetic fixtures)", () => {
  const PTS = [
    { lat: 59.4374, lon: 24.7454 },
    { lat: 59.4375, lon: 24.7455 },
    { lat: 59.45, lon: 24.76 },
  ];
  const BBOX = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

  it("sillyNearby orders by distance within the doorstep radius", () => {
    const near = sillyNearby(59.4374, 24.7454, PTS);
    expect(near.length).toBe(2);
    expect(near[0].distM).toBeLessThanOrEqual(near[1].distM);
    expect(sillyNearby(58.0, 22.0, PTS)).toEqual([]);
  });

  it("sillyPointsIn keeps finite bbox points in wire shape", () => {
    const pts = sillyPointsIn(
      [...PTS, { lat: NaN, lon: 24.7 }, { lat: 58.0, lon: 22.0 }],
      BBOX,
    );
    expect(pts).toHaveLength(3);
    expect(Object.keys(pts[0]).sort()).toEqual(["lat", "lon"]);
  });
});
