// Regression tests for aggregate weight categories (#819): multiplier
// math, calibrated shipped defaults (spot-checks + slider grid),
// defaults completeness (every non-pins layer has a default weight +
// category), and v2 store parsing (legacy hf-aggregate-v1 is never read).

import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor } from "./layers";
import {
  CATEGORIES,
  CATEGORY_LABEL,
  DEFAULT_CATEGORY_MULTIPLIERS,
  DEFAULT_WEIGHTS,
  LAYER_CATEGORY,
  LEGACY_STORE_KEY,
  STORE_KEY,
  cleanFactorMap,
  effectiveWeight,
  parseStoredAggregate,
  toggleFactor,
  type AggregateCategory,
} from "./aggregateWeights";

function nonPinsIds(): string[] {
  return LAYERS.filter((l) => {
    try {
      return bonusSpecFor(l.id).kind !== "pins";
    } catch {
      return false;
    }
  }).map((l) => l.id);
}

describe("weight categories: fixed set", () => {
  it("exports exactly the eleven specified categories", () => {
    expect([...CATEGORIES]).toEqual([
      "nature",
      "stores",
      "transport",
      "health",
      "safety",
      "education",
      "leisure",
      "housing",
      "environment",
      "utilities",
      "community",
    ]);
  });

  it("every category has a label and a default multiplier", () => {
    for (const c of CATEGORIES) {
      expect(typeof CATEGORY_LABEL[c]).toBe("string");
      expect(CATEGORY_LABEL[c].length).toBeGreaterThan(0);
      expect(typeof DEFAULT_CATEGORY_MULTIPLIERS[c]).toBe("number");
    }
  });

  it("ships neutral: every default multiplier is 1", () => {
    for (const c of CATEGORIES) {
      expect(DEFAULT_CATEGORY_MULTIPLIERS[c]).toBe(1);
    }
  });
});

describe("effectiveWeight: layer x category", () => {
  it("shipped defaults give the calibrated effective weights", () => {
    expect(effectiveWeight("parks", {}, {})).toBe(1.5);
    expect(effectiveWeight("transit", {}, {})).toBe(2);
    expect(effectiveWeight("noise", {}, {})).toBe(2);
    expect(effectiveWeight("asumedia", {}, {})).toBe(0);
  });

  it("multiplies layer weight by its category multiplier", () => {
    expect(effectiveWeight("parks", { parks: 2 }, { nature: 0.5 })).toBe(1);
    expect(effectiveWeight("parks", { parks: 1.5 }, { nature: 2 })).toBe(3);
  });

  it("zero on either side excludes the layer", () => {
    expect(effectiveWeight("parks", { parks: 0 }, { nature: 2 })).toBe(0);
    expect(effectiveWeight("parks", { parks: 2 }, { nature: 0 })).toBe(0);
  });

  it("unrelated layers and categories do not leak across", () => {
    // transit is transport, not nature: a nature tweak must not move it.
    expect(effectiveWeight("transit", {}, { nature: 0 })).toBe(2);
    expect(effectiveWeight("parks", {}, { transport: 0 })).toBe(1.5);
  });

  it("out-of-range inputs clamp to slider bounds", () => {
    expect(effectiveWeight("parks", { parks: 5 }, {})).toBe(2);
    expect(effectiveWeight("parks", { parks: -3 }, {})).toBe(0);
    expect(effectiveWeight("parks", {}, { nature: 5 })).toBe(3);
  });

  it("non-finite inputs fall back to shipped defaults", () => {
    expect(effectiveWeight("parks", { parks: NaN }, {})).toBe(1.5);
    expect(effectiveWeight("parks", {}, { nature: NaN })).toBe(1.5);
  });
});

describe("defaults completeness", () => {
  it("every non-pins layer has a default weight", () => {
    const ids = nonPinsIds();
    expect(ids.length).toBeGreaterThan(100);
    for (const id of ids) {
      expect(
        DEFAULT_WEIGHTS[id as keyof typeof DEFAULT_WEIGHTS],
        `${id} needs a default weight`,
      ).toBeDefined();
    }
  });

  it("every non-pins layer has a category from the fixed set", () => {
    const valid = new Set<string>(CATEGORIES);
    for (const id of nonPinsIds()) {
      const cat: AggregateCategory | undefined =
        LAYER_CATEGORY[id as keyof typeof LAYER_CATEGORY];
      expect(cat, `${id} needs a category`).toBeDefined();
      expect(valid.has(cat as string), `${id} has unknown category ${cat}`).toBe(true);
    }
  });

  it("ships calibrated: every layer default weight is on the 0..2 slider grid", () => {
    for (const id of nonPinsIds()) {
      const w = DEFAULT_WEIGHTS[id as keyof typeof DEFAULT_WEIGHTS];
      expect(w).toBeGreaterThanOrEqual(0);
      expect(w).toBeLessThanOrEqual(2);
      expect(Number.isInteger(w / 0.25), `${id} weight ${w} off 0.25 grid`).toBe(true);
    }
  });

  it("ships calibrated: spot-checks against the calibrator tables", () => {
    const w = DEFAULT_WEIGHTS as Record<string, number>;
    // top of the scale: daily-commute + universal livability drivers
    expect(w.transit).toBe(2);
    expect(w.gtfsstops).toBe(2);
    expect(w.noise).toBe(2);
    expect(w.dailyshop).toBe(2);
    // everyday conveniences above neutral
    expect(w.parks).toBe(1.5);
    expect(w.grocery).toBe(1.75);
    expect(w.healthcare).toBe(1.75);
    expect(w.harno).toBe(1.75);
    expect(w.schools).toBe(1.5);
    expect(w.kpo).toBe(1.75);
    // empty-on-purpose / taste-only layers stay off
    expect(w.asumedia).toBe(0);
    expect(w.buildings).toBe(0);
    expect(w.canopy).toBe(0);
    expect(w.relief).toBe(0);
    expect(w.density).toBe(0);
    expect(w["delay-offpeak"]).toBe(0);
  });

  it("ships calibrated: spot-checks for reassigned categories", () => {
    const c = LAYER_CATEGORY as Record<string, AggregateCategory>;
    expect(c.schoolbus).toBe("education");
    expect(c.darkness).toBe("safety");
    expect(c.aed).toBe("safety");
    expect(c.tervise).toBe("leisure");
    expect(c.forest).toBe("nature");
    expect(c.fixit).toBe("community");
    expect(c.postal).toBe("utilities");
    expect(c.poi_post).toBe("utilities");
    expect(c.soil).toBe("housing");
    expect(c.windsolar).toBe("utilities");
  });

  it("gap layers: the 22 registered layers with no calib entry have explicit defaults", () => {
    const w = DEFAULT_WEIGHTS as Record<string, number>;
    const c = LAYER_CATEGORY as Record<string, AggregateCategory>;
    const gap: Record<string, [number, AggregateCategory]> = {
      busmesh: [1.5, "transport"],
      "busmesh-sat": [1, "transport"],
      "busmesh-sun": [1, "transport"],
      "datex-cameras": [0.5, "transport"],
      "datex-counters": [0.5, "transport"],
      "datex-restrictions": [0.5, "transport"],
      "datex-srti": [0.5, "transport"],
      "datex-truckpark": [0.5, "transport"],
      "datex-weather": [0.5, "transport"],
      "shed-15-peak": [1.5, "transport"],
      "shed-15-offpeak": [0.5, "transport"],
      "shed-30-peak": [1.25, "transport"],
      "shed-30-offpeak": [0.5, "transport"],
      ehis_school: [1.5, "education"],
      ehis_kindergarten: [1.5, "education"],
      ehis_hobby: [1, "education"],
      poi_library: [0.75, "education"],
      poi_pharmacy: [1.5, "health"],
      poi_post: [1, "utilities"],
      sport_pool: [1.25, "leisure"],
      sport_hall: [1, "leisure"],
      sport_field: [1, "leisure"],
    };
    expect(Object.keys(gap)).toHaveLength(22);
    for (const [id, [weight, cat]] of Object.entries(gap)) {
      expect(w[id], `${id} weight`).toBe(weight);
      expect(c[id], `${id} category`).toBe(cat);
    }
  });
});

describe("v2 store", () => {
  it("uses a new key; the legacy v1 key is never the read key", () => {
    expect(STORE_KEY).toBe("hf-aggregate-v2");
    expect(LEGACY_STORE_KEY).toBe("hf-aggregate-v1");
    expect(STORE_KEY).not.toBe(LEGACY_STORE_KEY);
  });

  it("parses a full v2 blob", () => {
    const parsed = parseStoredAggregate({
      weights: { parks: 1.5 },
      multipliers: { nature: 0.5 },
      mode: "multiply",
    });
    expect(parsed).toEqual({
      weights: { parks: 1.5 },
      multipliers: { nature: 0.5 },
      mode: "multiply",
    });
  });

  it("unreadable blobs fall back to null (caller uses shipped defaults)", () => {
    expect(parseStoredAggregate(null)).toBeNull();
    expect(parseStoredAggregate("garbage")).toBeNull();
    expect(parseStoredAggregate(42)).toBeNull();
    expect(parseStoredAggregate({ weights: [1, 2] })).toBeNull();
    expect(parseStoredAggregate({ multipliers: "x" })).toBeNull();
  });

  it("clamps numerics and drops non-numeric entries", () => {
    const parsed = parseStoredAggregate({
      weights: { parks: 9, transit: "big", schools: NaN },
      multipliers: { nature: -4 },
      mode: "average",
    });
    expect(parsed?.weights).toEqual({ parks: 2 });
    expect(parsed?.multipliers).toEqual({ nature: 0 });
  });

  it("missing fields default to empty maps and average mode", () => {
    expect(parseStoredAggregate({})).toEqual({
      weights: {},
      multipliers: {},
      mode: "average",
    });
  });
});

describe("quick-trial toggles (#825)", () => {
  it("uncheck stashes the nonzero value and yields 0", () => {
    expect(toggleFactor(1.5, undefined, 1)).toEqual({ value: 0, stash: 1.5 });
  });

  it("re-check restores the stash", () => {
    expect(toggleFactor(0, 1.5, 1)).toEqual({ value: 1.5, stash: 1.5 });
  });

  it("re-check with no stash restores the shipped fallback", () => {
    expect(toggleFactor(0, undefined, 0.75)).toEqual({ value: 0.75, stash: undefined });
  });

  it("non-positive stash and fallback fall back to 1 (never stuck off)", () => {
    expect(toggleFactor(0, 0, 0)).toEqual({ value: 1, stash: 0 });
  });

  it("cleanFactorMap keeps finite non-negatives, drops the rest", () => {
    expect(
      cleanFactorMap({ a: 1.5, b: 0, c: -1, d: NaN, e: "x", f: Infinity }),
    ).toEqual({ a: 1.5, b: 0 });
    expect(cleanFactorMap({ a: 99 })).toEqual({ a: 2 });
    expect(cleanFactorMap(null)).toEqual({});
    expect(cleanFactorMap([1])).toEqual({});
  });
});
