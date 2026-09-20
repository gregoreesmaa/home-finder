import { describe, expect, it } from "vitest";
import { bonusSpecFor, type BBoxLike } from "./layers";
import { buildScoredField, type ScoredPoint } from "./distanceField";
import {
  SILLY_DBAND_EDGES,
  SILLY_DBAND_RADIUS_M,
  SILLY_QUIET_HALFM,
  sillyBonusSpecFor,
  type SillyLayerId,
} from "./layers_p4_silly";
import { SKIS_DBANDS, skisBonusSpecFor } from "./layers_p4_skis";

const AMENITY: SillyLayerId[] = [
  "manguvaljakud",
  "saunad",
  "talisuplus",
  "tanavasport",
  "vesi",
  "wc",
  "aed",
  "raamatukapid",
  "kalmistu",
];
const NUISANCE: SillyLayerId[] = ["kirikukellad", "kajakad", "koertepargid"];

// Bbox centred on (24.75, 59.44); kx ≈ 56.6 km/deg lon here.
const LON = 24.75;
const LAT = 59.44;
const KX = 111.32 * Math.cos((LAT * Math.PI) / 180);

function gridAt(distM: number): BBoxLike {
  // 3x3 grid, point under the centre cell; the west/east edge cells sit
  // exactly distM away in longitude (centre row has zero lat offset).
  const halfDeg = distM / 1000 / KX;
  return { minlon: LON - halfDeg, minlat: LAT - halfDeg, maxlon: LON + halfDeg, maxlat: LAT + halfDeg };
}

const CENTER = 4; // ix=1, iy=1
const WEST = 3; // ix=0, iy=1

function directOf(layer: Parameters<typeof bonusSpecFor>[0], points: ScoredPoint[], distM: number) {
  const spec = bonusSpecFor(layer);
  const field = buildScoredField(points, gridAt(distM), 3, 3, 0.5, spec);
  expect(field.direct).not.toBeNull();
  return field.direct!;
}

describe("807 silly goodness (dbands amenity + quiet nuisance)", () => {
  it("amenity layers score doorstep dbands; nuisances score quiet", () => {
    expect(SILLY_DBAND_RADIUS_M).toBe(500);
    expect(SILLY_DBAND_EDGES).toEqual([
      [250, 85],
      [500, 65],
    ]);
    expect(SILLY_QUIET_HALFM).toEqual({ kirikukellad: 300, kajakad: 200, koertepargid: 150 });
    for (const id of AMENITY) {
      expect(sillyBonusSpecFor(id)).toEqual({ kind: "dbands", radiusM: 500, edges: SILLY_DBAND_EDGES });
      expect(bonusSpecFor(id)).toEqual({ kind: "dbands", radiusM: 500, edges: SILLY_DBAND_EDGES });
    }
    for (const id of NUISANCE) {
      expect(sillyBonusSpecFor(id)).toEqual({ kind: "quiet", halfM: SILLY_QUIET_HALFM[id] });
      expect(bonusSpecFor(id)).toEqual({ kind: "quiet", halfM: SILLY_QUIET_HALFM[id] });
    }
  });

  it("dbands direction + decay: 200 m -> 85, 400 m -> 65, 600 m -> unknown", () => {
    const points: ScoredPoint[] = [{ lon: LON, lat: LAT }];
    // Centre cell (dist 0) reads the inner band.
    const inner = directOf("manguvaljakud", points, 200);
    expect(inner[CENTER]).toBe(85);
    // Edge cells 200 m out read the inner band too.
    expect(inner[WEST]).toBe(85);
    const mid = directOf("vesi", points, 400);
    expect(mid[CENTER]).toBe(85);
    expect(mid[WEST]).toBe(65);
    // Past the 500 m hard radius: unknown, never zero.
    const outer = directOf("wc", points, 600);
    expect(outer[CENTER]).toBe(85);
    expect(outer[WEST]).toBeNaN();
  });

  it("dbands empty input stays unknown (never a faked score)", () => {
    const spec = bonusSpecFor("saunad");
    const bbox: BBoxLike = { minlon: 24.7, minlat: 59.4, maxlon: 24.8, maxlat: 59.48 };
    const field = buildScoredField([], bbox, 4, 4, 0.5, spec);
    for (const v of field.direct!) expect(v).toBeNaN();
  });

  it("quiet direction: 0 on the nuisance, 50 at halfM, calm far away", () => {
    const points: ScoredPoint[] = [{ lon: LON, lat: LAT }];
    // On the church: 0 (worst); at 300 m (halfM): 50.
    const near = directOf("kirikukellad", points, 300);
    expect(near[CENTER]).toBe(0);
    expect(near[WEST]).toBeCloseTo(50, 9);
    // Far away: calm (~91 at 3 km), never unknown while mapped.
    const far = directOf("kirikukellad", points, 3000);
    expect(far[CENTER]).toBe(0);
    expect(far[WEST]).toBeGreaterThan(85);
    expect(far[WEST]).toBeLessThanOrEqual(100);
    // Empty input: unknown everywhere.
    const spec = bonusSpecFor("kajakad");
    const bbox: BBoxLike = { minlon: 24.7, minlat: 59.4, maxlon: 24.8, maxlat: 59.48 };
    const field = buildScoredField([], bbox, 4, 4, 0.5, spec);
    for (const v of field.direct!) expect(v).toBeNaN();
  });
});

describe("807 skis goodness (dormant dbands)", () => {
  it("scores a groomed entry within 1 km at 75", () => {
    expect(SKIS_DBANDS).toEqual({ radiusM: 1000, edges: [[1000, 75]] });
    expect(skisBonusSpecFor("skis")).toEqual({ kind: "dbands", radiusM: 1000, edges: [[1000, 75]] });
    expect(bonusSpecFor("skis")).toEqual({ kind: "dbands", radiusM: 1000, edges: [[1000, 75]] });
    const points: ScoredPoint[] = [{ lon: LON, lat: LAT }];
    const inner = directOf("skis", points, 500);
    expect(inner[CENTER]).toBe(75);
    expect(inner[WEST]).toBe(75);
    // Past 1 km the tracks say nothing about the backyard.
    const outer = directOf("skis", points, 1500);
    expect(outer[CENTER]).toBe(75);
    expect(outer[WEST]).toBeNaN();
  });

  it("off-season empty input scores null everywhere (honest empty)", () => {
    const spec = bonusSpecFor("skis");
    const bbox: BBoxLike = { minlon: 24.7, minlat: 59.4, maxlon: 24.8, maxlat: 59.48 };
    const field = buildScoredField([], bbox, 4, 4, 1.0, spec);
    for (const v of field.direct!) expect(v).toBeNaN();
  });
});
