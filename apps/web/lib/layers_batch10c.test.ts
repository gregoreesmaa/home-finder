import { describe, expect, it, vi } from "vitest";
import {
  BATCH10C_BONUS,
  BATCH10C_DECAY,
  BATCH10C_DEFS,
  BATCH10C_LAYER_IDS,
  BATCH10C_PARAMS,
  BATCH10C_TAGS,
  bonusSpecForBatch10C,
} from "./layers_batch10c";
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

describe("batch B10C registry (#121)", () => {
  it("defines exactly the two amenity layers plus fiber", () => {
    // SCOPE (cut after buyer review): p51/p262/p265 shipped as mast-
    // proximity map layers first and were removed — masts cannot show
    // fiber/mobile coverage. p51 returns as FIBER, built from real
    // TTJA-reported coverage instead of masts.
    expect(BATCH10C_LAYER_IDS).toEqual(["water", "waste", "fiber", "mobile"]);
    expect(BATCH10C_DEFS.map((d) => d.id)).toEqual(BATCH10C_LAYER_IDS);
  });

  it("maps each layer to its parameters3.md number", () => {
    expect(BATCH10C_PARAMS).toEqual({ water: 53, waste: 54, fiber: 51, mobile: 51 });
    for (const d of BATCH10C_DEFS) {
      expect(d.paramIds).toEqual([BATCH10C_PARAMS[d.id as keyof typeof BATCH10C_PARAMS]]);
    }
  });

  it("merges into LAYERS via the B10C-HOOK (page + routes serve all layers)", () => {
    const ids = LAYERS.map((l) => l.id);
    // Rebased onto current main (#230): 73 shipped layers + 4 B10C.
    // OSMDAILY-HOOK (#482): +6 daily-life layers.
    // GTFS-HOOK (#483): +1 stop overlay.
    // RSAFE-HOOK (#481): +1 road-safety layer.
    // P4-031-HOOK (#484): +senscom DIY-air overlay (86 with gtfsstops + roadsafety + senscom).
    // STATKOV-HOOK (#485): +3 choropleth layers join the registry (86 + 3).
    // P4PARK-HOOK (#479): +1 parking layer. (89 + 1).
    // MARUKOV-HOOK (#486): +4 MARU KOV choropleths join the registry (90 + 4).
    // FLOOD-HOOK (#487): +1 flood-risk polygon overlay (89 + 1). (94 + 1).
    // P4OSM-HOOK (#480): +2 walkability/darkness layers. (95 + 2).
    // OOKLA-HOOK (#489): +2 quarterly-tile layers join the registry (97 + 2).
    // ACCBLACK-HOOK (#490): +1 blackspot layer (99 + 1).
    // MAAPARCEL-HOOK (#491): +1 parcel overlay (100 + 1).

    // EELIS-HOOK (#488): +3 nature-polygon layers join the registry (101 + 3).
    // PLANKTPR-HOOK (#492): +1 designated-use polygon layer (104 + 1).
    // TERVISE-HOOK (#494): +1 tervise bathing-water layer (105 + 1).
    // ASUMEDIA-HOOK (#495): +1 per-asum median layer (106 + 1).
    // PAASTE-HOOK (#493): +1 komando overlay (107 + 1).
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    expect(ids.length).toBe(155); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    for (const id of BATCH10C_LAYER_IDS) expect(ids).toContain(id);
    for (const gone of ["internet", "redundancy", "ota"]) expect(ids).not.toContain(gone);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of BATCH10C_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source).toContain("2026-09-12");
      expect(d.fallbackPoints.length).toBeGreaterThan(0);
    }
  });
});

describe("batch B10C honesty (#121)", () => {
  it("frames water as public points, never the communal network", () => {
    const water = BATCH10C_DEFS.find((d) => d.id === "water");
    expect(water?.title).toBe("Avalikud veepunktid");
    expect(water?.source).toMatch(/ühisveevärk kaardil pole/);
  });

  it("frames waste as drop-off points, never the collection service", () => {
    const waste = BATCH10C_DEFS.find((d) => d.id === "waste");
    expect(waste?.title).toBe("Taarapunktid ja jäätmejaamad");
    expect(waste?.source).toMatch(/prügivedu kaardil pole/);
  });

  it("labels fiber operator-reported coverage, never measured speed", () => {
    const fiber = BATCH10C_DEFS.find((d) => d.id === "fiber");
    expect(fiber?.title).toMatch(/Fiiber/);
    expect(fiber?.source).toMatch(/operaatorite teatatud/);
    expect(fiber?.source).toMatch(/mitte mõõdetud kiirus/);
  });

  it("labels mobile crowdsourced density with its bias disclosed", () => {
    const mobile = BATCH10C_DEFS.find((d) => d.id === "mobile");
    expect(mobile?.title).toMatch(/Mobiililevi/);
    expect(mobile?.source).toMatch(/OpenCellID/);
    expect(mobile?.source).toMatch(/CC-BY-SA/);
    expect(mobile?.source).toMatch(/Telia alakaetud/);
  });
});

describe("batch B10C scoring contract (#121)", () => {
  it("locks radii and bonus specs (raster contract + Euclidean fallback)", () => {
    // BONUS is the single source of halves (the old HALVES dict is gone);
    // mobile is measured-coverage discs, self-scaling, no half.
    expect(BATCH10C_DECAY).toEqual({ water: 0.5, waste: 0.3, fiber: 0.3, mobile: 1.0 });
    expect(BATCH10C_BONUS).toEqual({
      water: { kind: "area", half: 1 },
      waste: { kind: "area", half: 6 },
      fiber: { kind: "area", half: 50 },
      mobile: { kind: "cover", sigma: 1.0 },
    });
    for (const id of BATCH10C_LAYER_IDS) {
      expect(radiusKmFor(id)).toBeCloseTo(BATCH10C_DECAY[id], 5);
      expect(bonusSpecFor(id)).toEqual(BATCH10C_BONUS[id]);
    }
  });

  it("bonusSpecForBatch10C answers B10C ids and ignores other layers", () => {
    expect(bonusSpecForBatch10C("waste")).toEqual({ kind: "area", half: 6 });
    expect(bonusSpecForBatch10C("parks")).toBeUndefined();
  });

  it("raster docs bake matching calibration (matchesContract)", () => {
    const AREA_HALF = { water: 1, waste: 6, fiber: 50 } as const;
    for (const id of ["water", "waste", "fiber"] as const) {
      expect(
        matchesContract({ half: AREA_HALF[id], sigma: BATCH10C_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(true);
      // Stale half is rejected, never silently rendered.
      expect(
        matchesContract({ half: 999, sigma: BATCH10C_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(false);
    }
    // Cover-kind: null half + sigma match; a half-bearing doc is stale.
    expect(matchesContract({ half: null, sigma: 1.0, per: 0, cap: 0 }, "mobile")).toBe(true);
    expect(matchesContract({ half: 15, sigma: 1.0, per: 0, cap: 0 }, "mobile")).toBe(false);
  });

  it("scores 100 on top of a feature, decays with distance", () => {
    const pts = [{ lat: 59.4372, lon: 24.7536 }];
    expect(goodnessAt(59.4372, 24.7536, pts, "waste")).toBe(100);
    const near = goodnessAt(59.4472, 24.7536, pts, "water") as number;
    const far = goodnessAt(59.5372, 24.7536, pts, "water") as number;
    expect(near).toBeGreaterThan(far);
  });
});

describe("batch B10C queries and tags (#121)", () => {
  it("documents the verified snapshot tags per layer", () => {
    expect(BATCH10C_TAGS.water).toContain("drinking_water");
    expect(BATCH10C_TAGS.waste).toContain("waste_disposal");
    expect(BATCH10C_TAGS.waste).toContain("recycling");
    expect(BATCH10C_TAGS.fiber).toContain("kaabliyhendused_1000");
    expect(BATCH10C_TAGS.mobile).toContain("mcc=248");
  });

  it("builds bbox-scoped Overpass QL for the new layers", () => {
    const q = overpassQueryFor("waste", TALLINN_BBOX);
    expect(q).toContain("waste_disposal");
    expect(q).toContain("24.5");
    const water = overpassQueryFor("water", TALLINN_BBOX);
    expect(water).toContain("drinking_water");
  });

  it("fetches new layers through the generic server proxy", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ points: [{ lat: 59.43, lon: 24.75 }], provenance: "snapshot", ageMs: 1 }),
    });
    const res = await fetchLayerPoints("water", TALLINN_BBOX, fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0]).startsWith("/api/layers/water?")).toBe(true);
    expect(res.provenance).toBe("snapshot");
  });
});
