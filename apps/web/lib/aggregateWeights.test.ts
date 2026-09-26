// Regression tests for aggregate weight categories (#819): multiplier
// math, neutral shipped defaults, defaults completeness (every
// non-pins layer has a default weight + category), and v2 store
// parsing (legacy hf-aggregate-v1 is never read).

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
  effectiveWeight,
  parseStoredAggregate,
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
  it("neutral defaults give weight 1", () => {
    expect(effectiveWeight("parks", {}, {})).toBe(1);
    expect(effectiveWeight("transit", {}, {})).toBe(1);
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
    expect(effectiveWeight("transit", {}, { nature: 0 })).toBe(1);
    expect(effectiveWeight("parks", {}, { transport: 0 })).toBe(1);
  });

  it("out-of-range inputs clamp to slider bounds", () => {
    expect(effectiveWeight("parks", { parks: 5 }, {})).toBe(2);
    expect(effectiveWeight("parks", { parks: -3 }, {})).toBe(0);
    expect(effectiveWeight("parks", {}, { nature: 5 })).toBe(2);
  });

  it("non-finite inputs fall back to shipped defaults", () => {
    expect(effectiveWeight("parks", { parks: NaN }, {})).toBe(1);
    expect(effectiveWeight("parks", {}, { nature: NaN })).toBe(1);
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

  it("ships neutral: every layer default weight is 1", () => {
    for (const id of nonPinsIds()) {
      expect(DEFAULT_WEIGHTS[id as keyof typeof DEFAULT_WEIGHTS]).toBe(1);
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
