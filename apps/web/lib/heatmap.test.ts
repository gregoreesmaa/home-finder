import { describe, expect, it } from "vitest";
import { heatLevel, toHeatPoints } from "./heatmap";

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
