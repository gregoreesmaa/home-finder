import { describe, expect, it } from "vitest";
import {
  BATCH4_CAL,
  BATCH4_DECAY_KM,
  BATCH4_LAYERS,
  BATCH4_RASTER_FILE,
  BATCH4_TAGS,
  batch4BonusSpec,
  batch4GoodnessAt,
  batch4HavKm,
  batch4RadiusKmFor,
  batch4Saturate,
  batch4ScoreFromWait,
  batch4WaitMin,
} from "./layers_batch4";

describe("batch4 registry", () => {
  it("binds five layers to parameters3 ids", () => {
    expect(BATCH4_LAYERS.map((l) => l.id)).toEqual([
      "teens",
      "airport",
      "lockers",
      "securepickup",
      "rideshare",
    ]);
    expect(BATCH4_LAYERS.find((l) => l.id === "teens")?.paramIds).toEqual([125]);
    expect(BATCH4_LAYERS.find((l) => l.id === "airport")?.paramIds).toEqual([343]);
    expect(BATCH4_LAYERS.find((l) => l.id === "lockers")?.paramIds).toEqual([141]);
    expect(BATCH4_LAYERS.find((l) => l.id === "securepickup")?.paramIds).toEqual([282]);
    expect(BATCH4_LAYERS.find((l) => l.id === "rideshare")?.paramIds).toEqual([342]);
  });

  it("every layer explains green=good / red=bad in Estonian", () => {
    for (const l of BATCH4_LAYERS) {
      expect(l.title.length).toBeGreaterThan(0);
      expect(l.goodLabel).toMatch(/roheline/);
      expect(l.badLabel).toMatch(/punane/);
      expect(l.source).toContain("2026-09-12");
      expect(l.fallbackPoints.length).toBeGreaterThan(0);
    }
  });

  it("rideshare is honestly labeled a proxy, never measured data", () => {
    const r = BATCH4_LAYERS.find((l) => l.id === "rideshare");
    expect(r?.title).toMatch(/proksi/);
    expect(r?.source).toMatch(/PROKSI/);
  });

  it("tags use snapshot-verified OSM tags only", () => {
    expect(BATCH4_TAGS.lockers).toContain("parcel_locker");
    expect(BATCH4_TAGS.securepickup).toContain("parcel_locker");
    expect(BATCH4_TAGS.securepickup).toContain("post_office");
    expect(BATCH4_TAGS.teens).toContain("bus_stop");
    expect(BATCH4_TAGS.airport).toContain("bus_stop");
  });

  it("raster filenames follow the base master convention", () => {
    for (const id of ["teens", "airport", "lockers", "securepickup", "rideshare"] as const) {
      expect(BATCH4_RASTER_FILE[id]).toMatch(/-walk-raster\.json$/);
    }
  });
});

describe("batch4 calibration", () => {
  it("matches scripts/build/batch_b4_common.py CAL (pytest cross-checks too)", () => {
    expect(BATCH4_CAL.teens).toEqual({ sigma: 0.2, half: 800 });
    expect(BATCH4_CAL.airport).toEqual({ sigma: 0.3, half: 150 });
    expect(BATCH4_CAL.lockers).toEqual({ sigma: 0.3, half: 4 });
    expect(BATCH4_CAL.securepickup).toEqual({ sigma: 0.3, half: 6 });
    expect(BATCH4_CAL.rideshare).toEqual({
      sigma: 0.3,
      transitHalf: 1500,
      roadHalf: 800,
      waitMin: 2,
      waitMax: 15,
    });
  });

  it("sigmas agree with the decay radii", () => {
    for (const id of Object.keys(BATCH4_DECAY_KM) as (keyof typeof BATCH4_DECAY_KM)[]) {
      expect(batch4RadiusKmFor(id)).toBe(BATCH4_CAL[id].sigma);
    }
  });

  it("bonus specs carry the locked halves", () => {
    expect(batch4BonusSpec("teens")).toEqual({ kind: "trips", half: 800 });
    expect(batch4BonusSpec("airport")).toEqual({ kind: "trips", half: 150 });
    expect(batch4BonusSpec("lockers")).toEqual({ kind: "area", half: 4 });
    expect(batch4BonusSpec("securepickup")).toEqual({ kind: "area", half: 6 });
    expect(batch4BonusSpec("rideshare")).toEqual({ kind: "wait", waitMin: 2, waitMax: 15 });
  });
});

describe("batch4 scoring math", () => {
  it("haversine uses the walk-graph lon scale", () => {
    expect(batch4HavKm(0, 0, 1, 0)).toBeCloseTo(57.29, 9);
    expect(batch4HavKm(0, 0, 0, 1)).toBeCloseTo(110.57, 9);
  });

  it("saturate hits 50 at half", () => {
    expect(batch4Saturate(800, 800)).toBe(50);
    expect(batch4Saturate(0, 800)).toBe(0);
  });

  it("wait mapping is explicit: 2 min -> 100, 15 min -> 0, linear", () => {
    expect(batch4WaitMin(1, 1)).toBe(2);
    expect(batch4WaitMin(0, 0)).toBe(15);
    expect(batch4ScoreFromWait(2)).toBe(100);
    expect(batch4ScoreFromWait(15)).toBe(0);
    expect(batch4ScoreFromWait(8.5)).toBe(50);
  });

  it("trips layers score high next to frequent stops, null on empty", () => {
    const pts = [{ lat: 59.44, lon: 24.75, t: 2000 }];
    const at = batch4GoodnessAt("teens", 59.44, 24.75, pts);
    expect(at).toBeGreaterThan(60);
    expect(batch4GoodnessAt("teens", 59.44, 24.75, [])).toBeNull();
    expect(batch4GoodnessAt("airport", 59.44, 24.75, [{ lat: 0, lon: 0, t: 5 }])).toBeNull();
  });

  it("locker layers weight post offices above lockers", () => {
    const locker = batch4GoodnessAt("securepickup", 59.44, 24.75, [
      { lat: 59.44, lon: 24.75, a: 1 },
    ]) as number;
    const office = batch4GoodnessAt("securepickup", 59.44, 24.75, [
      { lat: 59.44, lon: 24.75, a: 2 },
    ]) as number;
    expect(office).toBeGreaterThan(locker);
  });

  it("rideshare fallback degrades honestly without raster density", () => {
    const pts = [{ lat: 59.44, lon: 24.75, t: 3000 }];
    const s = batch4GoodnessAt("rideshare", 59.44, 24.75, pts) as number;
    expect(s).toBeGreaterThanOrEqual(0);
    expect(s).toBeLessThanOrEqual(100);
    expect(batch4GoodnessAt("rideshare", 59.44, 24.75, [])).toBeNull();
  });
});
