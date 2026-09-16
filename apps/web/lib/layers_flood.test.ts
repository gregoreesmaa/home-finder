// Flood-risk polygon overlay tests (issue #487): p112 ships as an honest
// KAUR zone-membership choropleth (polygons only, never a gradient).
// Hermetic: inline area fixtures only, no network, no snapshot files.
import { describe, expect, it, vi } from "vitest";
import {
  FLOOD_BONUS,
  FLOOD_DECAY,
  FLOOD_DEFS,
  FLOOD_HOOK,
  FLOOD_LAYER_IDS,
  FLOOD_NO_METRO,
  FLOOD_PARAMS,
  FLOOD_RASTER_FILE,
  FLOOD_TAGS,
  bonusSpecForFlood,
  fetchFloodAreas,
  isFloodLayerId,
  isPolygonOnlyLayer,
} from "./layers_flood";
import {
  LAYERS,
  bonusSpecFor,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

const AREA = {
  zone_id: "KR-001",
  nimi: "Mullutu-Suurlaht kogu kalda ulatuses",
  veekogu: "Mullutu-Suurlaht",
  tyyp: "Suurte üleujutusaladega siseveekogu",
  b: [22.0, 58.2, 22.2, 58.3] as [number, number, number, number],
  r: [
    [
      [22.0, 58.2],
      [22.2, 58.2],
      [22.2, 58.3],
      [22.0, 58.3],
    ],
  ],
};

describe("floodzone registry (#487)", () => {
  it("ships exactly one layer bound to p112 (shared with Group 8 batch A)", () => {
    expect(FLOOD_LAYER_IDS).toEqual(["floodzone"]);
    expect(FLOOD_DEFS.map((d) => d.id)).toEqual(["floodzone"]);
    // p112 is shared on purpose (p13/p15 precedent): G08A keeps the
    // OSM-snapshot no-map verdict, floodzone asks KAUR zone membership.
    expect(FLOOD_PARAMS).toEqual({ floodzone: 112 });
    expect(FLOOD_DEFS[0].paramIds).toEqual([112]);
  });

  it("merges into LAYERS via the FLOOD-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 94 shipped layers (main at #503: +parking, +4 maru) + 1 flood-risk polygon overlay (94 + 1) + 2 P4OSM (P4OSM-HOOK #480, 95 + 2) +
    // 2 ookla tile layers (OOKLA-HOOK #489, 97 + 2) +
    // 1 accblack layer (ACCBLACK-HOOK #490, 99 + 1) + 1 maaparcel (MAAPARCEL-HOOK #491, 100 + 1) +
    // 3 eelis (EELIS-HOOK #488, 101 + 3) + 1 planktpr (PLANKTPR-HOOK #492, 104 + 1) +
    // 1 tervise (TERVISE-HOOK #494, 105 + 1) +
    // 1 asumedia (ASUMEDIA-HOOK #495, 106 + 1).
    // 3 eelis (EELIS-HOOK #488, 101 + 3) + 1 planktpr (PLANKTPR-HOOK #492, 104 + 1).
    // TERVISE-HOOK (#494): +1 tervise bathing-water layer (105 + 1).
    // PAASTE-HOOK (#493): +1 komando overlay (107 + 1).
    expect(ids.length).toBe(122); // SPORT-HOOK (#607): +3 sport slices (108 + 3); EHIS-HOOK (#608): +3 school slices (111 + 3); MEDRE-HOOK (#609): +2 care slices (114 + 2); OHUSEIRE-HOOK (#610): +1 station dots (116 + 1); KLIIMA-HOOK (#611): +2 climate slices (117 + 2); POI-HOOK (#612): +3 long-tail slices (119 + 3)
    expect(ids).toContain("floodzone");
  });

  it("explains green=good / red=bad in Estonian with NO demo points", () => {
    for (const d of FLOOD_DEFS) {
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
    expect(FLOOD_HOOK).toContain("FLOOD-HOOK (#487)");
    expect(FLOOD_RASTER_FILE.floodzone).toBe("floodzone-walk-raster.json");
    expect(FLOOD_NO_METRO).toBe(true);
  });
});

describe("floodzone honesty (#487)", () => {
  it("frames the layer as a zone-membership choropleth, never a hazard model", () => {
    const def = FLOOD_DEFS[0];
    expect(def.title).toMatch(/tsooniliide/);
    expect(def.goodLabel).toMatch(/hinnang, mitte mõõdetud risk/);
    expect(def.badLabel).toMatch(/teadmata, mitte kuiv/);
    expect(def.source).toMatch(/kr_yleujutusohuga_ala/);
    expect(def.source).toMatch(/Tallinna aknas 0/);
    expect(def.source).toMatch(/EFAS\/GloFAS tellimuse taga/);
  });

  it("carries the outside-unknown caveat in the legend (OTA PR #131 precedent)", () => {
    expect(overlayLegendFor("floodzone")).toContain("väljaspool = teadmata, mitte kuiv");
    expect(overlayLegendFor("floodzone")).toContain("T-bändid ja Tallinna polügoonid registris puuduvad");
    expect(overlayLegendFor("floodzone").length).toBeGreaterThan(10);
  });

  it("paints a distinct polygon color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("floodzone")).toBe("#1e3a8a");
  });
});

describe("floodzone scoring contract (#487)", () => {
  it("locks the inert decay placeholder (polygons only: never evaluated)", () => {
    expect(FLOOD_DECAY).toEqual({ floodzone: 0.5 });
    expect(radiusKmFor("floodzone")).toBeCloseTo(0.5, 5);
  });

  it("locks the inert bonus placeholder (zero points + null raster)", () => {
    expect(FLOOD_BONUS).toEqual({ floodzone: { kind: "area", half: 60 } });
    expect(bonusSpecFor("floodzone")).toEqual({ kind: "area", half: 60 });
  });

  it("bonusSpecForFlood answers floodzone and ignores other layers", () => {
    expect(bonusSpecForFlood("floodzone")).toEqual({ kind: "area", half: 60 });
    expect(bonusSpecForFlood("parks")).toBeUndefined();
    expect(isFloodLayerId("floodzone")).toBe(true);
    expect(isFloodLayerId("parks")).toBe(false);
    expect(isPolygonOnlyLayer("floodzone")).toBe(true);
    expect(isPolygonOnlyLayer("parks")).toBe(false);
    expect(isPolygonOnlyLayer("roadsafety")).toBe(false);
  });
});

describe("floodzone source and sidecar (#487)", () => {
  it("documents the KAUR WFS layer (no Overpass source)", () => {
    expect(FLOOD_TAGS.floodzone).toContain("kr_yleujutusohuga_ala");
    expect(FLOOD_TAGS.floodzone).toMatch(/Overpass-uta/);
  });

  it("carries the WFS provenance through the query builder", () => {
    const q = overpassQueryFor("floodzone", TALLINN_BBOX);
    expect(q).toContain("kr_yleujutusohuga_ala");
  });

  it("fetches zone polygons through the areas sidecar route", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA] }),
    });
    const areas = await fetchFloodAreas(fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0])).toBe("/api/layers/floodzone/areas");
    expect(areas).toHaveLength(1);
    expect(areas?.[0].nimi).toContain("Mullutu-Suurlaht");
  });

  it("drops malformed zones and fails null (never faked)", async () => {
    const bad = { ...AREA, r: [[[22.0]]] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA, bad, null, 7] }),
    });
    expect(await fetchFloodAreas(fetchImpl)).toHaveLength(1);
    const failImpl = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchFloodAreas(failImpl)).toBeNull();
    const shapeImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: "nope" }),
    });
    expect(await fetchFloodAreas(shapeImpl)).toBeNull();
  });
});
