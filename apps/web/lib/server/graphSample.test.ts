import { promises as fs } from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  clearGraphCache,
  findJunctions,
  graphOverlayFor,
  isDensityLayer,
  loadFootGraph,
  sampleInBBox,
} from "./graphSample";

// Tiny cross: node 0 is a 4-way junction, 1..4 are dead ends, 5..6 a
// degree-2 shape segment. Parallel twin 0-1 edges share one neighbor.
const NODES = [
  [24.75, 59.43], // 0 junction
  [24.76, 59.43], // 1
  [24.75, 59.44], // 2
  [24.74, 59.43], // 3
  [24.75, 59.42], // 4
  [24.9, 59.5], // 5 shape
  [24.91, 59.5], // 6 shape
  [30.0, 60.0], // 7 far away (out of view)
];
const EDGES = [
  [0, 1, 10],
  [0, 1, 10], // parallel twin: still one neighbor
  [0, 2, 10],
  [0, 3, 10],
  [0, 4, 10],
  [5, 6, 10],
  [6, 7, 10],
];

const VIEW = { minlon: 24.7, minlat: 59.4, maxlon: 24.95, maxlat: 59.55 };

afterEach(() => clearGraphCache());

describe("foot-graph junctions", () => {
  it("finds degree>=3 nodes, ignoring shape points and twin edges", () => {
    expect(findJunctions(NODES, EDGES)).toEqual([0]);
  });

  it("skips malformed edges without failing", () => {
    expect(findJunctions(NODES, [...EDGES, [0, 99, 1], [-1, 2, 1], [3, 3, 1] as never])).toEqual([
      0,
    ]);
    expect(findJunctions(NODES, "nope" as unknown as number[][])).toEqual([]);
  });
});

describe("bbox sampling", () => {
  it("filters to the view and stride-caps deterministically", () => {
    const all = [0, 1, 2, 3, 4, 5, 6, 7];
    const capped = sampleInBBox(NODES, all, VIEW, 3);
    expect(capped).toHaveLength(3);
    for (const p of capped) {
      expect(p.lon).toBeGreaterThanOrEqual(VIEW.minlon);
      expect(p.lat).toBeLessThanOrEqual(VIEW.maxlat);
      expect(p.w).toBe(1);
    }
    expect(sampleInBBox(NODES, all, VIEW, 3)).toEqual(capped);
    // Small sets pass through whole.
    expect(sampleInBBox(NODES, [0], VIEW, 800)).toEqual([{ lon: 24.75, lat: 59.43, w: 1 }]);
    expect(sampleInBBox(NODES, all, VIEW, 0)).toEqual([]);
  });
});

describe("density layer routing", () => {
  it("sends only walkability/pedinfra/cycling to the graph sidecar", () => {
    expect(isDensityLayer("walkability")).toBe(true);
    expect(isDensityLayer("pedinfra")).toBe(true);
    expect(isDensityLayer("cycling")).toBe(true);
    expect(isDensityLayer("parks")).toBe(false);
    expect(isDensityLayer("transit")).toBe(false);
  });
});

async function fixtureDir(): Promise<string> {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "hf-graph-"));
  await fs.mkdir(path.join(dir, "osm"), { recursive: true });
  await fs.writeFile(
    path.join(dir, "osm", "harju-foot-graph.json"),
    JSON.stringify({ directed: false, nodes: NODES, edges: EDGES }),
  );
  return dir;
}

describe("graphOverlayFor (snapshot sidecar)", () => {
  it("serves walkability junctions in view", async () => {
    const pts = await graphOverlayFor("walkability", VIEW, 800, await fixtureDir());
    expect(pts).toEqual([{ lon: 24.75, lat: 59.43, w: 1 }]);
  });

  it("serves a capped street sample for pedinfra/cycling", async () => {
    const dir = await fixtureDir();
    const ped = await graphOverlayFor("pedinfra", VIEW, 800, dir);
    expect(ped.length).toBeGreaterThan(1);
    const cyc = await graphOverlayFor("cycling", VIEW, 2, dir);
    expect(cyc).toHaveLength(2);
  });

  it("is honestly empty outside coverage or without a sidecar", async () => {
    const dir = await fixtureDir();
    const far = { minlon: 10, minlat: 50, maxlon: 11, maxlat: 51 };
    await expect(graphOverlayFor("walkability", far, 800, dir)).resolves.toEqual([]);
    const missing = await fs.mkdtemp(path.join(os.tmpdir(), "hf-graph-missing-"));
    await expect(graphOverlayFor("cycling", VIEW, 800, missing)).resolves.toEqual([]);
    await expect(loadFootGraph(missing)).resolves.toBeNull();
  });
});
