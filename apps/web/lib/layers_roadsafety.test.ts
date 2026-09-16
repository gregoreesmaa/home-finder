// OSM road-safety overlay tests (issue #481): P4-012 proxy ships as a
// honestly-labeled crossing/calming count hinnang. Hermetic: inline point
// fixtures only, no network, no snapshot files.
import { describe, expect, it, vi } from "vitest";
import {
  RSAFE_BONUS,
  RSAFE_CAL,
  RSAFE_DECAY,
  RSAFE_DEFS,
  RSAFE_HOOK,
  RSAFE_LAYER_IDS,
  RSAFE_NO_METRO,
  RSAFE_PARAMS,
  RSAFE_RASTER_FILE,
  RSAFE_TAGS,
  bonusSpecForRsafe,
  isRsafeLayerId,
} from "./layers_roadsafety";
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

describe("roadsafety registry (#481)", () => {
  it("ships exactly one layer bound to p13 (shared with B5 safety)", () => {
    expect(RSAFE_LAYER_IDS).toEqual(["roadsafety"]);
    expect(RSAFE_DEFS.map((d) => d.id)).toEqual(["roadsafety"]);
    // p13 is shared on purpose (fiber/mobile share p51): B5 safety asks
    // police proximity, roadsafety asks furniture density.
    expect(RSAFE_PARAMS).toEqual({ roadsafety: 13 });
    expect(RSAFE_DEFS[0].paramIds).toEqual([13]);
  });

  it("merges into LAYERS via the RSAFE-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 84 shipped layers (OSMDAILY-HOOK #482 + GTFS-HOOK #483 on main) + 1 road-safety.
    // P4-031-HOOK (#484): +senscom DIY-air overlay (85 + 1).
    // STATKOV-HOOK (#485): +3 choropleth layers (86 + 3).
    // P4PARK-HOOK (#479): +1 parking layer (89 + 1).
    // MARUKOV-HOOK (#486): +4 MARU KOV choropleths (90 + 4).
    // FLOOD-HOOK (#487): +1 flood-risk polygon overlay (94 + 1) + 2 P4OSM (P4OSM-HOOK #480, 95 + 2).
    // OOKLA-HOOK (#489): +2 quarterly-tile layers (97 + 2).
    // ACCBLACK-HOOK (#490): +1 blackspot layer (99 + 1).
    // MAAPARCEL-HOOK (#491): +1 parcel overlay (100 + 1).

    // EELIS-HOOK (#488): +3 nature-polygon layers (101 + 3).
    // PLANKTPR-HOOK (#492): +1 designated-use polygon layer (104 + 1).
    // TERVISE-HOOK (#494): +1 tervise bathing-water layer (105 + 1).
    // ASUMEDIA-HOOK (#495): +1 per-asum median layer (106 + 1).
    // PAASTE-HOOK (#493): +1 komando overlay (107 + 1).
<<<<<    expect(ids.length).toBe(119); // SPORT-HOOK (#607): +3 sport slices (108 + 3); EHIS-HOOK (#608): +3 school slices (111 + 3); MEDRE-HOOK (#609): +2 care slices (114 + 2); OHUSEIRE-HOOK (#610): +1 station dots (116 + 1); KLIIMA-HOOK (#611): +2 climate slices (117 + 2)
    expect(ids).toContain("roadsafety");
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of RSAFE_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source).toContain("2026-09-12");
      expect(d.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the hook marker + raster file + no-metro verdict", () => {
    expect(RSAFE_HOOK).toContain("RSAFE-HOOK (#481)");
    expect(RSAFE_RASTER_FILE.roadsafety).toBe("roadsafety-walk-raster.json");
    expect(RSAFE_NO_METRO).toBe(true);
  });
});

describe("roadsafety honesty (#481)", () => {
  it("frames the layer as a furniture-density hinnang, never measured safety", () => {
    const def = RSAFE_DEFS[0];
    expect(def.title).toMatch(/hinnang/);
    expect(def.source).toMatch(/EI OLE mõõdetud liiklusohutus/);
    expect(def.source).toMatch(/Transpordiameti õnnetuspunktid/);
    expect(def.source).toMatch(/Päästeameti sõiduajad/);
    expect(def.source).toMatch(/proksi/);
  });

  it("carries the usage-not-safety caveat in the legend (P4-032 precedent)", () => {
    const def = RSAFE_DEFS[0];
    expect(def.goodLabel).toMatch(/kaardistuskasutus, mitte ohutustõde/);
    expect(def.source).toMatch(/kaardistatud mööbli tihedus/);
  });
});

describe("roadsafety scoring contract (#481)", () => {
  it("locks the blackspot kernel radius (<=500 m per issue AC)", () => {
    expect(RSAFE_DECAY).toEqual({ roadsafety: 0.5 });
    expect(RSAFE_CAL.roadsafety.sigma).toBe(0.5);
    expect(RSAFE_CAL.roadsafety.half).toBe(60);
    expect(radiusKmFor("roadsafety")).toBeCloseTo(0.5, 5);
  });

  it("locks the density half (a grocery half would saturate the city)", () => {
    expect(RSAFE_BONUS).toEqual({ roadsafety: { kind: "area", half: 60 } });
    expect(bonusSpecFor("roadsafety")).toEqual({ kind: "area", half: 60 });
  });

  it("bonusSpecForRsafe answers roadsafety and ignores other layers", () => {
    expect(bonusSpecForRsafe("roadsafety")).toEqual({ kind: "area", half: 60 });
    expect(bonusSpecForRsafe("parks")).toBeUndefined();
    expect(isRsafeLayerId("roadsafety")).toBe(true);
    expect(isRsafeLayerId("parks")).toBe(false);
  });

  it("raster docs bake matching calibration (matchesContract)", () => {
    expect(matchesContract({ half: 60, sigma: 0.5, per: 0, cap: 0 }, "roadsafety")).toBe(true);
    // Stale half is rejected, never silently rendered.
    expect(matchesContract({ half: 6, sigma: 0.5, per: 0, cap: 0 }, "roadsafety")).toBe(false);
    expect(matchesContract({ half: 60, sigma: 0.3, per: 0, cap: 0 }, "roadsafety")).toBe(false);
  });

  it("scores 100 on top of furniture, decays with distance (fixture points)", () => {
    const pts = [
      { lat: 59.4374, lon: 24.7454 }, // mapped crossing
      { lat: 59.4375, lon: 24.7456 }, // mapped calming
    ];
    expect(goodnessAt(59.4374, 24.7454, pts, "roadsafety")).toBe(100);
    const near = goodnessAt(59.4474, 24.7454, pts, "roadsafety") as number;
    const far = goodnessAt(59.5374, 24.7454, pts, "roadsafety") as number;
    expect(near).toBeGreaterThan(far);
  });
});

describe("roadsafety queries and tags (#481)", () => {
  it("documents the verified snapshot tags (crossing + calming)", () => {
    expect(RSAFE_TAGS.roadsafety).toContain('highway"="crossing');
    expect(RSAFE_TAGS.roadsafety).toContain("traffic_calming");
  });

  it("builds a bbox-scoped Overpass QL for the new layer", () => {
    const q = overpassQueryFor("roadsafety", TALLINN_BBOX);
    expect(q).toContain("crossing");
    expect(q).toContain("traffic_calming");
    expect(q).toContain("24.5");
  });

  it("fetches the new layer through the generic server proxy", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ points: [{ lat: 59.43, lon: 24.75 }], provenance: "snapshot", ageMs: 1 }),
    });
    const res = await fetchLayerPoints("roadsafety", TALLINN_BBOX, fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0]).startsWith("/api/layers/roadsafety?")).toBe(true);
    expect(res.provenance).toBe("snapshot");
  });
});
