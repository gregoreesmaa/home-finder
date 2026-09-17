import { describe, expect, it, vi } from "vitest";
import {
  P4PARK_BONUS,
  P4PARK_CAL,
  P4PARK_DECAY,
  P4PARK_DEFS,
  P4PARK_HOOK,
  P4PARK_LAYER_IDS,
  P4PARK_PARAMS,
  P4PARK_RASTER_FILE,
  P4PARK_TAGS,
  bonusSpecForP4Parking,
  isP4ParkingLayerId,
} from "./layers_p4_parking";
import {
  LAYERS,
  bonusSpecFor,
  fetchLayerPoints,
  goodnessAt,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { matchesContract } from "./server/snapshot";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("P4 parking registry (#479)", () => {
  it("defines exactly the one OSM parking proximity layer", () => {
    expect(P4PARK_LAYER_IDS).toEqual(["parking"]);
    expect(P4PARK_DEFS.map((d) => d.id)).toEqual(P4PARK_LAYER_IDS);
    expect(P4PARK_HOOK).toContain("P4PARK-HOOK (#479)");
  });

  it("binds the layer to P4-013 in the reserved 4XXX registry block", () => {
    // Canary convention (see layers_p4_parking.ts): P4-XXX has no
    // parameters3 number, so 4000 + ordinal keeps the "(pN)" buttons
    // collision-free; the title carries the true P4-013 id.
    expect(P4PARK_PARAMS).toEqual({ parking: 4013 });
    for (const d of P4PARK_DEFS) {
      expect(d.paramIds).toEqual([P4PARK_PARAMS[d.id as keyof typeof P4PARK_PARAMS]]);
    }
  });

  it("merges into LAYERS via the P4PARK-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 89 shipped layers (main at #502: +senscom, +3 statkov) + 1 P4 parking layer.
    // +4 maru layers (MARUKOV-HOOK #486, 90 + 4) + 1 floodzone (FLOOD-HOOK #487, 94 + 1) + 2 P4OSM (P4OSM-HOOK #480, 95 + 2) +
    // 2 ookla tile layers (OOKLA-HOOK #489, 97 + 2) +
    // 1 accblack layer (ACCBLACK-HOOK #490, 99 + 1) + 1 maaparcel (MAAPARCEL-HOOK #491, 100 + 1) +
    // 3 eelis (EELIS-HOOK #488, 101 + 3) + 1 planktpr (PLANKTPR-HOOK #492, 104 + 1) +
    // 1 tervise (TERVISE-HOOK #494, 105 + 1) +
    // 1 asumedia (ASUMEDIA-HOOK #495, 106 + 1).
    // 3 eelis (EELIS-HOOK #488, 101 + 3) + 1 planktpr (PLANKTPR-HOOK #492, 104 + 1).
    // TERVISE-HOOK (#494): +1 tervise bathing-water layer (105 + 1).
    // PAASTE-HOOK (#493): +1 komando overlay (107 + 1).
    expect(ids.length).toBe(134); // MERGE (#613+#614+#615+#616+#617+#618+#619+#620): 123 shipped + seveso + stateland + quarry + maaparandus + soil + etak + relief + canopy = 131 (both branch counts superseded).
    expect(ids).toContain("parking");
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of P4PARK_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source).toContain("2026-09-12");
      expect(d.fallbackPoints.length).toBeGreaterThan(0);
    }
  });
});

describe("P4 parking honesty (#479)", () => {
  it("says kaardistatud + hinnang/proksi in the title, never measured availability", () => {
    const parking = P4PARK_DEFS.find((d) => d.id === "parking");
    expect(parking?.title).toContain("Kaardistatud");
    expect(parking?.title).toMatch(/P4-013/);
    expect(parking?.title).toMatch(/hinnang|proksi/);
    expect(parking?.title).not.toMatch(/saadavus|vabad kohad/i);
  });

  it("names the missing fee/permit/courtyard/availability facts in the source", () => {
    const parking = P4PARK_DEFS.find((d) => d.id === "parking");
    expect(parking?.source).toMatch(/tsoonirežiim/);
    expect(parking?.source).toMatch(/elanikloa/);
    expect(parking?.source).toMatch(/VABADE KOHTADE/);
    expect(parking?.source).toMatch(/PROKSI/);
    expect(parking?.source).toMatch(/mitte mõõdetud saadavust/);
  });

  it("keeps the labels honest about mapping gaps", () => {
    const parking = P4PARK_DEFS.find((d) => d.id === "parking");
    expect(parking?.goodLabel).toContain("hinnang");
    expect(parking?.badLabel).toContain("hinnang");
    expect(parking?.badLabel).toMatch(/kaardistamata/);
  });
});

describe("P4 parking scoring contract (#479)", () => {
  it("locks radius and bonus spec (raster contract + Euclidean fallback)", () => {
    // P4PARK_CAL is the single source (mirrored by the Python
    // builder — parsed by scripts/build/test_batch_p4_parking.py).
    expect(P4PARK_CAL).toEqual({ parking: { half: 75, sigma: 0.8 } });
    expect(P4PARK_DECAY).toEqual({ parking: 0.8 });
    expect(P4PARK_BONUS).toEqual({ parking: { kind: "area", half: 75 } });
    expect(radiusKmFor("parking")).toBeCloseTo(0.8, 5);
    expect(bonusSpecFor("parking")).toEqual({ kind: "area", half: 75 });
  });

  it("guards and lookups answer parking and ignore other layers", () => {
    expect(isP4ParkingLayerId("parking")).toBe(true);
    expect(isP4ParkingLayerId("parks")).toBe(false);
    expect(bonusSpecForP4Parking("parking")).toEqual({ kind: "area", half: 75 });
    expect(bonusSpecForP4Parking("parks")).toBeUndefined();
  });

  it("names the raster master the snapshot serves under the contract", () => {
    expect(P4PARK_RASTER_FILE).toEqual({ parking: "parking-walk-raster.json" });
  });

  it("raster docs bake matching calibration (matchesContract)", () => {
    expect(matchesContract({ half: 75, sigma: 0.8, per: 0, cap: 0 }, "parking")).toBe(true);
    // Stale half is rejected, never silently rendered.
    expect(matchesContract({ half: 999, sigma: 0.8, per: 0, cap: 0 }, "parking")).toBe(false);
    // Wrong sigma is rejected too (the 800 m tier is load-bearing).
    expect(matchesContract({ half: 75, sigma: 0.3, per: 0, cap: 0 }, "parking")).toBe(false);
  });

  it("scores 100 on top of a feature, decays with distance", () => {
    const pts = [{ lat: 59.4372, lon: 24.7536 }];
    expect(goodnessAt(59.4372, 24.7536, pts, "parking")).toBe(100);
    const near = goodnessAt(59.4472, 24.7536, pts, "parking") as number;
    const far = goodnessAt(59.5372, 24.7536, pts, "parking") as number;
    expect(near).toBeGreaterThan(far);
  });
});

describe("P4 parking queries and tags (#479)", () => {
  it("documents the verified snapshot tag", () => {
    expect(P4PARK_TAGS.parking).toContain('amenity"="parking"');
  });

  it("builds a bbox-scoped Overpass QL query covering nodes and ways", () => {
    const q = overpassQueryFor("parking", TALLINN_BBOX);
    expect(q).toContain("amenity");
    expect(q).toContain("parking");
    expect(q).toContain("nwr[");
    expect(q).toContain("24.5");
  });

  it("fetches through the generic server proxy", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ points: [{ lat: 59.43, lon: 24.75 }], provenance: "snapshot", ageMs: 1 }),
    });
    const res = await fetchLayerPoints("parking", TALLINN_BBOX, fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0]).startsWith("/api/layers/parking?")).toBe(true);
    expect(res.provenance).toBe("snapshot");
  });
});
