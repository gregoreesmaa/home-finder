import { describe, expect, it, vi } from "vitest";

import {
  KPO_BAND_FILL,
  KPO_DEFS,
  KPO_FAMILIES,
  KPO_HOOK,
  KPO_NO_METRO,
  KPO_NO_RASTER,
  KPO_VINTAGE,
  bonusSpecForKpo,
  fetchKpoAreas,
  isKpoArea,
  isKpoLayerId,
  isKpoPolygonOnlyLayer,
  kpoFillKey,
} from "./layers_p4_kpo";

const AREA = {
  family: "elekter",
  nimi: "JAAM",
  voond: "Elektripaigaldise kaitsevöönd",
  reegel: "Ehitusseadustik",
  b: [24.74, 59.43, 24.75, 59.44] as [number, number, number, number],
  r: [
    [
      [24.74, 59.43],
      [24.75, 59.43],
      [24.75, 59.44],
      [24.74, 59.44],
    ],
  ],
};

describe("kpo areas (#626)", () => {
  it("accepts well-formed zones, refuses wrong families and degenerate rows", () => {
    expect(isKpoArea(AREA)).toBe(true);
    expect(isKpoArea({ ...AREA, family: "midagi" })).toBe(false);
    expect(isKpoArea({ ...AREA, r: [] })).toBe(false);
    expect(
      isKpoArea({ ...AREA, r: [[[24.74, 59.43]]] }),
    ).toBe(false);
  });

  it("maps zone types to ban / conditioned / unknown fills", () => {
    expect(kpoFillKey("ehituskeeld")).toBe("ban");
    expect(kpoFillKey("Veekogu ehituskeeluvöönd")).toBe("ban");
    expect(kpoFillKey("tingimuslik-kooskõlastus")).toBe("conditioned");
    expect(kpoFillKey("teavitus")).toBe("conditioned");
    // Live harvest values (#626): conditioned, never unknown.
    expect(kpoFillKey("Elektripaigaldise kaitsevöönd")).toBe("conditioned");
    expect(kpoFillKey("Piiratud asjaõigusega ala")).toBe("conditioned");
    // Heritage family conditions whatever the wording (#626).
    expect(kpoFillKey("Arheoloogiamälestis", "muinsuskaitse")).toBe(
      "conditioned",
    );
    expect(kpoFillKey("Arheoloogiamälestis", "elekter")).toBe("unknown");
    expect(kpoFillKey("")).toBe("unknown");
    expect(KPO_BAND_FILL.ban).toBe("#dc2626");
    expect(KPO_BAND_FILL.conditioned).toBe("#f59e0b");
  });

  it("fetches zones from the kpo areas endpoint", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ areas: [AREA] })),
    ) as unknown as typeof fetch;
    const areas = await fetchKpoAreas(fetchImpl);
    expect(areas).toHaveLength(1);
    expect(areas?.[0].family).toBe("elekter");
  });

  it("fails null on transport error or malformed body (never faked)", async () => {
    const bad = vi.fn(async () => {
      throw new Error("down");
    }) as unknown as typeof fetch;
    expect(await fetchKpoAreas(bad)).toBeNull();
    const malformed = vi.fn(async () =>
      new Response(JSON.stringify({ areas: "nope" })),
    ) as unknown as typeof fetch;
    expect(await fetchKpoAreas(malformed)).toBeNull();
  });
});

describe("kpo registry (#626)", () => {
  it("is a polygons-only P4 layer with no fallback points", () => {
    expect(isKpoLayerId("kpo")).toBe(true);
    expect(isKpoPolygonOnlyLayer("kpo")).toBe(true);
    expect(isKpoPolygonOnlyLayer("noise")).toBe(false);
    expect(KPO_DEFS[0].paramLabel).toBe("P4-kitsendus");
    expect(KPO_DEFS[0].fallbackPoints).toEqual([]);
  });

  it("pins zones spec + vintage + families + hook marker (#807)", () => {
    expect(KPO_NO_RASTER).toBe(true);
    expect(KPO_NO_METRO).toBe(true);
    expect(KPO_VINTAGE).toBe("2026-09");
    expect(KPO_FAMILIES).toHaveLength(18);
    expect(bonusSpecForKpo("kpo")).toEqual({ kind: "zones" });
    expect(bonusSpecForKpo("nope")).toBeUndefined();
    expect(KPO_HOOK).toContain("KPO-HOOK (#626)");
  });
});
