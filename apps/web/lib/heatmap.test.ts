import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  binListingsToHexes,
  buildViewportGrid,
  ESTONIA_BBOX,
  heatLevel,
  heatmapLayerProps,
  hexesFromGeoJSON,
  colorForWeight,
  DETAILED_NEIGHBORHOOD_HEXES,
  interpolateGoodness,
  legendBuckets,
  listingsToPoints,
  mergeHeatData,
  MOCK_HEXES,
  MIN_HEATMAP_COLS,
  MIN_HEATMAP_ROWS,
  nearestHeatPoint,
  pickHeatInput,
  popupText,
  resolutionForZoom,
  resolveHexes,
  toHeatPoints,
  viewportGridDimensions,
} from "./heatmap";

describe("heatmap transform (GET /area-scores -> deck.gl HeatmapLayer)", () => {
  it("thresholds: good>=70, mid 40-69, bad<40", () => {
    expect(heatLevel(70)).toBe("good");
    expect(heatLevel(69)).toBe("mid");
    expect(heatLevel(40)).toBe("mid");
    expect(heatLevel(39)).toBe("bad");
  });

  it("maps hexes to weighted points with level colors", () => {
    const pts = toHeatPoints([
      { h3: "a", score_goodness: 85, lon: 24.75, lat: 59.43 },
      { h3: "b", score_goodness: 55, lon: 26.72, lat: 58.37 },
      { h3: "c", score_goodness: 20, lon: 24.5, lat: 58.38 },
    ]);
    expect(pts.map((p) => p.level)).toEqual(["good", "mid", "bad"]);
    expect(pts[0].weight).toBeCloseTo(0.85);
    expect(pts[2].weight).toBeCloseTo(0.2);
    // goodness and badness both visible: distinct fill colors per level
    const colors = new Set(pts.map((p) => p.fillColor.join(",")));
    expect(colors.size).toBe(3);
    for (const p of pts) {
      expect(p.fillColor).toHaveLength(4);
    }
  });

  it("clamps out-of-range scores to [0,1] weights", () => {
    const pts = toHeatPoints([
      { h3: "x", score_goodness: 140, lon: 0, lat: 0 },
      { h3: "y", score_goodness: -5, lon: 0, lat: 0 },
    ]);
    expect(pts[0].weight).toBe(1);
    expect(pts[1].weight).toBe(0);
  });
});

describe("heatmap binning (listings -> hex cells, weight = livability)", () => {
  it("bins same-cell listings and averages livability", () => {
    const hexes = binListingsToHexes([
      { lon: 24.76, lat: 59.44, livability: 80 },
      { lon: 24.78, lat: 59.45, livability: 90 },
      { lon: 26.72, lat: 58.37, livability: 50 },
    ]);
    expect(hexes).toHaveLength(2);
    const tallinn = hexes.find((h) => h.h3.includes("99:237"));
    expect(tallinn?.score_goodness).toBeCloseTo(85);
    // averaged cell feeds the heat weight end to end
    const pts = toHeatPoints(hexes);
    expect(pts.find((p) => p.h3 === tallinn?.h3)?.weight).toBeCloseTo(0.85);
  });

  it("returns [] for empty or invalid input", () => {
    expect(binListingsToHexes([])).toEqual([]);
    expect(
      binListingsToHexes([{ lon: NaN, lat: 59.4, livability: 80 }]),
    ).toEqual([]);
  });
});

describe("heatmap legend + popup (issue #2)", () => {
  it("legend covers good/mid/bad with distinct colors", () => {
    const buckets = legendBuckets();
    expect(buckets.map((b) => b.level)).toEqual(["good", "mid", "bad"]);
    expect(new Set(buckets.map((b) => b.css)).size).toBe(3);
  });

  it("popup text names the cell, score and level", () => {
    const [pt] = toHeatPoints([MOCK_HEXES[0]]);
    const text = popupText(pt);
    expect(text).toContain("mock-tallinn");
    expect(text).toContain("85");
    expect(text).toContain("hea");
  });

  it("nearestHeatPoint picks the closest cell and nulls out far away", () => {
    const pts = toHeatPoints(MOCK_HEXES);
    expect(nearestHeatPoint(pts, 24.76, 59.44)?.h3).toBe("mock-tallinn");
    expect(nearestHeatPoint(pts, 0, 0)).toBeNull();
  });
});

describe("heat source picker (B1: live cells > binned listings > mock)", () => {
  const live = [{ h3: "db-1", score_goodness: 80, lon: 24.75, lat: 59.43 }];
  const geo = [
    { lon: 24.76, lat: 59.44, score_livability: 80 },
    { lon: 26.72, lat: 58.37, score_livability: 50 },
  ];

  it("prefers live DB cells", () => {
    const p = pickHeatInput(live, true, listingsToPoints(geo), MOCK_HEXES);
    expect(p.source).toBe("cells");
    expect(p.hexes).toEqual(live);
  });

  it("bins geocoded listings when cells are not live", () => {
    const p = pickHeatInput([], false, listingsToPoints(geo), MOCK_HEXES);
    expect(p.source).toBe("listings");
    expect(p.hexes).toHaveLength(2);
  });

  it("falls back to mock only when nothing else exists", () => {
    const p = pickHeatInput([], false, listingsToPoints([]), MOCK_HEXES);
    expect(p.source).toBe("mock");
    expect(p.hexes).toEqual(MOCK_HEXES);
  });

  it("listingsToPoints drops rows without coords or score", () => {
    expect(
      listingsToPoints([
        { lon: 24.7, lat: 59.4, score_livability: 80 },
        { lon: null, lat: 59.4, score_livability: 80 },
        { lon: 24.7, lat: 59.4, score_livability: null },
      ]),
    ).toHaveLength(1);
  });
});

describe("mock GeoJSON fallback (GET /area-scores offline)", () => {
  it("bundled mockHexes.geojson parses to the MOCK_HEXES cells", () => {
    const fc = JSON.parse(
      readFileSync(new URL("./mockHexes.geojson", import.meta.url), "utf-8"),
    );
    const hexes = hexesFromGeoJSON(fc);
    expect(hexes.map((h) => h.h3).sort()).toEqual(
      MOCK_HEXES.map((h) => h.h3).sort(),
    );
    expect(hexesFromGeoJSON({ type: "FeatureCollection", features: [] })).toEqual(
      [],
    );
  });

  it("resolveHexes accepts arrays + GeoJSON, else falls back to mock", () => {
    expect(resolveHexes(MOCK_HEXES, [])).toEqual(MOCK_HEXES);
    const fc = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { h3: "cell-1:2", score_goodness: 70 },
          geometry: { type: "Point", coordinates: [25.0, 58.75] },
        },
        {
          type: "Feature",
          properties: { h3: "broken" },
          geometry: { type: "Point", coordinates: [25.0, 58.75] },
        },
      ],
    };
    expect(resolveHexes(fc, MOCK_HEXES)).toEqual([
      { h3: "cell-1:2", score_goodness: 70, lon: 25.0, lat: 58.75 },
    ]);
    expect(resolveHexes(null, MOCK_HEXES)).toEqual(MOCK_HEXES);
    expect(resolveHexes([], MOCK_HEXES)).toEqual(MOCK_HEXES);
  });
});

describe("zoom-aware continuous surface (no uncolored gaps)", () => {
  const pts = toHeatPoints(MOCK_HEXES);

  it("zoom maps to finer granularity (coarse out, fine detail in)", () => {
    expect(resolutionForZoom(7)).toBeCloseTo(0.25);
    expect(resolutionForZoom(6)).toBeCloseTo(0.5);
    expect(resolutionForZoom(9)).toBeCloseTo(0.0625);
    expect(resolutionForZoom(10)).toBeLessThan(resolutionForZoom(6));
    expect(resolutionForZoom(Number.NaN)).toBeCloseTo(0.25);
    // monotonic: zooming in never yields a coarser step
    let prev = Infinity;
    for (let z = 0; z <= 15; z++) {
      const r = resolutionForZoom(z);
      expect(r).toBeLessThanOrEqual(prev);
      prev = r;
    }
  });

  it("heatmap layer config keeps MEAN with zero threshold at every zoom", () => {
    for (const z of [5, 7, 10, 14]) {
      const p = heatmapLayerProps(z);
      expect(p.aggregation).toBe("MEAN");
      expect(p.threshold).toBe(0);
      expect(p.radiusPixels).toBeGreaterThan(0);
    }
    // radius grows so zoomed-in kernels still overlap into one surface
    expect(heatmapLayerProps(10).radiusPixels).toBeGreaterThan(
      heatmapLayerProps(6).radiusPixels,
    );
  });

  it("interpolation hits cell values exactly and means elsewhere", () => {
    expect(interpolateGoodness(pts, 24.75, 59.43)).toBeCloseTo(85);
    const two = toHeatPoints([
      { h3: "a", score_goodness: 80, lon: 24, lat: 58 },
      { h3: "b", score_goodness: 60, lon: 26, lat: 58 },
    ]);
    expect(interpolateGoodness(two, 25, 58)).toBeCloseTo(70);
    expect(interpolateGoodness([], 25, 58)).toBeNull();
  });

  it("viewport grid covers the full bbox with a color on every cell", () => {
    const grid = buildViewportGrid(pts, ESTONIA_BBOX, 7);
    expect(grid.length).toBeGreaterThan(0);
    // every cell carries a goodness color: no uncolored gaps by construction
    for (const g of grid) {
      expect(Number.isFinite(g.score_goodness)).toBe(true);
      expect(g.level).toBe(heatLevel(g.score_goodness));
      expect(g.fillColor).toHaveLength(4);
      expect(g.weight).toBeGreaterThanOrEqual(0);
      expect(g.weight).toBeLessThanOrEqual(1);
    }
    // tiles the bbox edge to edge: first/last centers sit half a step inside
    const lons = grid.map((g) => g.lon);
    const lats = grid.map((g) => g.lat);
    const cols = new Set(lons.map((v) => v.toFixed(9))).size;
    const rows = new Set(lats.map((v) => v.toFixed(9))).size;
    expect(cols * rows).toBe(grid.length);
    const w = (ESTONIA_BBOX.maxlon - ESTONIA_BBOX.minlon) / cols;
    const h = (ESTONIA_BBOX.maxlat - ESTONIA_BBOX.minlat) / rows;
    expect(Math.min(...lons)).toBeCloseTo(ESTONIA_BBOX.minlon + w / 2, 9);
    expect(Math.max(...lons)).toBeCloseTo(ESTONIA_BBOX.maxlon - w / 2, 9);
    expect(Math.min(...lats)).toBeCloseTo(ESTONIA_BBOX.minlat + h / 2, 9);
    expect(Math.max(...lats)).toBeCloseTo(ESTONIA_BBOX.maxlat - h / 2, 9);
  });

  it("grid refines with zoom: more cells when zoomed in", () => {
    const coarse = buildViewportGrid(pts, ESTONIA_BBOX, 6);
    const fine = buildViewportGrid(pts, ESTONIA_BBOX, 9);
    expect(fine.length).toBeGreaterThan(coarse.length);
  });

  it("one far-flung cell still colors the whole viewport", () => {
    const one = toHeatPoints([
      { h3: "solo", score_goodness: 90, lon: 25, lat: 58.7 },
    ]);
    const grid = buildViewportGrid(one, ESTONIA_BBOX, 8);
    expect(grid.length).toBeGreaterThan(0);
    for (const g of grid) expect(g.score_goodness).toBeCloseTo(90);
  });

  it("guarantees at least 200x100 resolution at any given zoom level", () => {
    // Zoom levels spanning global out to street level, plus non-finite zoom
    const zooms = [-2, 0, 1, 4, 6, 7, 8, 9, 10, 13, 16, 19, Number.NaN];
    for (const z of zooms) {
      const dims = viewportGridDimensions(ESTONIA_BBOX, z);
      expect(dims.cols).toBeGreaterThanOrEqual(MIN_HEATMAP_COLS);
      expect(dims.rows).toBeGreaterThanOrEqual(MIN_HEATMAP_ROWS);
      expect(dims.cols).toBeGreaterThanOrEqual(200);
      expect(dims.rows).toBeGreaterThanOrEqual(100);

      // Verify the generated grid itself also satisfies at least 200x100
      const grid = buildViewportGrid(pts, ESTONIA_BBOX, z);
      expect(grid.length).toBeGreaterThanOrEqual(200 * 100);
      expect(grid.length).toBe(dims.cols * dims.rows);
    }
  });

  it("empty input and degenerate bboxes yield no surface (fallback owns it)", () => {
    expect(buildViewportGrid([], ESTONIA_BBOX, 8)).toEqual([]);
    expect(
      buildViewportGrid(pts, { minlon: 1, minlat: 1, maxlon: 1, maxlat: 1 }, 8),
    ).toEqual([]);
  });

  it("gradient dynamically scales to local worst and best values in Tallinn viewport", () => {
    const tallinnBbox = { minlon: 24.6, minlat: 59.38, maxlon: 24.9, maxlat: 59.48 };
    // Mix of varied neighborhood benchmarks and mock points
    const input = toHeatPoints(mergeHeatData([], []));
    const grid = buildViewportGrid(input, tallinnBbox, 12);

    expect(grid.length).toBeGreaterThanOrEqual(20000);

    // Verify local min and max are captured and not identical
    const localMin = grid[0].localMin!;
    const localMax = grid[0].localMax!;
    expect(Number.isFinite(localMin)).toBe(true);
    expect(Number.isFinite(localMax)).toBe(true);
    expect(localMax).toBeGreaterThan(localMin);

    // Verify weights span the full [0, 1] range (not solid green!)
    const weights = grid.map((g) => g.weight);
    const minW = Math.min(...weights);
    const maxW = Math.max(...weights);
    expect(minW).toBeCloseTo(0, 1);
    expect(maxW).toBeCloseTo(1, 1);

    // Must have distinct contrast: both lower end (<0.33) and upper end (>0.67) represented
    const lowCount = weights.filter((w) => w < 0.33).length;
    const highCount = weights.filter((w) => w > 0.67).length;
    expect(lowCount).toBeGreaterThan(0);
    expect(highCount).toBeGreaterThan(0);
  });

  it("dynamically recomputes based on position when panning between cities", () => {
    const tallinnBbox = { minlon: 24.6, minlat: 59.38, maxlon: 24.9, maxlat: 59.48 };
    const tartuBbox = { minlon: 26.65, minlat: 58.34, maxlon: 26.78, maxlat: 58.42 };

    const data = toHeatPoints(DETAILED_NEIGHBORHOOD_HEXES);
    const tallinnGrid = buildViewportGrid(data, tallinnBbox, 12);
    const tartuGrid = buildViewportGrid(data, tartuBbox, 12);

    // Viewport coordinates match their respective positions
    expect(tallinnGrid[0].lon).toBeLessThan(25.0);
    expect(tartuGrid[0].lon).toBeGreaterThan(26.0);
    expect(tallinnGrid[0].lat).toBeGreaterThan(59.0);
    expect(tartuGrid[0].lat).toBeLessThan(59.0);

    // Both cities have their own local worst and best computed
    expect(tallinnGrid[0].localMax).toBeGreaterThan(tallinnGrid[0].localMin!);
    expect(tartuGrid[0].localMax).toBeGreaterThan(tartuGrid[0].localMin!);
  });

  it("mergeHeatData involves all available data (listings + cells + benchmarks)", () => {
    const cells = [{ h3: "cell-1", score_goodness: 70, lon: 24.7, lat: 59.4 }];
    const listings = [
      { lon: 24.72, lat: 59.44, livability: 85 },
      { lon: 24.80, lat: 59.42, livability: 40 },
    ];
    const merged = mergeHeatData(cells, listings, true);
    expect(merged.length).toBeGreaterThan(cells.length + listings.length);
    // Preserves individual listings
    expect(merged.some((m) => m.score_goodness === 85)).toBe(true);
    expect(merged.some((m) => m.score_goodness === 40)).toBe(true);
    // Preserves area cells
    expect(merged.some((m) => m.h3 === "cell-1")).toBe(true);
  });

  it("legendBuckets adjusts labels to local worst and best range", () => {
    const local = legendBuckets(35, 88);
    expect(local).toHaveLength(3);
    expect(local[0].label).toContain("88");
    expect(local[2].label).toContain("35");
  });

  it("colorForWeight maps weights smoothly across the red-amber-green gradient", () => {
    const worst = colorForWeight(0);
    const mid = colorForWeight(0.5);
    const best = colorForWeight(1.0);
    // Red has high R, low G
    expect(worst[0]).toBeGreaterThan(worst[1]);
    // Green has high G, low R
    expect(best[1]).toBeGreaterThan(best[0]);
    // Mid has high R and high G (amber)
    expect(mid[0]).toBeGreaterThan(200);
    expect(mid[1]).toBeGreaterThan(150);
  });
});
