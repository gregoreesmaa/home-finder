import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  clearSnapshotCache,
  intersectsCoverage,
  loadLayerRaster,
  loadParkAreas,
  loadSnapshotPoints,
  loadWindowRaster,
  nominalArea,
  type ParkArea,
  parksAreas,
  SNAPSHOT_BBOX,
  SnapshotUnavailable,
} from "./snapshot";

/** Self-contained fixture snapshot (never the real ~/hf-data tree). */
async function fixtureDir(points: unknown, layer = "parks"): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "hf-snap-"));
  await mkdir(join(dir, "osm"), { recursive: true });
  await writeFile(join(dir, "osm", `derived-${layer}.json`), JSON.stringify(points));
  return dir;
}

afterEach(async () => {
  clearSnapshotCache();
});

describe("snapshot loader", () => {
  it("loads points clipped to the bbox, cleaning tags and skipping junk", async () => {
    const dir = await fixtureDir([
      { lat: 59.44, lon: 24.75, tags: { leisure: "park" } },
      { lat: 59.0, lon: 24.0, tags: { leisure: "playground" } },
      { lat: 59.4405, lon: 24.7505 },
      { lat: "x", lon: 24.75 },
      { lon: 24.75 },
    ]);
    try {
      const pts = await loadSnapshotPoints(
        "parks",
        { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 },
        dir,
      );
      expect(pts).toEqual([
        { lat: 59.44, lon: 24.75, tags: { leisure: "park" }, a: 2 },
        { lat: 59.4405, lon: 24.7505, a: 0.3 },
      ]);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("throws SnapshotUnavailable for missing dir, bad JSON, or non-array", async () => {
    await expect(loadSnapshotPoints("parks", SNAPSHOT_BBOX, "/nonexistent-dir-xyz")).rejects.toBeInstanceOf(
      SnapshotUnavailable,
    );
    const bad = await mkdtemp(join(tmpdir(), "hf-snap-bad-"));
    await mkdir(join(bad, "osm"), { recursive: true });
    await writeFile(join(bad, "osm", "derived-parks.json"), "{nope");
    try {
      await expect(loadSnapshotPoints("parks", SNAPSHOT_BBOX, bad)).rejects.toBeInstanceOf(
        SnapshotUnavailable,
      );
    } finally {
      await rm(bad, { recursive: true, force: true });
    }
    clearSnapshotCache();
    const obj = await fixtureDir({ elements: [] });
    try {
      await expect(loadSnapshotPoints("parks", SNAPSHOT_BBOX, obj)).rejects.toBeInstanceOf(
        SnapshotUnavailable,
      );
    } finally {
      await rm(obj, { recursive: true, force: true });
    }
  });

  it("caches per process (survives the file going away)", async () => {
    const dir = await fixtureDir([{ lat: 59.44, lon: 24.75 }]);
    const bbox = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };
    const first = await loadSnapshotPoints("parks", bbox, dir);
    await rm(dir, { recursive: true, force: true });
    const second = await loadSnapshotPoints("parks", bbox, dir);
    expect(second).toEqual(first);
  });
});

describe("park area features", () => {
  const square = [
    [24.74, 59.43],
    [24.76, 59.43],
    [24.76, 59.45],
    [24.74, 59.45],
  ];
  const area63: ParkArea = { b: [24.74, 59.43, 24.76, 59.45], a: 63, r: [square] };

  it("loads area rings for outlines, skipping junk, [] when missing", async () => {
    const dir = await fixtureDir([{ lat: 1, lon: 1 }], "parks");
    await writeFile(
      join(dir, "osm", "park-areas.json"),
      JSON.stringify([
        { b: [0, 0, 1, 1], a: 6.4, r: [[[0, 0], [1, 0], [1, 1], [0, 1]]] },
        { b: [0, 0, 1, 1], a: "huge", r: "not-rings" },
        null,
      ]),
    );
    try {
      const areas = await loadParkAreas(dir);
      expect(areas).toEqual([{ b: [0, 0, 1, 1], a: 6.4, r: [[[0, 0], [1, 0], [1, 1], [0, 1]]] }]);
      expect(await loadParkAreas(join(dir, "nope"))).toEqual([]);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("assigns nominal hectares by leisure type", () => {
    expect(nominalArea({ leisure: "playground" })).toBe(0.1);
    expect(nominalArea({ leisure: "garden" })).toBe(0.15);
    expect(nominalArea({ leisure: "park" })).toBe(2.0);
    expect(nominalArea(undefined)).toBe(0.3);
  });

  it("emits polygon areas subdivided, dropping covered points", () => {
    // 63 ha / 19.6-ha cells (sigma 0.25) -> 4 sub-features of 15.75 ha each.
    const pts = parksAreas(
      [
        { lat: 59.44, lon: 24.75, tags: { leisure: "playground" } },
        { lat: 59.46, lon: 24.78, tags: { leisure: "park" } },
      ],
      [area63],
    );
    expect(pts).toEqual([
      { lon: 24.745, lat: 59.435, a: 15.75 },
      { lon: 24.745, lat: 59.445, a: 15.75 },
      { lon: 24.755, lat: 59.435, a: 15.75 },
      { lon: 24.755, lat: 59.445, a: 15.75 },
      { lon: 24.78, lat: 59.46, tags: { leisure: "park" }, a: 2 },
    ]);
  });

  it("conserves hectares for sparse polygons (diagonal shapes keep all area)", () => {
    // Thin diagonal strip: few grid centers land in-ring, but the total
    // stamped area must still equal the polygon's hectares.
    const strip: ParkArea = {
      b: [24.8, 59.44, 24.9, 59.45],
      a: 40,
      r: [
        [
          [24.8, 59.44],
          [24.9, 59.45],
          [24.9, 59.448],
          [24.8, 59.438],
        ],
      ],
    };
    const pts = parksAreas([], [strip]);
    expect(pts.length).toBeGreaterThan(0);
    const total = pts.reduce((s, p) => s + (p.a ?? 0), 0);
    expect(total).toBeCloseTo(40, 0);
  });

  it("sums areas inside ~20 m cells", () => {
    const pts = parksAreas(
      [
        { lat: 59.44, lon: 24.75, tags: { leisure: "playground" } },
        { lat: 59.44, lon: 24.75, tags: { leisure: "garden" } },
      ],
      [],
    );
    expect(pts).toEqual([{ lat: 59.44, lon: 24.75, tags: { leisure: "playground" }, a: 0.25 }]);
  });

  it("serves areas end to end for parks, departures for transit", async () => {
    const dir = await fixtureDir(
      [
        { lat: 59.44, lon: 24.75, tags: { leisure: "playground" } },
        { lat: 59.45, lon: 24.76, tags: { leisure: "park" } },
      ],
      "parks",
    );
    const tdir = await fixtureDir(
      [
        { lat: 59.44, lon: 24.75, tags: { highway: "bus_stop" } },
        { lat: 59.45, lon: 24.76, tags: { highway: "bus_stop" } },
        { lat: 59.46, lon: 24.78, tags: { highway: "bus_stop" } },
        // Same complex as the first stop (~13 m from its GTFS entry):
        // departures count once, at the nearest node.
        { lat: 59.4401, lon: 24.7501, tags: { highway: "bus_stop" } },
      ],
      "transit",
    );
    await writeFile(
      join(tdir, "osm", "transit-frequency.json"),
      JSON.stringify({
        stops: [
          { lon: 24.75, lat: 59.44, trips: 974 },
          { lon: 24.76, lat: 59.45, trips: 42 },
        ],
      }),
    );
    const bbox = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };
    try {
      expect(await loadSnapshotPoints("parks", bbox, dir)).toEqual([
        { lat: 59.44, lon: 24.75, tags: { leisure: "playground" }, a: 0.1 },
        { lat: 59.45, lon: 24.76, tags: { leisure: "park" }, a: 2 },
      ]);
      expect(await loadSnapshotPoints("transit", bbox, tdir)).toEqual([
        { lat: 59.44, lon: 24.75, tags: { highway: "bus_stop" }, t: 974 },
        { lat: 59.45, lon: 24.76, tags: { highway: "bus_stop" }, t: 42 },
        { lat: 59.46, lon: 24.78, tags: { highway: "bus_stop" }, t: 100 },
        { lat: 59.4401, lon: 24.7501, tags: { highway: "bus_stop" }, t: 0 },
      ]);
    } finally {
      await rm(dir, { recursive: true, force: true });
      await rm(tdir, { recursive: true, force: true });
    }
  });

  it("transit degrades to default departures without a frequency file", async () => {
    const dir = await fixtureDir([{ lat: 59.44, lon: 24.75 }], "transit");
    try {
      const pts = await loadSnapshotPoints(
        "transit",
        { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 },
        dir,
      );
      expect(pts).toEqual([{ lat: 59.44, lon: 24.75, t: 100 }]);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("layer walk rasters", () => {
  const rasterDoc = (contract: { half?: number | null; sigma: number; per?: number; cap?: number }) => ({
    cols: 2,
    rows: 2,
    bbox: { minlon: 24.0, minlat: 59.0, maxlon: 24.2, maxlat: 59.1 },
    step_m: 75,
    half: contract.half ?? null,
    sigma: contract.sigma,
    per: contract.per ?? 0,
    cap: contract.cap ?? 0,
    unknown: 255,
    dtype: "uint8",
    data: Buffer.from([80, 255, 40, 60]).toString("base64"),
  });

  it("serves the transit raster when it matches the scoring contract", async () => {
    const dir = await fixtureDir([{ lat: 59.44, lon: 24.75 }], "transit");
    await writeFile(
      join(dir, "osm", "transit-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 1500, sigma: 0.2 })),
    );
    try {
      const { raster, distance } = await loadLayerRaster("transit", dir);
      expect(distance).toBe("walk");
      expect(raster?.cols).toBe(2);
      expect(raster?.data).toBe(Buffer.from([80, 255, 40, 60]).toString("base64"));
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("serves parks and schools rasters under their own contracts", async () => {
    const pdir = await fixtureDir([{ lat: 59.44, lon: 24.75 }], "parks");
    await writeFile(
      join(pdir, "osm", "parks-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 15, sigma: 0.25 })),
    );
    try {
      expect((await loadLayerRaster("parks", pdir)).distance).toBe("walk");
    } finally {
      await rm(pdir, { recursive: true, force: true });
    }
    const sdir = await fixtureDir([{ lat: 59.44, lon: 24.75 }], "schools");
    await writeFile(
      join(sdir, "osm", "schools-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: null, sigma: 0.8, per: 12, cap: 36 })),
    );
    try {
      expect((await loadLayerRaster("schools", sdir)).distance).toBe("walk");
    } finally {
      await rm(sdir, { recursive: true, force: true });
    }
  });

  it("reports euclidean for the Euclidean-built drainage master", async () => {
    // The drainage proxy field is stamped with direct distance (see
    // batch_g03_cadastre.py), so the distance label must say so —
    // "walk" would claim footpath routing the master never used.
    const dir = await fixtureDir([{ lat: 59.47, lon: 24.82 }], "drainage");
    await writeFile(
      join(dir, "osm", "drainage-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 300, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("drainage", dir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(300);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
    // Stale drainage half: rejected under the quiet contract.
    const stale = await fixtureDir([{ lat: 59.47, lon: 24.82 }], "drainage");
    await writeFile(
      join(stale, "osm", "drainage-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 500, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("drainage", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves G03D moorage + shoredist rasters under area + quiet contracts", async () => {
    // G03D-HOOK (#154): moorage area contract (half 1, sigma 0.3) —
    // Euclidean count-kernel-built (see batch_g03d_cadastre.py), so the
    // distance label says euclidean, like drainage.
    const mdir = await fixtureDir([{ lat: 59.468, lon: 24.821, a: 1 }], "moorage");
    await writeFile(
      join(mdir, "osm", "moorage-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 1, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("moorage", mdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(1);
    } finally {
      await rm(mdir, { recursive: true, force: true });
    }
    // G03D-HOOK (#154): shoredist quiet contract (halfM 100 on the wire
    // as half, sigma 0.3); Euclidean-built like drainage. A stale half
    // is rejected.
    const sdir = await fixtureDir([{ lat: 59.47, lon: 24.82 }], "shoredist");
    await writeFile(
      join(sdir, "osm", "shoredist-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 100, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("shoredist", sdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(100);
    } finally {
      await rm(sdir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.47, lon: 24.82 }], "shoredist");
    await writeFile(
      join(stale, "osm", "shoredist-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 300, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("shoredist", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves the G08A wildfire raster under the quiet contract", async () => {
    // G08A-HOOK (#167): wildfire quiet contract (halfM 100 on the wire
    // as half, sigma 0.3); Euclidean-built like drainage/shoredist. A
    // stale half is rejected.
    const dir = await fixtureDir([{ lat: 59.3862, lon: 24.6611 }], "wildfire");
    await writeFile(
      join(dir, "osm", "wildfire-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 100, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("wildfire", dir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(100);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.3862, lon: 24.6611 }], "wildfire");
    await writeFile(
      join(stale, "osm", "wildfire-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 300, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("wildfire", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves the G08D vernalpool raster under the quiet contract", async () => {
    // G08D-HOOK (#170): vernalpool quiet contract (halfM 300 on the
    // wire as half, sigma 0.3); Euclidean-built like drainage. A stale
    // half is rejected.
    const dir = await fixtureDir([{ lat: 59.4425, lon: 24.7972 }], "vernalpool");
    await writeFile(
      join(dir, "osm", "vernalpool-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 300, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("vernalpool", dir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(300);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.4425, lon: 24.7972 }], "vernalpool");
    await writeFile(
      join(stale, "osm", "vernalpool-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 500, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("vernalpool", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves G08C surgeroad + slidebuf rasters under quiet contracts", async () => {
    // G08C-HOOK (#169): surgeroad quiet contract (halfM 150 on the wire
    // as half, sigma 0.3) — Euclidean Dijkstra-built (see
    // batch_g08c_flood.py), so the distance label says euclidean.
    const rdir = await fixtureDir([{ lat: 59.46048, lon: 24.81723 }], "surgeroad");
    await writeFile(
      join(rdir, "osm", "surgeroad-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 150, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("surgeroad", rdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(150);
    } finally {
      await rm(rdir, { recursive: true, force: true });
    }
    // G08C-HOOK (#169): slidebuf quiet contract (halfM 100, sigma 0.3).
    // A stale half is rejected.
    const sdir = await fixtureDir([{ lat: 59.44208, lon: 24.80809 }], "slidebuf");
    await writeFile(
      join(sdir, "osm", "slidebuf-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 100, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("slidebuf", sdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(100);
    } finally {
      await rm(sdir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.44208, lon: 24.80809 }], "slidebuf");
    await writeFile(
      join(stale, "osm", "slidebuf-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 300, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("slidebuf", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves G08B windtunnel + saltspray rasters under the quiet contract", async () => {
    // G08B-HOOK (#168): windtunnel quiet contract (halfM 200 on the
    // wire as half, sigma 0.2); Euclidean-built like drainage. A stale
    // half is rejected.
    const wdir = await fixtureDir([{ lat: 59.412, lon: 24.655 }], "windtunnel");
    await writeFile(
      join(wdir, "osm", "windtunnel-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 200, sigma: 0.2 })),
    );
    try {
      const res = await loadLayerRaster("windtunnel", wdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(200);
    } finally {
      await rm(wdir, { recursive: true, force: true });
    }
    // G08B-HOOK (#168): saltspray quiet contract (halfM 500 on the
    // wire as half, sigma 0.5); Euclidean-built like shoredist.
    const sdir = await fixtureDir([{ lat: 59.468, lon: 24.821 }], "saltspray");
    await writeFile(
      join(sdir, "osm", "saltspray-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 500, sigma: 0.5 })),
    );
    try {
      const res = await loadLayerRaster("saltspray", sdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(500);
    } finally {
      await rm(sdir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.468, lon: 24.821 }], "saltspray");
    await writeFile(
      join(stale, "osm", "saltspray-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 100, sigma: 0.5 })),
    );
    try {
      expect(await loadLayerRaster("saltspray", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves the G05D strsat raster under the avoid contract", async () => {
    // G05D-HOOK (#164): strsat avoid contract (half 0.35 walk-km on the
    // wire, sigma 0.5); Euclidean-built like G08B. A stale half is
    // rejected.
    const sdir = await fixtureDir([{ lat: 59.4366, lon: 24.7449 }], "strsat");
    await writeFile(
      join(sdir, "osm", "strsat-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 0.35, sigma: 0.5 })),
    );
    try {
      const res = await loadLayerRaster("strsat", sdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(0.35);
    } finally {
      await rm(sdir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.4366, lon: 24.7449 }], "strsat");
    await writeFile(
      join(stale, "osm", "strsat-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 0.21, sigma: 0.5 })),
    );
    try {
      expect(await loadLayerRaster("strsat", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves G05A ehitus + korterstock rasters under the area contract", async () => {
    // G05A-HOOK (#161): ehitus area contract (half 1 on the wire,
    // sigma 0.3); Euclidean-built like moorage. A stale half is rejected.
    const edir = await fixtureDir([{ lat: 59.4405, lon: 24.7369 }], "ehitus");
    await writeFile(
      join(edir, "osm", "ehitus-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 1, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("ehitus", edir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(1);
    } finally {
      await rm(edir, { recursive: true, force: true });
    }
    // G05A-HOOK (#161): korterstock area contract (half 15 on the
    // wire, sigma 0.3); Euclidean-built like moorage.
    const kdir = await fixtureDir([{ lat: 59.44, lon: 24.82 }], "korterstock");
    await writeFile(
      join(kdir, "osm", "korterstock-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 15, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("korterstock", kdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(15);
    } finally {
      await rm(kdir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.44, lon: 24.82 }], "korterstock");
    await writeFile(
      join(stale, "osm", "korterstock-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 1, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("korterstock", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves G05C commbleed + windsolar + viewshed rasters under their contracts", async () => {
    // G05C-HOOK (#163): commbleed quiet contract (halfM 300 on the
    // wire as half, sigma 0.3); Euclidean-built like drainage. A stale
    // half is rejected.
    const cdir = await fixtureDir([{ lat: 59.4229, lon: 24.7956 }], "commbleed");
    await writeFile(
      join(cdir, "osm", "commbleed-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 300, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("commbleed", cdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(300);
    } finally {
      await rm(cdir, { recursive: true, force: true });
    }
    // G05C-HOOK (#163): windsolar quiet contract (halfM 800 on the
    // wire as half, sigma 0.3); Euclidean-built like saltspray.
    const wdir = await fixtureDir([{ lat: 59.39614, lon: 24.67064 }], "windsolar");
    await writeFile(
      join(wdir, "osm", "windsolar-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 800, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("windsolar", wdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(800);
    } finally {
      await rm(wdir, { recursive: true, force: true });
    }
    // G05C-HOOK (#163): viewshed AREA contract (half 1 on the wire,
    // sigma 0.3, moorage precedent); Euclidean count kernel.
    const vdir = await fixtureDir([{ lat: 59.4357, lon: 24.7399 }], "viewshed");
    await writeFile(
      join(vdir, "osm", "viewshed-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 1, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("viewshed", vdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(1);
    } finally {
      await rm(vdir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.4357, lon: 24.7399 }], "viewshed");
    await writeFile(
      join(stale, "osm", "viewshed-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 2, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("viewshed", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves the G05E equestrian raster under its contract", async () => {
    // G05E-HOOK (#165): equestrian AREA contract (half 1 on the wire,
    // sigma 0.3, viewshed precedent); Euclidean count kernel. A stale
    // half is rejected.
    const edir = await fixtureDir([{ lat: 59.42642, lon: 24.66428 }], "equestrian");
    await writeFile(
      join(edir, "osm", "equestrian-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 1, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("equestrian", edir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(1);
    } finally {
      await rm(edir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.42642, lon: 24.66428 }], "equestrian");
    await writeFile(
      join(stale, "osm", "equestrian-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 2, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("equestrian", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves the G05F upcycle raster under its contract", async () => {
    // G05F-HOOK (#166): upcycle AREA contract (half 2 on the wire,
    // sigma 0.3, buildout precedent); Euclidean count kernel. A stale
    // half is rejected.
    const udir = await fixtureDir([{ lat: 59.43205, lon: 24.76142 }], "upcycle");
    await writeFile(
      join(udir, "osm", "upcycle-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 2, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("upcycle", udir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(2);
    } finally {
      await rm(udir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.43205, lon: 24.76142 }], "upcycle");
    await writeFile(
      join(stale, "osm", "upcycle-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 1, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("upcycle", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves the G10R skyview raster under its contract", async () => {
    // G10R-HOOK (#171): skyview quiet contract (halfM 150 on the
    // wire as half, sigma 0.3); Euclidean-built like windsolar. A
    // stale half is rejected.
    const sdir = await fixtureDir([{ lat: 59.44, lon: 24.82 }], "skyview");
    await writeFile(
      join(sdir, "osm", "skyview-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 150, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("skyview", sdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(150);
    } finally {
      await rm(sdir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.44, lon: 24.82 }], "skyview");
    await writeFile(
      join(stale, "osm", "skyview-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 300, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("skyview", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves G18A dayopen + glassglare rasters under their contracts", async () => {
    // G18A-HOOK (#172): dayopen quiet contract (halfM 150 on the
    // wire as half, sigma 0.3); Euclidean-built like commbleed. A
    // stale half is rejected.
    const ddir = await fixtureDir([{ lat: 59.44, lon: 24.82 }], "dayopen");
    await writeFile(
      join(ddir, "osm", "dayopen-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 150, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("dayopen", ddir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(150);
    } finally {
      await rm(ddir, { recursive: true, force: true });
    }
    // G18A-HOOK (#172): glassglare quiet contract (halfM 200 on the
    // wire as half, sigma 0.3); Euclidean-built like windsolar.
    const gdir = await fixtureDir([{ lat: 59.4313, lon: 24.7619 }], "glassglare");
    await writeFile(
      join(gdir, "osm", "glassglare-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 200, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("glassglare", gdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(200);
    } finally {
      await rm(gdir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.4313, lon: 24.7619 }], "glassglare");
    await writeFile(
      join(stale, "osm", "glassglare-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 800, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("glassglare", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves G18B fishbowl + mossrisk + daylight rasters under their contracts", async () => {
    // G18B-HOOK (#173): fishbowl quiet contract (halfM 150 on the
    // wire as half, sigma 0.3); Euclidean-built like drainage. A stale
    // half is rejected.
    const fdir = await fixtureDir([{ lat: 59.4374, lon: 24.7454 }], "fishbowl");
    await writeFile(
      join(fdir, "osm", "fishbowl-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 150, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("fishbowl", fdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(150);
    } finally {
      await rm(fdir, { recursive: true, force: true });
    }
    // G18B-HOOK (#173): mossrisk quiet contract (halfM 250 on the
    // wire as half, sigma 0.3); Euclidean-built like windsolar.
    const mdir = await fixtureDir([{ lat: 59.36, lon: 24.66 }], "mossrisk");
    await writeFile(
      join(mdir, "osm", "mossrisk-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 250, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("mossrisk", mdir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(250);
    } finally {
      await rm(mdir, { recursive: true, force: true });
    }
    // G18B-HOOK (#173): daylight SPARSE contract (half 150 on the wire,
    // sigma 0.3 — inverted count, green where sparse); Euclidean-built.
    // A stale half is rejected like every other layer.
    const ddir = await fixtureDir([{ lat: 59.4405, lon: 24.7369 }], "daylight");
    await writeFile(
      join(ddir, "osm", "daylight-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 150, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("daylight", ddir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(150);
    } finally {
      await rm(ddir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.4405, lon: 24.7369 }], "daylight");
    await writeFile(
      join(stale, "osm", "daylight-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 50, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("daylight", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves G17A compost + gritbin + leafdrop rasters under their contracts", async () => {
    // G17A-HOOK (#177): all three carry the AREA contract (half 1 on
    // the wire, sigma 0.3, viewshed/moorage precedent); Euclidean-built
    // like viewshed. A stale half is rejected.
    for (const layer of ["compost", "gritbin", "leafdrop"] as const) {
      const dir = await fixtureDir([{ lat: 59.36103, lon: 24.64352 }], layer);
      await writeFile(
        join(dir, "osm", `${layer}-walk-raster.json`),
        JSON.stringify(rasterDoc({ half: 1, sigma: 0.3 })),
      );
      try {
        const res = await loadLayerRaster(layer, dir);
        expect(res.distance).toBe("euclidean");
        expect(res.raster?.half).toBe(1);
      } finally {
        await rm(dir, { recursive: true, force: true });
      }
    }
    const stale = await fixtureDir([{ lat: 59.36103, lon: 24.64352 }], "compost");
    await writeFile(
      join(stale, "osm", "compost-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 2, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("compost", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves the G17B lawncare raster under its contract", async () => {
    // G17B-HOOK (#178): lawncare AREA contract (half 20 on the wire,
    // sigma 0.3, viewshed/G17A shape with a density half); Euclidean
    // count kernel. A stale half is rejected.
    const ldir = await fixtureDir([{ lat: 59.412, lon: 24.655 }], "lawncare");
    await writeFile(
      join(ldir, "osm", "lawncare-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 20, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("lawncare", ldir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(20);
    } finally {
      await rm(ldir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.412, lon: 24.655 }], "lawncare");
    await writeFile(
      join(stale, "osm", "lawncare-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 1, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("lawncare", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves the G17R privroad raster under its contract", async () => {
    // G17R-HOOK (#196): privroad QUIET contract (halfM 200 on the
    // wire half field, sigma 0.3); exact-grid Dijkstra Euclidean
    // master. A stale half is rejected.
    const ldir = await fixtureDir([{ lat: 59.44256, lon: 24.57679 }], "privroad");
    await writeFile(
      join(ldir, "osm", "privroad-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 200, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("privroad", ldir);
      expect(res.distance).toBe("euclidean");
      expect(res.raster?.half).toBe(200);
    } finally {
      await rm(ldir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.44256, lon: 24.57679 }], "privroad");
    await writeFile(
      join(stale, "osm", "privroad-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 300, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("privroad", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves grocery and walkability rasters under the area contract", async () => {
    const gdir = await fixtureDir([{ lat: 59.44, lon: 24.75, a: 1 }], "grocery");
    await writeFile(
      join(gdir, "osm", "grocery-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 6, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("grocery", gdir);
      expect(res.distance).toBe("walk");
      expect(res.raster?.half).toBe(6);
    } finally {
      await rm(gdir, { recursive: true, force: true });
    }
    const wdir = await fixtureDir([{ lat: 59.44, lon: 24.75, a: 1 }], "walkability");
    await writeFile(
      join(wdir, "osm", "walkability-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 300, sigma: 0.2 })),
    );
    try {
      expect((await loadLayerRaster("walkability", wdir)).distance).toBe("walk");
    } finally {
      await rm(wdir, { recursive: true, force: true });
    }
    // Stale grocery half: rejected.
    const stale = await fixtureDir([{ lat: 59.44, lon: 24.75, a: 1 }], "grocery");
    await writeFile(
      join(stale, "osm", "grocery-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 3, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("grocery", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves G11D leftover-B rasters under area + quiet contracts", async () => {
    // G11D-HOOK (#135): mailbox area contract (half 2.5, sigma 0.5).
    const mdir = await fixtureDir([{ lat: 59.44, lon: 24.75, a: 1 }], "mailbox");
    await writeFile(
      join(mdir, "osm", "mailbox-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 2.5, sigma: 0.5 })),
    );
    try {
      const res = await loadLayerRaster("mailbox", mdir);
      expect(res.distance).toBe("walk");
      expect(res.raster?.half).toBe(2.5);
    } finally {
      await rm(mdir, { recursive: true, force: true });
    }
    // G11D-HOOK (#135): trailprivacy quiet contract (halfM 1500 on the
    // wire as half, sigma 0.5); a stale half is rejected.
    const tdir = await fixtureDir([{ lat: 59.44, lon: 24.75, a: 1 }], "trailprivacy");
    await writeFile(
      join(tdir, "osm", "trailprivacy-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 1500, sigma: 0.5 })),
    );
    try {
      expect((await loadLayerRaster("trailprivacy", tdir)).distance).toBe("walk");
    } finally {
      await rm(tdir, { recursive: true, force: true });
    }
    const stale = await fixtureDir([{ lat: 59.44, lon: 24.75, a: 1 }], "postal");
    await writeFile(
      join(stale, "osm", "postal-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 4, sigma: 0.8 })),
    );
    try {
      expect(await loadLayerRaster("postal", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("serves G07 quiet rasters under the halfM contract", async () => {
    const idir = await fixtureDir([{ lat: 59.466, lon: 24.698 }], "industprox");
    await writeFile(
      join(idir, "osm", "industprox-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 500, sigma: 0.5 })),
    );
    try {
      const res = await loadLayerRaster("industprox", idir);
      expect(res.distance).toBe("walk");
      expect(res.raster?.half).toBe(500);
    } finally {
      await rm(idir, { recursive: true, force: true });
    }
    // Stale odor half (area-half scale): rejected.
    const stale = await fixtureDir([{ lat: 59.466, lon: 24.698 }], "odorsrc");
    await writeFile(
      join(stale, "osm", "odorsrc-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 120, sigma: 0.5 })),
    );
    try {
      expect(await loadLayerRaster("odorsrc", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });

  it("falls back to euclidean when a raster is missing, corrupt, or stale", async () => {
    const missing = await fixtureDir([{ lat: 59.44, lon: 24.75 }], "transit");
    try {
      expect(await loadLayerRaster("transit", missing)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(missing, { recursive: true, force: true });
    }
    const corrupt = await fixtureDir([{ lat: 59.44, lon: 24.75 }], "parks");
    await writeFile(join(corrupt, "osm", "parks-walk-raster.json"), "{nope");
    try {
      expect(await loadLayerRaster("parks", corrupt)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(corrupt, { recursive: true, force: true });
    }
    // Stale calibration (half 500): rejected, never silently rendered.
    const stale = await fixtureDir([{ lat: 59.44, lon: 24.75 }], "transit");
    await writeFile(
      join(stale, "osm", "transit-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 500, sigma: 0.2 })),
    );
    try {
      expect(await loadLayerRaster("transit", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
    // Wrong variety ladder on schools: rejected too.
    const staleSchools = await fixtureDir([{ lat: 59.44, lon: 24.75 }], "schools");
    await writeFile(
      join(staleSchools, "osm", "schools-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: null, sigma: 0.8, per: 6, cap: 30 })),
    );
    try {
      expect(await loadLayerRaster("schools", staleSchools)).toEqual({
        raster: null,
        distance: "euclidean",
      });
    } finally {
      await rm(staleSchools, { recursive: true, force: true });
    }
  });
});

describe("raster window serving", () => {
  // Mini masters: metro 4x4 @ step 1 (bbox 0..4), county 2x2 @ step 2 same extent.
  const metroMeta = (half: number, sigma: number) => ({
    bbox: { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 },
    step_m: 1,
    cols: 4,
    rows: 4,
    half,
    sigma,
    per: 0,
    cap: 0,
    unknown: 255,
    dtype: "uint8",
  });
  // Metro values: 90 at x<2, unknown (255) at x>=2.
  const metroBytes = Buffer.from([90, 90, 255, 255, 80, 80, 255, 255, 70, 70, 255, 255, 60, 60, 255, 255]);
  const countyDoc = (half: number, sigma: number) => ({
    cols: 2,
    rows: 2,
    bbox: { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 },
    step_m: 2,
    half,
    sigma,
    per: 0,
    cap: 0,
    unknown: 255,
    dtype: "uint8",
    data: Buffer.from([11, 22, 33, 44]).toString("base64"),
  });
  const view = { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 };

  async function fixtureWithMasters(layer: string, half: number, sigma: number) {
    const dir = await fixtureDir([{ lat: 1, lon: 1, a: 1 }], layer);
    await writeFile(join(dir, "osm", `${layer}-walk-raster.json`), JSON.stringify(countyDoc(half, sigma)));
    await writeFile(join(dir, "osm", `${layer}-metro.json`), JSON.stringify(metroMeta(half, sigma)));
    await writeFile(join(dir, "osm", `${layer}-metro.u8`), metroBytes);
    return dir;
  }

  it("composites metro over county, falling back per cell", async () => {
    const dir = await fixtureWithMasters("grocery", 6, 0.3);
    try {
      const win = await loadWindowRaster("grocery", view, 4, 4, dir);
      expect(win).not.toBeNull();
      const raw = Buffer.from(win!.data, "base64");
      // West half reads metro (90/80/70/60 column for rows 0..3... row-major).
      expect(raw[0]).toBe(90);
      expect(raw[4]).toBe(80);
      // East half metro-unknown falls back to county, bilinearly blended:
      // x=2.5 mixes county 11/22 into (11*.1875+22*.5625)/.75 = 19.25 -> 19,
      // x=3.5 sees only county 22 -> 22.
      expect(raw[2]).toBe(19);
      expect(raw[3]).toBe(22);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("echoes the quiet halfM on G07 county-only windows (no metro)", async () => {
    const dir = await fixtureDir([{ lat: 1, lon: 1 }], "odorsrc");
    await writeFile(join(dir, "osm", "odorsrc-walk-raster.json"), JSON.stringify(countyDoc(500, 0.5)));
    try {
      const win = await loadWindowRaster("odorsrc", view, 2, 2, dir);
      expect(win).not.toBeNull();
      expect(win?.half).toBe(500);
      expect(win?.sigma).toBe(0.5);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("serves county-only windows outside the metro extent", async () => {
    const dir = await fixtureWithMasters("grocery", 6, 0.3);
    try {
      const win = await loadWindowRaster(
        "grocery",
        { minlon: 10, minlat: 10, maxlon: 12, maxlat: 12 },
        2,
        2,
        dir,
      );
      expect(win).not.toBeNull();
      expect(Buffer.from(win!.data, "base64").every((v) => v === 255)).toBe(true);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("rejects stale masters and clamps grid sizes", async () => {
    const dir = await fixtureWithMasters("grocery", 6, 0.3);
    await writeFile(
      join(dir, "osm", "grocery-metro.json"),
      JSON.stringify(metroMeta(999, 0.3)),
    );
    try {
      // Stale metro: county-only window still serves.
      const win = await loadWindowRaster("grocery", view, 2, 2, dir);
      expect(win).not.toBeNull();
      expect(Buffer.from(win!.data, "base64")[0]).toBe(11);
      // Absurd grid sizes clamp instead of exploding.
      const big = await loadWindowRaster("grocery", view, 100000, 100000, dir);
      expect(big!.cols).toBeLessThanOrEqual(512);
      expect(big!.rows).toBeLessThanOrEqual(512);
      // Garbage bbox reads null.
      expect(await loadWindowRaster("grocery", { minlon: 5, minlat: 5, maxlon: 1, maxlat: 1 }, 4, 4, dir)).toBeNull();
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("hole filling", () => {
  // County-only fixture (no metro files): 6x2 over 0..6/0..4, a 3-wide
  // unknown gap between a 0-score west edge and a 100-score east edge.
  // Window cells sit on exact county centers, so the gap survives the
  // bilinear composite for the hole-fill to resolve two-sided.
  async function gapFixture() {
    const dir = await fixtureDir([{ lat: 1, lon: 1, a: 1 }], "grocery");
    await writeFile(
      join(dir, "osm", "grocery-walk-raster.json"),
      JSON.stringify({
        cols: 6,
        rows: 2,
        bbox: { minlon: 0, minlat: 0, maxlon: 6, maxlat: 4 },
        step_m: 1,
        half: 6,
        sigma: 0.3,
        per: 0,
        cap: 0,
        unknown: 255,
        dtype: "uint8",
        data: Buffer.from([0, 255, 255, 255, 255, 100, 0, 255, 255, 255, 255, 100]).toString("base64"),
      }),
    );
    return dir;
  }

  it("fills holes with the distance-weighted average of surroundings", async () => {
    const dir = await gapFixture();
    try {
      const win = await loadWindowRaster(
        "grocery",
        { minlon: 0, minlat: 0, maxlon: 6, maxlat: 4 },
        6,
        2,
        dir,
      );
      expect(win).not.toBeNull();
      const raw = Buffer.from(win!.data, "base64");
      // Gap columns inherit from BOTH sides: strictly inside (0,100),
      // rising west->east toward the 25/50/75 Laplace gradient.
      expect(raw[1]).toBeGreaterThan(0);
      expect(raw[1]).toBeLessThan(raw[2]);
      expect(raw[2]).toBeLessThan(raw[3]);
      expect(raw[3]).toBeLessThan(100);
      const rowSum = raw[1] + raw[2] + raw[3];
      expect(rowSum).toBeGreaterThan(140);
      expect(rowSum).toBeLessThan(160);
      expect(Array.from(raw).every((v) => v !== 255)).toBe(true);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("bilinear-blends county cells instead of snapping to blocks", async () => {
    // County-only 2x2: west col 0, east col 100. A 1x1 window centered on
    // the seam must read the average (50), not snap to a block (100).
    const dir = await fixtureDir([{ lat: 1, lon: 1, a: 1 }], "grocery");
    await writeFile(
      join(dir, "osm", "grocery-walk-raster.json"),
      JSON.stringify({
        cols: 2,
        rows: 2,
        bbox: { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 },
        step_m: 2,
        half: 6,
        sigma: 0.3,
        per: 0,
        cap: 0,
        unknown: 255,
        dtype: "uint8",
        data: Buffer.from([0, 100, 0, 100]).toString("base64"),
      }),
    );
    try {
      const win = await loadWindowRaster("grocery", { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 }, 1, 1, dir);
      expect(win).not.toBeNull();
      expect(Buffer.from(win!.data, "base64")[0]).toBe(50);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("bilinear county blend skips unknown corners", async () => {
    // Only diagonal corners known (0 and 100): renormalized blend is 50.
    const dir = await fixtureDir([{ lat: 1, lon: 1, a: 1 }], "grocery");
    await writeFile(
      join(dir, "osm", "grocery-walk-raster.json"),
      JSON.stringify({
        cols: 2,
        rows: 2,
        bbox: { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 },
        step_m: 2,
        half: 6,
        sigma: 0.3,
        per: 0,
        cap: 0,
        unknown: 255,
        dtype: "uint8",
        data: Buffer.from([0, 255, 255, 100]).toString("base64"),
      }),
    );
    try {
      const win = await loadWindowRaster("grocery", { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 }, 1, 1, dir);
      expect(win).not.toBeNull();
      expect(Buffer.from(win!.data, "base64")[0]).toBe(50);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("fills near holes but leaves far unknown cells red", async () => {
    const dir = await fixtureDir([{ lat: 1, lon: 1, a: 1 }], "grocery");
    await writeFile(
      join(dir, "osm", "grocery-walk-raster.json"),
      JSON.stringify({
        cols: 2,
        rows: 2,
        bbox: { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 },
        step_m: 2,
        half: 6,
        sigma: 0.3,
        per: 0,
        cap: 0,
        unknown: 255,
        dtype: "uint8",
        data: Buffer.from([50, 255, 255, 255]).toString("base64"),
      }),
    );
    try {
      // 400-wide strip: bilinear renormalizing extends the known 50 east
      // to lon 3.0 (col 300); the 100-cell unknown run past that exceeds
      // the 64-pass fill reach, so the far end stays red.
      const win = await loadWindowRaster("grocery", { minlon: 0, minlat: 0, maxlon: 4, maxlat: 1 }, 400, 1, dir);
      expect(win).not.toBeNull();
      const raw = Buffer.from(win!.data, "base64");
      expect(raw[300]).toBe(50);
      expect(raw[399]).toBe(255);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("snapshot coverage", () => {
  it("covers Harjumaa but not Tartu", () => {
    // Balti jaam (Tallinn) is inside; Tartu is outside.
    expect(
      intersectsCoverage({ minlon: 24.7, minlat: 59.4, maxlon: 24.8, maxlat: 59.5 }),
    ).toBe(true);
    expect(
      intersectsCoverage({ minlon: 26.6, minlat: 58.3, maxlon: 26.8, maxlat: 58.45 }),
    ).toBe(false);
    expect(SNAPSHOT_BBOX.minlon).toBeLessThan(SNAPSHOT_BBOX.maxlon);
    expect(SNAPSHOT_BBOX.minlat).toBeLessThan(SNAPSHOT_BBOX.maxlat);
  });
});

describe("G07B quiet rasters (brownsoil/oiltank/agriland)", () => {
describe("G07D quiet rasters (agrifield/wildcorr)", () => {
  const rasterDoc = (contract: { half?: number | null; sigma: number }) => ({
    cols: 2,
    rows: 2,
    bbox: { minlon: 24.0, minlat: 59.0, maxlon: 24.2, maxlat: 59.1 },
    step_m: 75,
    half: contract.half ?? null,
    sigma: contract.sigma,
    per: 0,
    cap: 0,
    unknown: 255,
    dtype: "uint8",
    data: Buffer.from([80, 255, 40, 60]).toString("base64"),
  });

  it("serves G07B quiet rasters under the halfM contract", async () => {
    const idir = await fixtureDir([{ lat: 59.4513, lon: 24.7222 }], "brownsoil");
    await writeFile(
      join(idir, "osm", "brownsoil-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 500, sigma: 0.5 })),
    );
    try {
      const res = await loadLayerRaster("brownsoil", idir);
      expect(res.distance).toBe("walk");
      expect(res.raster?.half).toBe(500);
    } finally {
      await rm(idir, { recursive: true, force: true });
    }
    // Stale tank half (area-half scale): rejected.
    const stale = await fixtureDir([{ lat: 59.4983, lon: 24.937 }], "oiltank");
    await writeFile(
      join(stale, "osm", "oiltank-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 120, sigma: 0.5 })),
    );
    try {
      expect(await loadLayerRaster("oiltank", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
    // Agriland halves at the 800 m spray-drift scale.
    const adir = await fixtureDir([{ lat: 59.44, lon: 24.9261 }], "agriland");
    await writeFile(
      join(adir, "osm", "agriland-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 800, sigma: 0.8 })),
    );
    try {
      const res = await loadLayerRaster("agriland", adir);
      expect(res.distance).toBe("walk");
      expect(res.raster?.half).toBe(800);
    } finally {
      await rm(adir, { recursive: true, force: true });
    }
  });

  it("echoes the quiet halfM on G07B county-only windows (no metro)", async () => {
    const countyDoc = (half: number, sigma: number) => ({
      cols: 2,
      rows: 2,
      bbox: { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 },
      step_m: 2,
      half,
      sigma,
      per: 0,
      cap: 0,
      unknown: 255,
      dtype: "uint8",
      data: Buffer.from([11, 22, 33, 44]).toString("base64"),
    });
    const dir = await fixtureDir([{ lat: 1, lon: 1 }], "agriland");
    await writeFile(join(dir, "osm", "agriland-walk-raster.json"), JSON.stringify(countyDoc(800, 0.8)));
    try {
      const win = await loadWindowRaster("agriland", { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 }, 2, 2, dir);
      expect(win).not.toBeNull();
      expect(win?.half).toBe(800);
      expect(win?.sigma).toBe(0.8);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("serves G07D quiet rasters under the halfM contract", async () => {
    const idir = await fixtureDir([{ lat: 59.4407, lon: 24.8041 }], "agrifield");
    await writeFile(
      join(idir, "osm", "agrifield-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 800, sigma: 0.8 })),
    );
    try {
      const res = await loadLayerRaster("agrifield", idir);
      expect(res.distance).toBe("walk");
      expect(res.raster?.half).toBe(800);
    } finally {
      await rm(idir, { recursive: true, force: true });
    }
    // Stale wildcorr half (parcel scale is 500, not 800): rejected.
    const stale = await fixtureDir([{ lat: 59.4364, lon: 24.7489 }], "wildcorr");
    await writeFile(
      join(stale, "osm", "wildcorr-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 800, sigma: 0.5 })),
    );
    try {
      expect(await loadLayerRaster("wildcorr", stale)).toEqual({ raster: null, distance: "euclidean" });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
    // Wildcorr halves at the 500 m parcel scale.
    const wdir = await fixtureDir([{ lat: 59.4364, lon: 24.7489 }], "wildcorr");
    await writeFile(
      join(wdir, "osm", "wildcorr-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 500, sigma: 0.5 })),
    );
    try {
      const res = await loadLayerRaster("wildcorr", wdir);
      expect(res.distance).toBe("walk");
      expect(res.raster?.half).toBe(500);
    } finally {
      await rm(wdir, { recursive: true, force: true });
    }
  });

  it("echoes the quiet halfM on G07D county-only windows (no metro)", async () => {
    const countyDoc = (half: number, sigma: number) => ({
      cols: 2,
      rows: 2,
      bbox: { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 },
      step_m: 2,
      half,
      sigma,
      per: 0,
      cap: 0,
      unknown: 255,
      dtype: "uint8",
      data: Buffer.from([11, 22, 33, 44]).toString("base64"),
    });
    const dir = await fixtureDir([{ lat: 1, lon: 1 }], "agriland");
    await writeFile(join(dir, "osm", "agriland-walk-raster.json"), JSON.stringify(countyDoc(800, 0.8)));
    try {
      const win = await loadWindowRaster("agriland", { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 }, 2, 2, dir);
      expect(win).not.toBeNull();
      expect(win?.half).toBe(800);
      expect(win?.sigma).toBe(0.8);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("echoes the quiet halfM on G07D county-only windows (no metro)", async () => {
    const countyDoc = (half: number, sigma: number) => ({
      cols: 2,
      rows: 2,
      bbox: { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 },
      step_m: 2,
      half,
      sigma,
      per: 0,
      cap: 0,
      unknown: 255,
      dtype: "uint8",
      data: Buffer.from([11, 22, 33, 44]).toString("base64"),
    });
    const dir = await fixtureDir([{ lat: 1, lon: 1 }], "agrifield");
    await writeFile(join(dir, "osm", "agrifield-walk-raster.json"), JSON.stringify(countyDoc(800, 0.8)));
    try {
      const win = await loadWindowRaster("agrifield", { minlon: 0, minlat: 0, maxlon: 4, maxlat: 4 }, 2, 2, dir);
      expect(win).not.toBeNull();
      expect(win?.half).toBe(800);
      expect(win?.sigma).toBe(0.8);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("G07C quiet raster (vectorhabitat, #142)", () => {
  // G07C-HOOK(#142): quiet kind echoes halfM 300 on the wire half slot.
  const rasterDoc = (contract: { half?: number | null; sigma: number }) => ({
    cols: 2,
    rows: 2,
    bbox: { minlon: 24.0, minlat: 59.0, maxlon: 24.2, maxlat: 59.1 },
    step_m: 75,
    half: contract.half ?? null,
    sigma: contract.sigma,
    per: 0,
    cap: 0,
    unknown: 255,
    dtype: "uint8",
    data: Buffer.from([80, 255, 40, 60]).toString("base64"),
  });

  it("serves the vectorhabitat raster under the quiet contract (halfM on half)", async () => {
    const dir = await fixtureDir(
      [{ lat: 59.3862, lon: 24.6611, tags: { natural: "wood" } }],
      "vectorhabitat",
    );
    await writeFile(
      join(dir, "osm", "vectorhabitat-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 300, sigma: 0.3 })),
    );
    try {
      const res = await loadLayerRaster("vectorhabitat", dir);
      expect(res.distance).toBe("walk");
      expect(res.raster?.half).toBe(300);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
    // Wrong halfM: rejected, never silently rendered.
    const stale = await fixtureDir([{ lat: 59.3862, lon: 24.6611 }], "vectorhabitat");
    await writeFile(
      join(stale, "osm", "vectorhabitat-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 500, sigma: 0.3 })),
    );
    try {
      expect(await loadLayerRaster("vectorhabitat", stale)).toEqual({
        raster: null,
        distance: "euclidean",
      });
    } finally {
      await rm(stale, { recursive: true, force: true });
    }
  });
});
});
