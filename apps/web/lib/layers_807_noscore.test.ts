import { describe, expect, it } from "vitest";
import { bonusSpecFor, LAYERS, type BBoxLike } from "./layers";
import { buildScoredField } from "./distanceField";

// Dated no-score decisions (issue #807): these layers keep their
// markers/tints/INERT specs BY DECISION — pins measure activity or
// availability, tints describe taste, cadastre answers identity, and
// asumedia waits on real data. Each case pins the retained spec +
// the unknown-everywhere behavior so a future scorer cannot silently
// appear (or disappear) without updating this file.

const PINS_RETAINED = [
  "fixit",
  "incidents",
  "datex-restrictions",
  "datex-srti",
  "datex-weather",
  "datex-counters",
  "datex-cameras",
  "datex-truckpark",
] as const;

const INERT_RETAINED = ["relief", "canopy", "buildings", "density", "maaparcel"] as const;

const BBOX: BBoxLike = { minlon: 24.7, minlat: 59.4, maxlon: 24.8, maxlat: 59.48 };

describe("807 no-score decisions (activity/availability/taste/identity/dormant)", () => {
  it("activity + availability pins stay pins (fixit precedent)", () => {
    for (const id of PINS_RETAINED) {
      expect(bonusSpecFor(id), id).toEqual({ kind: "pins" });
    }
    // The pins kernel paints no field: all-NaN direct on any input.
    const field = buildScoredField(
      [{ lon: 24.75, lat: 59.44 }],
      BBOX,
      4,
      4,
      0.5,
      bonusSpecFor("fixit"),
    );
    for (const v of field.direct!) expect(v).toBeNaN();
  });

  it("taste tints + cadastre stay INERT with zero fallback points", () => {
    for (const id of INERT_RETAINED) {
      expect(bonusSpecFor(id), id).toEqual({ kind: "area", half: 60 });
      expect(LAYERS.find((l) => l.id === id)?.fallbackPoints, id).toEqual([]);
    }
  });

  it("asumedia stays dormant: cover kernel, empty set, unknown field", () => {
    expect(bonusSpecFor("asumedia")).toEqual({ kind: "cover", sigma: 0.5 });
    expect(LAYERS.find((l) => l.id === "asumedia")?.fallbackPoints).toEqual([]);
    const field = buildScoredField([], BBOX, 4, 4, 0.5, bonusSpecFor("asumedia"));
    for (const v of field.direct!) expect(v).toBeNaN();
  });

  it("every no-score layer still explains itself in Estonian", () => {
    for (const id of [...PINS_RETAINED, ...INERT_RETAINED, "asumedia"]) {
      const def = LAYERS.find((l) => l.id === id);
      expect(def, id).toBeDefined();
      expect(def!.goodLabel.length).toBeGreaterThan(0);
      expect(def!.badLabel.length).toBeGreaterThan(0);
    }
  });
});
