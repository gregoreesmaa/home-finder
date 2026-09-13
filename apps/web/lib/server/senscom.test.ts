// Hermetic tests for the senscom extract loader (issue #484). Extract
// fixtures are FULLY SYNTHETIC (clearly labelled) with the
// tallinn_extract shape ({fetched, bbox, sensors, n_sensors}) — real
// observed values appear only in docs/p4_senscom.md. No network: temp
// files only, never the real /tmp/hf-senscom tree.

import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  SENSCOM_SNAPSHOT_NAME,
  loadSenscomSnapshot,
  senscomCacheDir,
  senscomPointsIn,
  senscomSnapshotPath,
} from "./senscom";

let dirs: string[] = [];
afterEach(async () => {
  for (const d of dirs) await rm(d, { recursive: true, force: true });
  dirs = [];
});

async function fixtureFile(body: unknown): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "hf-senscom-"));
  dirs.push(dir);
  const file = join(dir, SENSCOM_SNAPSHOT_NAME);
  await writeFile(file, typeof body === "string" ? body : JSON.stringify(body));
  return file;
}

/** Synthetic Tallinn-extract-shaped fixture (never live data). */
function syntheticExtract() {
  return {
    fetched: "2026-09-13",
    bbox: { lon_min: 24.3, lon_max: 25.1, lat_min: 59.3, lat_max: 59.6 },
    sensors: [
      { id: 9001, lat: 59.4375, lon: 24.7454, types: ["SDS011"] },
      { id: 9002, lat: 59.438, lon: 24.746, types: ["PMS5003"] },
      { id: 9003, lat: 58.364, lon: 25.582, types: ["BME280"] },
    ],
    n_sensors: 3,
  };
}

describe("loadSenscomSnapshot", () => {
  it("loads extract rows as points with the fetch date", async () => {
    const snap = await loadSenscomSnapshot(await fixtureFile(syntheticExtract()));
    expect(snap?.fetched).toBe("2026-09-13");
    expect(snap?.points).toEqual([
      { lat: 59.4375, lon: 24.7454 },
      { lat: 59.438, lon: 24.746 },
      { lat: 58.364, lon: 25.582 },
    ]);
  });

  it("returns null for a missing extract (never data, never throws)", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-senscom-"));
    dirs.push(dir);
    expect(await loadSenscomSnapshot(join(dir, SENSCOM_SNAPSHOT_NAME))).toBeNull();
  });

  it("returns null for corrupt JSON / wrong shapes (never throws)", async () => {
    expect(await loadSenscomSnapshot(await fixtureFile("{nope"))).toBeNull();
    expect(await loadSenscomSnapshot(await fixtureFile([1, 2]))).toBeNull();
    expect(await loadSenscomSnapshot(await fixtureFile({ fetched: "x" }))).toBeNull();
    expect(await loadSenscomSnapshot(await fixtureFile({ sensors: "x" }))).toBeNull();
    expect(await loadSenscomSnapshot(await fixtureFile(null))).toBeNull();
  });

  it("skips coordless junk rows, keeps the rest", async () => {
    const snap = await loadSenscomSnapshot(
      await fixtureFile({
        fetched: "2026-09-13",
        sensors: [
          { id: 1, lat: 59.43, lon: 24.75 },
          { id: 2, lat: null, lon: 24.75 },
          { id: 3, lon: 24.75 },
          "junk",
          null,
          { id: 4, lat: 59.43, lon: "east" },
        ],
      }),
    );
    expect(snap?.points).toEqual([{ lat: 59.43, lon: 24.75 }]);
  });

  it("nulls an unusable fetch date instead of passing garbage", async () => {
    const snap = await loadSenscomSnapshot(
      await fixtureFile({ sensors: [{ lat: 59.43, lon: 24.75 }] }),
    );
    expect(snap?.fetched).toBeNull();
    expect(snap?.points).toHaveLength(1);
  });
});

describe("senscomPointsIn", () => {
  it("clips extract points to the view bbox", () => {
    const snap = { fetched: "2026-09-13", points: syntheticExtract().sensors.map((s) => ({ lat: s.lat, lon: s.lon })) };
    const tallinn = senscomPointsIn(snap, { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 });
    expect(tallinn).toHaveLength(2);
    expect(senscomPointsIn(snap, { minlon: 25.5, minlat: 58.3, maxlon: 25.7, maxlat: 58.5 })).toHaveLength(1);
    expect(senscomPointsIn(snap, { minlon: 0, minlat: 0, maxlon: 1, maxlat: 1 })).toEqual([]);
  });
});

describe("senscom extract path", () => {
  it("defaults to the scorer's cache file (operator step target)", () => {
    expect(senscomCacheDir().endsWith("hf-senscom")).toBe(true);
    expect(senscomSnapshotPath()).toBe(join(senscomCacheDir(), SENSCOM_SNAPSHOT_NAME));
    delete process.env.SENSCOM_SNAPSHOT_PATH;
    expect(senscomSnapshotPath()).toContain(SENSCOM_SNAPSHOT_NAME);
  });

  it("honors SENSCOM_SNAPSHOT_PATH for operators outside /tmp", async () => {
    const file = await fixtureFile(syntheticExtract());
    process.env.SENSCOM_SNAPSHOT_PATH = file;
    try {
      expect((await loadSenscomSnapshot())?.points).toHaveLength(3);
    } finally {
      delete process.env.SENSCOM_SNAPSHOT_PATH;
    }
  });
});
