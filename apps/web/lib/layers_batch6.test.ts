import { describe, expect, it, vi } from "vitest";
import {
  B6_CAL,
  B6_YARD_BANDS,
  BATCH6_BONUS,
  BATCH6_DECAY,
  BATCH6_DEFS,
  BATCH6_LAYER_IDS,
  BATCH6_NO_MAP,
  BATCH6_PARAMS,
  BATCH6_RASTER_FILE,
  BATCH6_TAGS,
  b6HavKm,
  b6MatchesContract,
  b6QuietFromHalf,
  b6QuietnessAt,
  b6YardScore,
  bonusSpecForBatch6,
} from "./layers_batch6";
import {
  LAYERS,
  bonusSpecFor,
  fetchLayerPoints,
  overpassQueryFor,
  radiusKmFor,
} from "./layers";
import { matchesContract } from "./server/snapshot";

const TALLINN_BBOX = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("batch B6 registry (#133)", () => {
  it("defines exactly the three shipped layers (p220/p270/p386)", () => {
    expect(BATCH6_LAYER_IDS).toEqual(["droneclear", "droneviab", "rentbleed"]);
    expect(BATCH6_DEFS.map((d) => d.id)).toEqual(BATCH6_LAYER_IDS);
  });

  it("maps each layer to its parameters3.md number", () => {
    expect(BATCH6_PARAMS).toEqual({ droneclear: 220, droneviab: 270, rentbleed: 386 });
    for (const d of BATCH6_DEFS) {
      expect(d.paramIds).toEqual([BATCH6_PARAMS[d.id as keyof typeof BATCH6_PARAMS]]);
    }
  });

  it("merges into LAYERS via the B6-HOOK (page + routes serve all fifty-three)", () => {
    const ids = LAYERS.map((l) => l.id);
    // G03-HOOK (#151): drainage joins the registry.
    // G07C-HOOK(#142): vectorhabitat joins the registry.
    // G03D-HOOK (#154): moorage + shoredist join the registry.
    // G08A-HOOK (#167): wildfire joins the registry.
    // G08D-HOOK (#170): vernalpool joins the registry.
    // G08C-HOOK (#169): surgeroad + slidebuf join the registry.
    // G08B-HOOK (#168): windtunnel + saltspray join the registry.
    // G05B-HOOK (#162): gardens + buildout join the registry.
    // G05D-HOOK (#164): strsat joins the registry.
    // G05A-HOOK (#161): ehitus + korterstock join the registry.
    // G05C-HOOK (#163): commbleed + windsolar + viewshed join the registry.
    // G05E-HOOK (#165): equestrian joins the registry.
    // G05F-HOOK (#166): upcycle joins the registry.
    expect(ids.length).toBe(62);
    for (const id of BATCH6_LAYER_IDS) expect(ids).toContain(id);
  });

  it("documents the p11/p17 no-map verdicts instead of mapping them", () => {
    expect(BATCH6_NO_MAP.map((v) => v.param)).toEqual([11, 17]);
    for (const v of BATCH6_NO_MAP) {
      expect(v.verdict).toBe("no-map");
      expect(v.reason.length).toBeGreaterThan(0);
      expect(v.scorer).toContain("dims_");
    }
    // No-map params must NOT gain a layer by accident.
    const params = LAYERS.flatMap((l) => l.paramIds);
    expect(params).not.toContain(11);
    expect(params).not.toContain(17);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of BATCH6_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source).toContain("2026-09-12");
      expect(d.fallbackPoints.length).toBeGreaterThan(0);
    }
  });
});

describe("batch B6 honesty (#133)", () => {
  it("never claims EANS permission, yard suitability or euros", () => {
    const byId = Object.fromEntries(BATCH6_DEFS.map((d) => [d.id, d]));
    for (const d of BATCH6_DEFS) {
      expect(d.title).toMatch(/proksi.*hinnang|hinnang.*proksi/i);
    }
    expect(byId.droneclear.source).toMatch(/mitte EANS DroneMap/);
    expect(byId.droneclear.source).toMatch(/tegelikku lennuluba ei näita/);
    expect(byId.droneviab.source).toMatch(/mitte EANS DroneMap/);
    expect(byId.rentbleed.source).toMatch(/mitte üüriregister/);
    expect(byId.rentbleed.source).toMatch(/eurosid ei mõõda/i);
  });
});

describe("batch B6 scoring contract (#133)", () => {
  it("locks radii and quiet halves (raster contract + Euclidean fallback)", () => {
    expect(BATCH6_DECAY).toEqual({ droneclear: 0.3, droneviab: 0.3, rentbleed: 0.3 });
    expect(B6_CAL.droneclear).toEqual({ halfM: 1300, sigma: 0.3 });
    expect(B6_CAL.droneviab).toEqual({ clearHalfM: 800, sigma: 0.3 });
    expect(B6_CAL.rentbleed).toEqual({ halfM: 800, sigma: 0.3 });
    expect(BATCH6_BONUS.droneclear).toEqual({ kind: "quiet", halfM: 1300 });
    // Wire carries the droneviab CLEARANCE leg (yard is raster-side-only).
    expect(BATCH6_BONUS.droneviab).toEqual({ kind: "quiet", halfM: 800 });
    expect(BATCH6_BONUS.rentbleed).toEqual({ kind: "quiet", halfM: 800 });
    for (const id of BATCH6_LAYER_IDS) {
      expect(radiusKmFor(id)).toBeCloseTo(0.3, 5);
      expect(bonusSpecFor(id)).toEqual(BATCH6_BONUS[id]);
      expect(bonusSpecForBatch6(id)).toEqual(BATCH6_BONUS[id]);
    }
  });

  it("bonusSpecForBatch6 answers B6 ids and ignores the original eight", () => {
    expect(bonusSpecForBatch6("rentbleed")).toEqual({ kind: "quiet", halfM: 800 });
    expect(bonusSpecForBatch6("parks")).toBeUndefined();
  });

  it("raster docs bake matching calibration (matchesContract)", () => {
    const wire: Record<string, { half: number; sigma: number }> = {
      droneclear: { half: 1300, sigma: 0.3 },
      droneviab: { half: 800, sigma: 0.3 },
      rentbleed: { half: 800, sigma: 0.3 },
    };
    for (const id of BATCH6_LAYER_IDS) {
      const w = wire[id];
      expect(b6MatchesContract({ half: w.half, sigma: w.sigma }, id)).toBe(true);
      expect(
        matchesContract({ half: w.half, sigma: w.sigma, per: 0, cap: 0 }, id),
      ).toBe(true);
      // Stale half is rejected, never silently rendered.
      expect(
        matchesContract({ half: 999, sigma: w.sigma, per: 0, cap: 0 }, id),
      ).toBe(false);
    }
  });

  it("pins the yard step bands to the p270 scorer bands", () => {
    expect(B6_YARD_BANDS.map(([d]) => d)).toEqual([100, 300, 500, 1000, Infinity]);
    expect(b6YardScore(0)).toBe(100);
    expect(b6YardScore(100)).toBe(100);
    expect(b6YardScore(101)).toBe(80);
    expect(b6YardScore(500)).toBe(60);
    expect(b6YardScore(1000)).toBe(40);
    expect(b6YardScore(1001)).toBe(25);
  });

  it("scores calm far away, exposed on the source", () => {
    expect(b6QuietFromHalf(0, 1300)).toBe(0);
    expect(b6QuietFromHalf(1300, 1300)).toBe(50);
    expect(b6QuietFromHalf(Infinity, 1300)).toBe(100);
    expect(b6HavKm(0, 0, 1, 0)).toBeCloseTo(57.29, 5);
    const site = [{ lat: 59.41646, lon: 24.79659 }]; // Lennujaam
    expect(b6QuietnessAt("droneclear", 59.41646, 24.79659, site)).toBe(0);
    const near = b6QuietnessAt("droneclear", 59.4278, 24.7611, site) as number;
    const far = b6QuietnessAt("droneclear", 59.51, 24.83, site) as number;
    expect(near).toBeGreaterThan(0);
    expect(far).toBeGreaterThan(near);
  });

  it("droneviab binds the min (blocker wins, never an average)", () => {
    const site = [{ lat: 59.41646, lon: 24.79659 }];
    // On the airfield with a park next door: clearance binds at 0.
    expect(b6QuietnessAt("droneviab", 59.41646, 24.79659, site, 50)).toBe(0);
    // Far from the airfield with no park mapped: yard binds at 25.
    expect(b6QuietnessAt("droneviab", 59.2, 24.5, site, null)).toBe(25);
    // Empty points score nothing, never a faked zero.
    expect(b6QuietnessAt("droneclear", 59.43, 24.75, [])).toBeNull();
  });

  it("serves rasters under the quiet contract filenames", () => {
    expect(BATCH6_RASTER_FILE).toEqual({
      droneclear: "droneclear-walk-raster.json",
      droneviab: "droneviab-walk-raster.json",
      rentbleed: "rentbleed-walk-raster.json",
    });
  });
});

describe("batch B6 queries and tags (#133)", () => {
  it("documents the verified snapshot tags per layer", () => {
    expect(BATCH6_TAGS.droneclear).toContain("aeroway");
    expect(BATCH6_TAGS.droneclear).toContain("helipad");
    expect(BATCH6_TAGS.droneviab).toContain("aerodrome");
    expect(BATCH6_TAGS.rentbleed).toContain("university");
    expect(BATCH6_TAGS.rentbleed).toContain("college");
    expect(BATCH6_TAGS.rentbleed).toContain("dormitory");
  });

  it("builds bbox-scoped Overpass QL for the new layers", () => {
    const q = overpassQueryFor("droneclear", TALLINN_BBOX);
    expect(q).toContain("aeroway");
    expect(q).toContain("24.5");
    const uni = overpassQueryFor("rentbleed", TALLINN_BBOX);
    expect(uni).toContain("university");
    expect(uni).toContain("59.35");
  });

  it("fetches new layers through the generic server proxy", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ points: [{ lat: 59.43, lon: 24.75 }], provenance: "snapshot", ageMs: 1 }),
    });
    const res = await fetchLayerPoints("rentbleed", TALLINN_BBOX, fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0]).startsWith("/api/layers/rentbleed?")).toBe(true);
    expect(res.provenance).toBe("snapshot");
  });
});
