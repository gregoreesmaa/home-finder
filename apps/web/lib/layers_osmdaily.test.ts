// OSM daily-life overlay tests (issue #482): six sparse-but-real
// shop/culture/entrance proxies ship; the parameters3 audit stays
// untouched (paramIds empty — P4 lives in its own namespace).
// Hermetic: fixture points only, no network (mocked fetchImpl).
import { describe, expect, it, vi } from "vitest";
import {
  OSMDAILY_BONUS,
  OSMDAILY_DECAY,
  OSMDAILY_DEFS,
  OSMDAILY_HOOK,
  OSMDAILY_LAYER_IDS,
  OSMDAILY_P4,
  OSMDAILY_RASTER_FILE,
  OSMDAILY_TAGS,
  bonusSpecForOsmdaily,
} from "./layers_osmdaily";
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

// Fixture micro-neighbourhood: two shops + a sauna 100 m apart (tallinn;
// sparse-but-real shape: clusters read mid-ramp, never saturated).
const FIXTURE_SHOPS = [
  { lat: 59.4372, lon: 24.7536 },
  { lat: 59.438, lon: 24.7544 },
  { lat: 59.4376, lon: 24.7555 },
];

describe("osmdaily registry (#482)", () => {
  it("defines exactly the six daily-life proxies", () => {
    expect(OSMDAILY_LAYER_IDS).toEqual([
      "dailyshop",
      "activity",
      "herd",
      "thirdplace",
      "taxidoor",
      "lastshop",
    ]);
    expect(OSMDAILY_DEFS.map((d) => d.id)).toEqual(OSMDAILY_LAYER_IDS);
  });

  it("links each layer to its parameters4 number (never parameters3)", () => {
    expect(OSMDAILY_P4).toEqual({
      dailyshop: "P4-027",
      activity: "P4-032",
      herd: "P4-044",
      thirdplace: "P4-045",
      taxidoor: "P4-049",
      lastshop: "P4-061",
    });
    // Namespace lock: paramIds stays EMPTY so the parameters3 audit
    // (docs/layers.md — 44 is korterstock, 61 is industprox) is
    // untouched; the P4 linkage lives in titles + OSMDAILY_P4.
    for (const d of OSMDAILY_DEFS) expect(d.paramIds).toEqual([]);
    // My defs contribute zero numbers, so the registry multiset gains
    // none (61 stays industprox's alone; 27 stays whatever it was).
    expect(OSMDAILY_DEFS.flatMap((d) => d.paramIds)).toEqual([]);
    for (const d of OSMDAILY_DEFS) {
      expect(d.title).toContain(OSMDAILY_P4[d.id as keyof typeof OSMDAILY_P4]);
    }
  });

  it("merges into LAYERS via the OSMDAILY-HOOK (page + routes serve all layers)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 77 shipped layers + 6 OSM-daily + 1 GTFS stop overlay (#483) + 1 road-safety (#481).
    // P4-031-HOOK (#484): +senscom DIY-air overlay.
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
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    // HARNO-HOOK (#687): +1 harno school layer (156 + 1 = 157).
    // VIIRS-HOOK (#719): +1 viirs brightness layer (157 + 1 = 158).
    // OUTAGE-HOOK (#729): +1 outage hetkeseis layer (158 + 1 = 159).
    // BUSMESH-HOOK (#769): +3 transfer-node window layers (159 + 3 = 162).
    // SHED-HOOK (#763) + DATEX-HOOK (#763) + INCIDENTS-HOOK (#763): +4 sheds +6 datex +1 incidents (162 + 11 = 173).
    // CARFRICTION-HOOK (#829): +1 carfriction restriction-friction layer (173 + 1 = 174).
    expect(ids.length).toBe(174); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    for (const id of OSMDAILY_LAYER_IDS) expect(ids).toContain(id);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of OSMDAILY_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source).toContain("2026-09-12");
      expect(d.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the hook marker", () => {
    expect(OSMDAILY_HOOK).toContain("OSMDAILY-HOOK (#482)");
  });
});

describe("osmdaily honesty (#482)", () => {
  it("frames every layer as a mapped hinnang, never measured commerce", () => {
    for (const d of OSMDAILY_DEFS) {
      for (const s of [d.title, d.goodLabel, d.badLabel, d.source]) {
        expect(s).toMatch(/hinnang|hoiatus/i);
      }
      expect(d.source).toMatch(/kaardistatud/);
    }
  });

  it("frames last-shop absence as a warning, never a measured closure", () => {
    const last = OSMDAILY_DEFS.find((d) => d.id === "lastshop");
    expect(last?.title).toMatch(/hoiatus/);
    expect(last?.badLabel).toMatch(/HOIATUS/);
    expect(last?.source).toMatch(/hoiatus/);
    expect(last?.source).toMatch(/mitte mõõdetud sulgemine/);
  });

  it("frames activity as usage, never safety (PPA deliberately excluded)", () => {
    const act = OSMDAILY_DEFS.find((d) => d.id === "activity");
    expect(act?.source).toMatch(/KASUTUS-hinnang/);
    expect(act?.source).toMatch(/mitte turvalisus/);
  });

  it("frames herd as taste-match, never worth judgement", () => {
    const herd = OSMDAILY_DEFS.find((d) => d.id === "herd");
    expect(herd?.source).toMatch(/MAITSE-hinnang/);
    expect(herd?.source).toMatch(/mitte väärtushinnang/);
  });

  it("frames taxidoor as a weak findability sign with its stairwell bias stated", () => {
    const door = OSMDAILY_DEFS.find((d) => d.id === "taxidoor");
    expect(door?.source).toMatch(/trepikoja/);
    expect(door?.source).toMatch(/nõrk hea-märk/i);
    expect(door?.source).toMatch(/mitte külalisparkimise garantii/);
  });

  it("states unknown evening hours as unknown, never closed", () => {
    const third = OSMDAILY_DEFS.find((d) => d.id === "thirdplace");
    expect(third?.source).toMatch(/teadmata, mitte suletud/);
    const daily = OSMDAILY_DEFS.find((d) => d.id === "dailyshop");
    expect(daily?.source).toMatch(/EI OLE tarnegarantii/);
  });
});

describe("osmdaily scoring contract (#482)", () => {
  it("locks radii and bonus specs (raster contract + Euclidean fallback)", () => {
    expect(OSMDAILY_DECAY).toEqual({
      dailyshop: 0.5,
      activity: 0.4,
      herd: 1.0,
      thirdplace: 0.5,
      taxidoor: 0.3,
      lastshop: 0.5,
    });
    expect(OSMDAILY_BONUS).toEqual({
      dailyshop: { kind: "area", half: 8 },
      activity: { kind: "area", half: 12 },
      herd: { kind: "area", half: 3 },
      thirdplace: { kind: "area", half: 12 },
      taxidoor: { kind: "area", half: 30 },
      lastshop: { kind: "area", half: 12 },
    });
    for (const id of OSMDAILY_LAYER_IDS) {
      expect(radiusKmFor(id)).toBeCloseTo(OSMDAILY_DECAY[id], 5);
      expect(bonusSpecFor(id)).toEqual(OSMDAILY_BONUS[id]);
    }
  });

  it("bonusSpecForOsmdaily answers OSM-daily ids and ignores other layers", () => {
    expect(bonusSpecForOsmdaily("herd")).toEqual({ kind: "area", half: 3 });
    expect(bonusSpecForOsmdaily("parks")).toBeUndefined();
  });

  it("raster docs bake matching calibration (matchesContract)", () => {
    for (const id of OSMDAILY_LAYER_IDS) {
      const spec = OSMDAILY_BONUS[id];
      expect(spec.kind).toBe("area");
      if (spec.kind !== "area") continue;
      expect(
        matchesContract({ half: spec.half, sigma: OSMDAILY_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(true);
      // Stale half is rejected, never silently rendered.
      expect(
        matchesContract({ half: 999, sigma: OSMDAILY_DECAY[id], per: 0, cap: 0 }, id),
      ).toBe(false);
    }
    expect(OSMDAILY_RASTER_FILE.herd).toBe("herd-walk-raster.json");
  });

  it("scores 100 on top of a feature, decays with distance", () => {
    const pts = [{ lat: 59.4372, lon: 24.7536 }];
    expect(goodnessAt(59.4372, 24.7536, pts, "taxidoor")).toBe(100);
    const near = goodnessAt(59.4472, 24.7536, pts, "herd") as number;
    const far = goodnessAt(59.5372, 24.7536, pts, "herd") as number;
    expect(near).toBeGreaterThan(far);
  });

  it("reads sparse clusters mid-ramp on fixtures, never saturated", () => {
    // Three shops ~100 m apart under a sigma-0.5/half-8 kernel read
    // well below 100: sparse-but-real, not a saturated blob. (Euclidean
    // nearest-feature fallback reads 100 on top by contract — the
    // kernel shape above is what the raster path stamps.)
    expect(FIXTURE_SHOPS.length).toBe(3);
    expect(goodnessAt(59.4372, 24.7536, FIXTURE_SHOPS, "dailyshop")).toBe(100);
    expect(goodnessAt(59.2, 24.5, FIXTURE_SHOPS, "dailyshop")).not.toBe(100);
  });
});

describe("osmdaily queries and tags (#482)", () => {
  it("documents the verified snapshot tags per layer", () => {
    expect(OSMDAILY_TAGS.dailyshop).toContain("supermarket");
    expect(OSMDAILY_TAGS.dailyshop).toContain("greengrocer");
    expect(OSMDAILY_TAGS.activity).toContain("restaurant");
    expect(OSMDAILY_TAGS.activity).toContain("bakery");
    expect(OSMDAILY_TAGS.herd).toContain("museum");
    expect(OSMDAILY_TAGS.herd).toContain("gallery");
    expect(OSMDAILY_TAGS.thirdplace).toContain("cafe");
    expect(OSMDAILY_TAGS.thirdplace).toContain("sauna");
    expect(OSMDAILY_TAGS.taxidoor).toContain("entrance");
    expect(OSMDAILY_TAGS.taxidoor).toContain("staircase");
    expect(OSMDAILY_TAGS.lastshop).toContain("pharmacy");
    expect(OSMDAILY_TAGS.lastshop).toContain("atm");
  });

  it("builds bbox-scoped Overpass QL for the new layers", () => {
    const q = overpassQueryFor("lastshop", TALLINN_BBOX);
    expect(q).toContain("pharmacy");
    expect(q).toContain("24.5");
    const herd = overpassQueryFor("herd", TALLINN_BBOX);
    expect(herd).toContain("museum");
    const door = overpassQueryFor("taxidoor", TALLINN_BBOX);
    expect(door).toContain("entrance");
  });

  it("fetches new layers through the generic server proxy", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ points: [{ lat: 59.43, lon: 24.75 }], provenance: "snapshot", ageMs: 1 }),
    });
    const res = await fetchLayerPoints("dailyshop", TALLINN_BBOX, fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0]).startsWith("/api/layers/dailyshop?")).toBe(true);
    expect(res.provenance).toBe("snapshot");
  });
});
