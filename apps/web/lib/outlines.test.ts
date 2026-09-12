import { describe, expect, it, vi } from "vitest";
import {
  applyOutlines,
  applyPointOverlay,
  clearVectorOverlays,
  type OutlineMap,
} from "./outlines";

function mockMap(style: unknown = {}): OutlineMap & {
  added: unknown[];
  beforeIds: (string | undefined)[];
  removedLayers: string[];
  removedSources: string[];
  layers: Set<string>;
  sources: Set<string>;
} {
  const m = {
    added: [] as unknown[],
    beforeIds: [] as (string | undefined)[],
    removedLayers: [] as string[],
    removedSources: [] as string[],
    layers: new Set<string>(),
    sources: new Set<string>(),
    getStyle: () => style,
    addSource: vi.fn((id: string, src: unknown) => {
      m.sources.add(id);
      m.added.push(src);
    }),
    addLayer: vi.fn((l: unknown, beforeId?: string) => {
      const id = (l as { id: string }).id;
      m.layers.add(id);
      m.beforeIds.push(beforeId);
      m.added.push(l);
    }),
    removeLayer: vi.fn((id: string) => {
      m.removedLayers.push(id);
      m.layers.delete(id);
    }),
    removeSource: vi.fn((id: string) => {
      m.removedSources.push(id);
      m.sources.delete(id);
    }),
    getLayer: (id: string) => (m.layers.has(id) ? {} : undefined),
    getSource: (id: string) => (m.sources.has(id) ? {} : undefined),
  };
  return m;
}

const RING = [
  [24.7, 59.41],
  [24.71, 59.41],
  [24.71, 59.42],
];

describe("applyOutlines", () => {
  it("paints casing + core line layers with closed rings", () => {
    const map = mockMap();
    applyOutlines(map, [{ b: [24.7, 59.41, 24.71, 59.42], a: 6.4, r: [RING] }]);
    expect(map.sources.has("park-outlines")).toBe(true);
    expect(map.layers.has("park-outline-casing")).toBe(true);
    expect(map.layers.has("park-outline-core")).toBe(true);
    const src = map.added[0] as {
      data: { features: { geometry: { coordinates: number[][][] } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    const closed = src.data.features[0].geometry.coordinates[0];
    expect(closed[0]).toEqual([24.7, 59.41]);
    expect(closed[closed.length - 1]).toEqual([24.7, 59.41]);
  });

  it("clears stale layers on nullish input and skips junk rings", () => {
    const map = mockMap();
    map.layers.add("park-outline-casing");
    map.layers.add("park-outline-core");
    map.sources.add("park-outlines");
    applyOutlines(map, null);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
    const map2 = mockMap();
    applyOutlines(map2, [
      { b: [0, 0, 1, 1], a: 1, r: [[[0, 0]]] },
      { b: [0, 0, 1, 1], a: 1, r: "nope" as unknown as number[][][] },
    ]);
    expect(map2.sources.size).toBe(0);
  });

  it("no-ops before the style loads", () => {
    const map = mockMap(null);
    applyOutlines(map, [{ b: [0, 0, 1, 1], a: 1, r: [RING] }]);
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

describe("applyPointOverlay", () => {
  it("paints casing + core circle layers with weights and color", () => {
    const map = mockMap();
    applyPointOverlay(map, [
      { lon: 24.75, lat: 59.43, w: 974 },
      { lon: 24.76, lat: 59.44 },
    ], { color: "#1d4ed8" });
    expect(map.sources.has("layer-overlay-src")).toBe(true);
    expect(map.layers.has("layer-overlay-casing")).toBe(true);
    expect(map.layers.has("layer-overlay-core")).toBe(true);
    const src = map.added[0] as {
      data: { features: { properties: { w: number }; geometry: { coordinates: number[] } }[] };
    };
    expect(src.data.features).toHaveLength(2);
    expect(src.data.features[0].properties.w).toBe(974);
    // Missing weight still draws (unknown is not bad).
    expect(src.data.features[1].properties.w).toBe(1);
    const core = map.added[2] as { paint: Record<string, unknown> };
    expect(core.paint["circle-color"]).toBe("#1d4ed8");
    // Radius is data-driven off the weight (transit hubs read bigger).
    expect(JSON.stringify(core.paint["circle-radius"])).toContain('"get","w"');
  });

  it("sits under street labels when the style has them", () => {
    const map = mockMap({
      layers: [
        { id: "road", type: "line" },
        { id: "label", type: "symbol" },
      ],
    });
    applyPointOverlay(map, [{ lon: 24.75, lat: 59.43 }], { color: "#1d4ed8" });
    expect(map.beforeIds).toEqual(["label", "label"]);
  });

  it("sits above buildings when an early symbol sits under the fills", () => {
    const map = mockMap({
      layers: [
        { id: "early-poi", type: "symbol" },
        { id: "building", type: "fill" },
        { id: "road", type: "line" },
        { id: "label", type: "symbol" },
      ],
    });
    applyPointOverlay(map, [{ lon: 24.75, lat: 59.43 }], { color: "#1d4ed8" });
    // Before the label block, NOT before the early symbol (that buries dots).
    expect(map.beforeIds).toEqual(["label", "label"]);
  });

  it("goes topmost when paint runs to the top, bottom with paint-free styles", () => {
    const top = mockMap({
      layers: [
        { id: "early-poi", type: "symbol" },
        { id: "building", type: "fill" },
      ],
    });
    applyPointOverlay(top, [{ lon: 24.75, lat: 59.43 }], { color: "#1d4ed8" });
    expect(top.beforeIds).toEqual([undefined, undefined]);
    const bare = mockMap({ layers: [{ id: "label", type: "symbol" }] });
    applyPointOverlay(bare, [{ lon: 24.75, lat: 59.43 }], { color: "#1d4ed8" });
    expect(bare.beforeIds).toEqual(["label", "label"]);
  });

  it("shares one overlay slot with park outlines (never stacks)", () => {
    const map = mockMap();
    applyOutlines(map, [{ b: [24.7, 59.41, 24.71, 59.42], a: 6.4, r: [RING] }]);
    expect(map.layers.has("park-outline-core")).toBe(true);
    applyPointOverlay(map, [{ lon: 24.75, lat: 59.43 }], { color: "#1d4ed8" });
    expect(map.layers.has("park-outline-core")).toBe(false);
    expect(map.layers.has("layer-overlay-core")).toBe(true);
    expect(map.sources.has("park-outlines")).toBe(false);
    applyOutlines(map, [{ b: [24.7, 59.41, 24.71, 59.42], a: 6.4, r: [RING] }]);
    expect(map.layers.has("layer-overlay-core")).toBe(false);
    expect(map.layers.has("park-outline-core")).toBe(true);
  });

  it("clears stale layers on nullish input and skips junk points", () => {
    const map = mockMap();
    map.layers.add("layer-overlay-casing");
    map.layers.add("layer-overlay-core");
    map.sources.add("layer-overlay-src");
    applyPointOverlay(map, null, { color: "#1d4ed8" });
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
    const map2 = mockMap();
    applyPointOverlay(
      map2,
      [
        { lon: NaN, lat: 59.43 },
        { lon: 24.75, lat: Infinity },
        null as unknown as { lon: number; lat: number },
      ],
      { color: "#1d4ed8" },
    );
    expect(map2.sources.size).toBe(0);
  });

  it("no-ops before the style loads", () => {
    const map = mockMap(null);
    applyPointOverlay(map, [{ lon: 24.75, lat: 59.43 }], { color: "#1d4ed8" });
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

describe("clearVectorOverlays", () => {
  it("removes both overlay kinds at once", () => {
    const map = mockMap();
    for (const id of [
      "park-outline-casing",
      "park-outline-core",
      "layer-overlay-casing",
      "layer-overlay-core",
    ]) {
      map.layers.add(id);
    }
    map.sources.add("park-outlines");
    map.sources.add("layer-overlay-src");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });
});
