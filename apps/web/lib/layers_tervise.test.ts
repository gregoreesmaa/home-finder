// Terviseamet monitoring-point overlay tests (issue #494): tervise
// ships as an honest points-empty layer (dated negative feed verdict —
// monitoring-point locations are not openly published, so no points
// are ever plotted and per-point quality stays NULL).
// Hermetic: no network, no snapshot files.
import { describe, expect, it } from "vitest";
import {
  TERVISE_BONUS,
  TERVISE_DECAY,
  TERVISE_DEFS,
  TERVISE_FEED_VERDICT,
  TERVISE_HOOK,
  TERVISE_LAYER_IDS,
  TERVISE_NO_METRO,
  TERVISE_PARAM_LABEL,
  TERVISE_RASTER_FILE,
  TERVISE_TAGS,
  bonusSpecForTervise,
  isTerviseLayerId,
} from "./layers_tervise";
import {
  LAYERS,
  bonusSpecFor,
  goodnessAt,
  layerParamTag,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("tervise registry (#494)", () => {
  it("ships exactly one layer in the parameters4 namespace (no faked parameters3 id)", () => {
    expect(TERVISE_LAYER_IDS).toEqual(["tervise"]);
    expect(TERVISE_DEFS.map((d) => d.id)).toEqual(["tervise"]);
    // P4-017/P4-024 are parameters4 buyer-param slices (same namespace
    // lock as senscom P4-031 and the osmdaily/statkov P4 layers): nearest
    // parameters3 numbers are taken map layers, so paramIds stays [] and
    // the button tag names the slices instead.
    expect(TERVISE_DEFS[0].paramIds).toEqual([]);
    expect(TERVISE_DEFS[0].paramLabel).toBe("P4-017+P4-024");
    expect(TERVISE_PARAM_LABEL).toBe("P4-017+P4-024");
    expect(layerParamTag(TERVISE_DEFS[0])).toBe("(P4-017+P4-024)");
  });

  it("merges into LAYERS via the TERVISE-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 95 shipped layers (main at #494: +floodzone) + 1 Terviseamet
    // monitoring-point overlay (95 + 1).
    expect(ids.length).toBe(96);
    expect(ids).toContain("tervise");
  });

  it("explains green=good / red=bad in Estonian with NO demo points", () => {
    for (const d of TERVISE_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source.length).toBeGreaterThan(0);
      // Points-empty pin: a demo point would paint a fake gradient
      // splat for unpublished monitoring locations, so the def carries
      // none (generic labels test carves points-empty layers out of
      // its fallbackPoints assertion).
      expect(d.fallbackPoints).toEqual([]);
    }
  });

  it("pins the hook marker + raster file + no-metro verdict", () => {
    expect(TERVISE_HOOK).toContain("TERVISE-HOOK (#494)");
    expect(TERVISE_RASTER_FILE.tervise).toBe("tervise-walk-raster.json");
    expect(TERVISE_NO_METRO).toBe(true);
  });
});

describe("tervise honesty (#494)", () => {
  it("frames the layer as a missing feed, never a health gradient", () => {
    const def = TERVISE_DEFS[0];
    expect(def.title).toMatch(/voog puudub/);
    expect(def.badLabel).toMatch(/EI OLE/);
    expect(def.source).toMatch(/2026-09-13/);
    expect(def.source).toMatch(/punkte ei leiutata/);
    expect(def.source).toMatch(/vtiav\.sm\.ee/);
  });

  it("pins the dated feed verdict (negative, with re-check date)", () => {
    expect(TERVISE_FEED_VERDICT.status).toBe("no-open-feed");
    expect(TERVISE_FEED_VERDICT.checked).toBe("2026-09-13");
    expect(TERVISE_FEED_VERDICT.recheckBy).toBe("2027-03-13");
  });

  it("carries the missing-feed caveat in the legend (OTA PR #131 precedent)", () => {
    expect(overlayLegendFor("tervise")).toContain("masinvoog puudub");
    expect(overlayLegendFor("tervise")).toContain("EI OLE");
    expect(overlayLegendFor("tervise").length).toBeGreaterThan(10);
  });

  it("paints a distinct marker color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("tervise")).toBe("#10b981");
  });

  it("scores nothing anywhere (zero points stay unknown, never zero)", () => {
    expect(goodnessAt(59.4372, 24.7536, [])).toBeNull();
    expect(radiusKmFor("tervise")).toBeCloseTo(0.5, 5);
  });
});

describe("tervise scoring contract (#494)", () => {
  it("locks the inert decay placeholder (points empty: never evaluated)", () => {
    expect(TERVISE_DECAY).toEqual({ tervise: 0.5 });
    expect(radiusKmFor("tervise")).toBeCloseTo(0.5, 5);
  });

  it("locks the inert bonus placeholder (zero points + null raster)", () => {
    expect(TERVISE_BONUS).toEqual({ tervise: { kind: "area", half: 60 } });
    expect(bonusSpecFor("tervise")).toEqual({ kind: "area", half: 60 });
  });

  it("bonusSpecForTervise answers tervise and ignores other layers", () => {
    expect(bonusSpecForTervise("tervise")).toEqual({ kind: "area", half: 60 });
    expect(bonusSpecForTervise("parks")).toBeUndefined();
    expect(isTerviseLayerId("tervise")).toBe(true);
    expect(isTerviseLayerId("parks")).toBe(false);
    expect(isTerviseLayerId("floodzone")).toBe(false);
  });
});

describe("tervise source note (#494)", () => {
  it("documents the missing feed (no Overpass source, no snapshot tags)", () => {
    expect(TERVISE_TAGS.tervise).toContain("vtiav.sm.ee");
    expect(TERVISE_TAGS.tervise).toMatch(/Overpass-uta/);
  });

  it("carries the provenance note through the query builder", () => {
    const q = overpassQueryFor("tervise", TALLINN_BBOX);
    expect(q).toContain("vtiav.sm.ee");
  });
});
