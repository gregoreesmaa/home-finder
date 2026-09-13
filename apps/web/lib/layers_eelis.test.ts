// EELIS nature-polygons overlay tests (issue #488): kaitse + niit +
// raie ship as honest zone-membership choropleths (polygons only,
// never a gradient). Hermetic: inline area fixtures only, no network,
// no snapshot files.
import { describe, expect, it, vi } from "vitest";
import {
  EELIS_BONUS,
  EELIS_DECAY,
  EELIS_DEFS,
  EELIS_HOOK,
  EELIS_KIND,
  EELIS_LAYER_IDS,
  EELIS_NO_METRO,
  EELIS_PARAM_LABELS,
  EELIS_RASTER_FILE,
  EELIS_TAGS,
  EELIS_WFS_LAYER,
  bonusSpecForEelis,
  eelisAreasForKind,
  eelisKindForLayer,
  fetchEelisAreas,
  isEelisLayerId,
  isEelisPolygonOnlyLayer,
} from "./layers_eelis";
import {
  LAYERS,
  bonusSpecFor,
  layerParamTag,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import { matchesContract } from "./server/snapshot";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

const AREA = {
  kiht: "kaitse",
  zone_id: "KLO-123",
  nimi: "Pirita jõeoru maastikukaitseala",
  lisa: "maastikukaitseala",
  b: [24.83, 59.44, 24.88, 59.48] as [number, number, number, number],
  r: [
    [
      [24.83, 59.44],
      [24.88, 59.44],
      [24.88, 59.48],
      [24.83, 59.48],
    ],
  ],
};

describe("eelis registry (#488)", () => {
  it("ships exactly the three nature-polygon layers", () => {
    expect(EELIS_LAYER_IDS).toEqual(["eeliskaitse", "eelisniit", "eelisraie"]);
    expect(EELIS_DEFS.map((d) => d.id)).toEqual(EELIS_LAYER_IDS);
    expect(EELIS_HOOK).toContain("EELIS-HOOK (#488)");
    // Flood is owned by #487, emitters are a point register — neither
    // gains a layer here, ever.
    expect(EELIS_LAYER_IDS).not.toContain("eelisvesi");
    expect(EELIS_LAYER_IDS).not.toContain("floodzone");
    expect(EELIS_LAYER_IDS).not.toContain("eelisheide");
    for (const d of EELIS_DEFS) expect(d.paramIds).toEqual([]);
  });

  it("merges into LAYERS via the EELIS-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 101 shipped layers on main (#507 maaparcel) + 3 eelis
    // nature-polygon overlays (EELIS-HOOK #488, 101 + 3) + 1 planktpr (PLANKTPR-HOOK #492, 104 + 1).
    expect(ids.length).toBe(105);
    for (const id of EELIS_LAYER_IDS) expect(ids).toContain(id);
  });

  it("binds the P4 buyer-param slices as labels, never parameters3 ids", () => {
    expect(EELIS_PARAM_LABELS).toEqual({
      eeliskaitse: "P4-015",
      eelisniit: "P4-024",
      eelisraie: "P4-030",
    });
    for (const d of EELIS_DEFS) {
      expect(d.paramLabel).toBe(EELIS_PARAM_LABELS[d.id as keyof typeof EELIS_PARAM_LABELS]);
      expect(layerParamTag(d)).toBe(`(${d.paramLabel})`);
    }
    expect(LAYERS.find((l) => l.id === "eeliskaitse")?.paramIds).toEqual([]);
    expect(LAYERS.find((l) => l.id === "eelisniit")?.paramIds).toEqual([]);
    expect(LAYERS.find((l) => l.id === "eelisraie")?.paramIds).toEqual([]);
  });

  it("carries the P4 question id in every title", () => {
    expect(EELIS_DEFS.find((d) => d.id === "eeliskaitse")?.title).toContain("P4-015");
    expect(EELIS_DEFS.find((d) => d.id === "eelisniit")?.title).toContain("P4-024");
    expect(EELIS_DEFS.find((d) => d.id === "eelisraie")?.title).toContain("P4-030");
  });

  it("explains in-zone vs honestly-unknown-outside with NO demo points", () => {
    for (const d of EELIS_DEFS) {
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

  it("pins the hook marker + raster files + no-metro verdict", () => {
    expect(EELIS_HOOK).toContain("EELIS-HOOK (#488)");
    expect(EELIS_HOOK).toContain("emitters refused");
    expect(EELIS_RASTER_FILE).toEqual({
      eeliskaitse: "eeliskaitse-walk-raster.json",
      eelisniit: "eelisniit-walk-raster.json",
      eelisraie: "eelisraie-walk-raster.json",
    });
    expect(EELIS_NO_METRO).toBe(true);
  });
});

describe("eelis honesty (#488)", () => {
  it("says hinnang/proksi in every title and never claims measured truth", () => {
    for (const d of EELIS_DEFS) {
      expect(d.title).toMatch(/hinnang/);
      expect(d.title + d.source).not.toMatch(/mõõdetud|tegelik arv|täpne arv/);
    }
  });

  it("names the missing legs with EI OLE in every source", () => {
    const kaitse = EELIS_DEFS.find((d) => d.id === "eeliskaitse");
    expect(kaitse?.source).toMatch(/EI OLE/);
    expect(kaitse?.source).toMatch(/EI FEIGITA/);
    const niit = EELIS_DEFS.find((d) => d.id === "eelisniit");
    expect(niit?.source).toMatch(/rohevõrgustikku EI OLE/);
    expect(niit?.source).toMatch(/mitte liigiväide/);
    const raie = EELIS_DEFS.find((d) => d.id === "eelisraie");
    expect(raie?.source).toMatch(/satelliidi.*EI OLE/);
    expect(raie?.source).toMatch(/mitte delta/);
  });

  it("frames outside-every-polygon as unknown, never clear", () => {
    for (const d of EELIS_DEFS) {
      expect(d.badLabel).toMatch(/teadmata, mitte /);
    }
  });

  it("documents the flood/emitter refusals in the hook marker", () => {
    expect(EELIS_HOOK).toMatch(/flood owned by #487/);
    expect(EELIS_HOOK).toMatch(/point register/);
  });

  it("carries the outside-unknown caveat in the legend", () => {
    for (const id of EELIS_LAYER_IDS) {
      expect(overlayLegendFor(id)).toContain("väljaspool = teadmata");
      expect(overlayLegendFor(id)).toContain("hinnang");
      expect(overlayLegendFor(id).length).toBeGreaterThan(10);
    }
  });

  it("paints three distinct polygon colors (distinct-color registry covers them)", () => {
    const colors = EELIS_LAYER_IDS.map(overlayColorFor);
    expect(new Set(colors).size).toBe(3);
    expect(overlayColorFor("eeliskaitse")).toBe("#1a2e05");
    expect(overlayColorFor("eelisniit")).toBe("#10b981");
    expect(overlayColorFor("eelisraie")).toBe("#9c4221");
  });
});

describe("eelis scoring contract (#488)", () => {
  it("locks the inert decay placeholders (polygons only: never evaluated)", () => {
    expect(EELIS_DECAY).toEqual({ eeliskaitse: 0.5, eelisniit: 0.5, eelisraie: 0.5 });
    for (const id of EELIS_LAYER_IDS) expect(radiusKmFor(id)).toBeCloseTo(0.5, 5);
  });

  it("locks the inert bonus placeholders (zero points + null raster)", () => {
    expect(EELIS_BONUS).toEqual({
      eeliskaitse: { kind: "area", half: 60 },
      eelisniit: { kind: "area", half: 60 },
      eelisraie: { kind: "area", half: 60 },
    });
    for (const id of EELIS_LAYER_IDS) {
      expect(bonusSpecFor(id)).toEqual({ kind: "area", half: 60 });
      expect(bonusSpecForEelis(id)).toEqual({ kind: "area", half: 60 });
    }
    expect(bonusSpecForEelis("parks")).toBeUndefined();
    expect(isEelisLayerId("eeliskaitse")).toBe(true);
    expect(isEelisLayerId("parks")).toBe(false);
    expect(isEelisPolygonOnlyLayer("eelisniit")).toBe(true);
    expect(isEelisPolygonOnlyLayer("parks")).toBe(false);
    expect(isEelisPolygonOnlyLayer("senscom")).toBe(false);
  });

  it("matches the inert wire contract shape (half 60, sigma 0.5)", () => {
    for (const id of EELIS_LAYER_IDS) {
      expect(matchesContract({ half: 60, sigma: 0.5, per: 0, cap: 0 }, id)).toBe(true);
      expect(matchesContract({ half: 61, sigma: 0.5, per: 0, cap: 0 }, id)).toBe(false);
    }
  });
});

describe("eelis source and sidecar (#488)", () => {
  it("names the WFS layer per map layer (no Overpass source)", () => {
    expect(EELIS_WFS_LAYER).toEqual({
      eeliskaitse: "eelis:kr_kaitseala",
      eelisniit: "eelis:niidud",
      eelisraie: "eelis:kaadamisalad",
    });
    for (const id of EELIS_LAYER_IDS) {
      expect(EELIS_TAGS[id]).toContain(EELIS_WFS_LAYER[id]);
      expect(EELIS_TAGS[id]).toMatch(/Overpass-uta/);
    }
  });

  it("carries the WFS provenance through the query builder", () => {
    expect(overpassQueryFor("eeliskaitse", TALLINN_BBOX)).toContain("kr_kaitseala");
    expect(overpassQueryFor("eelisniit", TALLINN_BBOX)).toContain("niidud");
    expect(overpassQueryFor("eelisraie", TALLINN_BBOX)).toContain("kaadamisalad");
  });

  it("maps each layer to its sidecar kind (shared sidecar, per-kind paint)", () => {
    expect(EELIS_KIND).toEqual({ eeliskaitse: "kaitse", eelisniit: "niit", eelisraie: "raie" });
    expect(eelisKindForLayer("eeliskaitse")).toBe("kaitse");
    expect(eelisKindForLayer("eelisniit")).toBe("niit");
    expect(eelisKindForLayer("eelisraie")).toBe("raie");
    expect(eelisKindForLayer("parks")).toBeNull();
    const rows = [
      { ...AREA, kiht: "kaitse" as const },
      { ...AREA, kiht: "niit" as const },
    ];
    expect(eelisAreasForKind(rows, "kaitse")).toHaveLength(1);
    expect(eelisAreasForKind(rows, "raie")).toHaveLength(0);
    expect(eelisAreasForKind(null, "kaitse")).toEqual([]);
  });

  it("fetches nature polygons through the eelis sidecar route", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA] }),
    });
    const areas = await fetchEelisAreas(fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0])).toBe("/api/layers/eelis/areas");
    expect(areas).toHaveLength(1);
    expect(areas?.[0].nimi).toContain("Pirita");
    expect(areas?.[0].kiht).toBe("kaitse");
  });

  it("drops malformed zones and fails null (never faked)", async () => {
    const bad = { ...AREA, r: [[[24.83]]] };
    const wrongKind = { ...AREA, kiht: "heide" };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA, bad, wrongKind, null, 7] }),
    });
    expect(await fetchEelisAreas(fetchImpl)).toHaveLength(1);
    const failImpl = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchEelisAreas(failImpl)).toBeNull();
    const shapeImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: "nope" }),
    });
    expect(await fetchEelisAreas(shapeImpl)).toBeNull();
  });
});
