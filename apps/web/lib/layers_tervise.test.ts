// Hermetic tests for the Terviseamet bathing-water overlay (issue #494).
// Synthetic fixtures below are FULLY SYNTHETIC (clearly labelled); the
// REAL-DATA pins read the committed TERVISE_POINTS extract (built
// offline by scripts/build/batch_tervise.py, vintage 2026-09-14 —
// fixtures only, never live). No network in tests.

import { describe, expect, it } from "vitest";
import {
  LAYERS,
  bonusSpecFor,
  fetchWindow,
  layerParamTag,
  radiusKmFor,
  toPoint,
} from "./layers";
import { buildScoredField } from "./distanceField";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  TERVISE_LAYER_IDS,
  TERVISE_LAYERS,
  TERVISE_PARAM_LABEL,
  TERVISE_POINTS,
  TERVISE_PROBE,
  TERVISE_RADIUS_M,
  isTerviseLayerId,
  terviseBandAt,
  terviseBonusSpecFor,
  tervisePointsIn,
  type TervisePoint,
} from "./layers_tervise";

/** Synthetic Tallinn backyard + synthetic monitored shores. */
const HOME = { lat: 59.4374, lon: 24.7454 };
const M_PER_DEG_LAT = 111194.9;
function shoreNorthOf(m: number, q?: number): TervisePoint {
  return { lat: HOME.lat + m / M_PER_DEG_LAT, lon: HOME.lon, q };
}

describe("tervise quality kernel (builder parity)", () => {
  it("pins the radius to the batch_tervise harvest (drift = bug)", () => {
    // Byte parity with TERVISE_RADIUS_M in scripts/build/batch_tervise.py
    // consumers: nearest site inside 1 km rules, quality bands ride q.
    expect(TERVISE_RADIUS_M).toBe(1000);
    expect(TERVISE_PROBE).toEqual({
      date: "2026-09-14",
      sitesXmlBytes: 313862,
      sites: 211,
      samples2026: 758,
      samples2025: 793,
      plotted: 205,
      droppedNoCoord: 6,
    });
  });

  it("scores the nearest synthetic shore's band, unknown stays null (never zero)", () => {
    expect(terviseBandAt(HOME.lat, HOME.lon, [])).toBeNull();
    expect(terviseBandAt(HOME.lat, HOME.lon, [shoreNorthOf(100, 80)])).toBe(80);
    expect(terviseBandAt(HOME.lat, HOME.lon, [shoreNorthOf(100, 30)])).toBe(30);
    // Nearest rules: a farther very-good shore never outranks the
    // nearest poor one (no averaging, no smoothing).
    expect(
      terviseBandAt(HOME.lat, HOME.lon, [shoreNorthOf(900, 80), shoreNorthOf(100, 30)]),
    ).toBe(30);
    expect(
      terviseBandAt(HOME.lat, HOME.lon, [shoreNorthOf(100, 80), shoreNorthOf(900, 30)]),
    ).toBe(80);
  });

  it("stays null where the nearest shore's quality is NULL (never a faked middle)", () => {
    expect(terviseBandAt(HOME.lat, HOME.lon, [shoreNorthOf(100)])).toBeNull();
    // ...even when a farther shore carries a band (nearest rules).
    expect(
      terviseBandAt(HOME.lat, HOME.lon, [shoreNorthOf(100), shoreNorthOf(200, 80)]),
    ).toBeNull();
  });

  it("applies the HARD 1 km cutoff (a 1.2 km shore is not a shore)", () => {
    expect(terviseBandAt(HOME.lat, HOME.lon, [shoreNorthOf(900, 80)])).toBe(80);
    expect(terviseBandAt(HOME.lat, HOME.lon, [shoreNorthOf(1200, 80)])).toBeNull();
  });

  it("skips coordless junk instead of scoring absence", () => {
    const junk = [
      { lat: NaN, lon: HOME.lon, q: 80 },
      { lat: HOME.lat, lon: Infinity, q: 80 },
    ] as unknown as TervisePoint[];
    expect(terviseBandAt(HOME.lat, HOME.lon, junk)).toBeNull();
    expect(terviseBandAt(HOME.lat, HOME.lon, [...junk, shoreNorthOf(100, 80)])).toBe(80);
  });
});

describe("tervise registry wiring", () => {
  it("registers one layer with no parameters3 id + the P4-024 slice label", () => {
    expect(TERVISE_LAYER_IDS).toEqual(["tervise"]);
    expect(TERVISE_LAYERS.map((l) => l.id)).toEqual(["tervise"]);
    expect(isTerviseLayerId("tervise")).toBe(true);
    expect(isTerviseLayerId("parks")).toBe(false);
    const def = LAYERS.find((l) => l.id === "tervise");
    expect(def?.paramIds).toEqual([]);
    expect(def?.paramLabel).toBe(TERVISE_PARAM_LABEL);
    expect(TERVISE_PARAM_LABEL).toBe("P4-024");
  });

  it("tags the layer button (P4-024), leaving parameters3 tags untouched", () => {
    const def = LAYERS.find((l) => l.id === "tervise");
    expect(layerParamTag(def!)).toBe("(P4-024)");
    expect(layerParamTag(LAYERS.find((l) => l.id === "parks")!)).toBe("(p19)");
  });

  it("locks the qbands spec + radius (map kernel == builder kernel)", () => {
    expect(terviseBonusSpecFor("tervise")).toEqual({ kind: "qbands", radiusM: 1000 });
    expect(bonusSpecFor("tervise")).toEqual(terviseBonusSpecFor("tervise"));
    expect(radiusKmFor("tervise")).toBe(1.0);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    const def = LAYERS.find((l) => l.id === "tervise")!;
    for (const f of [def.title, def.goodLabel, def.badLabel, def.source]) {
      expect(f.length).toBeGreaterThan(0);
    }
    expect(def.fallbackPoints.length).toBeGreaterThan(0);
    expect(def.source).toContain("hinnang");
  });

  it("gives tervise a legend naming the bands + the missing P4-017 leg", () => {
    const legend = overlayLegendFor("tervise");
    expect(legend.length).toBeGreaterThan(10);
    expect(legend).toContain("1 km");
    expect(legend).toContain("80");
    expect(legend).toContain("30");
  });

  it("paints tervise markers lagoon emerald", () => {
    expect(overlayColorFor("tervise")).toBe("#34d399");
  });

  it("skips the raster window fetch (no master exists by decision)", async () => {
    const boom = () => {
      throw new Error("qbands layers must never fetch a window");
    };
    await expect(
      fetchWindow("tervise", { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 }, boom as unknown as typeof fetch),
    ).resolves.toBeNull();
  });

  it("passes quality through toPoint, dropping junk bands (never a faked middle)", () => {
    expect(toPoint({ lat: 59.47, lon: 24.83, q: 80 })).toEqual({ lat: 59.47, lon: 24.83, q: 80 });
    expect(toPoint({ lat: 59.47, lon: 24.83 })).toEqual({ lat: 59.47, lon: 24.83 });
    expect(toPoint({ lat: 59.47, lon: 24.83, q: NaN })).toEqual({ lat: 59.47, lon: 24.83 });
    expect(toPoint({ lat: 59.47, lon: 24.83, q: 101 })).toEqual({ lat: 59.47, lon: 24.83 });
    expect(toPoint({ lat: 59.47, lon: 24.83, q: "80" })).toEqual({ lat: 59.47, lon: 24.83 });
  });

  it("clips extract points to the view bbox (route contract)", () => {
    const pts = [
      { lat: 59.47215, lon: 24.830954, q: 80 },
      { lat: 58.0, lon: 24.0, q: 80 },
    ];
    const inTallinn = tervisePointsIn(pts, { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 });
    expect(inTallinn).toEqual([{ lat: 59.47215, lon: 24.830954, q: 80 }]);
  });
});

describe("tervise quality field (client render path)", () => {
  const bbox = { minlon: 24.73, minlat: 59.43, maxlon: 24.76, maxlat: 59.445 };
  const spec = terviseBonusSpecFor("tervise");
  if (spec.kind !== "qbands") throw new Error("tervise spec must be qbands");

  it("renders the shore band under the point, unknown far away", () => {
    const pts = [{ lon: 24.7454, lat: 59.4375, q: 80 }];
    const field = buildScoredField(pts, bbox, 24, 12, 1.0, spec);
    expect(field.direct).not.toBeNull();
    const vals = [...field.direct!].filter((v) => !Number.isNaN(v));
    expect(vals.length).toBeGreaterThan(0);
    for (const v of vals) expect(v).toBe(80);
    // Far corner cells (>1 km out) stay unknown, never zero.
    expect(field.direct![0]).toBeNaN();
  });

  it("renders the nearest band where synthetic shores overlap", () => {
    const shores = [
      { lon: 24.7454, lat: 59.4375, q: 30 },
      { lon: 24.7454, lat: 59.4395, q: 80 },
    ];
    const field = buildScoredField(shores, bbox, 24, 12, 1.0, spec);
    const vals = [...field.direct!].filter((v) => !Number.isNaN(v));
    expect(vals.length).toBeGreaterThan(0);
    for (const v of vals) expect([30, 80]).toContain(v);
  });

  it("renders all-unknown over a quality-NULL point (never a faked middle)", () => {
    const pts = [{ lon: 24.7454, lat: 59.4375 }];
    const field = buildScoredField(pts, bbox, 8, 8, 1.0, spec);
    expect(field.direct).not.toBeNull();
    for (const v of field.direct!) expect(v).toBeNaN();
  });

  it("renders all-unknown when nothing loaded (never a faked field)", () => {
    const field = buildScoredField([], bbox, 8, 8, 1.0, spec);
    expect(field.direct).not.toBeNull();
    for (const v of field.direct!) expect(v).toBeNaN();
  });
});

describe("tervise committed extract (real-data pins, vintage 2026-09-14)", () => {
  it("carries 205 projected sites (211 register rows minus 6 coordless)", () => {
    expect(TERVISE_POINTS).toHaveLength(205);
  });

  it("lands Pirita / Stroomi / Kakumae on their beaches", () => {
    const near = (lat: number, lon: number) =>
      TERVISE_POINTS.some((p) => Math.hypot(p.lat - lat, p.lon - lon) < 0.002);
    expect(near(59.4722, 24.831)).toBe(true); // Pirita rand
    expect(near(59.4425, 24.6839)).toBe(true); // Stroomi rand
    expect(near(59.4483, 24.5744)).toBe(true); // Kakumae rand
  });

  it("scores Pirita + Stroomi 80 (vaga hea, dated passing samples)", () => {
    expect(terviseBandAt(59.4722, 24.831, TERVISE_POINTS)).toBe(80);
    expect(terviseBandAt(59.4425, 24.6839, TERVISE_POINTS)).toBe(80);
  });

  it("keeps every band in the coarse ladder and every point inside Estonia", () => {
    for (const p of TERVISE_POINTS) {
      if (p.q !== undefined) expect([30, 45, 60, 70, 80]).toContain(p.q);
      expect(p.lat).toBeGreaterThan(57.4);
      expect(p.lat).toBeLessThan(60.1);
      expect(p.lon).toBeGreaterThan(21.5);
      expect(p.lon).toBeLessThan(28.3);
    }
  });
});
