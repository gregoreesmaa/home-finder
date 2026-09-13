// Hermetic tests for batch G11C (Group 11 leftovers A, issue #134).
// No network, no snapshot reads: registry wiring, tag queries, radii and
// contract numbers only. Run: npx vitest run apps/web/lib/layers_group11c.test.ts
import { describe, expect, it } from "vitest";
import {
  LAYERS,
  bonusSpecFor,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { matchesContract } from "./server/snapshot";
import {
  G11C_BONUS,
  G11C_DECAY,
  G11C_LAYER_IDS,
  G11C_DEFS,
  G11C_METRO_PREFIX,
  G11C_PARAMS,
  G11C_RASTER_FILE,
  G11C_TAGS,
  G11C_VERDICTS,
  bonusSpecForGroup11C,
} from "./layers_group11c";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("batch G11C registry", () => {
  it("binds five layers to their parameters3 ids", () => {
    expect([...G11C_LAYER_IDS].sort()).toEqual(
      ["forage", "medspecial", "recspecial", "schoolbus", "worship"].sort(),
    );
    expect(G11C_PARAMS).toEqual({
      schoolbus: 88,
      recspecial: 101,
      medspecial: 124,
      worship: 169,
      forage: 190,
    });
    for (const id of G11C_LAYER_IDS) {
      expect(LAYERS.find((l) => l.id === id)?.paramIds).toEqual([G11C_PARAMS[id]]);
    }
  });

  it("declares one verdict per param (proxy only for the unmapped bus routes)", () => {
    expect(G11C_VERDICTS).toEqual({
      schoolbus: "proxy",
      recspecial: "real",
      medspecial: "real",
      worship: "real",
      forage: "real",
    });
  });

  it("every layer explains green=good / red=bad in Estonian with snapshot provenance", () => {
    expect(G11C_DEFS).toHaveLength(5);
    for (const l of G11C_DEFS) {
      expect(l.title.length).toBeGreaterThan(0);
      expect(l.goodLabel).toContain("roheline");
      expect(l.badLabel).toContain("punane");
      expect(l.source).toContain("2026-09-12");
      expect(l.fallbackPoints.length).toBeGreaterThanOrEqual(2);
      for (const p of l.fallbackPoints) {
        expect(Number.isFinite(p.lat)).toBe(true);
        expect(Number.isFinite(p.lon)).toBe(true);
      }
    }
  });

  it("fallback points sit inside snapshot coverage", () => {
    for (const l of G11C_DEFS) {
      for (const p of l.fallbackPoints) {
        expect(p.lon).toBeGreaterThanOrEqual(23.3);
        expect(p.lon).toBeLessThanOrEqual(25.5);
        expect(p.lat).toBeGreaterThanOrEqual(58.4);
        expect(p.lat).toBeLessThanOrEqual(59.65);
      }
    }
  });

  it("labels the school-bus proxy honestly (hinnang, never a route)", () => {
    const def = G11C_DEFS.find((l) => l.id === "schoolbus");
    expect(def?.title).toContain("hinnang");
    expect(def?.badLabel).toContain("MITTE tegelik bussiliin");
    expect(def?.source).toContain("tegelikud koolibussiliinid kaardil pole");
  });
});

describe("batch G11C tag queries", () => {
  it("queries cover the verified snapshot tags per layer", () => {
    expect(G11C_TAGS.schoolbus).toContain('"amenity"="school"');
    expect(G11C_TAGS.schoolbus).toContain("bus_stop");
    expect(G11C_TAGS.recspecial).toContain("sports_centre");
    expect(G11C_TAGS.recspecial).toContain("swimming_pool");
    expect(G11C_TAGS.recspecial).toContain("golf_course");
    expect(G11C_TAGS.medspecial).toContain("hospital");
    expect(G11C_TAGS.medspecial).toContain("dentist");
    expect(G11C_TAGS.worship).toContain("place_of_worship");
    expect(G11C_TAGS.forage).toContain('"landuse"="forest"');
    expect(G11C_TAGS.forage).toContain("scrub");
  });

  it("builds a bbox query per layer without live fetching", () => {
    for (const id of G11C_LAYER_IDS) {
      const q = overpassQueryFor(id, TALLINN_BBOX);
      expect(q).toContain("24.5");
      expect(q).toContain("59.35");
    }
  });
});

describe("batch G11C calibration", () => {
  it("locks radii to the walk-kernel sigmas", () => {
    expect(G11C_DECAY).toEqual({
      schoolbus: 0.5,
      recspecial: 0.8,
      medspecial: 0.8,
      worship: 0.8,
      forage: 0.5,
    });
    for (const id of G11C_LAYER_IDS) {
      expect(radiusKmFor(id)).toBeCloseTo(G11C_DECAY[id], 5);
    }
  });

  it("locks halves to the histogram calibration (wire contract)", () => {
    expect(G11C_BONUS).toEqual({
      schoolbus: { kind: "area", half: 4.0 },
      recspecial: { kind: "area", half: 8.0 },
      medspecial: { kind: "area", half: 5.0 },
      worship: { kind: "area", half: 2.5 },
      forage: { kind: "area", half: 12.0 },
    });
    for (const id of G11C_LAYER_IDS) {
      expect(bonusSpecFor(id)).toEqual(G11C_BONUS[id]);
      expect(bonusSpecForGroup11C(id)).toEqual(G11C_BONUS[id]);
    }
    expect(bonusSpecForGroup11C("parks")).toBeUndefined();
  });

  it("matches the raster wire contract per layer", () => {
    const docs = {
      schoolbus: { half: 4.0, sigma: 0.5, per: 0, cap: 0 },
      recspecial: { half: 8.0, sigma: 0.8, per: 0, cap: 0 },
      medspecial: { half: 5.0, sigma: 0.8, per: 0, cap: 0 },
      worship: { half: 2.5, sigma: 0.8, per: 0, cap: 0 },
      forage: { half: 12.0, sigma: 0.5, per: 0, cap: 0 },
    } as const;
    for (const id of G11C_LAYER_IDS) {
      expect(matchesContract(docs[id], id)).toBe(true);
      expect(matchesContract({ ...docs[id], half: docs[id].half + 1 }, id)).toBe(false);
    }
  });

  it("names raster masters and county-only metro prefixes", () => {
    expect(G11C_RASTER_FILE).toEqual({
      schoolbus: "schoolbus-walk-raster.json",
      recspecial: "recspecial-walk-raster.json",
      medspecial: "medspecial-walk-raster.json",
      worship: "worship-walk-raster.json",
      forage: "forage-walk-raster.json",
    });
    for (const id of G11C_LAYER_IDS) {
      expect(G11C_METRO_PREFIX[id]).toBe(`${id}-metro`);
    }
  });
});
