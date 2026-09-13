// Hermetic tests for the ookla extract loader (issue #489). Extract
// fixtures are FULLY SYNTHETIC (clearly labelled) with the
// tallinn_extract shape ({quarter, fixed, mobile, n_fixed, n_mobile})
// — real observed values appear only in docs/p4_ookla.md. No network:
// temp files only, never the real /tmp/hf-ookla tree.

import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  OOKLA_SNAPSHOT_NAME,
  loadOoklaSnapshot,
  ooklaCacheDir,
  ooklaPointsIn,
  ooklaRowToPoint,
  ooklaSnapshotPath,
} from "./ookla";

let dirs: string[] = [];
afterEach(async () => {
  for (const d of dirs) await rm(d, { recursive: true, force: true });
  dirs = [];
});

async function fixtureFile(body: unknown): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "hf-ookla-"));
  dirs.push(dir);
  const file = join(dir, OOKLA_SNAPSHOT_NAME);
  await writeFile(file, typeof body === "string" ? body : JSON.stringify(body));
  return file;
}

/** Synthetic Tallinn-extract-shaped fixture (never live data). */
function syntheticExtract() {
  return {
    quarter: "2026-Q1",
    fixed: [
      { tile_x: 24.7454, tile_y: 59.4375, avg_d_kbps: 154425, avg_u_kbps: 117012, avg_lat_ms: 5, tests: 151, devices: 44, quadkey: "1201202310211212" },
      { tile_x: 24.75, tile_y: 59.44, avg_d_kbps: 92624, avg_u_kbps: 50000, avg_lat_ms: 8, tests: 36, devices: 12, quadkey: "1201202310211213" },
      { tile_x: 25.582, tile_y: 58.364, avg_d_kbps: 200000, avg_u_kbps: 90000, avg_lat_ms: 6, tests: 20, devices: 9, quadkey: "1201202310211999" },
    ],
    mobile: [
      { tile_x: 24.7454, tile_y: 59.4375, avg_d_kbps: 220138, avg_u_kbps: 26276, avg_lat_ms: 15, tests: 60, devices: 30, quadkey: "1201202310211212" },
    ],
    n_fixed: 3,
    n_mobile: 1,
  };
}

describe("loadOoklaSnapshot", () => {
  it("loads fixed + mobile rows as points with band tags + the quarter", async () => {
    const snap = await loadOoklaSnapshot(await fixtureFile(syntheticExtract()));
    expect(snap?.quarter).toBe("2026-Q1");
    expect(snap?.fixed).toEqual([
      { lat: 59.4375, lon: 24.7454, tags: { avg_d: "154425", tests: "151" } },
      { lat: 59.44, lon: 24.75, tags: { avg_d: "92624", tests: "36" } },
      { lat: 58.364, lon: 25.582, tags: { avg_d: "200000", tests: "20" } },
    ]);
    expect(snap?.mobile).toEqual([
      { lat: 59.4375, lon: 24.7454, tags: { avg_d: "220138", tests: "60" } },
    ]);
  });

  it("returns null for a missing extract (never data, never throws)", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-ookla-"));
    dirs.push(dir);
    expect(await loadOoklaSnapshot(join(dir, OOKLA_SNAPSHOT_NAME))).toBeNull();
  });

  it("returns null for corrupt JSON / wrong shapes (never throws)", async () => {
    expect(await loadOoklaSnapshot(await fixtureFile("{nope"))).toBeNull();
    expect(await loadOoklaSnapshot(await fixtureFile([1, 2]))).toBeNull();
    expect(await loadOoklaSnapshot(await fixtureFile({ quarter: "2026-Q1" }))).toBeNull();
    expect(await loadOoklaSnapshot(await fixtureFile({ fixed: "x", mobile: [] }))).toBeNull();
    expect(await loadOoklaSnapshot(await fixtureFile({ fixed: [], mobile: "x" }))).toBeNull();
    expect(await loadOoklaSnapshot(await fixtureFile(null))).toBeNull();
  });

  it("skips coordless junk rows, keeps the rest (no coords = no join key)", async () => {
    const snap = await loadOoklaSnapshot(
      await fixtureFile({
        quarter: "2026-Q1",
        fixed: [
          { tile_x: 24.75, tile_y: 59.43, avg_d_kbps: 100000, tests: 10 },
          { tile_x: null, tile_y: 59.43, avg_d_kbps: 100000, tests: 10 },
          { tile_y: 59.43, avg_d_kbps: 100000, tests: 10 },
          "junk",
        ],
        mobile: [],
      }),
    );
    expect(snap?.fixed).toEqual([
      { lat: 59.43, lon: 24.75, tags: { avg_d: "100000", tests: "10" } },
    ]);
  });

  it("keeps partial rows faithful (guards live in the kernel, never pre-scored out)", async () => {
    const snap = await loadOoklaSnapshot(
      await fixtureFile({
        quarter: "2026-Q1",
        fixed: [
          { tile_x: 24.75, tile_y: 59.43, avg_d_kbps: null, tests: 2 },
          { tile_x: 24.76, tile_y: 59.44, avg_d_kbps: 381664, tests: 3 },
        ],
        mobile: [],
      }),
    );
    // Partial tags ride along (faithful extract); the tileband kernel
    // still never qualifies them (avg_d guard + MIN_TESTS).
    expect(snap?.fixed).toEqual([
      { lat: 59.43, lon: 24.75, tags: { tests: "2" } },
      { lat: 59.44, lon: 24.76, tags: { avg_d: "381664", tests: "3" } },
    ]);
  });

  it("defaults to the quarterly cache path outside /tmp scratch", () => {
    expect(OOKLA_SNAPSHOT_NAME).toBe("ookla-tallinn-2026Q1.json");
    expect(ooklaCacheDir()).toContain("hf-ookla");
    expect(ooklaSnapshotPath()).toContain(OOKLA_SNAPSHOT_NAME);
  });
});

describe("ooklaRowToPoint", () => {
  it("rejects non-rows and out-of-range centroids", () => {
    expect(ooklaRowToPoint(null)).toBeNull();
    expect(ooklaRowToPoint("junk")).toBeNull();
    expect(ooklaRowToPoint({ tile_x: 999, tile_y: 59.43 })).toBeNull();
  });
});

describe("ooklaPointsIn", () => {
  const bbox = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

  it("clips per service (fixed vs mobile never mix)", async () => {
    const snap = await loadOoklaSnapshot(await fixtureFile(syntheticExtract()));
    expect(ooklaPointsIn(snap!, "fixed", bbox)).toHaveLength(2);
    expect(ooklaPointsIn(snap!, "mobile", bbox)).toHaveLength(1);
  });
});
