// Group 17 HOA-rest layer tests (issue #196): p245 privroad proxy
// ships; p4/p49/p142/p145/p152/p167/p246/p247/p278/p368/p427 are
// documented no-map (no layer, scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G17R_CAL,
  G17R_RASTER_FILE,
  G17R_VERDICTS,
  GROUP17REST_ALL_PARAMS,
  GROUP17REST_HOOK,
  GROUP17REST_BONUS,
  GROUP17REST_DECAY,
  GROUP17REST_LAYER_IDS,
  GROUP17REST_LAYERS,
  GROUP17REST_NO_MAP_PARAMS,
  GROUP17REST_PARAM_IDS,
  GROUP17REST_TAGS,
  bonusSpecForGroup17Rest,
  group17RestMatchesContract,
  group17RestQuietFromHalf,
  group17RestQuietnessAt,
  isGroup17RestLayerId,
} from "./layers_group17rest";

describe("group17rest registry", () => {
  it("ships exactly one layer (p245); no-map params stay out", () => {
    expect(GROUP17REST_LAYER_IDS).toEqual(["privroad"]);
    expect(GROUP17REST_LAYERS.map((l) => l.id)).toEqual(["privroad"]);
    expect(GROUP17REST_PARAM_IDS).toEqual({ privroad: 245 });
    expect([...GROUP17REST_ALL_PARAMS]).toEqual([4, 49, 142, 145, 152, 167, 245, 246, 247, 278, 368, 427]);
    // The eleven document facts must never gain a layer silently: the
    // shipped param set is exactly p245.
    const shipped = new Set(GROUP17REST_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([245]);
    expect([...GROUP17REST_NO_MAP_PARAMS]).toEqual([4, 49, 142, 145, 152, 167, 246, 247, 278, 368, 427]);
  });

  it("labels the layer honestly (hinnang, never registry data)", () => {
    for (const def of GROUP17REST_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP17REST_LAYERS[0].source).toContain("KÜ");
    expect(GROUP17REST_LAYERS[0].source).toContain("Äriregister");
    expect(GROUP17REST_LAYERS[0].source).toContain("parkla");
  });

  it("documents the PBF-extract source tags (private shared roads)", () => {
    expect(GROUP17REST_TAGS.privroad).toContain("private");
    expect(GROUP17REST_TAGS.privroad).toContain("service");
    expect(GROUP17REST_TAGS.privroad).toContain("residential");
    // Shared roads only: driveways and parking aisles stay out of the
    // tag story (the exclusion lives in the scorer mapping).
    expect(GROUP17REST_TAGS.privroad).not.toContain("driveway");
    expect(GROUP17REST_TAGS.privroad).not.toContain("mall");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G17R_CAL.privroad.halfM).toBe(200);
    expect(G17R_CAL.privroad.sigma).toBe(0.3);
    expect(GROUP17REST_DECAY.privroad).toBe(0.3);
    expect(GROUP17REST_BONUS.privroad).toEqual({ kind: "quiet", halfM: 200 });
    expect(bonusSpecForGroup17Rest("privroad")).toEqual({ kind: "quiet", halfM: 200 });
    expect(bonusSpecForGroup17Rest("parks")).toBeUndefined();
    expect(isGroup17RestLayerId("privroad")).toBe(true);
    expect(isGroup17RestLayerId("parks")).toBe(false);
    expect(G17R_RASTER_FILE.privroad).toBe("privroad-walk-raster.json");
  });

  it("serves fallback demo points (near + far)", () => {
    for (const def of GROUP17REST_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G17R_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [4, "no-map"],
      [49, "no-map"],
      [142, "no-map"],
      [145, "no-map"],
      [152, "no-map"],
      [167, "no-map"],
      [245, "proxy"],
      [246, "no-map"],
      [247, "no-map"],
      [278, "no-map"],
      [368, "no-map"],
      [427, "no-map"],
    ]);
    expect(GROUP17REST_HOOK).toContain("G17R-HOOK (#196)");
  });
});

describe("group17rest math", () => {
  it("reads 0 on the source, 50 at halfM, ~100 when far", () => {
    expect(group17RestQuietFromHalf(0, 200)).toBe(0);
    expect(group17RestQuietFromHalf(200, 200)).toBe(50);
    expect(group17RestQuietFromHalf(Infinity, 200)).toBe(100);
    expect(group17RestQuietFromHalf(1e9, 200)).toBeGreaterThan(99.9);
  });

  it("scores nearest-source distance (100 m from a road reads 33)", () => {
    const pts = [{ lat: 59.44256, lon: 24.57679 }];
    expect(group17RestQuietnessAt("privroad", 59.44256, 24.57679, pts)).toBe(0);
    // 100 m from the source reads 100*100/300 = 33.33 -> 33.
    const q = group17RestQuietnessAt("privroad", 59.44256 - 100 / 110570, 24.57679, pts);
    expect(q).toBe(33);
    expect(group17RestQuietnessAt("privroad", 59.44256, 24.57679, [])).toBeNull();
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group17RestMatchesContract("privroad", { half: 200, sigma: 0.3 })).toBe(true);
    expect(group17RestMatchesContract("privroad", { half: 300, sigma: 0.3 })).toBe(false);
    expect(group17RestMatchesContract("privroad", { half: 200, sigma: 0.5 })).toBe(false);
    expect(group17RestMatchesContract("privroad", null)).toBe(false);
  });
});
