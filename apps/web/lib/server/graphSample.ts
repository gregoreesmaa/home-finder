// Foot-graph overlay samples for density layers (walkability/pedinfra/
// cycling), which have no snapshot points file. Served from the local
// 2026-09-12 snapshot sidecar (harju-foot-graph.json) — the same walk
// network the density rasters were snapped to — so the overlay shows the
// base network behind the score, honestly labeled as a sample.
//
// Walkability overlays JUNCTIONS (degree >= 3 distinct neighbors), exactly
// the features resolve_walkability() scores in scripts/walk_raster.py
// (shape points have degree 2 and never count; parallel twin edges share
// one neighbor and count once). Pedinfra/cycling overlay a strided street
// sample: their scored features are footway/cycleway km, which have no
// typed sidecar, so the legend calls this a base-network sample.

import { promises as fs } from "node:fs";
import * as path from "node:path";
import type { BBoxLike } from "../layers";
import type { OverlayPoint } from "../overlays";
import { intersectsCoverage, snapshotDir } from "./snapshot";

export type DensityLayer = "walkability" | "pedinfra" | "cycling";

export function isDensityLayer(layer: string): layer is DensityLayer {
  return layer === "walkability" || layer === "pedinfra" || layer === "cycling";
}

/** [lon, lat] pairs; edges are [nodeA, nodeB, lengthM?] index triples. */
export interface FootGraph {
  nodes: number[][];
  edges: number[][];
}

function isFootGraph(v: unknown): v is FootGraph {
  const g = v as Partial<FootGraph>;
  return (
    typeof g === "object" &&
    g !== null &&
    Array.isArray(g.nodes) &&
    Array.isArray(g.edges)
  );
}

/** Process-lifetime cache: the snapshot is permanent, so no TTL is needed. */
const graphCache = new Map<string, FootGraph | null>();

/** Test hook: forget cached graphs. */
export function clearGraphCache(): void {
  graphCache.clear();
}

/**
 * Load the foot graph sidecar. Null when missing/unreadable — never
 * throws: callers degrade to no overlay, never an error presented as data.
 */
export async function loadFootGraph(dir: string = snapshotDir()): Promise<FootGraph | null> {
  const hit = graphCache.get(dir);
  if (hit !== undefined) return hit;
  let graph: FootGraph | null = null;
  try {
    const raw = await fs.readFile(path.join(dir, "osm", "harju-foot-graph.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (isFootGraph(parsed)) graph = parsed;
  } catch {
    graph = null;
  }
  graphCache.set(dir, graph);
  return graph;
}

/**
 * Junction node indices: >= 3 DISTINCT neighbors (mirrors
 * resolve_walkability in scripts/walk_raster.py). Malformed nodes/edges
 * are skipped, never fatal.
 */
export function findJunctions(nodes: number[][], edges: number[][]): number[] {
  const adj = new Map<number, Set<number>>();
  const nodeCount = nodes.length;
  for (const e of edges) {
    if (!Array.isArray(e) || e.length < 2) continue;
    const [a, b] = e;
    if (!Number.isInteger(a) || !Number.isInteger(b)) continue;
    if (a < 0 || b < 0 || a >= nodeCount || b >= nodeCount || a === b) continue;
    let sa = adj.get(a);
    if (!sa) {
      sa = new Set<number>();
      adj.set(a, sa);
    }
    sa.add(b);
    let sb = adj.get(b);
    if (!sb) {
      sb = new Set<number>();
      adj.set(b, sb);
    }
    sb.add(a);
  }
  const out: number[] = [];
  for (const [k, nbs] of adj) {
    if (nbs.size >= 3) out.push(k);
  }
  out.sort((x, y) => x - y);
  return out;
}

function nodeLonLat(nodes: number[][], i: number): [number, number] | null {
  const n = nodes[i];
  if (!Array.isArray(n) || n.length < 2) return null;
  const [lon, lat] = n;
  if (typeof lon !== "number" || typeof lat !== "number") return null;
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
  return [lon, lat];
}

function inBBox(lon: number, lat: number, bbox: BBoxLike): boolean {
  return lon >= bbox.minlon && lon <= bbox.maxlon && lat >= bbox.minlat && lat <= bbox.maxlat;
}

/**
 * Candidate indices in the bbox -> deterministic stride sample capped at
 * `cap`. Index order is stable (file order / sorted junctions), so the
 * same view always draws the same sample.
 */
export function sampleInBBox(
  nodes: number[][],
  candidates: number[],
  bbox: BBoxLike,
  cap: number,
): OverlayPoint[] {
  const inView: number[] = [];
  for (const i of candidates) {
    const ll = nodeLonLat(nodes, i);
    if (ll && inBBox(ll[0], ll[1], bbox)) inView.push(i);
  }
  if (cap <= 0) return [];
  if (inView.length <= cap) {
    return inView.map((i) => {
      const [lon, lat] = nodeLonLat(nodes, i) as [number, number];
      return { lon, lat, w: 1 };
    });
  }
  const stride = inView.length / cap;
  const out: OverlayPoint[] = [];
  for (let k = 0; k < cap; k++) {
    const [lon, lat] = nodeLonLat(nodes, inView[Math.floor(k * stride)]) as [number, number];
    out.push({ lon, lat, w: 1 });
  }
  return out;
}

function allIndices(n: number): number[] {
  const out = new Array<number>(n);
  for (let i = 0; i < n; i++) out[i] = i;
  return out;
}

/**
 * Overlay points for one density layer in the view bbox, capped.
 * Empty (not null) outside snapshot coverage or when the sidecar is
 * missing — the map renders that as "no overlay", never as zero.
 */
export async function graphOverlayFor(
  layer: DensityLayer,
  bbox: BBoxLike,
  cap: number,
  dir: string = snapshotDir(),
): Promise<OverlayPoint[]> {
  if (!intersectsCoverage(bbox)) return [];
  const graph = await loadFootGraph(dir);
  if (!graph) return [];
  const safeCap = Math.min(2000, Math.max(0, Math.floor(cap)));
  if (layer === "walkability") {
    return sampleInBBox(graph.nodes, findJunctions(graph.nodes, graph.edges), bbox, safeCap);
  }
  return sampleInBBox(graph.nodes, allIndices(graph.nodes.length), bbox, safeCap);
}
