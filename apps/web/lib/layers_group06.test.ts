import { describe, expect, it, vi } from "vitest";
import {
  GROUP06_BONUS,
  GROUP06_DECAY,
  GROUP06_DEFS,
  GROUP06_HALVES,
  GROUP06_LAYER_IDS,
  GROUP06_NO_MAP,
  GROUP06_PARAMS,
  GROUP06_TAGS,
  bonusSpecForGroup06,
} from "./layers_group06";
import {
  LAYERS,
  bonusSpecFor,
  fetchLayerPoints,
  goodnessAt,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { matchesContract } from "./server/snapshot";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("batch G06 registry (#138)", () => {
  it("defines exactly the one Group 6 map layer (p72)", () => {
    expect(GROUP06_LAYER_IDS).toEqual(["heritage"]);
    expect(GROUP06_DEFS.map((d) => d.id)).toEqual(GROUP06_LAYER_IDS);
  });

  it("maps the layer to its parameters3.md number", () => {
    expect(GROUP06_PARAMS).toEqual({ heritage: 72 });
    for (const d of GROUP06_DEFS) {
      expect(d.paramIds).toEqual([GROUP06_PARAMS[d.id as keyof typeof GROUP06_PARAMS]]);
    }
  });

  it("documents exactly the four no-map verdicts (p158/p272/p320/p351)", () => {
    expect(GROUP06_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([158, 272, 320, 351]);
    for (const v of GROUP06_NO_MAP) expect(v.reason.length).toBeGreaterThan(20);
  });

  it("merges into LAYERS via the G06-HOOK (page + routes serve all twenty-one)", () => {
    const ids = LAYERS.map((l) => l.id);
    expect(ids.length).toBe(21);
    for (const id of GROUP06_LAYER_IDS) expect(ids).toContain(id);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of GROUP06_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source).toContain("2026-09-12");
      expect(d.fallbackPoints.length).toBeGreaterThan(0);
    }
  });
});

describe("batch G06 honesty (#138)", () => {
  it("labels p72 a heritage-proximity hinnang, never a registry decision", () => {
    const heritage = GROUP06_DEFS.find((d) => d.id === "heritage");
    expect(heritage?.title).toMatch(/hinnang/i);
    expect(heritage?.title).toMatch(/proksi/i);
    expect(heritage?.goodLabel).toMatch(/hinnang/i);
    // The source must disclaim the official register explicitly.
    expect(heritage?.source).toMatch(/Muinsuskaitseameti register hetktõmmises pole/);
    expect(heritage?.badLabel).toMatch(/MITTE registriotsus/);
  });
});

describe("batch G06 scoring contract (#138)", () => {
  it("locks radius and area half (raster contract + Euclidean fallback)", () => {
    expect(GROUP06_DECAY).toEqual({ heritage: 0.8 });
    expect(GROUP06_HALVES).toEqual({ heritage: 2 });
    for (const id of GROUP06_LAYER_IDS) {
      expect(radiusKmFor(id)).toBeCloseTo(GROUP06_DECAY[id], 5);
      expect(bonusSpecFor(id)).toEqual({ kind: "area", half: GROUP06_HALVES[id] });
      expect(GROUP06_BONUS[id]).toEqual({ kind: "area", half: GROUP06_HALVES[id] });
    }
  });

  it("bonusSpecForGroup06 answers G06 ids and ignores the other layers", () => {
    expect(bonusSpecForGroup06("heritage")).toEqual({ kind: "area", half: 2 });
    expect(bonusSpecForGroup06("parks")).toBeUndefined();
  });

  it("raster docs bake matching calibration (matchesContract)", () => {
    for (const id of GROUP06_LAYER_IDS) {
      expect(
        matchesContract({ half: GROUP06_HALVES[id], sigma: GROUP06_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(true);
      // Stale half is rejected, never silently rendered.
      expect(
        matchesContract({ half: 999, sigma: GROUP06_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(false);
    }
  });

  it("scores 100 on top of a feature, decays with distance", () => {
    const pts = [{ lat: 59.4374, lon: 24.7454 }];
    expect(goodnessAt(59.4374, 24.7454, pts, "heritage")).toBe(100);
    const near = goodnessAt(59.4474, 24.7454, pts, "heritage") as number;
    const far = goodnessAt(59.5374, 24.7454, pts, "heritage") as number;
    expect(near).toBeGreaterThan(far);
  });
});

describe("batch G06 queries and tags (#138)", () => {
  it("documents the verified snapshot tags", () => {
    expect(GROUP06_TAGS.heritage).toContain('"historic"');
    expect(GROUP06_TAGS.heritage).toContain('"heritage"');
    expect(GROUP06_TAGS.heritage).toContain('"unesco"');
  });

  it("builds bbox-scoped Overpass QL for the new layer", () => {
    const q = overpassQueryFor("heritage", TALLINN_BBOX);
    expect(q).toContain("historic");
    expect(q).toContain("24.5");
  });

  it("fetches the new layer through the generic server proxy", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ points: [{ lat: 59.43, lon: 24.75 }], provenance: "snapshot", ageMs: 1 }),
    });
    const res = await fetchLayerPoints("heritage", TALLINN_BBOX, fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0]).startsWith("/api/layers/heritage?")).toBe(true);
    expect(res.provenance).toBe("snapshot");
  });
});
