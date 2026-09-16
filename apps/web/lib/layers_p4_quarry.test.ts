// Quarry extraction + exploration polygon overlay tests (issue #614):
// one honest class choropleth (polygons only, never a gradient).
// Hermetic: inline area fixtures only, no network, no snapshot files.
import { describe, expect, it, vi } from "vitest";
import {
  QUARRY_ATTRIBUTION,
  QUARRY_BONUS,
  QUARRY_CLASS_FILL,
  QUARRY_CLASS_SCORE,
  QUARRY_CLASSES,
  QUARRY_DECAY,
  QUARRY_DEFS,
  QUARRY_HOOK,
  QUARRY_LAYER_IDS,
  QUARRY_NO_METRO,
  QUARRY_NO_RASTER,
  QUARRY_RASTER_FILE,
  QUARRY_TAGS,
  bonusSpecForQuarry,
  fetchQuarryAreas,
  isQuarryLayerId,
  isQuarryPolygonOnlyLayer,
} from "./layers_p4_quarry";
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
  zone_id: "13379",
  nimi: "Huntaugu I liivakarjäär",
  cls: "active",
  loa: "HARM-139",
  loa_lopp: "20310301",
  operaator: "AS TREV-2 Grupp",
  b: [25.36, 59.42, 25.38, 59.44] as [number, number, number, number],
  r: [
    [
      [25.36, 59.42],
      [25.38, 59.42],
      [25.38, 59.44],
      [25.36, 59.44],
    ],
  ],
};

describe("quarry registry (#614)", () => {
  it("ships exactly one layer in the parameters4 namespace", () => {
    expect(QUARRY_LAYER_IDS).toEqual(["quarry"]);
    expect(QUARRY_DEFS.map((d) => d.id)).toEqual(["quarry"]);
    expect(QUARRY_DEFS[0].paramIds).toEqual([]);
    expect(QUARRY_DEFS[0].paramLabel).toBe("P4-maavara");
  });

  it("merges into LAYERS via the QUARRY-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 123 shipped layers on main (#623 fixit) + 1 quarry
    // extraction/exploration overlay (QUARRY-HOOK #614, 123 + 1).
    expect(ids.length).toBe(124);
    expect(ids).toContain("quarry");
  });

  it("explains green=good / red=bad in Estonian with NO demo points", () => {
    for (const d of QUARRY_DEFS) {
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
    expect(QUARRY_HOOK).toContain("QUARRY-HOOK (#614)");
    expect(QUARRY_RASTER_FILE.quarry).toBe("quarry-walk-raster.json");
    expect(QUARRY_NO_RASTER).toBe(true);
    expect(QUARRY_NO_METRO).toBe(true);
  });
});

describe("quarry honesty (#614)", () => {
  it("frames the layer as a permit-class choropleth, never a quarry-free claim", () => {
    const def = QUARRY_DEFS[0];
    expect(def.title).toMatch(/Karjäär/);
    expect(def.badLabel).toMatch(/teadmata, mitte kaevandusvaba/);
    expect(def.source).toMatch(/Maa- ja Ruumiamet/);
    expect(def.source).toMatch(/taotletavaid lubasid EI OLE/);
  });

  it("carries the outside-unknown caveat in the legend (OTA PR #131 precedent)", () => {
    expect(overlayLegendFor("quarry")).toContain("väljaspool = teadmata, mitte kaevandusvaba");
    expect(overlayLegendFor("quarry").length).toBeGreaterThan(10);
  });

  it("paints a distinct polygon color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("quarry")).toBe("#431407");
  });

  it("locks two map classes with scorer parity (facts, never scores)", () => {
    expect(QUARRY_CLASS_FILL).toEqual({
      active: "#c2410c",
      exploration: "#eab308",
    });
    // Scorer parity: dims_p4_maavara_extract (active inside 25,
    // exploration watch-flag 55; the <= 2 km near-band 45 is
    // scorer-side only and has no map class).
    expect(QUARRY_CLASS_SCORE).toEqual({ active: 25, exploration: 55 });
    expect(QUARRY_CLASSES).toEqual(["active", "exploration"]);
  });

  it("attributes Maa- ja Ruumiamet (CC BY 4.0)", () => {
    expect(QUARRY_ATTRIBUTION).toContain("Maa- ja Ruumiamet");
    expect(QUARRY_ATTRIBUTION).toContain("CC BY 4.0");
  });
});

describe("quarry scoring contract (#614)", () => {
  it("locks the inert decay placeholder (polygons only: never evaluated)", () => {
    expect(QUARRY_DECAY).toEqual({ quarry: 0.5 });
    expect(radiusKmFor("quarry")).toBeCloseTo(0.5, 5);
  });

  it("locks the inert bonus placeholder (zero points + null raster)", () => {
    expect(QUARRY_BONUS).toEqual({ quarry: { kind: "area", half: 60 } });
    expect(bonusSpecFor("quarry")).toEqual({ kind: "area", half: 60 });
  });

  it("bonusSpecForQuarry answers quarry and ignores other layers", () => {
    expect(bonusSpecForQuarry("quarry")).toEqual({ kind: "area", half: 60 });
    expect(bonusSpecForQuarry("parks")).toBeUndefined();
    expect(isQuarryLayerId("quarry")).toBe(true);
    expect(isQuarryLayerId("parks")).toBe(false);
    expect(isQuarryPolygonOnlyLayer("quarry")).toBe(true);
    expect(isQuarryPolygonOnlyLayer("parks")).toBe(false);
    expect(isQuarryPolygonOnlyLayer("roadsafety")).toBe(false);
  });
});

describe("quarry source and sidecar (#614)", () => {
  it("documents the Maa-amet WFS register (no Overpass source)", () => {
    expect(QUARRY_TAGS.quarry).toContain("maeeraldis_aktiivne");
    expect(QUARRY_TAGS.quarry).toMatch(/Overpass-uta/);
  });

  it("carries the register provenance through the query builder", () => {
    const q = overpassQueryFor("quarry", TALLINN_BBOX);
    expect(q).toContain("maeeraldis_aktiivne");
  });

  it("skips the raster window fetch (no master by decision — no designed 500)", async () => {
    const fetchImpl = vi.fn(() => {
      throw new Error("window must not be fetched for polygon-only layers");
    });
    expect(await fetchWindow("quarry", TALLINN_BBOX, fetchImpl)).toBeNull();
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("fetches permit polygons through the areas sidecar route", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA] }),
    });
    const areas = await fetchQuarryAreas(fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0])).toBe("/api/layers/quarry/areas");
    expect(areas).toHaveLength(1);
    expect(areas?.[0].zone_id).toBe("13379");
    expect(areas?.[0].cls).toBe("active");
    expect(areas?.[0].loa).toBe("HARM-139");
  });

  it("drops malformed areas and fails null (never faked)", async () => {
    const bad = { ...AREA, cls: "pending", r: [[[25.3]]] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA, bad, null, 7] }),
    });
    expect(await fetchQuarryAreas(fetchImpl)).toHaveLength(1);
    const failImpl = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchQuarryAreas(failImpl)).toBeNull();
    const shapeImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: "nope" }),
    });
    expect(await fetchQuarryAreas(shapeImpl)).toBeNull();
  });
});
