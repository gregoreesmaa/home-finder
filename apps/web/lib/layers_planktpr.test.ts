import { describe, expect, it, vi } from "vitest";
import {
  PLANKTPR_BONUS,
  PLANKTPR_CAP,
  PLANKTPR_DECAY,
  PLANKTPR_DEFS,
  PLANKTPR_HOOK,
  PLANKTPR_LAYER_IDS,
  PLANKTPR_NO_METRO,
  PLANKTPR_NO_RASTER,
  PLANKTPR_PARAMS,
  PLANKTPR_RASTER_FILE,
  PLANKTPR_TAGS,
  PLANKTPR_USE_BANDS,
  PLANKTPR_USE_COLORS,
  PLANKTPR_VERDICTS,
  bonusSpecForPlanktpr,
  fetchPlanktprAreas,
  isPlanktprArea,
  isPlanktprLayerId,
  planktprBandForUse,
  planktprClassifyUse,
  planktprColorForUse,
  planktprFold,
  planktprIsTallinn,
  planktprPointInRing,
  planktprScoreAt,
  type PlanktprArea,
} from "./layers_planktpr";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";

/** Two fixture polygons: elamu square + tootmis square, Tallinn. */
const ELAMU: PlanktprArea = {
  plan_id: "DP-001",
  use: "elamumaa",
  stage: "kehtestatud",
  kov: "Tallinn",
  rings: [
    [
      [24.7, 59.43],
      [24.72, 59.43],
      [24.72, 59.45],
      [24.7, 59.45],
    ],
  ],
};
const TOOTMIS: PlanktprArea = {
  plan_id: "DP-002",
  use: "tootmismaa",
  stage: "kehtestatud",
  kov: "Tallinna linn",
  rings: [
    [
      [24.8, 59.43],
      [24.82, 59.43],
      [24.82, 59.45],
      [24.8, 59.45],
    ],
  ],
};

describe("planktpr registry (#492)", () => {
  it("defines exactly the designated-use polygon layer", () => {
    expect(PLANKTPR_LAYER_IDS).toEqual(["planktpr"]);
    expect(PLANKTPR_DEFS.map((d) => d.id)).toEqual(PLANKTPR_LAYER_IDS);
    expect(PLANKTPR_PARAMS).toEqual({ planktpr: 47 });
    expect(PLANKTPR_DEFS[0].paramIds).toEqual([47]);
  });

  it("merges into LAYERS via the PLANKTPR-HOOK", () => {
    const ids = LAYERS.map((l) => l.id);
    expect(ids).toContain("planktpr");
    // 104 shipped layers on main (#508 eelis) + 1 designated-use
    // polygon layer (PLANKTPR-HOOK #492, 104 + 1) + 1 tervise (TERVISE-HOOK #494, 105 + 1) + 1 asumedia
    // (ASUMEDIA-HOOK #495, 106 + 1).
    // polygon layer (PLANKTPR-HOOK #492, 104 + 1) + 1 tervise (TERVISE-HOOK #494, 105 + 1).
    // PAASTE-HOOK (#493): +1 komando overlay (107 + 1).
    expect(ids.length).toBe(131); // MERGE (#613+#614+#615+#616+#617+#618+#619+#620): 123 shipped + seveso + stateland + quarry + maaparandus + soil + etak + relief + canopy = 131 (both branch counts superseded).
    expect(PLANKTPR_HOOK).toContain("PLANKTPR-HOOK (#492)");
  });

  it("labels the dated WFS negative honestly in Estonian", () => {
    const d = PLANKTPR_DEFS[0];
    expect(d.title).toContain("Sihtotstarve");
    expect(d.goodLabel).toContain("hinnang");
    expect(d.badLabel).toContain("EI OLE");
    expect(d.source).toContain("2026-09-13");
    expect(d.source).toContain("EI OLE");
    expect(d.source).toContain("kehtestatud");
    // Polygons only: no honest demo polygons exist, so the fallback is
    // EMPTY by decision — never faked fills.
    expect(d.fallbackPoints).toEqual([]);
  });

  it("uses the cover fallback spec with the wire sigma", () => {
    expect(PLANKTPR_BONUS).toEqual({ planktpr: { kind: "cover", sigma: 0.5 } });
    expect(bonusSpecForPlanktpr("planktpr")).toEqual(PLANKTPR_BONUS.planktpr);
    expect(bonusSpecForPlanktpr("parks")).toBeUndefined();
    expect(bonusSpecFor("planktpr")).toEqual(PLANKTPR_BONUS.planktpr);
    expect(isPlanktprLayerId("planktpr")).toBe(true);
    expect(isPlanktprLayerId("parks")).toBe(false);
    expect(PLANKTPR_DECAY).toEqual({ planktpr: 0.5 });
    expect(radiusKmFor("planktpr")).toBe(0.5);
  });

  it("documents the WFS (not Overpass) source vocabulary", () => {
    expect(PLANKTPR_TAGS.planktpr).toContain("WFS");
    expect(PLANKTPR_TAGS.planktpr).toContain("plank/areas.json");
  });

  it("builds no raster or metro master (polygons ARE the field)", () => {
    expect(PLANKTPR_RASTER_FILE).toEqual({ planktpr: "planktpr-walk-raster.json" });
    expect(PLANKTPR_NO_RASTER).toBe(true);
    expect(PLANKTPR_NO_METRO).toBe(true);
  });

  it("keeps p74/p274 scorer-only (decree texts and ceilings are not polygons)", () => {
    expect(PLANKTPR_VERDICTS.find((v) => v.param === 47)?.kind).toBe("polygons");
    expect(PLANKTPR_VERDICTS.find((v) => v.param === 74)?.kind).toBe("scorer-only");
    expect(PLANKTPR_VERDICTS.find((v) => v.param === 274)?.kind).toBe("scorer-only");
    expect(PLANKTPR_CAP).toBe(80);
  });
});

describe("planktpr use bands (#492, scorer parity)", () => {
  it("matches the overturn USE_BANDS first cut (cap 80)", () => {
    expect(PLANKTPR_USE_BANDS).toEqual({
      residential: 80,
      mixed: 60,
      commercial: 35,
      restricted: 20,
    });
  });

  it("folds Estonian diacritics before stem matching", () => {
    expect(planktprFold("Ärimaa")).toBe("arimaa");
    expect(planktprFold("  ")).toBeNull();
    expect(planktprFold(42)).toBeNull();
  });

  it("classifies use codes conservatively (restricted wins, unknown stays null)", () => {
    expect(planktprClassifyUse("elamumaa")).toBe("residential");
    expect(planktprClassifyUse("ELAMUPIIRKOND")).toBe("residential");
    expect(planktprClassifyUse("ärimaa")).toBe("commercial");
    expect(planktprClassifyUse("elamu- ja ärimaa")).toBe("mixed");
    expect(planktprClassifyUse("segafunktsioon")).toBe("mixed");
    // Restricted wins over housing even when both stems appear.
    expect(planktprClassifyUse("tootmis- ja elamumaa")).toBe("restricted");
    expect(planktprClassifyUse("tootmismaa")).toBe("restricted");
    expect(planktprClassifyUse("tundmatu kood 123")).toBeNull();
    expect(planktprClassifyUse(null)).toBeNull();
  });

  it("maps codes to bands, unknown codes to null (never assumed)", () => {
    expect(planktprBandForUse("elamumaa")).toBe(80);
    expect(planktprBandForUse("segafunktsioon")).toBe(60);
    expect(planktprBandForUse("ärimaa")).toBe(35);
    expect(planktprBandForUse("tootmismaa")).toBe(20);
    expect(planktprBandForUse("müstiline")).toBeNull();
  });

  it("colors fills green-to-red by band, unknown codes colorless", () => {
    expect(planktprColorForUse("elamumaa")).toBe(PLANKTPR_USE_COLORS.residential);
    expect(planktprColorForUse("ärimaa")).toBe(PLANKTPR_USE_COLORS.commercial);
    expect(planktprColorForUse("tootmismaa")).toBe(PLANKTPR_USE_COLORS.restricted);
    expect(planktprColorForUse("müstiline")).toBeNull();
    for (const c of Object.values(PLANKTPR_USE_COLORS)) {
      expect(c).toMatch(/^#[0-9a-f]{6}$/);
    }
  });

  it("accepts both Tallinn kov spellings, rejects the rest", () => {
    expect(planktprIsTallinn("Tallinn")).toBe(true);
    expect(planktprIsTallinn("Tallinna linn")).toBe(true);
    expect(planktprIsTallinn("Viimsi")).toBe(false);
    expect(planktprIsTallinn(null)).toBe(false);
  });
});

describe("planktpr exact per-parcel join (#492)", () => {
  it("scores inside kehtestatud polygons, null outside", () => {
    expect(planktprScoreAt(59.44, 24.71, [ELAMU, TOOTMIS])).toBe(80);
    expect(planktprScoreAt(59.44, 24.81, [ELAMU, TOOTMIS])).toBe(20);
    // Between the polygons: missing join is unknown, never good.
    expect(planktprScoreAt(59.44, 24.75, [ELAMU, TOOTMIS])).toBeNull();
    expect(planktprScoreAt(59.44, 24.71, [])).toBeNull();
  });

  it("refuses non-decree stages, non-Tallinn rows and unknown codes", () => {
    const menetluses = { ...ELAMU, stage: "menetluses" };
    expect(planktprScoreAt(59.44, 24.71, [menetluses])).toBeNull();
    const viimsi = { ...ELAMU, kov: "Viimsi vald" };
    expect(planktprScoreAt(59.44, 24.71, [viimsi])).toBeNull();
    const mystery = { ...ELAMU, use: "müstiline" };
    expect(planktprScoreAt(59.44, 24.71, [mystery])).toBeNull();
  });

  it("ray-casts rings (boundary corners stay deterministic)", () => {
    const ring = ELAMU.rings[0];
    expect(planktprPointInRing(24.71, 59.44, ring)).toBe(true);
    expect(planktprPointInRing(24.75, 59.44, ring)).toBe(false);
  });

  it("validates sidecar rows (malformed skipped, never faked)", () => {
    expect(isPlanktprArea(ELAMU)).toBe(true);
    expect(isPlanktprArea({ ...ELAMU, rings: [] })).toBe(false);
    expect(isPlanktprArea({ ...ELAMU, use: 42 })).toBe(false);
    expect(
      isPlanktprArea({ ...ELAMU, rings: [[[24.7, 59.43], [24.72, 59.43]]] }),
    ).toBe(false);
    expect(isPlanktprArea(null)).toBe(false);
  });

  it("fetches harvested polygons, null on any failure", async () => {
    const ok = vi.fn(async () => new Response(JSON.stringify({ areas: [ELAMU, { junk: 1 }] })));
    expect(await fetchPlanktprAreas(ok as unknown as typeof fetch)).toEqual([ELAMU]);
    const bad = vi.fn(async () => new Response("nope", { status: 500 }));
    expect(await fetchPlanktprAreas(bad as unknown as typeof fetch)).toBeNull();
    const throws = vi.fn(async () => {
      throw new Error("down");
    });
    expect(await fetchPlanktprAreas(throws as unknown as typeof fetch)).toBeNull();
  });
});

describe("planktpr overlay (#492)", () => {
  it("has a distinct marker color", () => {
    expect(overlayColorFor("planktpr")).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("legends the dated negative and the per-use fills in Estonian", () => {
    const legend = overlayLegendFor("planktpr");
    expect(legend.length).toBeGreaterThan(10);
    expect(legend).toContain("hinnang");
    expect(legend).toContain("EI OLE");
    expect(legend).toContain("2026-09-13");
    expect(legend).toContain("elamu");
  });
});
