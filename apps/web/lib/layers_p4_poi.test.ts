// Hermetic tests for the huvipunktid long-tail overlays (issue #612).
// Synthetic fixtures below are FULLY SYNTHETIC (clearly labelled);
// the REAL-DATA pins read the deployed snapshot sidecar shape only
// through poiPointsIn fixtures (points live outside the repo in
// ~/hf-data — fixtures only, never live). No network in tests.

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
  POI_EDGES_M,
  POI_LAYERS,
  POI_PROBE,
  POI_RADIUS_M,
  isPoiLayerId,
  poiBandAt,
  poiBonusSpecFor,
  poiNearby,
  poiPointsIn,
  poiSliceFor,
  type PoiLayerId,
  type PoiPoint,
  type PoiSlice,
} from "./layers_p4_poi";

/** Synthetic Tallinn backyard + synthetic sliced POIs. */
const HOME = { lat: 59.4374, lon: 24.7454 };
const M_PER_DEG_LAT = 111194.9;
function poiNorthOf(m: number, slice: PoiSlice): PoiPoint {
  return { lat: HOME.lat + m / M_PER_DEG_LAT, lon: HOME.lon, slice };
}

describe("poi walk kernel (scorer parity)", () => {
  it("pins the band table to _score_dist (drift = bug)", () => {
    expect(POI_EDGES_M).toEqual([
      [300, 85],
      [600, 70],
      [1000, 55],
    ]);
    expect(POI_RADIUS_M).toBe(1000);
    expect(poiBandAt(100)).toBe(85);
    expect(poiBandAt(300)).toBe(85);
    expect(poiBandAt(500)).toBe(70);
    expect(poiBandAt(900)).toBe(55);
    expect(poiBandAt(1001)).toBeNull();
  });

  it("scores the nearest sliced POI, other slices ignored", () => {
    const points = [poiNorthOf(200, "library"), poiNorthOf(50, "post")];
    const near = poiNearby(HOME.lat, HOME.lon, points, "library");
    expect(near).toHaveLength(1);
    expect(poiBandAt(near[0].distM)).toBe(85);
    expect(poiNearby(HOME.lat, HOME.lon, points, "pharmacy")).toEqual([]);
  });

  it("stays empty beyond the HARD 1 km cutoff (a 1.2 km POI is not a POI)", () => {
    const points = [poiNorthOf(1200, "library")];
    expect(poiNearby(HOME.lat, HOME.lon, points, "library")).toEqual([]);
  });

  it("skips coordless junk instead of scoring absence", () => {
    const points = [{ lat: NaN, lon: NaN, slice: "library" } as PoiPoint];
    expect(poiNearby(HOME.lat, HOME.lon, points, "library")).toEqual([]);
  });

  it("maps layer ids to slices", () => {
    expect(poiSliceFor("poi_library")).toBe("library");
    expect(poiSliceFor("poi_post")).toBe("post");
    expect(poiSliceFor("poi_pharmacy")).toBe("pharmacy");
    expect(isPoiLayerId("poi_library")).toBe(true);
    expect(isPoiLayerId("ohuseire")).toBe(false);
  });
});

describe("poi registry wiring", () => {
  it("registers three slices with no parameters3 id + per-slice P4-poi labels", () => {
    for (const layer of POI_LAYERS) {
      expect(layer.paramIds).toEqual([]);
    }
    expect(LAYERS.find((l) => l.id === "poi_library")?.paramLabel).toBe("P4-poi raamatukogu");
    expect(LAYERS.find((l) => l.id === "poi_post")?.paramLabel).toBe("P4-poi post");
    expect(LAYERS.find((l) => l.id === "poi_pharmacy")?.paramLabel).toBe("P4-poi apteek");
  });

  it("tags the layer buttons (P4-poi *), leaving parameters3 tags untouched", () => {
    expect(layerParamTag(LAYERS.find((l) => l.id === "poi_post")!)).toBe("(P4-poi post)");
    expect(layerParamTag(LAYERS.find((l) => l.id === "parks")!)).toBe("(p19)");
  });

  it("locks the dbands spec + edges (map kernel == scorer kernel)", () => {
    for (const id of ["poi_library", "poi_post", "poi_pharmacy"] as PoiLayerId[]) {
      expect(bonusSpecFor(id)).toEqual({
        kind: "dbands",
        radiusM: 1000,
        edges: [
          [300, 85],
          [600, 70],
          [1000, 55],
        ],
      });
    }
    expect(poiBonusSpecFor("poi_library").kind).toBe("dbands");
    expect(radiusKmFor("poi_post")).toBe(1.0);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const id of ["poi_library", "poi_post", "poi_pharmacy"] as PoiLayerId[]) {
      const def = LAYERS.find((l) => l.id === id)!;
      for (const f of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(f.length).toBeGreaterThan(0);
      }
      expect(def.fallbackPoints.length).toBeGreaterThan(0);
      expect(def.source).toContain("huvipunktid");
      expect(def.source).toContain("vahekiht");
    }
  });

  it("gives poi legends naming the bands + the register counts", () => {
    const legend = overlayLegendFor("poi_library");
    expect(legend.length).toBeGreaterThan(10);
    expect(legend).toContain("1 km");
    expect(legend).toContain("85");
    expect(legend).toContain("124");
    expect(overlayLegendFor("poi_post")).toContain("pakiautomaat");
    expect(overlayLegendFor("poi_pharmacy")).toContain("187");
  });

  it("paints poi markers book-purple + mailbox-amber + cross-green", () => {
    expect(overlayColorFor("poi_library")).toBe("#d8b4fe");
    expect(overlayColorFor("poi_post")).toBe("#fde68a");
    expect(overlayColorFor("poi_pharmacy")).toBe("#bbf7d0");
  });

  it("skips the raster window fetch (no master exists by decision)", async () => {
    const boom = () => {
      throw new Error("dbands layers must never fetch a window");
    };
    for (const id of ["poi_library", "poi_post", "poi_pharmacy"] as PoiLayerId[]) {
      await expect(
        fetchWindow(id, { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 }, boom as unknown as typeof fetch),
      ).resolves.toBeNull();
    }
  });

  it("clips sidecar points to the slice + view bbox (route contract)", () => {
    const points: PoiPoint[] = [
      { lat: 59.44, lon: 24.75, slice: "library" },
      { lat: 59.44, lon: 24.75, slice: "post" },
      { lat: 59.0, lon: 24.75, slice: "library" },
    ];
    const bbox = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };
    expect(poiPointsIn(points, "library", bbox)).toEqual([{ lat: 59.44, lon: 24.75 }]);
    expect(poiPointsIn(points, "post", bbox)).toEqual([{ lat: 59.44, lon: 24.75 }]);
    expect(poiPointsIn(points, "pharmacy", bbox)).toEqual([]);
  });
});

describe("poi walk field (client render path)", () => {
  const bbox = { minlon: 24.73, minlat: 59.43, maxlon: 24.76, maxlat: 59.445 };
  const spec = poiBonusSpecFor("poi_library");
  if (spec.kind !== "dbands") throw new Error("poi spec must be dbands");

  it("renders the band under the point, unknown far away", () => {
    const pts = [{ lon: 24.7454, lat: 59.4375 }];
    const field = buildScoredField(pts, bbox, 24, 12, 1.0, spec);
    expect(field.direct).not.toBeNull();
    const vals = [...field.direct!].filter((v) => !Number.isNaN(v));
    expect(vals.length).toBeGreaterThan(0);
    // Walk rings: 85 at the doorstep, 70/55 further out — never zero.
    for (const v of vals) expect([85, 70, 55]).toContain(v);
    expect(vals).toContain(85);
    // Far corner cells (>1 km out) stay unknown, never zero.
    expect(field.direct![0]).toBeNaN();
  });

  it("renders all-unknown when nothing loaded (never a faked field)", () => {
    const field = buildScoredField([], bbox, 8, 8, 1.0, spec);
    expect(field.direct).not.toBeNull();
    for (const v of field.direct!) expect(v).toBeNaN();
  });
});

describe("poi harvest pins (probe 2026-09-16)", () => {
  it("pins the county tallies (builder parity — drift = bug)", () => {
    expect(POI_PROBE.libraryFeatures).toBe(124);
    expect(POI_PROBE.postFeatures).toBe(536);
    expect(POI_PROBE.pharmacyFeatures).toBe(187);
    expect(POI_PROBE.droppedNoCoord).toBe(0);
    expect(POI_PROBE.licence).toContain("ruumiandmete litsents");
  });
});
