import { describe, expect, it, vi } from "vitest";
import {
  GROUP06B_BONUS,
  GROUP06B_DECAY,
  GROUP06B_DEFS,
  GROUP06B_HALVES,
  GROUP06B_LAYER_IDS,
  GROUP06B_NO_MAP,
  GROUP06B_PARAMS,
  GROUP06B_TAGS,
  bonusSpecForGroup06B,
  isGroup06BAvoidLayer,
} from "./layers_group06b";
import {
  LAYERS,
  bonusSpecFor,
  fetchLayerPoints,
  goodnessAt,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { buildScoredField, scoredAt } from "./distanceField";
import { matchesContract } from "./server/snapshot";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("batch G06B registry (#139)", () => {
  it("defines exactly the three Group 6 leftover map layers (p352/p353/p356)", () => {
    expect(GROUP06B_LAYER_IDS).toEqual(["plaster", "antiques", "woodfire"]);
    expect(GROUP06B_DEFS.map((d) => d.id)).toEqual(GROUP06B_LAYER_IDS);
  });

  it("maps each layer to its parameters3.md number", () => {
    expect(GROUP06B_PARAMS).toEqual({ plaster: 352, antiques: 353, woodfire: 356 });
    for (const d of GROUP06B_DEFS) {
      expect(d.paramIds).toEqual([GROUP06B_PARAMS[d.id as keyof typeof GROUP06B_PARAMS]]);
    }
  });

  it("documents exactly the four no-map verdicts (p354/p355/p359/p360)", () => {
    expect(GROUP06B_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([354, 355, 359, 360]);
    for (const v of GROUP06B_NO_MAP) expect(v.reason.length).toBeGreaterThan(20);
  });

  it("merges into LAYERS via the G06B-HOOK (page + routes serve all forty-two)", () => {
    const ids = LAYERS.map((l) => l.id);
    expect(ids.length).toBe(42);
    for (const id of GROUP06B_LAYER_IDS) expect(ids).toContain(id);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of GROUP06B_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source).toContain("2026-09-12");
      expect(d.fallbackPoints.length).toBeGreaterThan(0);
    }
  });
});

describe("batch G06B honesty (#139)", () => {
  it("labels every layer a mapped-data hinnang, never a registry decision", () => {
    for (const d of GROUP06B_DEFS) {
      expect(d.title).toMatch(/hinnang/i);
      expect(d.title).toMatch(/proksi/i);
      expect(d.badLabel).toMatch(/hinnang/i);
      expect(d.source).toMatch(/Muinsuskaitseameti register hetktõmmises pole/);
    }
  });

  it("admits the thin-mapping corners (antiques shop != stock, wood mapping sparse)", () => {
    const antiques = GROUP06B_DEFS.find((d) => d.id === "antiques");
    expect(antiques?.badLabel).toMatch(/kauplus ≠ furnituuriladu/);
    const woodfire = GROUP06B_DEFS.find((d) => d.id === "woodfire");
    expect(woodfire?.badLabel).toMatch(/MITTE konstruktsiooniuuring/);
    expect(woodfire?.source).toMatch(/kaardistus on hõre/);
  });
});

describe("batch G06B scoring contract (#139)", () => {
  it("locks radius and halves (raster contract + Euclidean fallback)", () => {
    expect(GROUP06B_DECAY).toEqual({ plaster: 0.5, antiques: 0.5, woodfire: 0.3 });
    expect(GROUP06B_HALVES).toEqual({ plaster: 6, antiques: 1, woodfire: 0.21 });
    for (const id of GROUP06B_LAYER_IDS) {
      expect(radiusKmFor(id)).toBeCloseTo(GROUP06B_DECAY[id], 5);
      expect(bonusSpecFor(id)).toEqual(GROUP06B_BONUS[id]);
    }
    expect(bonusSpecFor("woodfire")).toEqual({ kind: "avoid", half: 0.21 });
  });

  it("bonusSpecForGroup06B answers G06B ids and ignores the other layers", () => {
    expect(bonusSpecForGroup06B("plaster")).toEqual({ kind: "area", half: 6 });
    expect(bonusSpecForGroup06B("woodfire")).toEqual({ kind: "avoid", half: 0.21 });
    expect(bonusSpecForGroup06B("parks")).toBeUndefined();
  });

  it("marks exactly woodfire inverse", () => {
    expect(isGroup06BAvoidLayer("woodfire")).toBe(true);
    expect(isGroup06BAvoidLayer("plaster")).toBe(false);
    expect(isGroup06BAvoidLayer("parks")).toBe(false);
  });

  it("raster docs bake matching calibration (matchesContract)", () => {
    for (const id of GROUP06B_LAYER_IDS) {
      expect(
        matchesContract({ half: GROUP06B_HALVES[id], sigma: GROUP06B_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(true);
      // Stale half is rejected, never silently rendered.
      expect(
        matchesContract({ half: 999, sigma: GROUP06B_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(false);
    }
  });

  it("direct layers score 100 on top of a feature, decay with distance", () => {
    for (const id of ["plaster", "antiques"] as const) {
      const pts = [{ lat: 59.428, lon: 24.698 }];
      expect(goodnessAt(59.428, 24.698, pts, id)).toBe(100);
      const near = goodnessAt(59.438, 24.698, pts, id) as number;
      const far = goodnessAt(59.528, 24.698, pts, id) as number;
      expect(near).toBeGreaterThan(far);
    }
  });

  it("woodfire scores INVERSELY: 0 on the wooden house, ~50 at half km, high far away", () => {
    const pts = [{ lat: 59.4295, lon: 24.7138 }];
    expect(goodnessAt(59.4295, 24.7138, pts, "woodfire")).toBe(0);
    // 0.21 km north ≈ half -> ~50.
    const half = goodnessAt(59.4295 + 0.21 / 111.2, 24.7138, pts, "woodfire") as number;
    expect(Math.abs(half - 50)).toBeLessThanOrEqual(2);
    const near = goodnessAt(59.4295 + 0.05 / 111.2, 24.7138, pts, "woodfire") as number;
    const far = goodnessAt(59.4295 + 1.0 / 111.2, 24.7138, pts, "woodfire") as number;
    expect(near).toBeLessThan(half);
    expect(far).toBeGreaterThan(half);
    expect(goodnessAt(59.4295, 24.7138, [], "woodfire")).toBeNull();
  });

  it("Euclidean field agrees with the raster about inverse direction", () => {
    const pts = [{ lon: 24.7138, lat: 59.4295 }];
    const box: BBoxLike = { minlon: 24.69, minlat: 59.41, maxlon: 24.74, maxlat: 59.45 };
    const s = buildScoredField(pts, box, 24, 24, 0.3, { kind: "avoid", half: 0.21 });
    // Corner far from the house reads high (safe), centre cell low (risk).
    const corner = scoredAt(s, 0, 0) as number;
    expect(corner).toBeGreaterThan(80);
    let min = Infinity;
    for (let iy = 0; iy < 24; iy++)
      for (let ix = 0; ix < 24; ix++) {
        const v = scoredAt(s, ix, iy);
        if (v !== null && v < min) min = v;
      }
    expect(min).toBeLessThan(40);
  });
});

describe("batch G06B queries and tags (#139)", () => {
  it("documents the verified snapshot tags", () => {
    expect(GROUP06B_TAGS.plaster).toContain('"building:material"');
    expect(GROUP06B_TAGS.plaster).toContain('"plaster"');
    expect(GROUP06B_TAGS.antiques).toContain('"shop"');
    expect(GROUP06B_TAGS.antiques).toContain('"antiques"');
    expect(GROUP06B_TAGS.woodfire).toContain('"wood"');
  });

  it("builds bbox-scoped Overpass QL for the new layers", () => {
    const q = overpassQueryFor("plaster", TALLINN_BBOX);
    expect(q).toContain("building:material");
    expect(q).toContain("24.5");
    expect(overpassQueryFor("woodfire", TALLINN_BBOX)).toContain("nwr[");
  });

  it("fetches the new layers through the generic server proxy", async () => {
    for (const id of GROUP06B_LAYER_IDS) {
      const fetchImpl = vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({ points: [{ lat: 59.43, lon: 24.75 }], provenance: "snapshot", ageMs: 1 }),
      });
      const res = await fetchLayerPoints(id, TALLINN_BBOX, fetchImpl);
      expect(String(fetchImpl.mock.calls[0][0]).startsWith(`/api/layers/${id}?`)).toBe(true);
      expect(res.provenance).toBe("snapshot");
    }
  });
});
