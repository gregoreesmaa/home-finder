import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor, radiusKmFor } from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  ETAK_ATTRIBUTION,
  ETAK_BONUS,
  ETAK_CLASSES,
  ETAK_CLASS_FILL,
  ETAK_CLASS_SCORE,
  ETAK_DECAY,
  ETAK_DEFS,
  ETAK_HOOK,
  ETAK_NO_METRO,
  ETAK_NO_RASTER,
  ETAK_RASTER_FILE,
  ETAK_TAGS,
  bonusSpecForEtak,
  decodeEtakClass,
  fetchEtakAreas,
  isEtakArea,
  isEtakLayerId,
  isEtakPolygonOnlyLayer,
  type EtakArea,
} from "./layers_p4_etak";

describe("etak class decode (#618)", () => {
  it("decodes wetland tyyp (madalsoo/raba wettest, soovik mid)", () => {
    expect(decodeEtakClass("wetland", "Raba", null)).toBe("wet_wettest");
    expect(decodeEtakClass("wetland", "Madalsoo", null)).toBe("wet_wettest");
    expect(decodeEtakClass("wetland", "Soovik", null)).toBe("wet_mid");
    expect(decodeEtakClass("wetland", "Õõtsik", null)).toBe("wet_mid");
    expect(decodeEtakClass("wetland", "Siirdesoo", null)).toBe("wet_other");
    expect(decodeEtakClass("wetland", null, null)).toBe("wet_other");
  });
  it("decodes yard tyyp (era/tootmis impervious, haljasala green)", () => {
    expect(decodeEtakClass("yard", "Eraõu", null)).toBe("yard_impervious");
    expect(decodeEtakClass("yard", "Tootmisõu", null)).toBe("yard_impervious");
    expect(decodeEtakClass("yard", "Haljasala", null)).toBe("yard_green");
    expect(decodeEtakClass("yard", "Muu kõlvik", null)).toBe("yard_other");
    expect(decodeEtakClass("yard", null, null)).toBe("yard_other");
  });
  it("maps both water kinds to the water class (type never moves the edge)", () => {
    expect(decodeEtakClass("standing", null, "Saku tiik")).toBe("water");
    expect(decodeEtakClass("flowing", null, "Vääna jõgi")).toBe("water");
  });
  it("refuses unknown themes (never guessed)", () => {
    expect(decodeEtakClass("relief", null, null)).toBeNull();
  });
});

describe("etak class bands (#618)", () => {
  it("matches the scorer legs (wetland 25/35/30, water 30, yard 45/70/60)", () => {
    expect(ETAK_CLASS_SCORE).toEqual({
      wet_wettest: 25,
      wet_mid: 35,
      wet_other: 30,
      water: 30,
      yard_impervious: 45,
      yard_green: 70,
      yard_other: 60,
    });
  });
  it("gives every class a fill (map paints classes, never numbers)", () => {
    for (const cls of ETAK_CLASSES) expect(ETAK_CLASS_FILL[cls]).toMatch(/^#[0-9a-f]{6}$/);
  });
});

describe("etak registry (#618)", () => {
  it("merges into LAYERS via the ETAK-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 123 shipped + seveso (#613) + stateland (#615) + quarry (#614) +
    // maaparandus (#616) + soil (#617) + 1 etak overlay (ETAK-HOOK
    // #618, 128 + 1) + 1 relief overlay (RELIEF-HOOK #619,
    // 129 + 1) + 1 canopy overlay
    // (CANOPY-HOOK #620, 130 + 1) + 1 buildings overlay
    // (BUILDINGS-HOOK #621, 131 + 1) + 1 density overlay
    // (DENSITY-HOOK #622, 132 + 1) + 1 forest overlay
    // (FOREST-HOOK #624, 133 + 1 = 134).....
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    expect(ids.length).toBe(156); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    expect(ids).toContain("etak");
  });
  it("rides paramLabel with empty paramIds (polygons only, no parameters3 number)", () => {
    expect(ETAK_DEFS[0]?.paramIds).toEqual([]);
    expect(ETAK_DEFS[0]?.paramLabel).toBe("P4-etak");
    expect(ETAK_DEFS[0]?.fallbackPoints).toEqual([]);
  });
  it("guards by id, never by literal", () => {
    expect(isEtakLayerId("etak")).toBe(true);
    expect(isEtakLayerId("soil")).toBe(false);
    expect(isEtakPolygonOnlyLayer("etak")).toBe(true);
    expect(isEtakPolygonOnlyLayer("parks")).toBe(false);
    expect(bonusSpecForEtak("etak")).toEqual(ETAK_BONUS.etak);
    expect(bonusSpecForEtak("parks")).toBeUndefined();
  });
  it("pins inert placeholders + attribution + hook marker", () => {
    expect(ETAK_DECAY.etak).toBe(0.5);
    expect(ETAK_NO_RASTER).toBe(true);
    expect(ETAK_NO_METRO).toBe(true);
    expect(ETAK_RASTER_FILE.etak).toContain("etak");
    expect(ETAK_TAGS.etak).not.toContain("node(");
    expect(ETAK_ATTRIBUTION).toContain("CC BY 4.0");
    expect(ETAK_HOOK).toContain("ETAK-HOOK (#618)");
  });
});

describe("etak wiring (#618)", () => {
  it("locks the inert decay/bonus placeholders through layers.ts (never evaluated)", () => {
    expect(radiusKmFor("etak")).toBeCloseTo(0.5, 5);
    expect(bonusSpecFor("etak")).toEqual({ kind: "area", half: 60 });
  });
  it("carries the outside-unknown caveat in the legend (OTA PR #131 precedent)", () => {
    expect(overlayLegendFor("etak")).toContain("väljaspool = teadmata, mitte kuiv maa");
    expect(overlayLegendFor("etak").length).toBeGreaterThan(10);
  });
  it("paints a distinct toggle-dot color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("etak")).toBe("#1e1b4b");
  });
});

describe("etak area guard + fetch (#618)", () => {
  const AREA: EtakArea = {
    zone_id: "etak:123",
    theme: "wetland",
    cls: "wet_mid",
    score: 35,
    label: "Soovik",
    name: null,
    vintage: "2018-02-09",
    b: [24.6, 59.28, 24.7, 59.33],
    r: [
      [
        [24.6, 59.28],
        [24.7, 59.28],
        [24.7, 59.33],
        [24.6, 59.28],
      ],
    ],
  };
  it("accepts well-formed areas, rejects malformed (never faked)", () => {
    expect(isEtakArea(AREA)).toBe(true);
    expect(isEtakArea({ ...AREA, cls: "swamp" })).toBe(false);
    expect(isEtakArea({ ...AREA, r: [] })).toBe(false);
    expect(isEtakArea(null)).toBe(false);
  });
  it("fetches the viewport bbox from the etak areas endpoint", async () => {
    const seen: string[] = [];
    const fetchImpl = (async (url: string) => {
      seen.push(url);
      return { ok: true, json: async () => ({ areas: [AREA], note: null }) };
    }) as unknown as typeof fetch;
    const res = await fetchEtakAreas(
      { minlon: 24.6, minlat: 59.28, maxlon: 24.7, maxlat: 59.33 },
      fetchImpl,
    );
    expect(seen).toHaveLength(1);
    expect(seen[0]).toContain("/api/layers/etak/areas?bbox=24.6%2C59.28%2C24.7%2C59.33");
    expect(res?.areas).toHaveLength(1);
    expect(res?.note).toBeNull();
  });
  it("is null on any transport failure (errors never cached as data)", async () => {
    const failing = (async () => {
      throw new Error("down");
    }) as unknown as typeof fetch;
    await expect(
      fetchEtakAreas({ minlon: 0, minlat: 0, maxlon: 1, maxlat: 1 }, failing),
    ).resolves.toBeNull();
  });
});
