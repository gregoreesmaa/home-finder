import { describe, expect, it, vi } from "vitest";
import {
  SHED_ATTRIBUTION,
  SHED_BONUS,
  SHED_DECAY,
  SHED_DEFS,
  SHED_FILL,
  SHED_HOOK,
  SHED_LAYER_DEFS,
  SHED_LAYER_IDS,
  SHED_LAYER_SPEC,
  SHED_NO_METRO,
  SHED_RASTER_FILE,
  SHED_TAGS,
  SHED_UNMEASURED_FILL,
  SHED_WINDOW_ET,
  bonusSpecForSheds,
  fetchShedAreas,
  isShedLayerId,
  isShedPolygon,
  shedCoversPoint,
  shedPolygonsForLayer,
  type ShedPolygon,
} from "./layers_p4_tomtom_sheds";

const FIXTURE_SNAPSHOT = {
  polygons: [
    {
      hub: "city-center",
      budgetS: 1800,
      band: "rush",
      ring: [
        [59.4, 24.7],
        [59.4, 24.8],
        [59.47, 24.8],
        [59.47, 24.7],
      ],
    },
    {
      hub: "city-center",
      budgetS: 900,
      band: "rush",
      ring: [
        [59.42, 24.73],
        [59.42, 24.77],
        [59.45, 24.77],
        [59.45, 24.73],
      ],
    },
    { hub: "port", budgetS: 1800, band: "offpeak", ring: [] },
    { hub: "broken", budgetS: 1800, band: "rush", ring: "nope" },
  ],
};

describe("shed overlay (#670)", () => {
  it("ships four layers: 15/30 min x peak/off-peak", () => {
    expect(SHED_LAYER_IDS).toEqual([
      "shed-15-peak",
      "shed-15-offpeak",
      "shed-30-peak",
      "shed-30-offpeak",
    ]);
    expect(SHED_DEFS.map((d) => d.id)).toEqual(SHED_LAYER_IDS);
    expect(SHED_LAYER_SPEC["shed-30-peak"]).toEqual({
      budgetS: 1800,
      band: "rush",
    });
    expect(SHED_HOOK).toMatch(/SHED-HOOK \(#763\)/);
  });

  it("labels every layer windowed-never-live in Estonian (#783)", () => {
    for (const def of SHED_DEFS) {
      expect(def.hubCount).toBe(5);
      expect(`${def.title} ${def.source}`).toMatch(
        /mõõtmik, mitte reaalajas/,
      );
      expect(def.source).toContain(SHED_WINDOW_ET);
    }
    expect(SHED_ATTRIBUTION).toMatch(/mitte reaalajas/);
    expect(SHED_ATTRIBUTION).toContain(SHED_WINDOW_ET);
  });

  it("selects only matching-budget/band polygons with real rings", () => {
    const polys = shedPolygonsForLayer(FIXTURE_SNAPSHOT, "shed-30-peak");
    expect(polys.map((p) => p.hub)).toEqual(["city-center"]);
    expect(shedPolygonsForLayer(FIXTURE_SNAPSHOT, "shed-15-peak")).toHaveLength(
      1,
    );
    expect(shedPolygonsForLayer(FIXTURE_SNAPSHOT, "shed-30-offpeak")).toEqual(
      [],
    );
    expect(shedPolygonsForLayer({ polygons: [] }, "shed-30-peak")).toEqual([]);
    expect(shedPolygonsForLayer(null, "shed-30-peak")).toEqual([]);
  });

  it("covers points by ray casting (scorer parity)", () => {
    const poly = shedPolygonsForLayer(
      FIXTURE_SNAPSHOT,
      "shed-30-peak",
    )[0] as ShedPolygon;
    expect(shedCoversPoint(poly, 59.44, 24.75)).toBe(true);
    expect(shedCoversPoint(poly, 59.5, 24.9)).toBe(false);
    expect(
      shedCoversPoint({ ...poly, ring: [[59.4, 24.7]] }, 59.44, 24.75),
    ).toBe(false);
  });

  it("validates ids, polygons and unmeasured paint", () => {
    expect(isShedLayerId("shed-30-peak")).toBe(true);
    expect(isShedLayerId("delay-morning")).toBe(false);
    expect(isShedPolygon(FIXTURE_SNAPSHOT.polygons[0])).toBe(true);
    expect(isShedPolygon(FIXTURE_SNAPSHOT.polygons[3])).toBe(false);
    expect(SHED_UNMEASURED_FILL).toBe("#94a3b8");
    expect(Object.keys(SHED_FILL)).toEqual([...SHED_LAYER_IDS]);
  });
});

describe("shed wiring (#763)", () => {
  it("registers polygons-only defs (no demo points, P4 slice label)", () => {
    expect(SHED_LAYER_DEFS.map((d) => d.id)).toEqual(SHED_LAYER_IDS);
    for (const d of SHED_LAYER_DEFS) {
      expect(d.paramIds).toEqual([]);
      expect(d.paramLabel).toBe("P4-sõiduulatus");
      expect(d.fallbackPoints).toEqual([]);
    }
    expect(SHED_DECAY["shed-15-peak"]).toBe(0.2);
    expect(SHED_BONUS["shed-30-peak"]).toEqual({ kind: "pins" });
    expect(bonusSpecForSheds("shed-15-offpeak")).toEqual({ kind: "pins" });
    expect(bonusSpecForSheds("transit")).toBeUndefined();
    expect(SHED_TAGS["shed-15-peak"]).toContain("bus_stop");
    expect(SHED_RASTER_FILE["shed-30-peak"]).toBe(
      "shed-30-peak-walk-raster.json",
    );
    expect(SHED_NO_METRO).toBe(true);
  });

  it("fetches hub areas per layer, null on failure", async () => {
    const areas = [
      { hub: "city-center", ring: [[59.4, 24.7], [59.4, 24.8], [59.47, 24.8]] },
      { hub: "x", ring: [[1, 2]] },
      { hub: "y" },
    ];
    const ok = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ areas }),
    });
    const out = await fetchShedAreas("shed-15-peak", ok as never);
    expect(out).toEqual([areas[0]]);
    expect(String(ok.mock.calls[0][0])).toContain("layer=shed-15-peak");
    const bad = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchShedAreas("shed-15-peak", bad as never)).toBeNull();
  });

  it("maps the honest-empty 503-with-reason to null (never faked, #787)", async () => {
    const gone = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({
        error: "shed cache empty",
        reason: "TomTomi nädalapuhver puudub või on aegunud",
      }),
    });
    for (const layer of SHED_LAYER_IDS) {
      expect(await fetchShedAreas(layer, gone as never)).toBeNull();
    }
    const empty200 = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ areas: [], builtAtMs: null }),
    });
    expect(await fetchShedAreas("shed-30-peak", empty200 as never)).toEqual(
      [],
    );
  });
});
