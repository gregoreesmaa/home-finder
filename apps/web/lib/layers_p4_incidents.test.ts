import { describe, expect, it } from "vitest";
import {
  INCIDENTS_BONUS,
  INCIDENTS_CACHE_FILE,
  INCIDENTS_DECAY,
  INCIDENTS_DEFS,
  INCIDENTS_HOOK,
  INCIDENTS_LAYER_IDS,
  INCIDENTS_NO_METRO,
  INCIDENTS_RASTER_FILE,
  INCIDENTS_TAGS,
  INCIDENTS_TTL_S,
  bonusSpecForIncidents,
  incidentPointsForCache,
  isIncidentsLayerId,
} from "./layers_p4_incidents";

describe("incidents registry (#763)", () => {
  it("defines exactly the incidents overlay", () => {
    expect(INCIDENTS_LAYER_IDS).toEqual(["incidents"]);
    expect(INCIDENTS_DEFS.map((d) => d.id)).toEqual(INCIDENTS_LAYER_IDS);
    expect(INCIDENTS_HOOK).toMatch(/INCIDENTS-HOOK \(#763\)/);
    expect(INCIDENTS_TTL_S).toBe(6 * 3600);
    expect(INCIDENTS_CACHE_FILE).toBe("tomtom_incidents.json");
  });

  it("binds the P4 slice label and markers-only spec", () => {
    expect(INCIDENTS_DEFS[0].paramIds).toEqual([]);
    expect(INCIDENTS_DEFS[0].paramLabel).toBe("P4-intsidendid");
    expect(INCIDENTS_BONUS.incidents).toEqual({ kind: "pins" });
    expect(bonusSpecForIncidents("incidents")).toEqual({ kind: "pins" });
    expect(bonusSpecForIncidents("transit")).toBeUndefined();
    expect(isIncidentsLayerId("incidents")).toBe(true);
    expect(isIncidentsLayerId("busmesh")).toBe(false);
    expect(INCIDENTS_DECAY.incidents).toBe(0.2);
    expect(INCIDENTS_TAGS.incidents).toContain("highway");
    expect(INCIDENTS_RASTER_FILE.incidents).toBe("incidents-walk-raster.json");
    expect(INCIDENTS_NO_METRO).toBe(true);
  });
});

describe("incidents points (#763)", () => {
  const body = {
    incidents: [
      {
        id: "1",
        properties: { magnitudeOfDelay: 3, freeText: "Ummik" },
        geometry: { coordinates: [[24.75, 59.44], [24.76, 59.45]] },
      },
      {
        id: "2",
        properties: { magnitudeOfDelay: 9 },
        geometry: { coordinates: [[24.7, 59.4]] },
      },
      {
        id: "3",
        properties: {},
        geometry: { coordinates: [] },
      },
      { id: "4", properties: {}, geometry: { coordinates: [["x", true]] } },
      "junk",
    ],
  };

  it("plots first coordinates with magnitudes (unknown stays null)", () => {
    expect(incidentPointsForCache(body)).toEqual([
      { lon: 24.75, lat: 59.44, magnitude: 3 },
      { lon: 24.7, lat: 59.4, magnitude: null },
    ]);
  });

  it("junk bodies read empty", () => {
    expect(incidentPointsForCache(null)).toEqual([]);
    expect(incidentPointsForCache({ incidents: "nope" })).toEqual([]);
  });
});
