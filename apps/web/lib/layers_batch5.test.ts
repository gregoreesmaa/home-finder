import { describe, expect, it, vi } from "vitest";
import {
  BATCH5_BONUS,
  BATCH5_DECAY,
  BATCH5_DEFS,
  BATCH5_HALVES,
  BATCH5_LAYER_IDS,
  BATCH5_PARAMS,
  BATCH5_TAGS,
  bonusSpecForBatch5,
} from "./layers_batch5";
import {
  LAYERS,
  bonusSpecFor,
  fetchLayerPoints,
  goodnessAt,
  overpassQueryFor,
  pickFeatureTags,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { matchesContract } from "./server/snapshot";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("batch B5 registry (#102)", () => {
  it("defines exactly the five Group 14 layers", () => {
    expect(BATCH5_LAYER_IDS).toEqual(["safety", "emergency", "hydrants", "evac", "dispatch"]);
    expect(BATCH5_DEFS.map((d) => d.id)).toEqual(BATCH5_LAYER_IDS);
  });

  it("maps each layer to its parameters3.md number", () => {
    expect(BATCH5_PARAMS).toEqual({ safety: 13, emergency: 78, hydrants: 315, evac: 335, dispatch: 467 });
    for (const d of BATCH5_DEFS) {
      expect(d.paramIds).toEqual([BATCH5_PARAMS[d.id as keyof typeof BATCH5_PARAMS]]);
    }
  });

  it("merges into LAYERS via the B5-HOOK (page + routes serve all forty-four)", () => {
    const ids = LAYERS.map((l) => l.id);
    // G03-HOOK (#151): drainage joins the registry.
    // G07D-HOOK (#143): two env-health D layers join the registry.
    // G06B-HOOK (#139): three Group 6 leftover layers join the registry.
    // G11C-HOOK (#134): five Group 11 leftover-A layers join the registry.
    // B6-HOOK (#133): three mobility/access layers join the registry.
    // G07-HOOK (#140): two env-health layers join the registry.
    // G06-HOOK (#138): Group 6 heritage layer rides the same registry.
    // G02B-HOOK (#137): liftproxy joins the registry.
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
    // G10R-HOOK (#171): skyview joins the registry.
    // G18A-HOOK (#172): dayopen + glassglare join the registry.
    // G18B-HOOK (#173): fishbowl + mossrisk + daylight join the registry.
    // G17A-HOOK (#177): compost + gritbin + leafdrop join the registry.
    expect(ids.length).toBe(71);
    for (const id of BATCH5_LAYER_IDS) expect(ids).toContain(id);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of BATCH5_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source).toContain("2026-09-12");
      expect(d.fallbackPoints.length).toBeGreaterThan(0);
    }
  });
});

describe("batch B5 honesty (#102)", () => {
  it("labels p13 a police-proximity hinnang, never measured crime", () => {
    const safety = BATCH5_DEFS.find((d) => d.id === "safety");
    expect(safety?.title).toMatch(/hinnang/i);
    expect(safety?.goodLabel).toMatch(/hinnang/i);
    // The source must disclaim measured crime rates explicitly.
    expect(safety?.source).toMatch(/EI OLE mõõdetud kuritegevus/);
  });

  it("labels the other proxies as proximity estimates, not measurements", () => {
    const byId = Object.fromEntries(BATCH5_DEFS.map((d) => [d.id, d]));
    expect(byId.hydrants.source).toMatch(/lähedus, mitte mõõdetud vooluhulk/);
    expect(byId.emergency.source).toMatch(/mitte mõõdetud reageerimisajad/);
    expect(byId.dispatch.source).toMatch(/mitte mõõdetud väljakutseajad/);
    expect(byId.evac.source).toMatch(/mitte ametlik evakuatsiooniplaan/);
  });
});

describe("batch B5 scoring contract (#102)", () => {
  it("locks radii and area halves (raster contract + Euclidean fallback)", () => {
    expect(BATCH5_DECAY).toEqual({ safety: 0.8, emergency: 0.8, hydrants: 0.3, evac: 0.5, dispatch: 0.8 });
    expect(BATCH5_HALVES).toEqual({ safety: 1, emergency: 2, hydrants: 6, evac: 2, dispatch: 3 });
    for (const id of BATCH5_LAYER_IDS) {
      expect(radiusKmFor(id)).toBeCloseTo(BATCH5_DECAY[id], 5);
      expect(bonusSpecFor(id)).toEqual({ kind: "area", half: BATCH5_HALVES[id] });
      expect(BATCH5_BONUS[id]).toEqual({ kind: "area", half: BATCH5_HALVES[id] });
    }
  });

  it("bonusSpecForBatch5 answers B5 ids and ignores the original eight", () => {
    expect(bonusSpecForBatch5("hydrants")).toEqual({ kind: "area", half: 6 });
    expect(bonusSpecForBatch5("parks")).toBeUndefined();
  });

  it("raster docs bake matching calibration (matchesContract)", () => {
    for (const id of BATCH5_LAYER_IDS) {
      expect(
        matchesContract({ half: BATCH5_HALVES[id], sigma: BATCH5_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(true);
      // Stale half is rejected, never silently rendered.
      expect(
        matchesContract({ half: 999, sigma: BATCH5_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(false);
    }
  });

  it("scores 100 on top of a feature, decays with distance", () => {
    const pts = [{ lat: 59.4372, lon: 24.7536 }];
    expect(goodnessAt(59.4372, 24.7536, pts, "hydrants")).toBe(100);
    const near = goodnessAt(59.4472, 24.7536, pts, "safety") as number;
    const far = goodnessAt(59.5372, 24.7536, pts, "safety") as number;
    expect(near).toBeGreaterThan(far);
  });
});

describe("batch B5 queries and tags (#102)", () => {
  it("documents the verified snapshot tags per layer", () => {
    expect(BATCH5_TAGS.safety).toContain('amenity"="police');
    expect(BATCH5_TAGS.emergency).toContain("fire_station");
    expect(BATCH5_TAGS.emergency).toContain("hospital");
    expect(BATCH5_TAGS.hydrants).toContain('emergency"="fire_hydrant');
    expect(BATCH5_TAGS.evac).toContain("highway");
    expect(BATCH5_TAGS.dispatch).toContain("police");
  });

  it("builds bbox-scoped Overpass QL for the new layers", () => {
    const q = overpassQueryFor("hydrants", TALLINN_BBOX);
    expect(q).toContain("fire_hydrant");
    expect(q).toContain("24.5");
    const evac = overpassQueryFor("evac", TALLINN_BBOX);
    expect(evac).toContain("highway");
    expect(evac).toContain("trunk");
  });

  it("keeps emergency=fire_hydrant tags through the allowlist", () => {
    expect(pickFeatureTags({ emergency: "fire_hydrant" })).toEqual({ emergency: "fire_hydrant" });
  });

  it("fetches new layers through the generic server proxy", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ points: [{ lat: 59.43, lon: 24.75 }], provenance: "snapshot", ageMs: 1 }),
    });
    const res = await fetchLayerPoints("safety", TALLINN_BBOX, fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0]).startsWith("/api/layers/safety?")).toBe(true);
    expect(res.provenance).toBe("snapshot");
  });
});
