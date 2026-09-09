import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  binListingsToHexes,
  heatLevel,
  hexesFromGeoJSON,
  legendBuckets,
  listingsToPoints,
  MOCK_HEXES,
  nearestHeatPoint,
  pickHeatInput,
  popupText,
  resolveHexes,
  toHeatPoints,
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
