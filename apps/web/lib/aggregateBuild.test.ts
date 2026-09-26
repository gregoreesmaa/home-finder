// Regression tests for #830: the split raster-build / recombine stages.
// Locks that weight/mode-only recomputes over cached rasters produce
// byte-identical math to a full rebuild, and that nodata honesty holds
// through the new pipeline.

import { describe, expect, it } from "vitest";
import {
  buildStandardRasters,
  recombineCached,
  toCombineInputs,
  type AggregateFeed,
} from "./aggregateBuild";
import { combineStandardRasters } from "./aggregateRaster";
import { conformsToGrid } from "./standardRaster";
import { DEFAULT_WEIGHTS, DEFAULT_CATEGORY_MULTIPLIERS } from "./aggregateWeights";
import { ESTONIA_BBOX } from "./heatmap";
import { aggregateGridFor } from "./aggregateRaster";

const GRID = aggregateGridFor(ESTONIA_BBOX);

function feed(id: string, n: number, seed: number): AggregateFeed {
  // Deterministic pseudo-random points inside the grid bbox.
  let s = seed >>> 0;
  const rnd = () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const points = [];
  for (let i = 0; i < n; i++) {
    points.push({
      lon: GRID.bbox.minlon + rnd() * (GRID.bbox.maxlon - GRID.bbox.minlon),
      lat: GRID.bbox.minlat + rnd() * (GRID.bbox.maxlat - GRID.bbox.minlat),
    });
  }
  return { id: id as AggregateFeed["id"], points };
}

describe("buildStandardRasters", () => {
  it("returns one grid-conformant raster per usable feed", () => {
    // Real layer ids so radiusKmFor/bonusSpecFor resolve.
    const feeds = [feed("parks", 30, 1), feed("schools", 25, 2)];
    const built = buildStandardRasters(feeds, GRID);
    expect(built).toHaveLength(2);
    expect(built.map((b) => b.id)).toEqual(["parks", "schools"]);
    for (const b of built) {
      expect(conformsToGrid(b.raster, GRID)).toBe(true);
    }
  });

  it("skips feeds with no finite points, empty input builds nothing", () => {
    const bad = {
      id: "parks" as AggregateFeed["id"],
      points: [{ lon: NaN, lat: 58 }, { lon: Infinity, lat: NaN }],
    };
    expect(buildStandardRasters([bad], GRID)).toEqual([]);
    expect(buildStandardRasters([], GRID)).toEqual([]);
  });

  it("is deterministic for identical feeds+grid", () => {
    const feeds = [feed("parks", 40, 7)];
    const a = buildStandardRasters(feeds, GRID);
    const b = buildStandardRasters(feeds, GRID);
    expect(a[0].raster.bytes).toEqual(b[0].raster.bytes);
  });
});

describe("toCombineInputs", () => {
  it("applies layer x category effective weight, keeps zero entries", () => {
    const feeds = [feed("parks", 20, 3), feed("schools", 20, 4)];
    const built = buildStandardRasters(feeds, GRID);
    const inputs = toCombineInputs(
      built,
      { parks: 0, "schools": 2 },
      {},
    );
    expect(inputs).toHaveLength(2);
    // Zeroed layer stays in the inputs (combine excludes it, as before).
    expect(inputs[0].weight).toBe(0);
    expect(inputs[1].weight).toBeGreaterThan(0);
  });
});

describe("recombineCached: no-math-change", () => {
  const feeds = [feed("parks", 30, 11), feed("schools", 30, 12)];
  const weights = { ...DEFAULT_WEIGHTS };
  const multipliers = { ...DEFAULT_CATEGORY_MULTIPLIERS };

  for (const mode of ["average", "multiply", "overlay"] as const) {
    it(`matches a full rebuild for mode ${mode}`, () => {
      const cached = buildStandardRasters(feeds, GRID);
      const viaCache = recombineCached(cached, GRID, weights, multipliers, mode);
      // Full rebuild: fresh rasters + the same weights, as the old
      // inline useMemo did on every tick.
      const fresh = buildStandardRasters(feeds, GRID);
      const full = combineStandardRasters(
        toCombineInputs(fresh, weights, multipliers),
        GRID,
        mode,
      );
      expect(viaCache).not.toBeNull();
      expect(Array.from(viaCache!.mean)).toEqual(Array.from(full.mean));
      expect(Array.from(viaCache!.spread)).toEqual(Array.from(full.spread));
      expect(Array.from(viaCache!.known)).toEqual(Array.from(full.known));
    });
  }

  it("weight-zero recompute excludes the layer but keeps nodata transparent", () => {
    const cached = buildStandardRasters(feeds, GRID);
    const off = recombineCached(
      cached,
      GRID,
      { ...weights, parks: 0, "schools": 0 },
      multipliers,
      "average",
    );
    expect(off).not.toBeNull();
    // Nothing known anywhere: every cell stays NaN (transparent).
    expect(off!.mean.every((m) => Number.isNaN(m))).toBe(true);
    expect(off!.known.every((k) => k === 0)).toBe(true);
  });

  it("returns null with no built rasters", () => {
    expect(recombineCached([], GRID, weights, multipliers, "average")).toBeNull();
  });
});
