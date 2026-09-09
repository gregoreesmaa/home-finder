import { describe, expect, it } from "vitest";
import {
  DEFAULT_BALANCE,
  DIMS,
  isDefaultWeights,
  parseBalanceParam,
  parseWeightsParam,
  weightedLivability,
  weightsToParam,
} from "./weights";

const DIMS_FULL = {
  schools: 90,
  transit: 80,
  services: 70,
  green: 60,
  water: 50,
  rail: 40,
  urban: 30,
  safety: 20,
  connect: 10,
};

describe("weightedLivability", () => {
  it("all-default multipliers reproduce the renormalized mean", () => {
    // 0.18*90+0.12*80+0.12*70+0.10*60+0.08*50+0.07*40+0.03*30+0.15*20+0.15*10
    // = 52.4 -> 52
    expect(weightedLivability(DIMS_FULL, {})).toBe(52);
  });

  it("skips missing dims and renormalizes", () => {
    expect(weightedLivability({ schools: 100 }, {})).toBe(100);
    expect(weightedLivability({ schools: null }, {})).toBeNull();
    expect(weightedLivability(null, {})).toBeNull();
    expect(weightedLivability({}, { schools: 0 })).toBeNull();
  });

  it("multipliers move the score (green x2 lifts a green listing)", () => {
    const base = weightedLivability(DIMS_FULL, {}) as number;
    expect(weightedLivability({ ...DIMS_FULL, green: 100 }, { green: 200 })).toBeGreaterThan(
      base,
    );
    expect(weightedLivability(DIMS_FULL, { schools: 0 })).not.toBe(base);
  });

  it("registry weights sum to 1 and keys are stable", () => {
    const sum = DIMS.reduce((s, d) => s + d.weight, 0);
    expect(sum).toBeCloseTo(1, 10);
    expect(DIMS.map((d) => d.key).sort()).toEqual(
      ["connect", "green", "rail", "safety", "schools", "services", "transit", "urban", "water"],
    );
  });
});

describe("weights URL params", () => {
  it("round-trips non-default multipliers", () => {
    expect(parseWeightsParam("green:200,schools:0")).toEqual({ green: 200, schools: 0 });
    expect(weightsToParam({ green: 200, schools: 0 })).toBe("schools:0,green:200");
    expect(weightsToParam({})).toBe("");
    expect(weightsToParam({ green: 100 })).toBe("");
  });

  it("rejects unknown dims and clamps ranges", () => {
    expect(parseWeightsParam("nope:200")).toEqual({});
    expect(parseWeightsParam("green:999")).toEqual({ green: 200 });
    expect(parseWeightsParam("green:-5")).toEqual({ green: 0 });
    expect(parseWeightsParam("green")).toEqual({});
    expect(parseWeightsParam(null)).toEqual({});
  });

  it("balance parses with default fallback", () => {
    expect(parseBalanceParam("35")).toBe(35);
    expect(parseBalanceParam("nope")).toBe(DEFAULT_BALANCE);
    expect(parseBalanceParam(null)).toBe(DEFAULT_BALANCE);
    expect(parseBalanceParam("140")).toBe(100);
  });

  it("detects default vs customized", () => {
    expect(isDefaultWeights({}, DEFAULT_BALANCE)).toBe(true);
    expect(isDefaultWeights({ green: 100 }, DEFAULT_BALANCE)).toBe(true);
    expect(isDefaultWeights({ green: 200 }, DEFAULT_BALANCE)).toBe(false);
    expect(isDefaultWeights({}, 50)).toBe(false);
  });
});
