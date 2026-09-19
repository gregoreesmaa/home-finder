// Maa-amet kataster parcel overlay tests (issue #491): p364 ships as an
// honest omandivorm-class choropleth (polygons only, never a gradient).
// Hermetic: inline area fixtures only, no network, no snapshot files.
import { describe, expect, it, vi } from "vitest";
import {
  MAAPARCEL_BONUS,
  MAAPARCEL_CLASS_FILL,
  MAAPARCEL_DECAY,
  MAAPARCEL_DEFS,
  MAAPARCEL_HOOK,
  MAAPARCEL_LAYER_IDS,
  MAAPARCEL_NO_METRO,
  MAAPARCEL_PARAMS,
  MAAPARCEL_RASTER_FILE,
  MAAPARCEL_TAGS,
  bonusSpecForMaaParcel,
  fetchMaaParcelAreas,
  isMaaParcelLayerId,
  isPolygonOnlyMaaLayer,
} from "./layers_maaparcel";
import {
  LAYERS,
  bonusSpecFor,
  fetchWindow,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

const PARCEL = {
  tunnus: "78401:107:0760",
  cls: "era",
  omvorm: "Eraomand",
  siht1: "ELAMUMAA",
  pindala: 1281,
  aadress: "Roosikrantsi tn 4c",
  kkis: 1,
  b: [24.74, 59.43, 24.75, 59.44] as [number, number, number, number],
  r: [
    [
      [24.74, 59.43],
      [24.75, 59.43],
      [24.75, 59.44],
      [24.74, 59.44],
    ],
  ],
};

describe("maaparcel registry (#491)", () => {
  it("ships exactly one layer bound to p364 (shared with the overturn hint)", () => {
    expect(MAAPARCEL_LAYER_IDS).toEqual(["maaparcel"]);
    expect(MAAPARCEL_DEFS.map((d) => d.id)).toEqual(["maaparcel"]);
    // p364 is shared on purpose (p13/p15 precedent): dims_overturn_maa
    // keeps the per-listing hint, maaparcel asks the fabric question.
    expect(MAAPARCEL_PARAMS).toEqual({ maaparcel: 364 });
    expect(MAAPARCEL_DEFS[0].paramIds).toEqual([364]);
  });

  it("merges into LAYERS via the MAAPARCEL-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 100 shipped layers on main (#506 accblack) + 1 kataster parcel
    // overlay (MAAPARCEL-HOOK #491, 100 + 1) + 3 eelis (EELIS-HOOK #488, 101 + 3) + 1 planktpr (PLANKTPR-HOOK #492, 104 + 1) +
    // 1 tervise (TERVISE-HOOK #494, 105 + 1) +
    // 1 asumedia (ASUMEDIA-HOOK #495, 106 + 1).
    // 1 tervise (TERVISE-HOOK #494, 105 + 1).
    // PAASTE-HOOK (#493): +1 komando overlay (107 + 1).
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    // HARNO-HOOK (#687): +1 harno school layer (156 + 1 = 157).
    // VIIRS-HOOK (#719): +1 viirs brightness layer (157 + 1 = 158).
    // OUTAGE-HOOK (#729): +1 outage hetkeseis layer (158 + 1 = 159).
    expect(ids.length).toBe(159); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    expect(ids).toContain("maaparcel");
  });

  it("explains green=good / red=bad in Estonian with NO demo points", () => {
    for (const d of MAAPARCEL_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source.length).toBeGreaterThan(0);
      // Polygons-only pin: a demo point would paint a fake gradient
      // splat, so the def carries none (generic labels test carves
      // polygon-only layers out of its fallbackPoints assertion).
      expect(d.fallbackPoints).toEqual([]);
    }
  });

  it("pins the hook marker + raster file + no-metro verdict", () => {
    expect(MAAPARCEL_HOOK).toContain("MAAPARCEL-HOOK (#491)");
    expect(MAAPARCEL_RASTER_FILE.maaparcel).toBe("maaparcel-walk-raster.json");
    expect(MAAPARCEL_NO_METRO).toBe(true);
  });
});

describe("maaparcel honesty (#491)", () => {
  it("frames the layer as an omandivorm-class choropleth, never suspicion", () => {
    const def = MAAPARCEL_DEFS[0];
    expect(def.title).toMatch(/omandivorm/);
    expect(def.goodLabel).toMatch(/RIK väljavõte jääb/);
    expect(def.badLabel).toMatch(/teadmata, mitte tühi/);
    expect(def.badLabel).toMatch(/100 katastritunnust Kesklinna aknas/);
    expect(def.source).toMatch(/kataster:ky_kehtiv/);
    expect(def.source).toMatch(/korduskontroll hiljemalt 2027-03-13/);
  });

  it("carries the outside-unknown caveat in the legend (OTA PR #131 precedent)", () => {
    expect(overlayLegendFor("maaparcel")).toContain("väljaspool = teadmata, mitte tühi");
    expect(overlayLegendFor("maaparcel")).toContain("RIK hoonestuse kontroll");
    expect(overlayLegendFor("maaparcel").length).toBeGreaterThan(10);
  });

  it("paints a distinct polygon color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("maaparcel")).toBe("#701a75");
  });

  it("locks four class fills (facts, never scores)", () => {
    expect(MAAPARCEL_CLASS_FILL).toEqual({
      era: "#22c55e",
      muni: "#fdba74",
      riik: "#fda4af",
      muu: "#94a3b8",
    });
  });
});

describe("maaparcel scoring contract (#491)", () => {
  it("locks the inert decay placeholder (polygons only: never evaluated)", () => {
    expect(MAAPARCEL_DECAY).toEqual({ maaparcel: 0.5 });
    expect(radiusKmFor("maaparcel")).toBeCloseTo(0.5, 5);
  });

  it("locks the inert bonus placeholder (zero points + null raster)", () => {
    expect(MAAPARCEL_BONUS).toEqual({ maaparcel: { kind: "area", half: 60 } });
    expect(bonusSpecFor("maaparcel")).toEqual({ kind: "area", half: 60 });
  });

  it("bonusSpecForMaaParcel answers maaparcel and ignores other layers", () => {
    expect(bonusSpecForMaaParcel("maaparcel")).toEqual({ kind: "area", half: 60 });
    expect(bonusSpecForMaaParcel("parks")).toBeUndefined();
    expect(isMaaParcelLayerId("maaparcel")).toBe(true);
    expect(isMaaParcelLayerId("parks")).toBe(false);
    expect(isPolygonOnlyMaaLayer("maaparcel")).toBe(true);
    expect(isPolygonOnlyMaaLayer("parks")).toBe(false);
    expect(isPolygonOnlyMaaLayer("roadsafety")).toBe(false);
  });
});

describe("maaparcel source and sidecar (#491)", () => {
  it("documents the kataster WFS layer (no Overpass source)", () => {
    expect(MAAPARCEL_TAGS.maaparcel).toContain("kataster:ky_kehtiv");
    expect(MAAPARCEL_TAGS.maaparcel).toMatch(/Overpass-uta/);
  });

  it("carries the WFS provenance through the query builder", () => {
    const q = overpassQueryFor("maaparcel", TALLINN_BBOX);
    expect(q).toContain("kataster:ky_kehtiv");
  });

  it("skips the raster window fetch (no master by decision — no designed 500)", async () => {
    const fetchImpl = vi.fn(() => {
      throw new Error("window must not be fetched for polygon-only layers");
    });
    expect(await fetchWindow("maaparcel", TALLINN_BBOX, fetchImpl)).toBeNull();
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("fetches parcel polygons through the areas sidecar route", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ parcels: [PARCEL] }),
    });
    const areas = await fetchMaaParcelAreas(fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0])).toBe("/api/layers/maaparcel/areas");
    expect(areas).toHaveLength(1);
    expect(areas?.[0].tunnus).toBe("78401:107:0760");
    expect(areas?.[0].cls).toBe("era");
    expect(areas?.[0].kkis).toBe(1);
  });

  it("drops malformed parcels and fails null (never faked)", async () => {
    const bad = { ...PARCEL, cls: "feudal", r: [[[24.7]]] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ parcels: [PARCEL, bad, null, 7] }),
    });
    expect(await fetchMaaParcelAreas(fetchImpl)).toHaveLength(1);
    const failImpl = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchMaaParcelAreas(failImpl)).toBeNull();
    const shapeImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ parcels: "nope" }),
    });
    expect(await fetchMaaParcelAreas(shapeImpl)).toBeNull();
  });
});
