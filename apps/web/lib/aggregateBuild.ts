// Raster-build stage of the aggregate view (#830).
//
// The aggregate route used to rebuild every layer's scored field (EDT
// splat over ~23k cells) inside the same useMemo as the combine, so
// every checkbox/slider tick re-ran ~115 EDT builds (~113 ms) plus the
// combine (~29 ms) on the main thread. This module isolates the
// feeds+grid-dependent stage as a pure function so the page can memo
// it on [feeds, grid] and re-run only the cheap combine on weight
// edits. Math is unchanged: the exact loop the page inlined before.

import { buildScoredField } from "./distanceField";
import { standardFromScoredField, type StandardRaster } from "./standardRaster";
import {
  combineStandardRasters,
  type AggregateField,
  type AggregateInput,
  type CombineMode,
} from "./aggregateRaster";
import { effectiveWeight } from "./aggregateWeights";
import { bonusSpecFor, radiusKmFor, type BBoxLike, type LayerId } from "./layers";

/** Minimal feed shape the build stage needs (page feeds have more). */
export interface AggregateFeed {
  id: LayerId;
  points: { lon: number; lat: number }[];
}

/** One built raster paired with its layer, in feed order. */
export interface BuiltRaster {
  id: LayerId;
  raster: StandardRaster;
}

/**
 * Build one standard raster per feed with usable points. Feeds whose
 * points are all non-finite are skipped (nodata honesty: never faked
 * in). Depends only on feeds + grid — never on weights or mode.
 */
export function buildStandardRasters(
  feeds: AggregateFeed[],
  grid: { cols: number; rows: number; bbox: BBoxLike },
): BuiltRaster[] {
  const out: BuiltRaster[] = [];
  for (const f of feeds) {
    const valid = f.points.filter(
      (p) => Number.isFinite(p.lon) && Number.isFinite(p.lat),
    );
    if (valid.length === 0) continue;
    const scored = buildScoredField(
      valid,
      grid.bbox,
      grid.cols,
      grid.rows,
      radiusKmFor(f.id),
      bonusSpecFor(f.id),
    );
    out.push({ id: f.id, raster: standardFromScoredField(scored) });
  }
  return out;
}

/**
 * Pair built rasters with their effective (layer x category) weights.
 * Zero-weight entries are kept: combineStandardRasters excludes them,
 * same as the old inline path.
 */
export function toCombineInputs(
  built: BuiltRaster[],
  weights: Record<string, number>,
  multipliers: Record<string, number>,
): AggregateInput[] {
  return built.map((b) => ({
    raster: b.raster,
    weight: effectiveWeight(b.id, weights, multipliers),
  }));
}

/**
 * Weight/mode-only recompute over cached rasters: the per-tick path.
 * Pure so tests can lock the pipeline output for every mode.
 */
export function recombineCached(
  built: BuiltRaster[],
  grid: { cols: number; rows: number; bbox: BBoxLike },
  weights: Record<string, number>,
  multipliers: Record<string, number>,
  mode: CombineMode,
): AggregateField | null {
  if (built.length === 0) return null;
  const inputs = toCombineInputs(built, weights, multipliers);
  if (inputs.length === 0) return null;
  return combineStandardRasters(inputs, grid, mode);
}
