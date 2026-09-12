import { describe, expect, it } from "vitest";
import {
  GROUP15_BONUS,
  GROUP15_CAL,
  GROUP15_DECAY_KM,
  GROUP15_LAYERS,
  GROUP15_RASTER_FILE,
  group15BonusSpec,
  group15HavKm,
  group15MatchesContract,
  group15QuietFromHalf,
  group15Saturate,
  group15ScoreAt,
  group15ShoreFromHalf,
  type Group15LayerId,
} from "./layers_group15";

const IDS: Group15LayerId[] = ["schoolchoice", "redistrict", "weedwater", "festival", "stadium"];

describe("group15 registry", () => {
  it("binds five layers to parameters3 ids 130/314/338/442/462", () => {
    expect(GROUP15_LAYERS.map((l) => l.id)).toEqual(IDS);
    expect(GROUP15_LAYERS.map((l) => l.paramIds)).toEqual([[130], [314], [338], [442], [462]]);
  });

  it("honestly labels every proxy (no official-data claims)", () => {
    for (const l of GROUP15_LAYERS) {
      const text = `${l.title} ${l.goodLabel} ${l.badLabel} ${l.source}`;
      expect(text).toMatch(/proksi/i);
    }
    const p130 = GROUP15_LAYERS[0];
    expect(`${p130.badLabel} ${p130.source}`).toMatch(/MITTE ametlik loosiinfo/);
    expect(GROUP15_LAYERS[2].source).toMatch(/hooldusprogrammid hetktõmmises pole/);
  });

  it("states the inverted green/red direction explicitly", () => {
    const fest = GROUP15_LAYERS.find((l) => l.id === "festival")!;
    expect(fest.goodLabel).toMatch(/kaugel/);
    expect(fest.badLabel).toMatch(/lähedal/);
    const stad = GROUP15_LAYERS.find((l) => l.id === "stadium")!;
    expect(stad.goodLabel).toMatch(/kaugel/);
    expect(stad.badLabel).toMatch(/lähedal/);
  });

  it("keeps raster filenames, decay and bonus specs in sync", () => {
    for (const id of IDS) {
      expect(GROUP15_RASTER_FILE[id]).toBe(`${id}-walk-raster.json`);
      expect(GROUP15_DECAY_KM[id]).toBeGreaterThan(0);
      expect(group15BonusSpec(id)).toEqual(GROUP15_BONUS[id]);
    }
    expect(GROUP15_BONUS.schoolchoice).toEqual({ kind: "area", half: 6 });
    expect(GROUP15_BONUS.redistrict).toEqual({ kind: "area", half: 2 });
    expect(GROUP15_BONUS.weedwater).toEqual({ kind: "shore", halfM: 600 });
    expect(GROUP15_BONUS.festival).toEqual({ kind: "quiet", halfM: 500 });
    expect(GROUP15_BONUS.stadium).toEqual({ kind: "quiet", halfM: 800 });
  });

  it("mirrors the locked 2026-09-12 calibration", () => {
    expect(GROUP15_CAL.schoolchoice).toEqual({ sigma: 0.5, radiusM: 1500, half: 6 });
    expect(GROUP15_CAL.redistrict).toEqual({ sigma: 0.8, radiusM: 2000, half: 2 });
    expect(GROUP15_CAL.weedwater).toEqual({ halfM: 600, sigma: 0.5 });
    expect(GROUP15_CAL.festival).toEqual({ halfM: 500, sigma: 0.5 });
    expect(GROUP15_CAL.stadium).toEqual({ halfM: 800, sigma: 0.8 });
  });
});

describe("group15 math", () => {
  it("uses the 57.29/110.57 lon scale", () => {
    expect(group15HavKm(0, 0, 1, 0)).toBeCloseTo(57.29, 9);
    expect(group15HavKm(0, 0, 0, 1)).toBeCloseTo(110.57, 9);
  });

  it("saturates counts with 0 staying 0", () => {
    expect(group15Saturate(0, 6)).toBe(0);
    expect(group15Saturate(6, 6)).toBe(50);
    expect(group15Saturate(1, 2)).toBe(33);
  });

  it("inverts quiet (red near) and shores green-near", () => {
    expect(group15QuietFromHalf(0, 500)).toBe(0);
    expect(group15QuietFromHalf(500, 500)).toBe(50);
    expect(group15QuietFromHalf(Infinity, 500)).toBe(100);
    expect(group15ShoreFromHalf(0, 600)).toBe(100);
    expect(group15ShoreFromHalf(600, 600)).toBe(50);
    expect(group15ShoreFromHalf(Infinity, 600)).toBe(0);
  });

  it("scores the fallback from points, null when empty", () => {
    expect(group15ScoreAt("festival", 59.44, 24.73, [])).toBeNull();
    // ~219 m to the venue reads ~30 (red-near).
    const q = group15ScoreAt("festival", 59.4405, 24.7369, [{ lat: 59.4425, lon: 24.7369 }]);
    expect(q).toBeGreaterThanOrEqual(28);
    expect(q).toBeLessThanOrEqual(32);
    // Same geometry shores green-near for water.
    const s = group15ScoreAt("weedwater", 59.4405, 24.7369, [{ lat: 59.4425, lon: 24.7369 }]);
    expect(s).toBeGreaterThanOrEqual(70);
    // Choice counts schools in radius only.
    const c = group15ScoreAt("schoolchoice", 59.4405, 24.7369, [
      { lat: 59.4415, lon: 24.7369 },
      { lat: 59.456, lon: 24.762 }, // >1.5 km out
    ]);
    expect(c).toBe(group15Saturate(1, 6));
  });

  it("accepts only matching raster contracts", () => {
    expect(group15MatchesContract({ half: 6, sigma: 0.5 }, "schoolchoice")).toBe(true);
    expect(group15MatchesContract({ half: 7, sigma: 0.5 }, "schoolchoice")).toBe(false);
    expect(group15MatchesContract({ half: 500, sigma: 0.5 }, "festival")).toBe(true);
    expect(group15MatchesContract({ half: 500, sigma: 0.8 }, "festival")).toBe(false);
    expect(group15MatchesContract({ half: 600, sigma: 0.5 }, "weedwater")).toBe(true);
    expect(group15MatchesContract(null, "stadium")).toBe(false);
  });
});
