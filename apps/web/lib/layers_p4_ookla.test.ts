// Hermetic tests for the P4-009 ookla overlay (issue #489). All tile
// fixtures below are FULLY SYNTHETIC (clearly labelled) — real observed
// values (2026-09-13: Kesklinn tile 176 Mbit/s down / 151 tests) appear
// only in docs/p4_ookla.md, never as ingested data. No network in tests.

import { describe, expect, it } from "vitest";
import {
  LAYERS,
  bonusSpecFor,
  fetchWindow,
  goodnessAt,
  layerParamTag,
  radiusKmFor,
} from "./layers";
import { buildScoredField, fieldResolution } from "./distanceField";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import { matchesContract } from "./server/snapshot";
import {
  OOKLA_BAND_EDGES,
  OOKLA_BANDS,
  OOKLA_HOOK,
  OOKLA_LAYERS,
  OOKLA_MIN_TESTS,
  OOKLA_PARAM_LABEL,
  OOKLA_QUARTER,
  OOKLA_RADIUS_M,
  isOoklaLayerId,
  ooklaBandForSpeed,
  ooklaBonusSpecFor,
  ooklaDirectField,
  ooklaTileAt,
  type OoklaPoint,
} from "./layers_p4_ookla";

/** Synthetic Tallinn home + synthetic tile centroids (true-haversine metres north). */
const HOME = { lat: 59.4374, lon: 24.7454 };
const M_PER_DEG_LAT = 111194.9;
function tileNorthOf(m: number, avgD: number, tests: number): OoklaPoint {
  return {
    lat: HOME.lat + m / M_PER_DEG_LAT,
    lon: HOME.lon,
    tags: { avg_d: String(avgD), tests: String(tests) },
  };
}

describe("ookla tileband kernel (scorer parity)", () => {
  it("pins the radius + guards + bands to the dims_p4_ookla scorer (drift = bug)", () => {
    // Byte parity with OOKLA_RADIUS_M / OOKLA_MIN_TESTS / _SPEED_BANDS
    // / _band_d in services/scoring/dims_p4_ookla.py: nearest
    // qualifying tile (avg_d present, >= 5 tests) <= 1000 m ->
    // <30 Mbit/s 35, <100 55, <300 75, else capped 85.
    expect(OOKLA_RADIUS_M).toBe(1000);
    expect(OOKLA_MIN_TESTS).toBe(5);
    expect([...OOKLA_BAND_EDGES]).toEqual([30000, 100000, 300000]);
    expect({ ...OOKLA_BANDS }).toEqual({ weak: 35, mid: 55, strong: 75, top: 85 });
    expect(OOKLA_QUARTER).toBe("2026-Q1");
  });

  it("maps download averages to bands at the EU-tier edges", () => {
    expect(ooklaBandForSpeed(0)).toBe(35);
    expect(ooklaBandForSpeed(29999)).toBe(35);
    expect(ooklaBandForSpeed(30000)).toBe(55);
    expect(ooklaBandForSpeed(99999)).toBe(55);
    expect(ooklaBandForSpeed(100000)).toBe(75);
    expect(ooklaBandForSpeed(299999)).toBe(75);
    expect(ooklaBandForSpeed(300000)).toBe(85);
    expect(ooklaBandForSpeed(220187)).toBe(75);
    expect(ooklaBandForSpeed(381664)).toBe(85);
  });

  it("stays null for unmeasured averages (never a band off nothing)", () => {
    expect(ooklaBandForSpeed(NaN)).toBeNull();
    expect(ooklaBandForSpeed(Infinity)).toBeNull();
  });

  it("scores the nearest qualifying synthetic tile (hinnang, never EI OLE territory)", () => {
    const join = ooklaTileAt(HOME.lat, HOME.lon, [tileNorthOf(100, 154425, 151)]);
    expect(join?.band).toBe(75);
    expect(join?.avgD).toBe(154425);
    expect(join?.tests).toBe(151);
  });

  it("prefers the nearer tile even when the farther one is faster (no smoothing)", () => {
    const tiles = [tileNorthOf(800, 381664, 40), tileNorthOf(100, 92624, 36)];
    expect(ooklaTileAt(HOME.lat, HOME.lon, tiles)?.band).toBe(55);
  });

  it("skips thin tiles (< 5 tests) and speed-less tiles instead of scoring them", () => {
    const thin = tileNorthOf(100, 381664, 4);
    expect(ooklaTileAt(HOME.lat, HOME.lon, [thin])).toBeNull();
    const noSpeed: OoklaPoint = {
      lat: HOME.lat,
      lon: HOME.lon,
      tags: { tests: "151" },
    };
    expect(ooklaTileAt(HOME.lat, HOME.lon, [noSpeed])).toBeNull();
    // A qualifying neighbour still joins past the thin tile.
    expect(ooklaTileAt(HOME.lat, HOME.lon, [thin, tileNorthOf(200, 92624, 36)])?.band).toBe(55);
  });

  it("applies the HARD 1 km cutoff (a 1.5 km tile is not a tile)", () => {
    expect(ooklaTileAt(HOME.lat, HOME.lon, [tileNorthOf(900, 154425, 36)])?.band).toBe(75);
    expect(ooklaTileAt(HOME.lat, HOME.lon, [tileNorthOf(1500, 154425, 36)])).toBeNull();
  });

  it("stays null with no tiles (scorer NULL: hinnang + EI OLE, never a faked score)", () => {
    expect(ooklaTileAt(HOME.lat, HOME.lon, [])).toBeNull();
  });

  it("skips coordless junk instead of scoring absence", () => {
    const junk = [
      { lat: NaN, lon: HOME.lon, tags: { avg_d: "154425", tests: "36" } },
      { lat: HOME.lat, lon: Infinity, tags: { avg_d: "154425", tests: "36" } },
    ] as unknown as OoklaPoint[];
    expect(ooklaTileAt(HOME.lat, HOME.lon, junk)).toBeNull();
    expect(ooklaTileAt(HOME.lat, HOME.lon, [...junk, tileNorthOf(100, 154425, 36)])?.band).toBe(75);
  });
});

describe("ookla registry wiring", () => {
  it("registers two layers with no parameters3 id + the P4-009 slice label", () => {
    expect(OOKLA_LAYERS.map((l) => l.id)).toEqual(["ookla_fixed", "ookla_mobile"]);
    expect(isOoklaLayerId("ookla_fixed")).toBe(true);
    expect(isOoklaLayerId("ookla_mobile")).toBe(true);
    expect(isOoklaLayerId("parks")).toBe(false);
    expect(isOoklaLayerId("senscom")).toBe(false);
    for (const id of ["ookla_fixed", "ookla_mobile"] as const) {
      const def = LAYERS.find((l) => l.id === id);
      expect(def?.paramIds).toEqual([]);
      expect(def?.paramLabel).toBe(OOKLA_PARAM_LABEL);
    }
    expect(OOKLA_PARAM_LABEL).toBe("P4-009");
    // parameters3 p9 is an inspection-group fact (documented no-map):
    // the overlays must never claim it.
    for (const id of ["ookla_fixed", "ookla_mobile"] as const) {
      expect(LAYERS.find((l) => l.id === id)?.paramIds).not.toContain(9);
    }
  });

  it("tags the layer buttons (P4-009), leaving parameters3 tags untouched", () => {
    expect(layerParamTag(LAYERS.find((l) => l.id === "ookla_fixed")!)).toBe("(P4-009)");
    expect(layerParamTag(LAYERS.find((l) => l.id === "ookla_mobile")!)).toBe("(P4-009)");
    expect(layerParamTag(LAYERS.find((l) => l.id === "parks")!)).toBe("(p19)");
  });

  it("locks the tileband specs + radii (map kernel == scorer kernel)", () => {
    for (const id of ["ookla_fixed", "ookla_mobile"] as const) {
      expect(ooklaBonusSpecFor(id)).toEqual({
        kind: "tileband",
        radiusM: 1000,
        minTests: 5,
        weak: 35,
        mid: 55,
        strong: 75,
        top: 85,
      });
      expect(bonusSpecFor(id)).toEqual(ooklaBonusSpecFor(id));
      expect(radiusKmFor(id)).toBe(1.0);
    }
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const id of ["ookla_fixed", "ookla_mobile"] as const) {
      const def = LAYERS.find((l) => l.id === id)!;
      for (const f of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(f.length).toBeGreaterThan(0);
      }
      expect(def.fallbackPoints.length).toBeGreaterThan(0);
      expect(def.source).toContain("hinnang");
      expect(def.source).toContain("2026-Q1");
    }
  });

  it("gives both ookla layers a legend naming the bands + the unmeasured truth", () => {
    for (const id of ["ookla_fixed", "ookla_mobile"] as const) {
      const legend = overlayLegendFor(id);
      expect(legend.length).toBeGreaterThan(10);
      expect(legend).toContain("1 km");
      expect(legend).toContain("35");
      expect(legend).toContain("55");
      expect(legend).toContain("75");
      expect(legend).toContain("85");
      expect(legend).toContain("katkestused teadmata");
    }
    expect(overlayLegendFor("ookla_fixed")).toContain("fikseeritud");
    expect(overlayLegendFor("ookla_mobile")).toContain("mobiilsed");
  });

  it("paints ookla markers wired blue vs airwaves pink (distinct pair)", () => {
    expect(overlayColorFor("ookla_fixed")).toBe("#172554");
    expect(overlayColorFor("ookla_mobile")).toBe("#be185d");
  });

  it("keeps the wiring contract greppable (hook marker)", () => {
    expect(OOKLA_HOOK).toContain("OOKLA-HOOK (#489)");
  });

  it("skips the raster window fetch (no master exists by decision)", async () => {
    const boom = () => {
      throw new Error("tileband layers must never fetch a window");
    };
    for (const id of ["ookla_fixed", "ookla_mobile"] as const) {
      await expect(
        fetchWindow(id, { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 }, boom as unknown as typeof fetch),
      ).resolves.toBeNull();
    }
  });

  it("rejects any raster under the tileband legend (stale by definition)", () => {
    for (const id of ["ookla_fixed", "ookla_mobile"] as const) {
      expect(
        matchesContract({ half: null, sigma: 1.0, per: 0, cap: 0 }, id),
      ).toBe(false);
    }
  });
});

describe("ookla tileband field (client render path)", () => {
  const bbox = { minlon: 24.73, minlat: 59.43, maxlon: 24.76, maxlat: 59.445 };
  const spec = ooklaBonusSpecFor("ookla_fixed");
  if (spec.kind !== "tileband") throw new Error("ookla spec must be tileband");

  it("renders the tile band under the tile, unknown far away", () => {
    const pts = [{ lat: 59.4375, lon: 24.7454, tags: { avg_d: "154425", tests: "151" } }];
    const field = buildScoredField(pts, bbox, 24, 12, 1.0, spec);
    expect(field.direct).not.toBeNull();
    const vals = [...field.direct!].filter((v) => !Number.isNaN(v));
    expect(vals.length).toBeGreaterThan(0);
    for (const v of vals) expect(v).toBe(75);
    // Far corner cells (>1 km out) stay unknown, never zero.
    expect(field.direct![0]).toBeNaN();
  });

  it("renders the nearer tile's band where two synthetic tiles overlap", () => {
    const pts = [
      { lat: 59.4375, lon: 24.7454, tags: { avg_d: "92624", tests: "36" } },
      { lat: 59.44, lon: 24.75, tags: { avg_d: "381664", tests: "40" } },
    ];
    const field = buildScoredField(pts, bbox, 24, 12, 1.0, spec);
    const vals = [...field.direct!].filter((v) => !Number.isNaN(v));
    expect(vals.length).toBeGreaterThan(0);
    // Band-shaped output only (no smoothing, no averaging).
    for (const v of vals) expect([55, 85]).toContain(v);
    // Cell under the slow tile (ix 12, iy 5 fencepost) reads 55, not
    // a blend of the two tiles.
    expect(field.direct![5 * 24 + 12]).toBe(55);
  });

  it("renders all-unknown when nothing loaded (never a faked field)", () => {
    const field = buildScoredField([], bbox, 8, 8, 1.0, spec);
    expect(field.direct).not.toBeNull();
    for (const v of field.direct!) expect(v).toBeNaN();
  });
});

describe("ookla goodness (hex-sample path)", () => {
  const pts = [{ lat: 59.4375, lon: 24.7454, tags: { avg_d: "154425", tests: "151" } }];

  it("reads the tile band at the tile, unknown past the radius", () => {
    expect(goodnessAt(59.4375, 24.7454, pts, "ookla_fixed")).toBe(75);
    expect(goodnessAt(59.43, 24.7, pts, "ookla_fixed")).toBeNull();
  });

  it("stays null with no tiles (never a faked hex)", () => {
    expect(goodnessAt(59.4375, 24.7454, [], "ookla_mobile")).toBeNull();
  });
});

describe("ookla crash fix (#516: indexed tileband rasterizer)", () => {
  // All fixtures FULLY SYNTHETIC (deterministic grid spread, no live
  // extract rows). No network in tests.
  const TALLINN = { minlon: 24.3, minlat: 59.3, maxlon: 25.1, maxlat: 59.6 };
  function spreadTiles(n: number): OoklaPoint[] {
    const pts: OoklaPoint[] = [];
    const side = Math.ceil(Math.sqrt(n));
    let k = 0;
    for (let iy = 0; iy < side && k < n; iy++) {
      for (let ix = 0; ix < side && k < n; ix++, k++) {
        pts.push({
          lon: TALLINN.minlon + ((ix + 0.5) / side) * (TALLINN.maxlon - TALLINN.minlon),
          lat: TALLINN.minlat + ((iy + 0.5) / side) * (TALLINN.maxlat - TALLINN.minlat),
          tags: { avg_d: String(50000 + (k % 4) * 100000), tests: "36" },
        });
      }
    }
    return pts;
  }
  function oldLoopCell(
    pts: OoklaPoint[],
    clon: number,
    clat: number,
  ): number {
    return ooklaTileAt(clat, clon, pts, OOKLA_RADIUS_M, OOKLA_MIN_TESTS)?.band ?? NaN;
  }

  it("is cell-identical to the old per-cell ooklaTileAt loop (same kernel, just indexed)", () => {
    // Adversarial rows included: thin + speed-less tiles (never join)
    // and two coincident tiles (tie-break path).
    const pts: OoklaPoint[] = [
      ...spreadTiles(60),
      { lat: 59.4375, lon: 24.7454, tags: { avg_d: "381664", tests: "4" } },
      { lat: 59.44, lon: 24.75, tags: { tests: "40" } },
      { lat: 59.4375, lon: 24.7454, tags: { avg_d: "92624", tests: "36" } },
      { lat: 59.4375, lon: 24.7454, tags: { avg_d: "381664", tests: "36" } },
    ];
    const cols = 48;
    const rows = 36;
    const indexed = ooklaDirectField(pts, TALLINN, cols, rows, OOKLA_RADIUS_M, OOKLA_MIN_TESTS);
    const spanLon = TALLINN.maxlon - TALLINN.minlon;
    const spanLat = TALLINN.maxlat - TALLINN.minlat;
    let known = 0;
    for (let c = 0; c < cols * rows; c++) {
      const iy = Math.floor(c / cols);
      const ix = c % cols;
      const clon = TALLINN.minlon + (ix / (cols - 1)) * spanLon;
      const clat = TALLINN.minlat + (iy / (rows - 1)) * spanLat;
      const want = oldLoopCell(pts, clon, clat);
      const got = indexed[c];
      if (Number.isNaN(want)) expect(got).toBeNaN();
      else {
        expect(got).toBe(want);
        known++;
      }
    }
    expect(known).toBeGreaterThan(0);
  });

  it("renders the production point count (1914 fixed tiles) at production resolution without hanging", () => {
    // Repro of the buyer report: the Tallinn view resolves to a
    // ~905x663 grid via fieldResolution; the old cells-x-tiles loop
    // took ~43 s here (tab freeze/crash). The indexed field must stay
    // interactive; 15 s is ~35x headroom over the observed ~0.4 s, so
    // this only trips on an algorithmic regression, never on CI noise.
    const pts = spreadTiles(1914);
    const res = fieldResolution(TALLINN, 1.0);
    expect(res.cols * res.rows).toBeGreaterThan(100000);
    const t0 = performance.now();
    const field = buildScoredField(pts, TALLINN, res.cols, res.rows, 1.0, ooklaBonusSpecFor("ookla_fixed"));
    const ms = performance.now() - t0;
    expect(ms).toBeLessThan(15000);
    expect(field.direct).not.toBeNull();
    let known = 0;
    for (const v of field.direct!) {
      if (Number.isNaN(v)) continue;
      expect([35, 55, 75, 85]).toContain(v);
      known++;
    }
    expect(known).toBeGreaterThan(0);
  });

  it("serves both layers (fixed + mobile) off the same fixed kernel", () => {
    const pts = spreadTiles(200);
    const cols = 40;
    const rows = 30;
    const fixed = buildScoredField(pts, TALLINN, cols, rows, 1.0, ooklaBonusSpecFor("ookla_fixed"));
    const mobile = buildScoredField(pts, TALLINN, cols, rows, 1.0, ooklaBonusSpecFor("ookla_mobile"));
    expect(fixed.direct).not.toBeNull();
    expect(mobile.direct).not.toBeNull();
    for (let c = 0; c < cols * rows; c++) {
      const a = fixed.direct![c];
      const b = mobile.direct![c];
      if (Number.isNaN(a)) expect(b).toBeNaN();
      else expect(b).toBe(a);
    }
  });

  it("stays all-unknown through the indexed path with no tiles", () => {
    const direct = ooklaDirectField([], TALLINN, 8, 8, OOKLA_RADIUS_M, OOKLA_MIN_TESTS);
    for (const v of direct) expect(v).toBeNaN();
  });
});
