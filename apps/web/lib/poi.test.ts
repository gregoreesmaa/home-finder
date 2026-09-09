import { describe, expect, it } from "vitest";
import { haversineKm, parsePois, poiBadge, poiMinutes, poisToParams } from "./poi";

const WORK = { lat: 59.4372, lon: 24.7536, label: "Töö" };

describe("poi minutes", () => {
  it("same spot is ~0 in every mode", () => {
    expect(poiMinutes(59.4372, 24.7536, WORK)).toEqual({ walk: 0, bike: 0, car: 0 });
  });

  it("scales by mode speed (10 km line)", () => {
    // ~10 km north of the POI
    const m = poiMinutes(59.5272, 24.7536, WORK);
    expect(m).not.toBeNull();
    expect(m?.car).toBeGreaterThanOrEqual(15);
    expect(m?.car).toBeLessThanOrEqual(20);
    expect(m?.walk).toBeGreaterThan((m?.bike as number));
    expect(m?.bike).toBeGreaterThan(m?.car as number);
  });

  it("needs coordinates", () => {
    expect(poiMinutes(null, 24.75, WORK)).toBeNull();
    expect(poiMinutes(59.43, NaN, WORK)).toBeNull();
  });

  it("haversine sanity: Tallinn–Tartu ~165 km", () => {
    expect(haversineKm(59.4372, 24.7536, 58.378, 26.729)).toBeGreaterThan(160);
    expect(haversineKm(59.4372, 24.7536, 58.378, 26.729)).toBeLessThan(170);
  });
});

describe("poi badge", () => {
  it("labels car time, adds walk when nearby", () => {
    expect(poiBadge(59.4372, 24.7536, WORK)).toBe("Töö · autoga ~0 min · jalgsi ~0 min");
    const far = poiBadge(58.378, 26.729, WORK);
    expect(far).toMatch(/^Töö · autoga ~\d+ min$/);
    expect(far).not.toContain("jalgsi");
  });

  it("null without coordinates", () => {
    expect(poiBadge(null, null, WORK)).toBeNull();
  });
});

describe("poi URL params", () => {
  it("round-trips repeated params, caps at 5", () => {
    const sp = new URLSearchParams();
    sp.append("poi", "59.43,24.75,Töö");
    sp.append("poi", "58.37,26.72,Kool, Tartu");
    expect(parsePois(sp)).toEqual([
      { lat: 59.43, lon: 24.75, label: "Töö" },
      { lat: 58.37, lon: 26.72, label: "Kool, Tartu" },
    ]);
    const many = Array.from({ length: 7 }, (_, i) => ({ lat: i, lon: i, label: `P${i}` }));
    expect(poisToParams(many)).toHaveLength(5);
  });

  it("rejects garbage", () => {
    const sp = new URLSearchParams("poi=nope&poi=91,0,X&poi=59,24,");
    expect(parsePois(sp)).toEqual([]);
  });
});
