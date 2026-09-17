import { describe, expect, it, vi } from "vitest";
import {
  DELAY_ATTRIBUTION,
  DELAY_BAND_FILL,
  DELAY_BAND_SCORE,
  DELAY_BANDS,
  DELAY_BONUS,
  DELAY_DECAY,
  DELAY_DEFS,
  DELAY_HOOK,
  DELAY_LAYER_BAND,
  DELAY_LAYER_IDS,
  DELAY_NO_METRO,
  DELAY_NO_RASTER,
  DELAY_RASTER_FILE,
  DELAY_TAGS,
  bonusSpecForDelay,
  delayBandForFactor,
  fetchDelayAreas,
  isDelayArea,
  isDelayLayerId,
  isDelayPolygonOnlyLayer,
} from "./layers_p4_delay";

describe("delay registry (#629)", () => {
  it("ships five layers: four hour bands + worst", () => {
    expect(DELAY_LAYER_IDS).toEqual([
      "delay-morning",
      "delay-midday",
      "delay-evening",
      "delay-offpeak",
      "delay-worst",
    ]);
    expect(DELAY_LAYER_BAND).toEqual({
      "delay-morning": "hommikune tipp",
      "delay-midday": "keskpäev",
      "delay-evening": "õhtune tipp",
      "delay-offpeak": "muu",
      "delay-worst": "worst",
    });
    expect(DELAY_DEFS.map((d) => d.id)).toEqual(DELAY_LAYER_IDS);
    for (const def of DELAY_DEFS) {
      expect(def.paramIds).toEqual([]);
      expect(def.fallbackPoints).toEqual([]);
    }
  });

  it("labels every layer typical-never-live in Estonian", () => {
    for (const def of DELAY_DEFS) {
      const text = `${def.title} ${def.goodLabel} ${def.badLabel} ${def.source}`;
      expect(text).toMatch(/tavaline, mitte reaalajas/);
    }
  });

  it("pins the hook marker + raster file + no-raster/no-metro verdict", () => {
    expect(DELAY_HOOK).toMatch(/DELAY-HOOK \(#629\)/);
    for (const id of DELAY_LAYER_IDS) {
      expect(DELAY_RASTER_FILE[id]).toBe("delay-walk-raster.json");
    }
    expect(DELAY_NO_RASTER).toBe(true);
    expect(DELAY_NO_METRO).toBe(true);
    expect(DELAY_ATTRIBUTION).toMatch(/Tallinna Linnavalitsus/);
  });
});

describe("delay bands (#629)", () => {
  it("maps factors to bands with scorer parity", () => {
    expect(delayBandForFactor(1.0)).toBe("free");
    expect(delayBandForFactor(1.1)).toBe("free");
    expect(delayBandForFactor(1.11)).toBe("steady");
    expect(delayBandForFactor(1.3)).toBe("steady");
    expect(delayBandForFactor(1.31)).toBe("slow");
    expect(delayBandForFactor(1.6)).toBe("slow");
    expect(delayBandForFactor(1.61)).toBe("jammed");
    expect(delayBandForFactor(9)).toBe("jammed");
  });

  it("sends null/NaN/sub-free factors to unknown (never green)", () => {
    for (const bad of [null, undefined, NaN, 0.5, -1, "1.2", true]) {
      expect(delayBandForFactor(bad)).toBe("unknown");
    }
    expect(DELAY_BANDS).toEqual(["free", "steady", "slow", "jammed", "unknown"]);
    expect(DELAY_BAND_SCORE).toEqual({
      free: 75,
      steady: 60,
      slow: 45,
      jammed: 30,
      unknown: 30,
    });
  });

  it("paints thin cells slate (mõõtmata, never free-flow green)", () => {
    expect(DELAY_BAND_FILL.unknown).toBe("#64748b");
    expect(DELAY_BAND_FILL.free).toBe("#16a34a");
    expect(DELAY_BAND_FILL.jammed).toBe("#dc2626");
  });
});

describe("delay scoring contract (#629)", () => {
  it("locks the inert decay placeholder (polygons only: never evaluated)", () => {
    for (const id of DELAY_LAYER_IDS) {
      expect(DELAY_DECAY[id]).toBe(0.5);
    }
  });

  it("locks the inert bonus placeholder + id guards", () => {
    for (const id of DELAY_LAYER_IDS) {
      expect(DELAY_BONUS[id]).toEqual({ kind: "area", half: 60 });
      expect(isDelayLayerId(id)).toBe(true);
      expect(isDelayPolygonOnlyLayer(id)).toBe(true);
      expect(bonusSpecForDelay(id)).toEqual({ kind: "area", half: 60 });
    }
    expect(isDelayLayerId("seveso")).toBe(false);
    expect(bonusSpecForDelay("seveso")).toBeUndefined();
  });

  it("documents the gps.txt harvest (no Overpass source)", () => {
    for (const id of DELAY_LAYER_IDS) {
      expect(DELAY_TAGS[id]).toMatch(/gps\.txt/);
    }
  });
});

describe("delay source and sidecar (#629)", () => {
  const row = {
    corridor: "Laagna tee",
    factors: {
      "hommikune tipp": 1.5,
      "keskpäev": null,
      "õhtune tipp": 1.2,
      muu: 1.0,
      worst: 1.5,
    },
    ns: {
      "hommikune tipp": 40,
      "keskpäev": 0,
      "õhtune tipp": 30,
      muu: 50,
      worst: 40,
    },
    rep: { lon: 24.83, lat: 59.435 },
    b: [24.8, 59.425, 24.86, 59.445],
    r: [
      [
        [24.8, 59.425],
        [24.86, 59.445],
        [24.861, 59.444],
        [24.801, 59.424],
        [24.8, 59.425],
      ],
    ],
  };

  it("guards sidecar rows (malformed skipped, never faked)", () => {
    expect(isDelayArea(row)).toBe(true);
    expect(isDelayArea({ ...row, factors: null })).toBe(false);
    expect(isDelayArea({ ...row, corridor: "" })).toBe(false);
    expect(isDelayArea({ ...row, r: [] })).toBe(false);
    expect(isDelayArea(null)).toBe(false);
  });

  it("fetches corridor bands through the areas sidecar route", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      json: async () => ({ areas: [row, { corridor: 1 }] }),
    }));
    const areas = await fetchDelayAreas(fetchImpl as unknown as typeof fetch);
    expect(fetchImpl).toHaveBeenCalledWith("/api/layers/delay/areas");
    expect(areas).toHaveLength(1);
    expect(areas?.[0]?.corridor).toBe("Laagna tee");
  });

  it("reads null on transport failure or malformed bodies", async () => {
    const bad = vi.fn(async () => {
      throw new Error("down");
    });
    expect(
      await fetchDelayAreas(bad as unknown as typeof fetch),
    ).toBeNull();
    const wrong = vi.fn(async () => ({
      ok: true,
      json: async () => ({ areas: "nope" }),
    }));
    expect(
      await fetchDelayAreas(wrong as unknown as typeof fetch),
    ).toBeNull();
  });
});
