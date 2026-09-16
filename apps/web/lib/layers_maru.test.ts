import { describe, expect, it } from "vitest";
import {
  MARUKOV_BANDS,
  MARUKOV_BONUS,
  MARUKOV_DECAY,
  MARUKOV_DEFAULTS,
  MARUKOV_DEFS,
  MARUKOV_HOOK,
  MARUKOV_LAYER_IDS,
  MARUKOV_PARAMS,
  MARUKOV_RASTER_FILE,
  MARUKOV_RESALE_RULE,
  bonusSpecForMaruKov,
  isMaruKovLayerId,
} from "./layers_maru";
import {
  LAYERS,
  bonusSpecFor,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { matchesContract } from "./server/snapshot";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("marukov registry (#486)", () => {
  it("defines exactly the four MARU KOV choropleth layers", () => {
    expect(MARUKOV_LAYER_IDS).toEqual(["kovkasv", "kovkaive", "kovedas", "kovkiirus"]);
    expect(MARUKOV_DEFS.map((d) => d.id)).toEqual(MARUKOV_LAYER_IDS);
    expect(MARUKOV_HOOK).toContain("MARUKOV-HOOK (#486)");
    // p421 is refused (needs the listing asking price -- no per-KOV
    // cell value exists): no fifth layer, ever.
    expect(MARUKOV_LAYER_IDS).not.toContain("kovgap");
    expect(MARUKOV_HOOK).toMatch(/p421 refused/);
    expect(Object.values(MARUKOV_PARAMS)).toEqual([41, 149, 43, 484]);
  });

  it("merges into LAYERS via the MARUKOV-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 90 shipped layers (main at #500: +parking) + 4 maru (90 + 4) +
    // 1 floodzone layer (FLOOD-HOOK #487, 94 + 1) + 2 P4OSM (P4OSM-HOOK #480, 95 + 2) +
    // 2 ookla tile layers (OOKLA-HOOK #489, 97 + 2) +
    // 1 accblack layer (ACCBLACK-HOOK #490, 99 + 1) + 1 maaparcel (MAAPARCEL-HOOK #491, 100 + 1) +
    // 3 eelis (EELIS-HOOK #488, 101 + 3) + 1 planktpr (PLANKTPR-HOOK #492, 104 + 1) +
    // 1 tervise (TERVISE-HOOK #494, 105 + 1) +
    // 1 asumedia (ASUMEDIA-HOOK #495, 106 + 1).
    // 3 eelis (EELIS-HOOK #488, 101 + 3) + 1 planktpr (PLANKTPR-HOOK #492, 104 + 1).
    // TERVISE-HOOK (#494): +1 tervise bathing-water layer (105 + 1).
    // PAASTE-HOOK (#493): +1 komando overlay (107 + 1).
    expect(ids.length).toBe(128); // MERGE (#613+#614+#615+#616+#617): 123 shipped + seveso + stateland + quarry + maaparandus + soil = 128 (both branch counts superseded).
    for (const id of MARUKOV_LAYER_IDS) expect(ids).toContain(id);
  });

  it("binds the real flipped G16 param numbers", () => {
    expect(LAYERS.find((l) => l.id === "kovkasv")?.paramIds).toEqual([41]);
    expect(LAYERS.find((l) => l.id === "kovkaive")?.paramIds).toEqual([149]);
    expect(LAYERS.find((l) => l.id === "kovedas")?.paramIds).toEqual([43]);
    expect(LAYERS.find((l) => l.id === "kovkiirus")?.paramIds).toEqual([484]);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of MARUKOV_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel).toMatch(/^roheline = /);
      expect(d.badLabel).toMatch(/^punane = /);
      expect(d.source).toContain("2026-09-12");
      expect(d.source).toContain("MARU");
      expect(d.fallbackPoints.length).toBeGreaterThan(0);
    }
  });

  it("carries the G16 question id in every title", () => {
    expect(MARUKOV_DEFS.find((d) => d.id === "kovkasv")?.title).toContain("p41");
    expect(MARUKOV_DEFS.find((d) => d.id === "kovkaive")?.title).toContain("p149");
    expect(MARUKOV_DEFS.find((d) => d.id === "kovedas")?.title).toContain("p43");
    expect(MARUKOV_DEFS.find((d) => d.id === "kovkiirus")?.title).toContain("p484");
  });
});

describe("marukov honesty (#486)", () => {
  it("says hinnang in every title and never claims measured truth", () => {
    for (const d of MARUKOV_DEFS) {
      expect(d.title).toMatch(/hinnang/);
      expect(d.title + d.source).not.toMatch(/mõõdetud|tegelik arv|täpne arv/);
    }
  });

  it("names the missing legs with EI OLE in every source", () => {
    const kasv = MARUKOV_DEFS.find((d) => d.id === "kovkasv");
    expect(kasv?.source).toMatch(/annualiseerimist EI OLE/);
    expect(kasv?.source).toMatch(/silumist EI OLE/);
    const kaive = MARUKOV_DEFS.find((d) => d.id === "kovkaive");
    expect(kaive?.source).toMatch(/jalga EI OLE/);
    const edas = MARUKOV_DEFS.find((d) => d.id === "kovedas");
    expect(edas?.source).toMatch(/EI FEIGITA/);
    expect(edas?.source).toMatch(/silumist EI OLE/);
    const kiirus = MARUKOV_DEFS.find((d) => d.id === "kovkiirus");
    expect(kiirus?.source).toMatch(/KV-adapteri jalga EI OLE/);
    expect(kiirus?.source).toMatch(/lagi 70/);
    expect(kiirus?.title).toMatch(/NÕRK/);
  });
});

describe("marukov calibration (#486)", () => {
  it("locks cover specs + decay (drift guard vs the Python builder)", () => {
    expect(MARUKOV_BONUS).toEqual({
      kovkasv: { kind: "cover", sigma: 0.5 },
      kovkaive: { kind: "cover", sigma: 0.5 },
      kovedas: { kind: "cover", sigma: 0.5 },
      kovkiirus: { kind: "cover", sigma: 0.5 },
    });
    expect(MARUKOV_DECAY).toEqual({ kovkasv: 0.5, kovkaive: 0.5, kovedas: 0.5, kovkiirus: 0.5 });
    for (const id of MARUKOV_LAYER_IDS) {
      expect(bonusSpecFor(id)).toEqual({ kind: "cover", sigma: 0.5 });
      expect(radiusKmFor(id)).toBe(0.5);
      expect(bonusSpecForMaruKov(id)).toEqual({ kind: "cover", sigma: 0.5 });
      expect(isMaruKovLayerId(id)).toBe(true);
    }
    expect(isMaruKovLayerId("parking")).toBe(false);
    expect(bonusSpecForMaruKov("parking")).toBeUndefined();
  });

  it("locks the band table (drift guard vs MARU_BANDS in Python)", () => {
    expect(MARUKOV_BANDS).toEqual({
      kovkasv: [[-5, 75], [0, 65], [5, 50], [10, 40]],
      kovkaive: [[300, 80], [100, 65], [30, 50]],
      kovkiirus: [[10, 70], [-10, 55]],
    });
    expect(MARUKOV_DEFAULTS).toEqual({ kovkasv: 30, kovkaive: 35, kovkiirus: 40 });
    // kovedas is a two-input composite, never a single-rate row.
    expect("kovedas" in MARUKOV_BANDS).toBe(false);
    expect(MARUKOV_RESALE_RULE).toContain("TT->70");
    expect(MARUKOV_RESALE_RULE).toContain("no half-comps");
  });

  it("matches the wire contract (half null, sigma 0.5)", () => {
    for (const id of MARUKOV_LAYER_IDS) {
      expect(matchesContract({ half: null, sigma: 0.5, per: 0, cap: 0 }, id)).toBe(true);
      expect(matchesContract({ half: 50, sigma: 0.5, per: 0, cap: 0 }, id)).toBe(false);
    }
  });

  it("names the raster masters built by the Python builder", () => {
    expect(MARUKOV_RASTER_FILE).toEqual({
      kovkasv: "kovkasv-walk-raster.json",
      kovkaive: "kovkaive-walk-raster.json",
      kovedas: "kovedas-walk-raster.json",
      kovkiirus: "kovkiirus-walk-raster.json",
    });
  });

  it("documents the KOV polygon source as relation queries", () => {
    for (const id of MARUKOV_LAYER_IDS) {
      expect(overpassQueryFor(id, TALLINN_BBOX)).toContain('admin_level"="7"');
    }
  });
});
