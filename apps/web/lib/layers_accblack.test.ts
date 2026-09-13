// Transpordiamet accident-blackspot overlay tests (issue #490): P4-012
// measured slice ships as an honestly-empty layer (L-EST97 verdict
// 2026-09-13 — zero measured points plotted rather than misplotted).
// Hermetic: inline fixtures only, no network, no snapshot files.
import { describe, expect, it, vi } from "vitest";
import {
  ACCBLACK_BONUS,
  ACCBLACK_DECAY,
  ACCBLACK_DEFS,
  ACCBLACK_HALF_KM,
  ACCBLACK_HOOK,
  ACCBLACK_LAYER_IDS,
  ACCBLACK_MEASURED_POINTS,
  ACCBLACK_NO_RASTER,
  ACCBLACK_PARAM_LABEL,
  ACCBLACK_RASTER_FILE,
  ACCBLACK_PROBE,
  ACCBLACK_TAGS,
  ACCBLACK_WINDOW_M,
  bonusSpecForAccBlack,
  isAccBlackLayerId,
} from "./layers_accblack";
import {
  LAYERS,
  bonusSpecFor,
  fetchLayerPoints,
  goodnessAt,
  layerHexes,
  radiusKmFor,
  type BBoxLike,
} from "./layers";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("accblack registry (#490)", () => {
  it("ships exactly one layer bound to the P4-012 slice (no parameters3 id)", () => {
    expect(ACCBLACK_LAYER_IDS).toEqual(["accblack"]);
    expect(ACCBLACK_DEFS.map((d) => d.id)).toEqual(["accblack"]);
    // P4-slice overlay (senscom #484 precedent): paramIds stays [] so no
    // parameters3 param gains a map by accident; the button tag reads
    // "(P4-012)" off paramLabel.
    expect(ACCBLACK_DEFS[0].paramIds).toEqual([]);
    expect(ACCBLACK_PARAM_LABEL).toBe("P4-012");
    expect(ACCBLACK_DEFS[0].paramLabel).toBe("P4-012");
  });

  it("merges into LAYERS via the ACCBLACK-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 99 shipped layers on main (#505 ookla) + 1 accident-blackspot
    // (ACCBLACK-HOOK #490, 99 + 1) + 1 maaparcel (MAAPARCEL-HOOK #491, 100 + 1) +
    // 3 eelis (EELIS-HOOK #488, 101 + 3) + 1 planktpr (PLANKTPR-HOOK #492, 104 + 1) +
    // 1 tervise (TERVISE-HOOK #494, 105 + 1) +
    // 1 asumedia (ASUMEDIA-HOOK #495, 106 + 1).
    // 1 tervise (TERVISE-HOOK #494, 105 + 1).
    // PAASTE-HOOK (#493): +1 komando overlay (107 + 1).
    expect(ids.length).toBe(108);
    expect(ids).toContain("accblack");
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    for (const d of ACCBLACK_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source).toContain("2026-09-13");
      expect(d.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the hook marker + no-raster verdict", () => {
    expect(ACCBLACK_HOOK).toContain("ACCBLACK-HOOK (#490)");
    expect(ACCBLACK_NO_RASTER).toBe(true);
    expect(ACCBLACK_RASTER_FILE.accblack).toBe("accblack-walk-raster.json");
  });
});

describe("accblack honesty (#490)", () => {
  it("frames the layer as measured-but-waiting, never as safety truth", () => {
    const def = ACCBLACK_DEFS[0];
    expect(def.title).toMatch(/mõõdetud — ootel/);
    expect(def.source).toMatch(/L-EST97/);
    expect(def.source).toMatch(/ei joonistata ühtegi punkti/);
    expect(def.source).toMatch(/Transpordiamet/);
  });

  it("says unknown-everywhere in the legend (never zero, never safe)", () => {
    const def = ACCBLACK_DEFS[0];
    expect(def.goodLabel).toMatch(/teadmata/);
    expect(def.badLabel).toMatch(/teadmata/);
  });

  it("ships an explicitly empty measured set (no points to misplot)", () => {
    expect(ACCBLACK_MEASURED_POINTS).toEqual([]);
  });

  it("documents no Overpass fragment (CSV join, dims_p4_trans precedent)", () => {
    expect(ACCBLACK_TAGS.accblack).toMatch(/lo_2011_2026/);
    expect(ACCBLACK_TAGS.accblack).toMatch(/mitte Overpassist/);
  });

  it("pins the dated probe constants (parsed by the Python drift guard)", () => {
    expect(ACCBLACK_PROBE.date).toBe("2026-09-13");
    expect(ACCBLACK_PROBE.csvBytes).toBe(12342189);
    expect(ACCBLACK_PROBE.headerCols).toBe(54);
  });
});

describe("accblack scoring contract (#490)", () => {
  it("locks the blackspot window (300 m scorer window, kernel pattern)", () => {
    expect(ACCBLACK_HALF_KM).toBe(0.3);
    expect(ACCBLACK_WINDOW_M).toBe(300);
    expect(ACCBLACK_DECAY).toEqual({ accblack: 0.3 });
    expect(radiusKmFor("accblack")).toBeCloseTo(0.3, 5);
  });

  it("scores avoid-kind (red on blackspots, woodfire precedent)", () => {
    expect(ACCBLACK_BONUS).toEqual({ accblack: { kind: "avoid", half: 0.3 } });
    expect(bonusSpecFor("accblack")).toEqual({ kind: "avoid", half: 0.3 });
  });

  it("bonusSpecForAccBlack answers accblack and ignores other layers", () => {
    expect(bonusSpecForAccBlack("accblack")).toEqual({ kind: "avoid", half: 0.3 });
    expect(bonusSpecForAccBlack("parks")).toBeUndefined();
    expect(isAccBlackLayerId("accblack")).toBe(true);
    expect(isAccBlackLayerId("roadsafety")).toBe(false);
  });

  it("scores null everywhere with the empty measured set (never a faked zero)", () => {
    expect(goodnessAt(59.4374, 24.7454, ACCBLACK_MEASURED_POINTS, "accblack")).toBeNull();
    expect(layerHexes("accblack", ACCBLACK_MEASURED_POINTS, TALLINN_BBOX)).toEqual([]);
  });

  it("serves the empty set through the generic server proxy as honestly-empty", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ points: [], provenance: "empty", ageMs: null }),
    });
    const res = await fetchLayerPoints("accblack", TALLINN_BBOX, fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0]).startsWith("/api/layers/accblack?")).toBe(true);
    expect(res.provenance).toBe("empty");
    expect(res.points).toEqual([]);
    expect(res.live).toBe(true);
  });
});
