import { describe, expect, it } from "vitest";
import { LAYERS } from "./layers";
import {
  GROUP02_PARAMS,
  GROUP02_UNMAPPED_PARAMS,
  GROUP02_VERDICTS,
  group02AllNoMap,
  type Group02ParamId,
} from "./layers_group02";

const IDS: Group02ParamId[] = [21, 30, 33, 35, 48];

describe("group02 verdicts", () => {
  it("covers all five batch-A params (p21/p30/p33/p35/p48)", () => {
    expect(GROUP02_PARAMS).toEqual(IDS);
    expect(GROUP02_VERDICTS.map((v) => v.param)).toEqual(IDS);
    expect(group02AllNoMap()).toBe(true);
  });

  it("verdicts every param as no-map with an Estonian reason + evidence", () => {
    for (const v of GROUP02_VERDICTS) {
      expect(v.status).toBe("no-map");
      expect(v.name.length).toBeGreaterThan(0);
      expect(v.reason.length).toBeGreaterThan(20);
      expect(v.evidence).toMatch(/hetktõmmis 2026-09-12/);
    }
  });

  it("names the scorer dim where one exists (p30/p35/p48), null for filter/taste", () => {
    const byParam = Object.fromEntries(GROUP02_VERDICTS.map((v) => [v.param, v]));
    expect(byParam[21].scorerDim).toBeNull(); // size filter, never scored
    expect(byParam[30].scorerDim).toBe("accessibility");
    expect(byParam[33].scorerDim).toBeNull(); // age taste axis, never scored
    expect(byParam[35].scorerDim).toBe("energy");
    expect(byParam[48].scorerDim).toBe("permits");
  });

  it("pins the snapshot evidence counts behind the verdicts", () => {
    const text = GROUP02_VERDICTS.map((v) => v.evidence).join(" ");
    // nwr/building PBF probes, 2026-09-12 (see module header for commands).
    expect(text).toMatch(/252146/);
    expect(text).toMatch(/13507/);
    expect(text).toMatch(/328/);
  });

  it("keeps every batch-A param out of the map registry (verdict lock)", () => {
    expect([...GROUP02_UNMAPPED_PARAMS].sort((a, b) => a - b)).toEqual([21, 30, 33, 35, 48]);
    const mapped = new Set(LAYERS.flatMap((l) => l.paramIds));
    for (const p of GROUP02_UNMAPPED_PARAMS) {
      expect(mapped.has(p)).toBe(false);
    }
  });
});
