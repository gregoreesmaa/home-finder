import { describe, expect, it } from "vitest";
import {
  G02B_BONUS,
  G02B_DECAY,
  G02B_DEFS,
  G02B_HALVES,
  G02B_LAYER_IDS,
  G02B_NO_MAP_PARAMS,
  G02B_NO_METRO,
  G02B_PARAMS,
  G02B_RASTER_FILE,
  G02B_TAGS,
  G02B_VERDICTS,
  bonusSpecForGroup02b,
} from "./layers_group02b";

describe("group02b layer registry", () => {
  it("ships exactly the p196 proxy layer", () => {
    expect(G02B_LAYER_IDS).toEqual(["liftproxy"]);
    expect(G02B_DEFS.map((l) => l.id)).toEqual(["liftproxy"]);
    expect(G02B_PARAMS).toEqual({ liftproxy: 196 });
    expect(G02B_DEFS[0].paramIds).toEqual([196]);
  });

  it("labels the proxy honestly: hinnang everywhere, EHR measurement nowhere", () => {
    for (const l of G02B_DEFS) {
      for (const s of [l.title, l.goodLabel, l.badLabel, l.source]) {
        expect(s.toLowerCase()).toContain("hinnang");
      }
      expect(l.source).toContain("EI OLE mõõdetud liftide register");
      expect(l.goodLabel).toContain("roheline");
      expect(l.badLabel).toContain("punane");
    }
  });

  it("has finite Estonian fallback points inside Harjumaa", () => {
    for (const l of G02B_DEFS) {
      expect(l.fallbackPoints.length).toBeGreaterThan(0);
      for (const p of l.fallbackPoints) {
        expect(Number.isFinite(p.lat) && Number.isFinite(p.lon)).toBe(true);
        expect(p.lat).toBeGreaterThan(59);
        expect(p.lat).toBeLessThan(60);
        expect(p.lon).toBeGreaterThan(24);
        expect(p.lon).toBeLessThan(26);
      }
    }
  });

  it("documents the levels>=5 source tag (no live fetch)", () => {
    expect(G02B_TAGS.liftproxy).toContain("building:levels");
    expect(G02B_TAGS.liftproxy.length).toBeGreaterThan(0);
  });

  it("locks the histogram calibration (sigma 0.3, half 2)", () => {
    expect(G02B_DECAY.liftproxy).toBe(0.3);
    expect(G02B_HALVES.liftproxy).toBe(2);
    expect(G02B_BONUS.liftproxy).toEqual({ kind: "area", half: 2 });
    expect(bonusSpecForGroup02b("liftproxy")).toEqual({ kind: "area", half: 2 });
    expect(bonusSpecForGroup02b("parks")).toBeUndefined();
  });

  it("ships no metro master by documented decision", () => {
    expect(G02B_NO_METRO).toBe(true);
    expect(G02B_RASTER_FILE.liftproxy).toBe("liftproxy-walk-raster.json");
  });
});

describe("group02b per-param verdicts", () => {
  it("covers exactly the four batch-B params", () => {
    expect(G02B_VERDICTS.map((v) => v.param).sort((a, b) => a - b)).toEqual([
      79, 154, 196, 495,
    ]);
  });

  it("ships p196 as proxy, keeps p79/p154/p495 as documented no-maps", () => {
    const byParam = Object.fromEntries(G02B_VERDICTS.map((v) => [v.param, v.kind]));
    expect(byParam).toEqual({ 79: "no-map", 154: "no-map", 196: "proxy", 495: "no-map" });
    expect([...G02B_NO_MAP_PARAMS].sort((a, b) => a - b)).toEqual([79, 154, 495]);
    for (const v of G02B_VERDICTS) {
      expect(v.reason.length).toBeGreaterThan(40);
    }
    // No-map reasons cite snapshot evidence, never bare judgment.
    const noMaps = G02B_VERDICTS.filter((v) => v.kind === "no-map");
    for (const v of noMaps) {
      expect(v.reason).toMatch(/snapshot|registries|OSM|mapped/i);
    }
  });
});
