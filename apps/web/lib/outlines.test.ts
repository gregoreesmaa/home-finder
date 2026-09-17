import { describe, expect, it, vi } from "vitest";
import {
  applyFloodPolygons,
  applyHarbourOverlays,

  applyMaaParcelPolygons,
  applyEelisPolygons,
  applyOutlines,
  applyPointOverlay,
  applySevesoPolygons,
  applySoilPolygons,
  applyStatelandPolygons,
  applyQuarryPolygons,
  applyMaaparandusPolygons,
  applyEtakPolygons,
  applyReliefTint,
  applyCanopyTint,
  applyUsePolygons,
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

describe("applyUsePolygons", () => {
  it("paints casing + band-colored fills with closed rings", () => {
    const map = mockMap();
    applyUsePolygons(map, [{ rings: [RING], color: "#16a34a" }]);
    expect(map.sources.has("planktpr-use-polys")).toBe(true);
    expect(map.layers.has("planktpr-use-casing")).toBe(true);
    expect(map.layers.has("planktpr-use-fill")).toBe(true);
    const src = map.added[0] as {
      data: {
        features: {
          properties: { color: string };
          geometry: { coordinates: number[][][] };
        }[];
      };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.color).toBe("#16a34a");
    const closed = src.data.features[0].geometry.coordinates[0];
    expect(closed[0]).toEqual([24.7, 59.41]);
    expect(closed[closed.length - 1]).toEqual([24.7, 59.41]);
    const fill = map.added.find(
      (l) => (l as { id: string }).id === "planktpr-use-fill",
    ) as { paint: Record<string, unknown> };
    expect(fill.paint["fill-color"]).toEqual(["get", "color"]);
  });

  it("shares one overlay slot with outlines and points (never stacks)", () => {
    const map = mockMap();
    applyOutlines(map, [{ b: [24.7, 59.41, 24.71, 59.42], a: 6.4, r: [RING] }]);
    expect(map.layers.has("park-outline-core")).toBe(true);
    applyUsePolygons(map, [{ rings: [RING], color: "#16a34a" }]);
    expect(map.layers.has("park-outline-core")).toBe(false);
    expect(map.layers.has("planktpr-use-fill")).toBe(true);
    expect(map.sources.has("park-outlines")).toBe(false);
    applyPointOverlay(map, [{ lon: 24.75, lat: 59.43 }], { color: "#1d4ed8" });
    expect(map.layers.has("planktpr-use-fill")).toBe(false);
    expect(map.layers.has("layer-overlay-core")).toBe(true);
    expect(map.sources.has("planktpr-use-polys")).toBe(false);
  });

  it("clears stale layers on nullish input and skips junk rings", () => {
    const map = mockMap();
    map.layers.add("planktpr-use-casing");
    map.layers.add("planktpr-use-fill");
    map.sources.add("planktpr-use-polys");
    applyUsePolygons(map, null);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
    const map2 = mockMap();
    applyUsePolygons(map2, [
      { rings: [[[0, 0]]], color: "#16a34a" },
      { rings: "nope" as unknown as number[][][], color: "#16a34a" },
    ]);
    expect(map2.sources.size).toBe(0);
  });

  it("no-ops before the style loads", () => {
    const map = mockMap(null);
    applyUsePolygons(map, [{ rings: [RING], color: "#16a34a" }]);
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
      // MAAPARCEL-HOOK (#491): parcel fill + casing join the cleared slot.
      "maaparcel-fill",
      "maaparcel-casing",

      // PLANKTPR-HOOK (#492): use-fill layers join the same slot.
      "planktpr-use-casing",
      "planktpr-use-fill",
    ]) {
      map.layers.add(id);
    }
    map.sources.add("park-outlines");
    map.sources.add("layer-overlay-src");
    // MAAPARCEL-HOOK (#491): parcel source joins the cleared slot.
    map.sources.add("maaparcel-polys");
    // PLANKTPR-HOOK (#492): use-fill source joins the same slot.
    map.sources.add("planktpr-use-polys");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });

  // FLOOD-HOOK (#487): flood fill + casing join the cleared slot — one
  // overlay slot paints any kind, never stacks.
  it("removes flood layers at once", () => {
    const map = mockMap();
    map.layers.add("flood-zone-fill");
    map.layers.add("flood-zone-casing");
    map.sources.add("flood-zone-polys");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });

  // EELIS-HOOK (#488): the eelis fill + casing + source join the
  // cleared slot (one overlay slot paints any kind, never stacks).
  it("removes the eelis polygon slot too", () => {
    const map = mockMap();
    map.layers.add("eelis-nature-fill");
    map.layers.add("eelis-nature-casing");
    map.sources.add("eelis-nature-polys");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });

  // SEVESO-HOOK (#613): the danger fill + casing + source join the
  // cleared slot (one overlay slot paints any kind, never stacks).
  // DRAINAGE-HOOK (#616): the network fill + casing + outflow line +
  // both sources join the cleared slot (one overlay slot paints any
  // kind, never stacks).
  it("removes the drainage network slot too", () => {
    const map = mockMap();
    map.layers.add("drainage-network-fill");
    map.layers.add("drainage-network-casing");
    map.layers.add("drainage-outflow-lines");
    map.sources.add("drainage-network-polys");
    map.sources.add("drainage-outflow-lines-src");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });

  it("removes the seveso danger slot too", () => {
    const map = mockMap();
    map.layers.add("seveso-danger-fill");
    map.layers.add("seveso-danger-casing");
    map.sources.add("seveso-danger-polys");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });

  // STATELAND-HOOK (#615): the parcel fill + casing + source join the
  // cleared slot (one overlay slot paints any kind, never stacks).
  it("removes the stateland parcel slot too", () => {
    const map = mockMap();
    map.layers.add("stateland-parcel-fill");
    map.layers.add("stateland-parcel-casing");
    map.sources.add("stateland-parcel-polys");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });

  // QUARRY-HOOK (#614): the permit fill + casing + source join the
  // cleared slot (one overlay slot paints any kind, never stacks).
  it("removes the quarry permit slot too", () => {
    const map = mockMap();
    map.layers.add("quarry-permit-fill");
    map.layers.add("quarry-permit-casing");
    map.sources.add("quarry-permit-polys");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });

  // SOIL-HOOK (#617): the contour fill + casing + source join the
  // cleared slot (one overlay slot paints any kind, never stacks).
  it("removes the soil contour slot too", () => {
    const map = mockMap();
    map.layers.add("soil-contour-fill");
    map.layers.add("soil-contour-casing");
    map.sources.add("soil-contour-polys");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });

  // ETAK-HOOK (#618): the contour fill + casing + source join the
  // cleared slot (one overlay slot paints any kind, never stacks).
  it("removes the etak contour slot too", () => {
    const map = mockMap();
    map.layers.add("etak-contour-fill");
    map.layers.add("etak-contour-casing");
    map.sources.add("etak-contour-polys");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });

  // RELIEF-HOOK (#619): the tint image source + raster layer join the
  // cleared slot (one overlay slot paints any kind, never stacks).
  it("removes the relief tint slot too", () => {
    const map = mockMap();
    map.layers.add("relief-tint-lyr");
    map.sources.add("relief-tint-src");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });

  // CANOPY-HOOK (#620): the tint image source + raster layer join the
  // cleared slot (one overlay slot paints any kind, never stacks).
  it("removes the canopy tint slot too", () => {
    const map = mockMap();
    map.layers.add("canopy-tint-lyr");
    map.sources.add("canopy-tint-src");
    clearVectorOverlays(map);
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
  });
});

describe("applyReliefTint (#619)", () => {
  const GRID = {
    cols: 2,
    rows: 1,
    bbox: { minlon: 24.6, minlat: 59.28, maxlon: 24.7, maxlat: 59.33 },
    vintage: "2026-09-17",
    heights: [10, NaN],
  };

  function stubDom() {
    const putImageData = vi.fn();
    const canvas = {
      width: 0,
      height: 0,
      getContext: () => ({ putImageData }),
      toDataURL: () => "data:image/png;base64,tint",
    };
    vi.stubGlobal("document", { createElement: () => canvas });
    vi.stubGlobal("ImageData", class {
      data: Uint8ClampedArray;
      constructor(data: Uint8ClampedArray) {
        this.data = data;
      }
    });
    return { putImageData, canvas };
  }

  it("paints a taste-only image overlay with county corners", () => {
    const { putImageData } = stubDom();
    try {
      const map = mockMap();
      applyReliefTint(map, GRID);
      expect(map.sources.has("relief-tint-src")).toBe(true);
      expect(map.layers.has("relief-tint-lyr")).toBe(true);
      expect(putImageData).toHaveBeenCalledOnce();
      const src = map.added[0] as {
        type: string;
        url: string;
        coordinates: number[][][];
      };
      expect(src.type).toBe("image");
      expect(src.url).toBe("data:image/png;base64,tint");
      expect(src.coordinates[0]).toEqual([24.6, 59.33]);
      expect(src.coordinates[2]).toEqual([24.7, 59.28]);
      const lyr = map.added.find(
        (l) => (l as { id?: string }).id === "relief-tint-lyr",
      ) as { type: string };
      expect(lyr.type).toBe("raster");
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("is a no-op on nullish grid (outside stays unpainted)", () => {
    stubDom();
    try {
      const map = mockMap();
      applyReliefTint(map, null);
      applyReliefTint(map, undefined);
      expect(map.sources.size).toBe(0);
      expect(map.layers.size).toBe(0);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("applyEelisPolygons (#488)", () => {
  const AREA = {
    kiht: "kaitse" as const,
    zone_id: "KLO-123",
    nimi: "Pirita jõeoru maastikukaitseala",
    lisa: "maastikukaitseala",
    b: [24.83, 59.44, 24.88, 59.48] as [number, number, number, number],
    r: [
      [
        [24.83, 59.44],
        [24.88, 59.44],
        [24.88, 59.48],
      ],
    ],
  };

  it("paints fill + casing layers with closed rings", () => {
    const map = mockMap();
    applyEelisPolygons(map, [AREA], { color: "#1a2e05" });
    expect(map.sources.has("eelis-nature-polys")).toBe(true);
    expect(map.layers.has("eelis-nature-fill")).toBe(true);
    expect(map.layers.has("eelis-nature-casing")).toBe(true);
    const src = map.added[0] as {
      data: { features: { geometry: { coordinates: number[][][][] } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    const closed = src.data.features[0].geometry.coordinates[0][0];
    expect(closed[0]).toEqual([24.83, 59.44]);
    expect(closed[closed.length - 1]).toEqual([24.83, 59.44]);
  });

  it("clears stale layers on nullish input and skips junk rings", () => {
    const map = mockMap();
    map.layers.add("eelis-nature-fill");
    map.layers.add("eelis-nature-casing");
    map.sources.add("eelis-nature-polys");
    applyEelisPolygons(map, null, { color: "#1a2e05" });
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
    const map2 = mockMap();
    applyEelisPolygons(
      map2,
      [{ ...AREA, r: [[[24.83]]] }, { ...AREA, r: [] }],
      { color: "#1a2e05" },
    );
    expect(map2.sources.size).toBe(0);
    expect(map2.layers.size).toBe(0);
  });

  it("no-ops before the style loads", () => {
    const map = mockMap(null);
    applyEelisPolygons(map, [AREA], { color: "#1a2e05" });
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

// FLOOD-HOOK (#487): KAUR flood-zone choropleth fills (polygons only).
describe("applyFloodPolygons", () => {
  const AREA = {
    zone_id: "KR-001",
    nimi: "Mullutu-Suurlaht kogu kalda ulatuses",
    veekogu: "Mullutu-Suurlaht",
    tyyp: "Suurte üleujutusaladega siseveekogu",
    b: [22.0, 58.2, 22.2, 58.3] as [number, number, number, number],
    r: [RING],
  };

  it("paints a translucent fill + white casing with closed rings", () => {
    const map = mockMap();
    applyFloodPolygons(map, [AREA], { color: "#1e3a8a" });
    expect(map.sources.has("flood-zone-polys")).toBe(true);
    expect(map.layers.has("flood-zone-fill")).toBe(true);
    expect(map.layers.has("flood-zone-casing")).toBe(true);
    const src = map.added[0] as {
      data: { features: { geometry: { coordinates: number[][][][] } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    const closed = src.data.features[0].geometry.coordinates[0][0];
    expect(closed[0]).toEqual([24.7, 59.41]);
    expect(closed[closed.length - 1]).toEqual([24.7, 59.41]);
    const fill = map.added.find(
      (l) => (l as { id: string }).id === "flood-zone-fill",
    ) as { paint: Record<string, unknown> };
    expect(fill.paint["fill-color"]).toBe("#1e3a8a");
    expect(fill.paint["fill-opacity"]).toBe(0.25);
  });

  it("clears stale layers on nullish input and skips junk rings", () => {
    const map = mockMap();
    map.layers.add("flood-zone-fill");
    map.sources.add("flood-zone-polys");
    applyFloodPolygons(map, null, { color: "#1e3a8a" });
    expect(map.layers.size).toBe(0);
    expect(map.sources.size).toBe(0);
    const map2 = mockMap();
    applyFloodPolygons(
      map2,
      [{ ...AREA, r: [[[22.0]]] }, { ...AREA, r: [] }],
      { color: "#1e3a8a" },
    );
    expect(map2.sources.size).toBe(0);
  });

  it("no-ops before the style loads", () => {
    const map = mockMap(null);
    applyFloodPolygons(map, [AREA], { color: "#1e3a8a" });
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

describe("applyMaaParcelPolygons (#491)", () => {
  const PARCEL = {
    tunnus: "78401:107:0760",
    cls: "era" as const,
    omvorm: "Eraomand",
    siht1: "ELAMUMAA",
    pindala: 1281,
    aadress: "Roosikrantsi tn 4c",
    kkis: 1,
    b: [24.74, 59.43, 24.75, 59.44] as [number, number, number, number],
    r: [
      [
        [24.74, 59.43],
        [24.75, 59.43],
        [24.75, 59.44],
        [24.74, 59.44],
      ],
    ],
  };

  it("paints class fills + casing with closed rings", () => {
    const map = mockMap();
    applyMaaParcelPolygons(map, [PARCEL], { casing: "#701a75" });
    expect(map.sources.has("maaparcel-polys")).toBe(true);
    expect(map.layers.has("maaparcel-fill")).toBe(true);
    expect(map.layers.has("maaparcel-casing")).toBe(true);
    const src = map.added[0] as {
      data: { features: { properties: { cls: string }; geometry: { coordinates: number[][][][] } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("era");
    const ring = src.data.features[0].geometry.coordinates[0][0];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });

  it("paints the class match expression (facts, never scores)", () => {
    const map = mockMap();
    applyMaaParcelPolygons(map, [PARCEL], { casing: "#701a75" });
    const fill = map.added.find(
      (l) => (l as { id?: string }).id === "maaparcel-fill",
    ) as { paint: { "fill-color": unknown[] } };
    expect(fill.paint["fill-color"][0]).toBe("match");
    expect(fill.paint["fill-color"]).toContain("era");
    expect(fill.paint["fill-color"]).toContain("#22c55e");
  });

  it("folds unknown classes to muu and skips ringless parcels (never faked)", () => {
    const map = mockMap();
    const weird = { ...PARCEL, cls: "feudal" };
    const ringless = { ...PARCEL, tunnus: "x:2", r: [] as number[][][] };
    applyMaaParcelPolygons(
      map,
      [weird as unknown as typeof PARCEL, ringless],
      { casing: "#701a75" },
    );
    const src = map.added[0] as {
      data: { features: { properties: { cls: string } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("muu");
  });

  it("is a no-op on nullish input (outside stays unpainted)", () => {
    const map = mockMap();
    applyMaaParcelPolygons(map, null, { casing: "#701a75" });
    applyMaaParcelPolygons(map, [], { casing: "#701a75" });
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

describe("applySevesoPolygons (#613)", () => {
  const AREA = {
    zone_id: "12.0",
    nimi: "Muuga terminal",
    danger: "toxic" as const,
    danger_label: "Mürgised ained",
    aadress: "Harju maakond, Muuga",
    b: [24.95, 59.48, 24.99, 59.51] as [number, number, number, number],
    r: [
      [
        [24.95, 59.48],
        [24.99, 59.48],
        [24.99, 59.51],
        [24.95, 59.51],
      ],
    ],
  };

  it("paints danger fills + casing with closed rings", () => {
    const map = mockMap();
    applySevesoPolygons(map, [AREA]);
    expect(map.sources.has("seveso-danger-polys")).toBe(true);
    expect(map.layers.has("seveso-danger-fill")).toBe(true);
    expect(map.layers.has("seveso-danger-casing")).toBe(true);
    const src = map.added[0] as {
      data: { features: { properties: { danger: string }; geometry: { coordinates: number[][][][] } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.danger).toBe("toxic");
    const ring = src.data.features[0].geometry.coordinates[0][0];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });

  it("paints the danger match expression (facts, never scores)", () => {
    const map = mockMap();
    applySevesoPolygons(map, [AREA]);
    const fill = map.added.find(
      (l) => (l as { id?: string }).id === "seveso-danger-fill",
    ) as { paint: { "fill-color": unknown[] } };
    expect(fill.paint["fill-color"][0]).toBe("match");
    expect(fill.paint["fill-color"]).toContain("toxic");
    expect(fill.paint["fill-color"]).toContain("#dc2626");
  });

  it("folds unknown dangers to unknown and skips ringless areas (never faked)", () => {
    const map = mockMap();
    const weird = { ...AREA, danger: "radioactive" };
    const ringless = { ...AREA, zone_id: "x:2", r: [] as number[][][] };
    applySevesoPolygons(map, [
      weird as unknown as typeof AREA,
      ringless,
    ]);
    const src = map.added[0] as {
      data: { features: { properties: { danger: string } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.danger).toBe("unknown");
  });

  it("is a no-op on nullish input (outside stays unpainted)", () => {
    const map = mockMap();
    applySevesoPolygons(map, null);
    applySevesoPolygons(map, []);
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

describe("applyHarbourOverlays (#627)", () => {
  const CELL = { lon: 24.75, lat: 59.45, pleasure: 42, all: 100 };
  const PORT = {
    harbour_id: "port-1",
    name: "KALASADAM",
    function: 3,
    function_label: "tasuta",
    address: "Tallinn",
    lon: 24.74,
    lat: 59.44,
  };

  it("paints cell fills + casing + port dots in one pass (never stacked)", () => {
    const map = mockMap();
    applyHarbourOverlays(map, [CELL], [PORT], { color: "#115e59" });
    expect(map.sources.has("harbour-cell-polys")).toBe(true);
    expect(map.layers.has("harbour-cell-fill")).toBe(true);
    expect(map.layers.has("harbour-cell-casing")).toBe(true);
    expect(map.sources.has("layer-overlay-src")).toBe(true);
    expect(map.layers.has("layer-overlay-casing")).toBe(true);
    expect(map.layers.has("layer-overlay-core")).toBe(true);
    // One clear pass: every id removed at most once (cells + dots share
    // the slot instead of wiping each other — two stacked painters
    // would clear twice).
    expect(new Set(map.removedLayers).size).toBe(map.removedLayers.length);
  });

  it("paints whichever half has data (cells-only, ports-only)", () => {
    const cellsOnly = mockMap();
    applyHarbourOverlays(cellsOnly, [CELL], [], { color: "#115e59" });
    expect(cellsOnly.layers.has("harbour-cell-fill")).toBe(true);
    expect(cellsOnly.layers.has("layer-overlay-core")).toBe(false);
    const portsOnly = mockMap();
    applyHarbourOverlays(portsOnly, [], [PORT], { color: "#115e59" });
    expect(portsOnly.layers.has("harbour-cell-fill")).toBe(false);
    expect(portsOnly.layers.has("layer-overlay-core")).toBe(true);
  });

  it("skips junk records, never faked", () => {
    const map = mockMap();
    const junkCell = { lon: Number.NaN, lat: 59.45, pleasure: 5, all: 9 };
    const junkPort = { ...PORT, harbour_id: "x", lon: Number.POSITIVE_INFINITY };
    applyHarbourOverlays(
      map,
      [junkCell, CELL],
      [junkPort, PORT],
      { color: "#115e59" },
    );
    const cellSrc = map.added.find(
      (s) => (s as { type?: string }).type === "geojson" && (s as { data: { features: { geometry: { type: string } }[] } }).data.features[0]?.geometry.type === "MultiPolygon",
    ) as { data: { features: unknown[] } };
    expect(cellSrc.data.features).toHaveLength(1);
  });

  it("is a no-op on nullish input (outside stays unpainted)", () => {
    const map = mockMap();
    applyHarbourOverlays(map, null, null, { color: "#115e59" });
    applyHarbourOverlays(map, [], [], { color: "#115e59" });
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

describe("applyStatelandPolygons (#615)", () => {
  const AREA = {
    zone_id: "78401:101:0123",
    nimi: "",
    cls: "state" as const,
    tunnus: "78401:101:0123",
    valitseja: "Kliimaministeerium",
    deadline: "",
    purpose: "",
    url: "",
    b: [24.74, 59.43, 24.75, 59.44] as [number, number, number, number],
    r: [
      [
        [24.74, 59.43],
        [24.75, 59.43],
        [24.75, 59.44],
        [24.74, 59.44],
      ],
    ],
  };

  it("paints parcel fills + casing with closed rings", () => {
    const map = mockMap();
    applyStatelandPolygons(map, [AREA]);
    expect(map.sources.has("stateland-parcel-polys")).toBe(true);
    expect(map.layers.has("stateland-parcel-fill")).toBe(true);
    expect(map.layers.has("stateland-parcel-casing")).toBe(true);
    const src = map.added[0] as {
      data: { features: { properties: { cls: string }; geometry: { coordinates: number[][][][] } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("state");
    const ring = src.data.features[0].geometry.coordinates[0][0];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });

  it("paints the class match expression (facts, never scores)", () => {
    const map = mockMap();
    applyStatelandPolygons(map, [AREA]);
    const fill = map.added.find(
      (l) => (l as { id?: string }).id === "stateland-parcel-fill",
    ) as { paint: { "fill-color": unknown[] } };
    expect(fill.paint["fill-color"][0]).toBe("match");
    expect(fill.paint["fill-color"]).toContain("state");
    expect(fill.paint["fill-color"]).toContain("#4d7c0f");
  });

  it("folds unknown classes to state and skips ringless areas (never faked)", () => {
    const map = mockMap();
    const weird = { ...AREA, cls: "private" };
    const ringless = { ...AREA, zone_id: "x:2", r: [] as number[][][] };
    applyStatelandPolygons(map, [
      weird as unknown as typeof AREA,
      ringless,
    ]);
    const src = map.added[0] as {
      data: { features: { properties: { cls: string } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("state");
  });

  it("is a no-op on nullish input (outside stays unpainted)", () => {
    const map = mockMap();
    applyStatelandPolygons(map, null);
    applyStatelandPolygons(map, []);
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

describe("applyQuarryPolygons (#614)", () => {
  const AREA = {
    zone_id: "13379",
    nimi: "Huntaugu I liivakarjäär",
    cls: "active" as const,
    loa: "HARM-139",
    loa_lopp: "20310301",
    operaator: "AS TREV-2 Grupp",
    b: [25.36, 59.42, 25.38, 59.44] as [number, number, number, number],
    r: [
      [
        [25.36, 59.42],
        [25.38, 59.42],
        [25.38, 59.44],
        [25.36, 59.44],
      ],
    ],
  };

  it("paints permit fills + casing with closed rings", () => {
    const map = mockMap();
    applyQuarryPolygons(map, [AREA]);
    expect(map.sources.has("quarry-permit-polys")).toBe(true);
    expect(map.layers.has("quarry-permit-fill")).toBe(true);
    expect(map.layers.has("quarry-permit-casing")).toBe(true);
    const src = map.added[0] as {
      data: { features: { properties: { cls: string }; geometry: { coordinates: number[][][][] } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("active");
    const ring = src.data.features[0].geometry.coordinates[0][0];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });

  it("paints the class match expression (facts, never scores)", () => {
    const map = mockMap();
    applyQuarryPolygons(map, [AREA]);
    const fill = map.added.find(
      (l) => (l as { id?: string }).id === "quarry-permit-fill",
    ) as { paint: { "fill-color": unknown[] } };
    expect(fill.paint["fill-color"][0]).toBe("match");
    expect(fill.paint["fill-color"]).toContain("active");
    expect(fill.paint["fill-color"]).toContain("#c2410c");
  });

  it("folds unknown classes to exploration and skips ringless areas (never faked)", () => {
    const map = mockMap();
    const weird = { ...AREA, cls: "pending" };
    const ringless = { ...AREA, zone_id: "x:2", r: [] as number[][][] };
    applyQuarryPolygons(map, [
      weird as unknown as typeof AREA,
      ringless,
    ]);
    const src = map.added[0] as {
      data: { features: { properties: { cls: string } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("exploration");
  });

  it("is a no-op on nullish input (outside stays unpainted)", () => {
    const map = mockMap();
    applyQuarryPolygons(map, null);
    applyQuarryPolygons(map, []);
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

describe("applySoilPolygons (#617)", () => {
  const AREA = {
    zone_id: "muld_0062DCE0",
    family: "liivsavi",
    cls: "liivsavi" as const,
    score: 65,
    code: "ls₂;l50-100/s",
    b: [24.6, 59.28, 24.7, 59.33] as [number, number, number, number],
    r: [
      [
        [24.6, 59.28],
        [24.7, 59.28],
        [24.7, 59.33],
        [24.6, 59.28],
      ],
    ],
  };

  it("paints contour fills + casing with closed rings", () => {
    const map = mockMap();
    applySoilPolygons(map, [AREA]);
    expect(map.sources.has("soil-contour-polys")).toBe(true);
    expect(map.layers.has("soil-contour-fill")).toBe(true);
    expect(map.layers.has("soil-contour-casing")).toBe(true);
    const src = map.added[0] as {
      data: { features: { properties: { cls: string }; geometry: { coordinates: number[][][][] } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("liivsavi");
    const ring = src.data.features[0].geometry.coordinates[0][0];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });

  it("paints the family match expression (facts, never scores)", () => {
    const map = mockMap();
    applySoilPolygons(map, [AREA]);
    const fill = map.added.find(
      (l) => (l as { id?: string }).id === "soil-contour-fill",
    ) as { paint: { "fill-color": unknown[] } };
    expect(fill.paint["fill-color"][0]).toBe("match");
    expect(fill.paint["fill-color"]).toContain("saviliiv");
    expect(fill.paint["fill-color"]).toContain("turvas");
    expect(fill.paint["fill-color"]).toContain("#84cc16");
  });

  it("folds unknown classes to liiv and skips ringless areas (never faked)", () => {
    const map = mockMap();
    const weird = { ...AREA, cls: "chernozem" };
    const ringless = { ...AREA, zone_id: "x:2", r: [] as number[][][] };
    applySoilPolygons(map, [
      weird as unknown as typeof AREA,
      ringless,
    ]);
    const src = map.added[0] as {
      data: { features: { properties: { cls: string } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("liiv");
  });

  it("is a no-op on nullish input (outside stays unpainted)", () => {
    const map = mockMap();
    applySoilPolygons(map, null);
    applySoilPolygons(map, []);
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

describe("applyMaaparandusPolygons (#616)", () => {
  const AREA = {
    zone_id: "5111040011290",
    nimi: "Allika5",
    cls: "network" as const,
    ms_kood: "5111040011290",
    ms_url: "https://portaal.agri.ee/avalik/#/maaparandus/systeem/5111040011290",
    b: [24.74, 59.43, 24.75, 59.44] as [number, number, number, number],
    r: [
      [
        [24.74, 59.43],
        [24.75, 59.43],
        [24.75, 59.44],
        [24.74, 59.44],
      ],
    ],
  };
  const LINE = {
    zone_id: "7",
    nimi: "Kraav",
    cls: "outflow" as const,
    ms_kood: "1",
    ms_url: "",
    b: [24.76, 59.43, 24.77, 59.44] as [number, number, number, number],
    l: [
      [
        [24.76, 59.43],
        [24.77, 59.44],
      ],
    ],
  };

  it("paints network fills + casing with closed rings", () => {
    const map = mockMap();
    applyMaaparandusPolygons(map, [AREA]);
    expect(map.sources.has("drainage-network-polys")).toBe(true);
    expect(map.layers.has("drainage-network-fill")).toBe(true);
    expect(map.layers.has("drainage-network-casing")).toBe(true);
    const src = map.added[0] as {
      data: { features: { properties: { cls: string }; geometry: { coordinates: number[][][][] } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("network");
    const ring = src.data.features[0].geometry.coordinates[0][0];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });

  it("paints the class match expression (facts, never scores)", () => {
    const map = mockMap();
    applyMaaparandusPolygons(map, [AREA]);
    const fill = map.added.find(
      (l) => (l as { id?: string }).id === "drainage-network-fill",
    ) as { paint: { "fill-color": unknown[] } };
    expect(fill.paint["fill-color"][0]).toBe("match");
    expect(fill.paint["fill-color"]).toContain("invalid");
    expect(fill.paint["fill-color"]).toContain("#92400e");
  });

  it("paints outflow centerlines with no fill (band stays scorer-side)", () => {
    const map = mockMap();
    applyMaaparandusPolygons(map, [LINE]);
    expect(map.layers.has("drainage-outflow-lines")).toBe(true);
    expect(map.layers.has("drainage-network-fill")).toBe(false);
    const line = map.added.find(
      (l) => (l as { id?: string }).id === "drainage-outflow-lines",
    ) as { type: string; paint: { "fill-color"?: unknown; "line-color": unknown } };
    expect(line.type).toBe("line");
    expect(line.paint["fill-color"]).toBeUndefined();
    expect(line.paint["line-color"]).toBe("#38bdf8");
  });

  it("folds unknown classes to network and skips shapeless areas (never faked)", () => {
    const map = mockMap();
    const weird = { ...AREA, cls: "ditch" };
    const shapeless = { ...AREA, zone_id: "x:2", r: [] as number[][][] };
    applyMaaparandusPolygons(map, [
      weird as unknown as typeof AREA,
      shapeless,
    ]);
    const src = map.added[0] as {
      data: { features: { properties: { cls: string } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("network");
  });

  it("is a no-op on nullish input (outside stays unpainted)", () => {
    const map = mockMap();
    applyMaaparandusPolygons(map, null);
    applyMaaparandusPolygons(map, []);
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

describe("applyEtakPolygons (#618)", () => {
  const AREA = {
    zone_id: "etak:8824",
    theme: "wetland" as const,
    cls: "wet_wettest" as const,
    score: 25,
    label: "Raba",
    name: "Ellamaa raba",
    vintage: "2024-06-01",
    b: [24.62, 59.3, 24.64, 59.31] as [number, number, number, number],
    r: [
      [
        [24.62, 59.3],
        [24.64, 59.3],
        [24.64, 59.31],
        [24.62, 59.3],
      ],
    ],
  };

  it("paints class fills + casing with closed rings", () => {
    const map = mockMap();
    applyEtakPolygons(map, [AREA]);
    expect(map.sources.has("etak-contour-polys")).toBe(true);
    expect(map.layers.has("etak-contour-fill")).toBe(true);
    expect(map.layers.has("etak-contour-casing")).toBe(true);
    const src = map.added[0] as {
      data: { features: { properties: { cls: string }; geometry: { coordinates: number[][][][] } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("wet_wettest");
    const ring = src.data.features[0].geometry.coordinates[0][0];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });

  it("paints the class match expression (facts, never scores)", () => {
    const map = mockMap();
    applyEtakPolygons(map, [AREA]);
    const fill = map.added.find(
      (l) => (l as { id?: string }).id === "etak-contour-fill",
    ) as { paint: { "fill-color": unknown[] } };
    expect(fill.paint["fill-color"][0]).toBe("match");
    expect(fill.paint["fill-color"]).toContain("wet_wettest");
    expect(fill.paint["fill-color"]).toContain("#0c4a6e");
    expect(fill.paint["fill-color"]).toContain("yard_green");
    expect(fill.paint["fill-color"]).toContain("#4ade80");
  });

  it("folds unknown classes to wet_other and skips shapeless areas (never faked)", () => {
    const map = mockMap();
    const weird = { ...AREA, cls: "bog" };
    const shapeless = { ...AREA, zone_id: "x:2", r: [] as number[][][] };
    applyEtakPolygons(map, [
      weird as unknown as typeof AREA,
      shapeless,
    ]);
    const src = map.added[0] as {
      data: { features: { properties: { cls: string } }[] };
    };
    expect(src.data.features).toHaveLength(1);
    expect(src.data.features[0].properties.cls).toBe("wet_other");
  });

  it("is a no-op on nullish input (outside stays unpainted)", () => {
    const map = mockMap();
    applyEtakPolygons(map, null);
    applyEtakPolygons(map, []);
    expect(map.sources.size).toBe(0);
    expect(map.layers.size).toBe(0);
  });
});

describe("applyCanopyTint (#620)", () => {
  const GRID = {
    cols: 2,
    rows: 1,
    bbox: { minlon: 24.6, minlat: 59.28, maxlon: 24.7, maxlat: 59.33 },
    vintage: "2022-suvi",
    classes: [3, 0],
  };

  function stubDom() {
    const putImageData = vi.fn();
    const canvas = {
      width: 0,
      height: 0,
      getContext: () => ({ putImageData }),
      toDataURL: () => "data:image/png;base64,tint",
    };
    vi.stubGlobal("document", { createElement: () => canvas });
    vi.stubGlobal("ImageData", class {
      data: Uint8ClampedArray;
      constructor(data: Uint8ClampedArray) {
        this.data = data;
      }
    });
    return { putImageData, canvas };
  }

  it("paints a taste-only image overlay with county corners", () => {
    const { putImageData } = stubDom();
    try {
      const map = mockMap();
      applyCanopyTint(map, GRID);
      expect(map.sources.has("canopy-tint-src")).toBe(true);
      expect(map.layers.has("canopy-tint-lyr")).toBe(true);
      expect(putImageData).toHaveBeenCalledOnce();
      const src = map.added[0] as {
        type: string;
        url: string;
        coordinates: number[][][];
      };
      expect(src.type).toBe("image");
      expect(src.url).toBe("data:image/png;base64,tint");
      expect(src.coordinates[0]).toEqual([24.6, 59.33]);
      expect(src.coordinates[2]).toEqual([24.7, 59.28]);
      const lyr = map.added.find(
        (l) => (l as { id?: string }).id === "canopy-tint-lyr",
      ) as { type: string };
      expect(lyr.type).toBe("raster");
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("is a no-op on nullish grid (outside stays unpainted)", () => {
    stubDom();
    try {
      const map = mockMap();
      applyCanopyTint(map, null);
      applyCanopyTint(map, undefined);
      expect(map.sources.size).toBe(0);
      expect(map.layers.size).toBe(0);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
