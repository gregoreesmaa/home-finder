import { describe, expect, it } from "vitest";
import {
  DATEX_BONUS,
  DATEX_DECAY,
  DATEX_DEFS,
  DATEX_HOOK,
  DATEX_LAYER_IDS,
  DATEX_NO_METRO,
  DATEX_POLE_DATASET,
  DATEX_RASTER_FILE,
  DATEX_TAGS,
  DATEX_TTL_S,
  bonusSpecForDatex,
  datexPointsForLayer,
  datexStatusNoun,
  isDatexGeoLayer,
  isDatexLayerId,
} from "./layers_datex";

describe("datex registry (#763)", () => {
  it("defines exactly the six DATEX overlays", () => {
    expect(DATEX_LAYER_IDS).toEqual([
      "datex-restrictions",
      "datex-srti",
      "datex-weather",
      "datex-counters",
      "datex-cameras",
      "datex-truckpark",
    ]);
    expect(DATEX_DEFS.map((d) => d.id)).toEqual(DATEX_LAYER_IDS);
    expect(DATEX_HOOK).toMatch(/DATEX-HOOK \(#763\)/);
  });

  it("binds P4 slice labels (never parameters3 numbers)", () => {
    for (const d of DATEX_DEFS) {
      expect(d.paramIds).toEqual([]);
      expect(typeof d.paramLabel).toBe("string");
    }
    expect(DATEX_DEFS[0].paramLabel).toBe("P4-piirangud");
  });

  it("pins pole datasets and harvester-parity TTLs", () => {
    expect(DATEX_POLE_DATASET["datex-weather"]).toBe("datex-weather");
    expect(DATEX_TTL_S).toEqual({
      "datex-restrictions": 24 * 3600,
      "datex-srti": 6 * 3600,
      "datex-weather": 1 * 3600,
      "datex-counters": 1 * 3600,
      "datex-cameras": 1 * 3600,
      "datex-truckpark": 30 * 24 * 3600,
    });
  });

  it("scores markers only (no field)", () => {
    for (const id of DATEX_LAYER_IDS) {
      expect(DATEX_BONUS[id]).toEqual({ kind: "pins" });
      expect(bonusSpecForDatex(id)).toEqual({ kind: "pins" });
    }
    expect(bonusSpecForDatex("transit")).toBeUndefined();
    expect(isDatexLayerId("datex-cameras")).toBe(true);
    expect(isDatexLayerId("busmesh")).toBe(false);
  });

  it("declares decay/tags/raster placeholders", () => {
    expect(DATEX_DECAY["datex-srti"]).toBe(0.2);
    expect(DATEX_TAGS["datex-weather"]).toContain("monitoring_station");
    expect(DATEX_RASTER_FILE["datex-truckpark"]).toBe(
      "datex-truckpark-walk-raster.json",
    );
    expect(DATEX_NO_METRO).toBe(true);
  });
});

describe("datex points (#763)", () => {
  const table = {
    rows: [
      { station_id: "a", lat: 59.44, lon: 24.75 },
      { station_id: "b", lat: null, lon: 24.75 },
      { station_id: "c", lat: 59.44, lon: "x" },
      {
        camera_id: "d",
        lat: 59.43,
        lon: 24.74,
        image_url: "https://example.invalid/i.jpg",
      },
      "junk",
    ],
  };

  it("plots only located rows (unlocated skipped, never zero-filled)", () => {
    const pts = datexPointsForLayer(table, "datex-weather");
    expect(pts).toEqual([
      { lon: 24.75, lat: 59.44 },
      { lon: 24.74, lat: 59.43 },
    ]);
  });

  it("plots camera positions only (binaries never ride the wire)", () => {
    const pts = datexPointsForLayer(table, "datex-cameras");
    expect(pts).toHaveLength(2);
    expect(pts[1]).toEqual({ lon: 24.74, lat: 59.43 });
  });

  it("geometry-less feeds always read empty (never placed)", () => {
    expect(datexPointsForLayer(table, "datex-restrictions")).toEqual([]);
    expect(datexPointsForLayer(table, "datex-srti")).toEqual([]);
    expect(isDatexGeoLayer("datex-srti")).toBe(false);
    expect(isDatexGeoLayer("datex-counters")).toBe(true);
  });

  it("junk tables read empty", () => {
    expect(datexPointsForLayer(null, "datex-weather")).toEqual([]);
    expect(datexPointsForLayer({ rows: "nope" }, "datex-weather")).toEqual([]);
  });

  it("names every feed for the status line", () => {
    expect(datexStatusNoun("datex-restrictions")).toBe("piirangud");
    expect(datexStatusNoun("datex-weather")).toBe("teeilmajaamad");
    expect(datexStatusNoun("datex-truckpark")).toBe("veoautoparklad");
  });
});
