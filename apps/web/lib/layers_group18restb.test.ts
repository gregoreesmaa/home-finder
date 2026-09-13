// Group 18 rest-B layer tests (issue #173): p468 fishbowl proxy +
// p479 mossrisk proxy + p405 daylight (sparse) proxy ship; p394/p403
// are documented no-map (no layer, scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G18B_CAL,
  G18B_RASTER_FILE,
  G18B_VERDICTS,
  GROUP18B_ALL_PARAMS,
  GROUP18B_HOOK,
  GROUP18B_BONUS,
  GROUP18B_DECAY,
  GROUP18B_LAYER_IDS,
  GROUP18B_LAYERS,
  GROUP18B_NO_MAP_PARAMS,
  GROUP18B_PARAM_IDS,
  GROUP18B_TAGS,
  bonusSpecForGroup18B,
  group18bDaylightAt,
  group18bHavKm,
  group18bMatchesContract,
  group18bQuietFromHalf,
  group18bQuietnessAt,
  group18bSparseScore,
  isGroup18BLayerId,
} from "./layers_group18restb";

describe("group18b registry", () => {
  it("ships exactly three layers (p468 + p479 + p405); no-map params stay out", () => {
    expect(GROUP18B_LAYER_IDS).toEqual(["fishbowl", "mossrisk", "daylight"]);
    expect(GROUP18B_LAYERS.map((l) => l.id)).toEqual(["fishbowl", "mossrisk", "daylight"]);
    expect(GROUP18B_PARAM_IDS).toEqual({ fishbowl: 468, mossrisk: 479, daylight: 405 });
    expect([...GROUP18B_ALL_PARAMS]).toEqual([394, 403, 405, 468, 479]);
    // p394/p403 must never gain a layer silently: the shipped
    // param set is exactly p405 + p468 + p479.
    const shipped = new Set(GROUP18B_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([468, 479, 405]);
    expect([...GROUP18B_NO_MAP_PARAMS]).toEqual([394, 403]);
  });

  it("labels all layers honestly (hinnang, never 3D-simulation data)", () => {
    for (const def of GROUP18B_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP18B_LAYERS[0].source).toContain("katastr");
    expect(GROUP18B_LAYERS[1].source).toContain("tänavapuu");
    expect(GROUP18B_LAYERS[2].source).toContain("luks");
  });

  it("documents the snapshot source tags (junctions + forest + buildings)", () => {
    expect(GROUP18B_TAGS.fishbowl).toContain("highway");
    expect(GROUP18B_TAGS.mossrisk).toContain("forest");
    expect(GROUP18B_TAGS.mossrisk).toContain("wood");
    // Street trees stay out by design (a street tree is not a moss stand).
    expect(GROUP18B_TAGS.mossrisk).not.toContain("tree");
    expect(GROUP18B_TAGS.daylight).toContain("building");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G18B_CAL.fishbowl.halfM).toBe(150);
    expect(G18B_CAL.fishbowl.sigma).toBe(0.3);
    expect(G18B_CAL.mossrisk.halfM).toBe(250);
    expect(G18B_CAL.mossrisk.sigma).toBe(0.3);
    expect(G18B_CAL.daylight.half).toBe(150);
    expect(G18B_CAL.daylight.sigma).toBe(0.3);
    expect(GROUP18B_DECAY.fishbowl).toBe(0.3);
    expect(GROUP18B_DECAY.mossrisk).toBe(0.3);
    expect(GROUP18B_DECAY.daylight).toBe(0.3);
    expect(GROUP18B_BONUS.fishbowl).toEqual({ kind: "quiet", halfM: 150 });
    expect(GROUP18B_BONUS.mossrisk).toEqual({ kind: "quiet", halfM: 250 });
    expect(GROUP18B_BONUS.daylight).toEqual({ kind: "sparse", half: 150 });
    expect(bonusSpecForGroup18B("fishbowl")).toEqual({ kind: "quiet", halfM: 150 });
    expect(bonusSpecForGroup18B("daylight")).toEqual({ kind: "sparse", half: 150 });
    expect(bonusSpecForGroup18B("parks")).toBeUndefined();
    expect(isGroup18BLayerId("mossrisk")).toBe(true);
    expect(isGroup18BLayerId("daylight")).toBe(true);
    expect(isGroup18BLayerId("parks")).toBe(false);
    expect(G18B_RASTER_FILE.fishbowl).toBe("fishbowl-walk-raster.json");
    expect(G18B_RASTER_FILE.mossrisk).toBe("mossrisk-walk-raster.json");
    expect(G18B_RASTER_FILE.daylight).toBe("daylight-walk-raster.json");
  });

  it("serves fallback demo points (near + far per layer)", () => {
    for (const def of GROUP18B_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G18B_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [394, "no-map"],
      [403, "no-map"],
      [405, "proxy"],
      [468, "proxy"],
      [479, "proxy"],
    ]);
    expect(GROUP18B_HOOK).toContain("G18B-HOOK (#173)");
  });
});

describe("group18b math", () => {
  it("reads 0 on the source, 50 at halfM, ~100 when far", () => {
    expect(group18bQuietFromHalf(0, 150)).toBe(0);
    expect(group18bQuietFromHalf(150, 150)).toBe(50);
    expect(group18bQuietFromHalf(250, 250)).toBe(50);
    expect(group18bQuietFromHalf(Infinity, 150)).toBe(100);
    expect(group18bQuietFromHalf(1e9, 250)).toBeGreaterThan(99.9);
  });

  it("scores nearest-settled-junction distance (Vanalinn probe: ~3 m -> ~2)", () => {
    const pts = [{ lat: 59.4374, lon: 24.7454 }];
    expect(group18bQuietnessAt("fishbowl", 59.4374, 24.7454, pts)).toBe(0);
    // 150 m from the junction reads 100*150/300 = 50.
    const q = group18bQuietnessAt("fishbowl", 59.4374 - 150 / 110570, 24.7454, pts);
    expect(q).toBe(50);
    // Same geometry, mossrisk half: 100*150/400 = 37.5 -> 38.
    expect(group18bQuietnessAt("mossrisk", 59.4374 - 150 / 110570, 24.7454, pts)).toBe(38);
    expect(group18bQuietnessAt("fishbowl", 59.4374, 24.7454, [])).toBeNull();
  });

  it("scores sparse openness inverted (open reads 100, half-count reads 50)", () => {
    expect(group18bSparseScore(0, 150)).toBe(100);
    expect(group18bSparseScore(150, 150)).toBe(50);
    expect(group18bSparseScore(450, 150)).toBe(25);
  });

  it("counts nearby buildings with Gaussian falloff (one house barely shades)", () => {
    // One building on the cell: S=1 -> 100*150/151 = 99.34 -> 99.
    const one = group18bDaylightAt(59.44, 24.75, [{ lat: 59.44, lon: 24.75 }]);
    expect(one).toBe(99);
    // Empty input is unknown (never a faked open 100)...
    expect(group18bDaylightAt(59.44, 24.75, [])).toBeNull();
    // ...but a loaded set with nothing in range reads measured-open 100.
    expect(group18bDaylightAt(59.44, 24.75, [{ lat: 59.5, lon: 24.9 }])).toBe(100);
    expect(group18bHavKm(24.75, 59.44, 24.75, 59.44)).toBe(0);
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group18bMatchesContract("fishbowl", { half: 150, sigma: 0.3 })).toBe(true);
    expect(group18bMatchesContract("fishbowl", { half: 100, sigma: 0.3 })).toBe(false);
    expect(group18bMatchesContract("mossrisk", { half: 250, sigma: 0.3 })).toBe(true);
    expect(group18bMatchesContract("mossrisk", { half: 250, sigma: 0.5 })).toBe(false);
    expect(group18bMatchesContract("daylight", { half: 150, sigma: 0.3 })).toBe(true);
    expect(group18bMatchesContract("daylight", { half: 50, sigma: 0.3 })).toBe(false);
    expect(group18bMatchesContract("fishbowl", null)).toBe(false);
  });
});
