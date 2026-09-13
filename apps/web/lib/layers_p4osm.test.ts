import { describe, expect, it, vi } from "vitest";
import {
  P4OSM_BONUS,
  P4OSM_DECAY,
  P4OSM_LAYERS,
  P4OSM_LAYER_IDS,
  P4OSM_PARAM_LABELS,
  P4OSM_TAGS,
  P4OSM_VERDICTS,
  bonusSpecForP4OSM,
  isP4OSMLayerId,
} from "./layers_p4osm";
import {
  LAYERS,
  bonusSpecFor,
  fetchLayerPoints,
  goodnessAt,
  layerParamTag,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { GROUP03_LAYERS } from "./layers_group03";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import { matchesContract } from "./server/snapshot";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("p4osm registry (#480)", () => {
  it("defines exactly the block-observer + darkness layers", () => {
    expect(P4OSM_LAYER_IDS).toEqual(["blockwalk", "darkness"]);
    expect(P4OSM_LAYERS.map((d) => d.id)).toEqual(P4OSM_LAYER_IDS);
  });

  it("labels each layer with its P4 slice and claims no P3 id", () => {
    // P4-029/P4-035 (parameters4.md) via paramLabel; paramIds stays []
    // so the P3 verdict locks (group02 global lock on 35, group03 guard
    // on 29) keep passing — same shape as the #484 senscom layer.
    expect(P4OSM_PARAM_LABELS).toEqual({ blockwalk: "P4-029", darkness: "P4-035" });
    for (const d of P4OSM_LAYERS) {
      expect(d.paramIds).toEqual([]);
      expect(d.paramLabel).toBe(P4OSM_PARAM_LABELS[d.id as keyof typeof P4OSM_PARAM_LABELS]);
      expect(layerParamTag(d)).toBe(`(${d.paramLabel})`);
    }
    expect(layerParamTag(LAYERS.find((l) => l.id === "parks")!)).toBe("(p19)");
  });

  it("merges into LAYERS via the P4OSM-HOOK (page + routes serve all layers)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 77 shipped layers + 2 P4OSM.
    expect(ids.length).toBe(79);
    for (const id of P4OSM_LAYER_IDS) expect(ids).toContain(id);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of P4OSM_LAYERS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source).toContain("2026-09-12");
      expect(d.fallbackPoints.length).toBeGreaterThan(0);
    }
  });

  it("leaves the P3 no-map guards alone (group03 still ships only p50)", () => {
    expect(new Set(GROUP03_LAYERS.flatMap((l) => l.paramIds))).toEqual(new Set([50]));
    // And this batch claims no P3 id at all: the group02 global verdict
    // lock (21/30/33/35/48) sees none of our rows.
    expect(P4OSM_LAYERS.flatMap((l) => l.paramIds)).toEqual([]);
    expect(new Set(LAYERS.flatMap((l) => l.paramIds)).has(35)).toBe(false);
  });
});

describe("p4osm honesty (#480)", () => {
  it("frames blockwalk as eye-level hinnang, never facade truth", () => {
    const blockwalk = P4OSM_LAYERS.find((d) => d.id === "blockwalk");
    expect(blockwalk?.title).toMatch(/hinnang/);
    expect(blockwalk?.source).toMatch(/kaardistatud|OSM/);
    expect(blockwalk?.source).toMatch(/mitte fassaadi-tõde/);
    expect(blockwalk?.source).toMatch(/Mapillary/);
  });

  it("frames darkness as mapped hinnang, never a lamp count", () => {
    const darkness = P4OSM_LAYERS.find((d) => d.id === "darkness");
    expect(darkness?.title).toMatch(/hinnang/);
    expect(darkness?.source).toMatch(/lit=yes/);
    expect(darkness?.source).toMatch(/mitte lampide loendus/);
    expect(darkness?.source).toMatch(/VIIRS/);
  });

  it('never prints "EI OLE" on a proxy (dims_p4_osm invariant, map side)', () => {
    for (const d of P4OSM_LAYERS) {
      for (const s of [d.title, d.goodLabel, d.badLabel, d.source]) {
        expect(s).not.toContain("EI OLE");
      }
    }
    for (const v of P4OSM_VERDICTS) {
      expect(v.kind).toBe("proxy");
      expect(v.reason).not.toContain("EI OLE");
    }
  });
});

describe("p4osm scoring contract (#480)", () => {
  it("locks radii at <=500 m and bonus priors (raster contract + Euclidean fallback)", () => {
    // Sigma 0.5 km == the issue AC (block-observer kernel <=500 m) ==
    // the scorer radii (BLOCK_RADIUS_M / DARKNESS_RADIUS_M). Halves are
    // priors until the raster builder confirms them (module header).
    expect(P4OSM_DECAY).toEqual({ blockwalk: 0.5, darkness: 0.5 });
    expect(P4OSM_BONUS).toEqual({
      blockwalk: { kind: "area", half: 1000 },
      darkness: { kind: "area", half: 500 },
    });
    for (const id of P4OSM_LAYER_IDS) {
      expect(radiusKmFor(id)).toBeLessThanOrEqual(0.5);
      expect(radiusKmFor(id)).toBeCloseTo(P4OSM_DECAY[id], 5);
      expect(bonusSpecFor(id)).toEqual(P4OSM_BONUS[id]);
    }
  });

  it("bonusSpecForP4OSM answers P4OSM ids and ignores other layers", () => {
    expect(bonusSpecForP4OSM("darkness")).toEqual({ kind: "area", half: 500 });
    expect(bonusSpecForP4OSM("parks")).toBeUndefined();
    expect(isP4OSMLayerId("blockwalk")).toBe(true);
    expect(isP4OSMLayerId("parks")).toBe(false);
  });

  it("raster docs bake matching calibration (matchesContract)", () => {
    const AREA_HALF = { blockwalk: 1000, darkness: 500 } as const;
    for (const id of ["blockwalk", "darkness"] as const) {
      expect(
        matchesContract({ half: AREA_HALF[id], sigma: P4OSM_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(true);
      // Stale half is rejected, never silently rendered.
      expect(
        matchesContract({ half: 999, sigma: P4OSM_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(false);
    }
  });

  it("scores 100 on top of a feature, decays with distance", () => {
    const pts = [{ lat: 59.4372, lon: 24.7536 }];
    expect(goodnessAt(59.4372, 24.7536, pts, "darkness")).toBe(100);
    const near = goodnessAt(59.4472, 24.7536, pts, "blockwalk") as number;
    const far = goodnessAt(59.5372, 24.7536, pts, "blockwalk") as number;
    expect(near).toBeGreaterThan(far);
  });

  it("serves markers + legends through the overlay path", () => {
    // Distinct from every other marker (global distinct-color test in
    // overlays.test.ts pins the full set).
    expect(overlayColorFor("blockwalk")).toMatch(/^#[0-9a-f]{6}$/);
    expect(overlayColorFor("darkness")).toMatch(/^#[0-9a-f]{6}$/);
    expect(overlayColorFor("blockwalk")).not.toBe(overlayColorFor("darkness"));
    expect(overlayLegendFor("blockwalk")).toContain("küllastus 1000");
    expect(overlayLegendFor("blockwalk")).toContain("hinnang");
    expect(overlayLegendFor("darkness")).toContain("küllastus 500");
    expect(overlayLegendFor("darkness")).toContain("hinnang");
  });
});

describe("p4osm queries and tags (#480)", () => {
  it("documents the verified snapshot tags per layer", () => {
    expect(P4OSM_TAGS.blockwalk).toContain('highway"="footway');
    expect(P4OSM_TAGS.blockwalk).toContain("sidewalk");
    expect(P4OSM_TAGS.blockwalk).toContain('surface"="asphalt');
    expect(P4OSM_TAGS.blockwalk).toContain('lit"="yes');
    expect(P4OSM_TAGS.darkness).toContain('lit"="yes');
  });

  it("builds bbox-scoped Overpass QL for the new layers", () => {
    const q = overpassQueryFor("blockwalk", TALLINN_BBOX);
    expect(q).toContain("footway");
    expect(q).toContain("24.5");
    const dark = overpassQueryFor("darkness", TALLINN_BBOX);
    expect(dark).toContain("lit");
    expect(dark).toContain("24.5");
  });

  it("fetches new layers through the generic server proxy", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ points: [{ lat: 59.43, lon: 24.75 }], provenance: "snapshot", ageMs: 1 }),
    });
    const res = await fetchLayerPoints("darkness", TALLINN_BBOX, fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0]).startsWith("/api/layers/darkness?")).toBe(true);
    expect(res.provenance).toBe("snapshot");
  });
});
