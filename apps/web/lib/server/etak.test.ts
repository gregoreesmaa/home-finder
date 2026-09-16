import { describe, expect, it, vi } from "vitest";
import {
  ETAK_WFS_TYPES,
  etakCacheKey,
  fetchEtakViewport,
  type EtakViewportDeps,
} from "./etak";

const BBOX = { minlon: 24.6, minlat: 59.28, maxlon: 24.7, maxlat: 59.33 };

function feature(props: Record<string, unknown>, ring: number[][]) {
  return {
    type: "Feature",
    properties: props,
    geometry: { type: "Polygon", coordinates: [ring] },
  };
}
const RING = [
  [24.62, 59.3],
  [24.64, 59.3],
  [24.64, 59.31],
  [24.62, 59.3],
];

function depsFor(
  payloads: Record<string, unknown>,
  seen: string[],
): EtakViewportDeps {
  return {
    fetchImpl: (async (url: string) => {
      seen.push(url);
      const hit = Object.entries(payloads).find(([t]) => url.includes(encodeURIComponent(t)));
      return { ok: true, json: async () => hit?.[1] ?? { numberMatched: 0, features: [] } };
    }) as unknown as typeof fetch,
    readCache: async () => null,
    writeCache: async () => {},
  };
}

describe("etak viewport proxy (#618)", () => {
  it("refuses malformed bboxes without touching the network", async () => {
    const fetchImpl = vi.fn();
    const res = await fetchEtakViewport({ ...BBOX, minlon: NaN }, {
      fetchImpl: fetchImpl as unknown as typeof fetch,
      readCache: async () => null,
      writeCache: async () => {},
    });
    expect(res).toEqual({ ok: false, reason: "bad-bbox" });
    expect(fetchImpl).not.toHaveBeenCalled();
  });
  it("queries all four measured themes (relief stays gated)", () => {
    expect(Object.keys(ETAK_WFS_TYPES)).toEqual(["wetland", "standing", "flowing", "yard"]);
  });
  it("snaps the bbox to the cache grid (settled pans share keys)", () => {
    expect(etakCacheKey(BBOX)).toBe(
      etakCacheKey({ minlon: 24.61, minlat: 59.281, maxlon: 24.69, maxlat: 59.329 }),
    );
  });
  it("merges themes, decodes classes, carries vintage (rings unmodified)", async () => {
    const seen: string[] = [];
    const payloads = {
      "e_306_margala_a": {
        numberMatched: 1,
        features: [
          feature(
            { etak_id: 1, tyyp_tekst: "Soovik", muutmisaeg: "2018-02-09T16:38:16Z" },
            RING,
          ),
        ],
      },
      "e_202_seisuveekogu_a": {
        numberMatched: 1,
        features: [
          feature({ etak_id: 2, nimetus: "Saku tiik", muutmisaeg: "2020-05-01T00:00:00Z" }, RING),
        ],
      },
      "e_203_vooluveekogu_a": { numberMatched: 0, features: [] },
      "e_302_ou_a": {
        numberMatched: 1,
        features: [
          feature({ etak_id: 3, tyyp_tekst: "Eraõu", muutmisaeg: "2019-01-01T00:00:00Z" }, RING),
        ],
      },
    };
    const written: string[] = [];
    const res = await fetchEtakViewport(BBOX, {
      ...depsFor(payloads, seen),
      writeCache: async (key: string, body: string) => {
        written.push(key);
        JSON.parse(body);
      },
    });
    expect(seen).toHaveLength(4);
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.areas).toHaveLength(3);
    const byTheme = Object.fromEntries(res.areas.map((a) => [a.theme, a]));
    expect(byTheme.wetland?.cls).toBe("wet_mid");
    expect(byTheme.wetland?.vintage).toBe("2018-02-09");
    expect(byTheme.standing?.cls).toBe("water");
    expect(byTheme.standing?.name).toBe("Saku tiik");
    expect(byTheme.yard?.cls).toBe("yard_impervious");
    expect(res.areas[0]?.r).toEqual([RING]);
    expect(written).toHaveLength(1);
  });
  it("refuses over-wide viewports honestly (zoom-in note, nothing cached)", async () => {
    const seen: string[] = [];
    const written: string[] = [];
    const res = await fetchEtakViewport(BBOX, {
      ...depsFor(
        { "e_306_margala_a": { numberMatched: 8824, features: [] } },
        seen,
      ),
      writeCache: async (key: string) => {
        written.push(key);
      },
    });
    expect(res).toEqual({ ok: false, reason: "too-wide" });
    expect(written).toHaveLength(0);
  });
  it("never caches transport errors as data", async () => {
    const written: string[] = [];
    const res = await fetchEtakViewport(BBOX, {
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
