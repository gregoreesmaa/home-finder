import { describe, expect, it } from "vitest";
import {
  STATKOV_BANDS,
  STATKOV_BONUS,
  STATKOV_DECAY,
  STATKOV_DEFAULTS,
  STATKOV_DEFS,
  STATKOV_HOOK,
  STATKOV_LAYER_IDS,
  STATKOV_RASTER_FILE,
  bonusSpecForStatKov,
  isStatKovLayerId,
} from "./layers_statkov";
import {
  LAYERS,
  bonusSpecFor,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { matchesContract } from "./server/snapshot";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("statkov registry (#485)", () => {
  it("defines exactly the three PX-Web KOV choropleth layers", () => {
    expect(STATKOV_LAYER_IDS).toEqual(["kovmigr", "kovehit", "kovfisc"]);
    expect(STATKOV_DEFS.map((d) => d.id)).toEqual(STATKOV_LAYER_IDS);
    expect(STATKOV_HOOK).toContain("STATKOV-HOOK (#485)");
    // IA028 is refused (national grain) -- no fourth layer, ever.
    expect(STATKOV_LAYER_IDS).not.toContain("kovhind");
    for (const d of STATKOV_DEFS) expect(d.paramIds).toEqual([]);
  });

  it("merges into LAYERS via the STATKOV-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 86 shipped layers on main (77 + 6 osmdaily #482 + 1 gtfs #483 +
    // 1 roadsafety #481 + 1 senscom #484) + 3 statkov layers (86 + 3) +
    // 1 parking layer (P4PARK-HOOK #479, 89 + 1).
    // MARUKOV-HOOK (#486): +4 MARU KOV choropleths join the registry (90 + 4).
    // FLOOD-HOOK (#487): +1 flood-risk polygon overlay (94 + 1) + 2 P4OSM (P4OSM-HOOK #480, 95 + 2).
    // 1 roadsafety #481 + 1 senscom #484) + 3 statkov layers (86 + 3).
    // OOKLA-HOOK (#489): +2 quarterly-tile layers (97 + 2).
    // 1 roadsafety #481 + 1 senscom #484) + 3 statkov layers (86 + 3)
    // + 1 accblack layer (ACCBLACK-HOOK #490, 89 + 1).
    // MAAPARCEL-HOOK (#491): +1 parcel overlay (100 + 1).

    // EELIS-HOOK (#488): +3 nature-polygon layers join the registry (101 + 3).
    // PLANKTPR-HOOK (#492): +1 designated-use polygon layer (104 + 1).
    // TERVISE-HOOK (#494): +1 tervise bathing-water layer (105 + 1).
    // ASUMEDIA-HOOK (#495): +1 per-asum median layer (106 + 1).
    // PAASTE-HOOK (#493): +1 komando overlay (107 + 1).
    expect(ids.length).toBe(116); // SPORT-HOOK (#607): +3 sport slices (108 + 3); EHIS-HOOK (#608): +3 school slices (111 + 3); MEDRE-HOOK (#609): +2 care slices (114 + 2)
    for (const id of STATKOV_LAYER_IDS) expect(ids).toContain(id);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of STATKOV_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel).toMatch(/^roheline = /);
      expect(d.badLabel).toMatch(/^punane = /);
      expect(d.source).toContain("2026-09-12");
      expect(d.source).toContain("2025");
      expect(d.fallbackPoints.length).toBeGreaterThan(0);
    }
  });

  it("carries the P4 question id in every title", () => {
    expect(STATKOV_DEFS.find((d) => d.id === "kovmigr")?.title).toContain("P4-025");
    expect(STATKOV_DEFS.find((d) => d.id === "kovehit")?.title).toContain("P4-050");
    expect(STATKOV_DEFS.find((d) => d.id === "kovfisc")?.title).toContain("P4-019");
  });
});

describe("statkov honesty (#485)", () => {
  it("says hinnang in every title and never claims measured truth", () => {
    for (const d of STATKOV_DEFS) {
      expect(d.title).toMatch(/hinnang/);
      expect(d.title + d.source).not.toMatch(/mõõdetud|tegelik arv|täpne arv/);
    }
  });

  it("names the missing legs with EI OLE in every source", () => {
    const fisc = STATKOV_DEFS.find((d) => d.id === "kovfisc");
    expect(fisc?.source).toMatch(/Võlakoormuse/);
    expect(fisc?.source).toMatch(/EI OLE/);
    expect(fisc?.source).toMatch(/lagi 70/);
    const ehit = STATKOV_DEFS.find((d) => d.id === "kovehit");
    expect(ehit?.source).toMatch(/EHITUSLUBADE/);
    expect(ehit?.source).toMatch(/EI FEIGITA/);
    const migr = STATKOV_DEFS.find((d) => d.id === "kovmigr");
    expect(migr?.source).toMatch(/EI OLE/);
    expect(migr?.source).toMatch(/silumist EI OLE/);
  });

  it("documents the IA028 refusal in the hook marker", () => {
    expect(STATKOV_HOOK).toMatch(/IA028 refused/);
  });
});

describe("statkov calibration (#485)", () => {
  it("locks cover specs + decay (drift guard vs the Python builder)", () => {
    expect(STATKOV_BONUS).toEqual({
      kovmigr: { kind: "cover", sigma: 0.5 },
      kovehit: { kind: "cover", sigma: 0.5 },
      kovfisc: { kind: "cover", sigma: 0.5 },
    });
    expect(STATKOV_DECAY).toEqual({ kovmigr: 0.5, kovehit: 0.5, kovfisc: 0.5 });
    for (const id of STATKOV_LAYER_IDS) {
      expect(bonusSpecFor(id)).toEqual({ kind: "cover", sigma: 0.5 });
      expect(radiusKmFor(id)).toBe(0.5);
      expect(bonusSpecForStatKov(id)).toEqual({ kind: "cover", sigma: 0.5 });
      expect(isStatKovLayerId(id)).toBe(true);
    }
    expect(isStatKovLayerId("parking")).toBe(false);
    expect(bonusSpecForStatKov("parking")).toBeUndefined();
  });

  it("locks the band table (drift guard vs STATKOV_BANDS in Python)", () => {
    expect(STATKOV_BANDS).toEqual({
      kovmigr: [[10, 75], [-5, 60], [-20, 45]],
      kovehit: [[20, 30], [10, 45], [4, 60]],
      kovfisc: [[10, 70], [5, 60], [0, 45]],
    });
    expect(STATKOV_DEFAULTS).toEqual({ kovmigr: 30, kovehit: 70, kovfisc: 30 });
  });

  it("matches the wire contract (half null, sigma 0.5)", () => {
    for (const id of STATKOV_LAYER_IDS) {
      expect(matchesContract({ half: null, sigma: 0.5, per: 0, cap: 0 }, id)).toBe(true);
      expect(matchesContract({ half: 50, sigma: 0.5, per: 0, cap: 0 }, id)).toBe(false);
    }
  });

  it("names the raster masters built by the Python builder", () => {
    expect(STATKOV_RASTER_FILE).toEqual({
      kovmigr: "kovmigr-walk-raster.json",
      kovehit: "kovehit-walk-raster.json",
      kovfisc: "kovfisc-walk-raster.json",
    });
  });

  it("documents the KOV polygon source as relation queries", () => {
    for (const id of STATKOV_LAYER_IDS) {
      expect(overpassQueryFor(id, TALLINN_BBOX)).toContain('admin_level"="7"');
    }
  });
});
