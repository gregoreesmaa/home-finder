// Hermetic tests for batch B1 (Group 11 amenity layers, issue #98).
// No network, no snapshot reads: registry wiring, tag queries, radii and
// contract numbers only. Run: npx vitest run apps/web/lib/layers_batch1.test.ts
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
  B1_BONUS,
  B1_DECAY,
  B1_LAYER_IDS,
  B1_LAYERS,
  B1_PARAM_IDS,
  B1_TAGS,
  b1BonusSpecFor,
  isB1LayerId,
} from "./layers_batch1";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("batch B1 registry", () => {
  it("binds five layers to their parameters3 ids", () => {
    expect([...B1_LAYER_IDS].sort()).toEqual(
      ["community", "culture", "libraries", "nightlife", "pets"].sort(),
    );
    expect(B1_PARAM_IDS).toEqual({
      pets: [86],
      community: [87],
      culture: [89],
      nightlife: [108],
      libraries: [313],
    });
    for (const id of B1_LAYER_IDS) {
      expect(LAYERS.find((l) => l.id === id)?.paramIds).toEqual(B1_PARAM_IDS[id]);
    }
  });

  it("every layer explains green=good / red=bad in Estonian with snapshot provenance", () => {
    expect(B1_LAYERS).toHaveLength(5);
    for (const l of B1_LAYERS) {
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
    for (const l of B1_LAYERS) {
      for (const p of l.fallbackPoints) {
        expect(p.lon).toBeGreaterThanOrEqual(23.3);
        expect(p.lon).toBeLessThanOrEqual(25.5);
        expect(p.lat).toBeGreaterThanOrEqual(58.4);
        expect(p.lat).toBeLessThanOrEqual(59.65);
      }
    }
  });
});

describe("batch B1 tag queries", () => {
  it("queries cover the verified snapshot tags per layer", () => {
    expect(B1_TAGS.pets).toContain("dog_park");
    expect(B1_TAGS.pets).toContain("veterinary");
    expect(B1_TAGS.pets).toContain('"shop"="pet"');
    expect(B1_TAGS.community).toContain("community_centre");
    expect(B1_TAGS.community).toContain("social_facility");
    expect(B1_TAGS.culture).toContain("theatre");
    expect(B1_TAGS.culture).toContain("museum");
    expect(B1_TAGS.nightlife).toContain("nightclub");
    expect(B1_TAGS.nightlife).toContain("cinema");
    expect(B1_TAGS.libraries).toContain("library");
    const q = overpassQueryFor("culture", TALLINN_BBOX);
    expect(q).toContain("59.35");
    expect(q).toContain("museum");
  });

  it("community and culture queries stay disjoint (Teachers' House rule)", () => {
    // The builder gives tourism=museum/gallery to culture; the community
    // query must not claim them.
    expect(B1_TAGS.community).not.toContain("museum");
    expect(B1_TAGS.community).not.toContain("gallery");
    expect(B1_TAGS.culture).not.toContain("community_centre");
  });

  it("steers clear of sibling batches' tags", () => {
    const all = Object.values(B1_TAGS).join(";");
    for (const foreign of ["events_venue", "festival_grounds", "stadium", "music_school"]) {
      expect(all).not.toContain(foreign);
    }
  });
});

describe("batch B1 scoring numbers", () => {
  it("locks radii and area halves (with the Python builder)", () => {
    expect(B1_DECAY).toEqual({
      pets: 0.5,
      community: 0.5,
      culture: 0.8,
      nightlife: 0.8,
      libraries: 0.8,
    });
    // Locked with LAYER_DEFAULTS in scripts/build/batch_b1_group11.py.
    expect(B1_BONUS).toEqual({
      pets: { kind: "area", half: 5.7 },
      community: { kind: "area", half: 3.3 },
      culture: { kind: "area", half: 4.5 },
      nightlife: { kind: "area", half: 7.5 },
      libraries: { kind: "area", half: 3.0 },
    });
    for (const id of B1_LAYER_IDS) {
      expect(radiusKmFor(id)).toBeCloseTo(B1_DECAY[id], 5);
      expect(bonusSpecFor(id)).toEqual(B1_BONUS[id]);
      expect(b1BonusSpecFor(id)).toEqual(B1_BONUS[id]);
      expect(isB1LayerId(id)).toBe(true);
    }
    expect(isB1LayerId("parks")).toBe(false);
    expect(isB1LayerId("grocery")).toBe(false);
  });

  it("matches the raster contract the server enforces", () => {
    for (const id of B1_LAYER_IDS) {
      const half = B1_BONUS[id].half;
      expect(matchesContract({ half, sigma: B1_DECAY[id], per: 0, cap: 0 }, id)).toBe(true);
      // Stale calibrations are rejected, never rendered.
      expect(matchesContract({ half: half + 1, sigma: B1_DECAY[id], per: 0, cap: 0 }, id)).toBe(
        false,
      );
    }
  });
});
