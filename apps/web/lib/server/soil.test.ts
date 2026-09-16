import { describe, expect, it, vi } from "vitest";
import {
  SOIL_WFS_TYPE,
  fetchSoilViewport,
  soilCacheKey,
  type SoilViewportDeps,
} from "./soil";

const BBOX = { minlon: 24.6, minlat: 59.28, maxlon: 24.7, maxlat: 59.33 };

function feature(name: string | null, label: string, ring: number[][]) {
  return {
    type: "Feature",
    properties: { gml_name: name, soilbodylabel: label, inspireid_identifier_localid: "m1" },
    geometry: { type: "Polygon", coordinates: [ring] },
  };
}
const RING = [
  [24.62, 59.3],
  [24.64, 59.3],
  [24.64, 59.31],
  [24.62, 59.3],
];
const CITY_RING = [
  [24.7, 59.42],
  [24.72, 59.42],
  [24.72, 59.43],
  [24.7, 59.42],
];

function depsWith(payload: unknown, seen: string[]): SoilViewportDeps {
  return {
    fetchImpl: (async (url: string) => {
      seen.push(url);
      return { ok: true, json: async () => payload };
    }) as unknown as typeof fetch,
    readCache: async () => null,
    writeCache: async () => {},
  };
}

describe("soil viewport proxy (#617)", () => {
  it("refuses malformed bboxes without touching the network", async () => {
    const fetchImpl = vi.fn();
    for (const bad of [
      { ...BBOX, minlon: NaN },
      { ...BBOX, minlon: 24.7, maxlon: 24.6 },
      { ...BBOX, minlat: -100 },
      { ...BBOX, maxlon: 200 },
    ]) {
      const res = await fetchSoilViewport(bad, {
        fetchImpl: fetchImpl as unknown as typeof fetch,
        readCache: async () => null,
        writeCache: async () => {},
      });
      expect(res).toEqual({ ok: false, reason: "bad-bbox" });
    }
    expect(fetchImpl).not.toHaveBeenCalled();
  });
  it("snaps the bbox to the cache grid (settled pans share keys)", () => {
    expect(soilCacheKey(BBOX)).toBe(
      soilCacheKey({ minlon: 24.61, minlat: 59.281, maxlon: 24.69, maxlat: 59.329 }),
    );
  });
  it("serves cache hits without fetching (polite: one WFS pull per cell per year)", async () => {
    const cached = JSON.stringify({
      atMs: Date.now(),
      areas: [
        {
          zone_id: "m1",
          family: "liiv",
          cls: "liiv",
          score: 70,
          code: "l",
          b: [24.6, 59.28, 24.7, 59.33],
          r: [RING],
        },
      ],
    });
    const fetchImpl = vi.fn();
    const res = await fetchSoilViewport(BBOX, {
      fetchImpl: fetchImpl as unknown as typeof fetch,
      readCache: async () => cached,
      writeCache: async () => {},
    });
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.areas).toHaveLength(1);
  });
  it("fetches lon-lat WFS, decodes families, drops urban + undecoded (rings unmodified)", async () => {
    const seen: string[] = [];
    const payload = {
      numberMatched: 3,
      features: [
        feature("ls₂;l50-100/s", "Go", RING),
        feature("l", "LIIg", CITY_RING),
        feature("v⁰₁ls₁40/p", "Korg", RING),
      ],
    };
    const written: string[] = [];
    const res = await fetchSoilViewport(BBOX, {
      ...depsWith(payload, seen),
      writeCache: async (key: string, body: string) => {
        written.push(key);
        JSON.parse(body);
      },
    });
    expect(seen).toHaveLength(1);
    expect(seen[0]).toContain(encodeURIComponent(SOIL_WFS_TYPE));
    expect(seen[0]).toContain("24.6%2C59.28%2C24.7%2C59.33%2CEPSG%3A4326");
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.areas).toHaveLength(1);
    expect(res.areas[0]?.family).toBe("liivsavi");
    expect(res.areas[0]?.score).toBe(65);
    expect(res.areas[0]?.r).toEqual([RING]);
    expect(res.urbanDropped).toBe(1);
    expect(res.undecoded).toBe(1);
    expect(written).toHaveLength(1);
  });
  it("routes wide-but-sane country views to too-wide (one hits query, never a 400)", async () => {
    const seen: string[] = [];
    const res = await fetchSoilViewport(
      { minlon: 21.5, minlat: 57.3, maxlon: 28.5, maxlat: 59.9 },
      depsWith({ numberMatched: 766555, features: [] }, seen),
    );
    expect(res).toEqual({ ok: false, reason: "too-wide" });
    expect(seen).toHaveLength(1);
  });
  it("refuses over-wide viewports honestly (zoom-in note, nothing cached)", async () => {
    const seen: string[] = [];
    const written: string[] = [];
    const res = await fetchSoilViewport(BBOX, {
      ...depsWith({ numberMatched: 86000, features: [] }, seen),
      writeCache: async (key: string) => {
        written.push(key);
      },
    });
    expect(res).toEqual({ ok: false, reason: "too-wide" });
    expect(written).toHaveLength(0);
  });
  it("never caches transport errors as data", async () => {
    const written: string[] = [];
    const res = await fetchSoilViewport(BBOX, {
      fetchImpl: (async () => ({ ok: false, status: 429 })) as unknown as typeof fetch,
      readCache: async () => null,
      writeCache: async (key: string) => {
        written.push(key);
      },
    });
    expect(res).toEqual({ ok: false, reason: "upstream" });
    expect(written).toHaveLength(0);
  });
});
