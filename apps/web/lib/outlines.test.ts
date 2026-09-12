import { describe, expect, it, vi } from "vitest";
import { applyOutlines, type OutlineMap } from "./outlines";

function mockMap(style: unknown = {}): OutlineMap & {
  added: unknown[];
  removedLayers: string[];
  removedSources: string[];
  layers: Set<string>;
  sources: Set<string>;
} {
  const m = {
    added: [] as unknown[],
    removedLayers: [] as string[],
    removedSources: [] as string[],
    layers: new Set<string>(),
    sources: new Set<string>(),
    getStyle: () => style,
    addSource: vi.fn((id: string, src: unknown) => {
      m.sources.add(id);
      m.added.push(src);
    }),
    addLayer: vi.fn((l: unknown) => {
      const id = (l as { id: string }).id;
      m.layers.add(id);
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
