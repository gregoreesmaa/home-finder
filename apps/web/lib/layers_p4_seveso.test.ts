// Seveso danger-area polygon overlay tests (issue #613): one honest
// danger-class choropleth (polygons only, never a gradient).
// Hermetic: inline area fixtures only, no network, no snapshot files.
import { describe, expect, it, vi } from "vitest";
import {
  SEVESO_ATTRIBUTION,
  SEVESO_BONUS,
  SEVESO_CLASS_FILL,
  SEVESO_DANGER_SCORE,
  SEVESO_DANGERS,
  SEVESO_DECAY,
  SEVESO_DEFS,
  SEVESO_HOOK,
  SEVESO_LAYER_IDS,
  SEVESO_NO_METRO,
  SEVESO_NO_RASTER,
  SEVESO_RASTER_FILE,
  SEVESO_TAGS,
  bonusSpecForSeveso,
  fetchSevesoAreas,
  isSevesoLayerId,
  isSevesoPolygonOnlyLayer,
} from "./layers_p4_seveso";
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

const AREA = {
  zone_id: "kaitse-001",
  nimi: "Muuga sadama terminaal",
  danger: "toxic",
  danger_label: "Mürgised ained",
  aadress: "Harju maakond, Muuga",
  b: [24.95, 59.48, 24.99, 59.51] as [number, number, number, number],
  r: [
    [
      [24.95, 59.48],
      [24.99, 59.48],
      [24.99, 59.51],
      [24.95, 59.51],
    ],
  ],
};

describe("seveso registry (#613)", () => {
  it("ships exactly one layer in the parameters4 namespace", () => {
    expect(SEVESO_LAYER_IDS).toEqual(["seveso"]);
    expect(SEVESO_DEFS.map((d) => d.id)).toEqual(["seveso"]);
    expect(SEVESO_DEFS[0].paramIds).toEqual([]);
    expect(SEVESO_DEFS[0].paramLabel).toBe("P4-ohuala");
  });

  it("merges into LAYERS via the SEVESO-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 123 shipped layers on main (#623 fixit) + 1 seveso danger-area
    // overlay (SEVESO-HOOK #613, 123 + 1) + 1 state/auction overlay
    // (STATELAND-HOOK #615, 124 + 1) + 1 quarry overlay
    // (QUARRY-HOOK #614, 125 + 1) + 1 drainage overlay
    // (DRAINAGE-HOOK #616, 126 + 1) + soil (#617, 127 + 1) + 1 etak
    // overlay (ETAK-HOOK #618, 128 + 1) + 1 relief overlay
    // (RELIEF-HOOK #619, 129 + 1) + 1 canopy overlay
    // (CANOPY-HOOK #620, 130 + 1) + 1 buildings overlay
    // (BUILDINGS-HOOK #621, 131 + 1) + 1 density overlay
    // (DENSITY-HOOK #622, 132 + 1) + 1 forest overlay
    // (FOREST-HOOK #624, 133 + 1 = 134).....
    expect(ids.length).toBe(135);
    expect(ids).toContain("seveso");
  });

  it("explains green=good / red=bad in Estonian with NO demo points", () => {
    for (const d of SEVESO_DEFS) {
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

  it("pins the hook marker + raster file + no-raster/no-metro verdict", () => {
    expect(SEVESO_HOOK).toContain("SEVESO-HOOK (#613)");
    expect(SEVESO_RASTER_FILE.seveso).toBe("seveso-walk-raster.json");
    expect(SEVESO_NO_RASTER).toBe(true);
    expect(SEVESO_NO_METRO).toBe(true);
  });
});

describe("seveso honesty (#613)", () => {
  it("frames the layer as a danger-class choropleth, never a safety claim", () => {
    const def = SEVESO_DEFS[0];
    expect(def.title).toMatch(/ohuala/);
    expect(def.badLabel).toMatch(/teadmata, mitte ohutu/);
    expect(def.source).toMatch(/Päästeamet/);
    expect(def.source).toMatch(/CC BY-NC-ND/);
  });

  it("carries the outside-unknown caveat in the legend (OTA PR #131 precedent)", () => {
    expect(overlayLegendFor("seveso")).toContain("väljaspool = teadmata, mitte ohutu");
    expect(overlayLegendFor("seveso").length).toBeGreaterThan(10);
  });

  it("paints a distinct polygon color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("seveso")).toBe("#3b0764");
  });

  it("locks five danger-class fills with scorer parity (facts, never scores)", () => {
    expect(SEVESO_CLASS_FILL).toEqual({
      toxic: "#dc2626",
      heat: "#f97316",
      overpressure: "#fb923c",
      combustion: "#b45309",
      unknown: "#94a3b8",
    });
    // Scorer parity: dims_p4_seveso DANGER_SCORES (toxic 20,
    // heat/overpressure 35, combustion 50, unknown 30).
    expect(SEVESO_DANGER_SCORE).toEqual({
      toxic: 20,
      heat: 35,
      overpressure: 35,
      combustion: 50,
      unknown: 30,
    });
    expect(SEVESO_DANGERS).toEqual(["toxic", "heat", "overpressure", "combustion", "unknown"]);
  });

  it("attributes Päästeamet on every row (CC BY-NC-ND)", () => {
    expect(SEVESO_ATTRIBUTION).toContain("Päästeamet");
    expect(SEVESO_ATTRIBUTION).toContain("CC BY-NC-ND");
  });
});

describe("seveso scoring contract (#613)", () => {
  it("locks the inert decay placeholder (polygons only: never evaluated)", () => {
    expect(SEVESO_DECAY).toEqual({ seveso: 0.5 });
    expect(radiusKmFor("seveso")).toBeCloseTo(0.5, 5);
  });

  it("locks the inert bonus placeholder (zero points + null raster)", () => {
    expect(SEVESO_BONUS).toEqual({ seveso: { kind: "area", half: 60 } });
    expect(bonusSpecFor("seveso")).toEqual({ kind: "area", half: 60 });
  });

  it("bonusSpecForSeveso answers seveso and ignores other layers", () => {
    expect(bonusSpecForSeveso("seveso")).toEqual({ kind: "area", half: 60 });
    expect(bonusSpecForSeveso("parks")).toBeUndefined();
    expect(isSevesoLayerId("seveso")).toBe(true);
    expect(isSevesoLayerId("parks")).toBe(false);
    expect(isSevesoPolygonOnlyLayer("seveso")).toBe(true);
    expect(isSevesoPolygonOnlyLayer("parks")).toBe(false);
    expect(isSevesoPolygonOnlyLayer("roadsafety")).toBe(false);
  });
});

describe("seveso source and sidecar (#613)", () => {
  it("documents the Paasteamet CSV register (no Overpass source)", () => {
    expect(SEVESO_TAGS.seveso).toContain("ohtlikud_kaitised_ohualad");
    expect(SEVESO_TAGS.seveso).toMatch(/Overpass-uta/);
  });

  it("carries the register provenance through the query builder", () => {
    const q = overpassQueryFor("seveso", TALLINN_BBOX);
    expect(q).toContain("ohtlikud_kaitised_ohualad");
  });

  it("skips the raster window fetch (no master by licence — no designed 500)", async () => {
    const fetchImpl = vi.fn(() => {
      throw new Error("window must not be fetched for polygon-only layers");
    });
    expect(await fetchWindow("seveso", TALLINN_BBOX, fetchImpl)).toBeNull();
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("fetches danger polygons through the areas sidecar route", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA] }),
    });
    const areas = await fetchSevesoAreas(fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0])).toBe("/api/layers/seveso/areas");
    expect(areas).toHaveLength(1);
    expect(areas?.[0].zone_id).toBe("kaitse-001");
    expect(areas?.[0].danger).toBe("toxic");
    expect(areas?.[0].danger_label).toBe("Mürgised ained");
  });

  it("drops malformed areas and fails null (never faked)", async () => {
    const bad = { ...AREA, danger: "radioactive", r: [[[24.7]]] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA, bad, null, 7] }),
    });
    expect(await fetchSevesoAreas(fetchImpl)).toHaveLength(1);
    const failImpl = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchSevesoAreas(failImpl)).toBeNull();
    const shapeImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: "nope" }),
    });
    expect(await fetchSevesoAreas(shapeImpl)).toBeNull();
  });
});
