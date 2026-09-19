import { describe, expect, it } from "vitest";
import { mkdtemp, rm, utimes, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  SHED_CACHE_FILE,
  SHED_EMPTY_REASON,
  SHED_HUBS,
  SHED_TTL_S,
  isShedCacheFresh,
  loadShedSnapshot,
  shedAreasForLayer,
  shedAreasResult,
} from "./sheds";

const HUB = SHED_HUBS[0];

function shedBody(n = 4): string {
  const ring = Array.from({ length: n }, (_, i) => ({
    latitude: 59.44 + i / 1000,
    longitude: 24.75 + i / 1000,
  }));
  return JSON.stringify({ reachableRange: { boundary: ring } });
}

async function cacheDir(withFiles: string[] = ["900", "1800"]): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "hf-sheds-"));
  for (const budget of withFiles) {
    for (const band of ["rush", "offpeak"]) {
      await writeFile(join(dir, SHED_CACHE_FILE(HUB, budget, band)), shedBody());
    }
  }
  return dir;
}

describe("sheds operator cache (#763)", () => {
  it("pins the 7-day TTL and hub/file contract", () => {
    expect(SHED_TTL_S).toBe(7 * 24 * 3600);
    expect(SHED_HUBS).toContain("city-center");
    expect(SHED_CACHE_FILE("port", "900", "rush")).toBe(
      "tomtom_shed_port_900_rush.json",
    );
    expect(isShedCacheFresh(Date.now() - 1000, Date.now())).toBe(true);
    expect(isShedCacheFresh(Date.now() - SHED_TTL_S * 1000 - 1, Date.now())).toBe(false);
  });

  it("assembles the snapshot polygons shape for shedPolygonsForLayer", async () => {
    const dir = await cacheDir();
    try {
      const snap = await loadShedSnapshot(dir);
      expect(snap).not.toBeNull();
      expect(snap?.polygons.length).toBeGreaterThan(0);
      expect(snap?.polygons[0]).toEqual({
        hub: HUB,
        budgetS: 900,
        band: "rush",
        ring: expect.any(Array),
      });
      expect(snap?.polygons[0].ring.length).toBe(4);
      expect(snap?.builtAtMs).toBeGreaterThan(0);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("missing cache reads null (honestly-empty, never demo polygons)", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-sheds-"));
    try {
      expect(await loadShedSnapshot(dir)).toBeNull();
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("stale hub files drop that hub (others still serve)", async () => {
    const dir = await cacheDir();
    try {
      const ancient = new Date(1000);
      await utimes(join(dir, SHED_CACHE_FILE(HUB, "900", "rush")), ancient, ancient);
      const snap = await loadShedSnapshot(dir);
      const hubs = new Set(snap?.polygons.map((p) => `${p.hub}:${p.budgetS}:${p.band}`));
      expect(hubs.has(`${HUB}:900:rush`)).toBe(false);
      expect(hubs.has(`${HUB}:1800:rush`)).toBe(true);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("selects paint areas per layer (empty rings never paint)", async () => {
    const dir = await cacheDir(["900"]);
    try {
      const snap = await loadShedSnapshot(dir);
      const areas = shedAreasForLayer(snap, "shed-15-peak");
      expect(areas.length).toBeGreaterThan(0);
      expect(areas[0].ring.length).toBeGreaterThanOrEqual(3);
      expect(shedAreasForLayer(snap, "shed-30-peak")).toEqual([]);
      expect(shedAreasForLayer(null, "shed-15-peak")).toEqual([]);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("shed empty-cache honesty (#787)", () => {
  async function fullCache(): Promise<string> {
    const dir = await mkdtemp(join(tmpdir(), "hf-sheds-full-"));
    for (const hub of SHED_HUBS) {
      for (const budget of ["900", "1800"]) {
        for (const band of ["rush", "offpeak"]) {
          await writeFile(
            join(dir, SHED_CACHE_FILE(hub, budget, band)),
            shedBody(),
          );
        }
      }
    }
    return dir;
  }

  it("fully-stale cache reads null (expired = honestly-empty)", async () => {
    const dir = await cacheDir();
    try {
      const ancient = new Date(1000);
      for (const budget of ["900", "1800"]) {
        for (const band of ["rush", "offpeak"]) {
          await utimes(
            join(dir, SHED_CACHE_FILE(HUB, budget, band)),
            ancient,
            ancient,
          );
        }
      }
      expect(await loadShedSnapshot(dir)).toBeNull();
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("empty reason names the weekly cache + TTL + refill, never faked", () => {
    expect(SHED_EMPTY_REASON).toMatch(/nädalapuhver/);
    expect(SHED_EMPTY_REASON).toMatch(/7-päeva TTL/);
    expect(SHED_EMPTY_REASON).toMatch(/run-tomtom-sheds/);
    expect(SHED_EMPTY_REASON).toMatch(/ei asendata väljamõeldud/);
  });

  it("null snapshot is a 503-with-reason (no polygons invented)", () => {
    for (const layer of [
      "shed-15-peak",
      "shed-15-offpeak",
      "shed-30-peak",
      "shed-30-offpeak",
    ] as const) {
      const res = shedAreasResult(null, layer);
      expect(res.status).toBe(503);
      const body = res.body as Record<string, unknown>;
      expect(body.error).toBe("shed cache empty");
      expect(body.reason).toBe(SHED_EMPTY_REASON);
      expect(body).not.toHaveProperty("areas");
    }
  });

  it("fresh weekly cache serves all 5 hubs x 4 layers once refilled", async () => {
    const dir = await fullCache();
    try {
      const snap = await loadShedSnapshot(dir);
      expect(snap).not.toBeNull();
      for (const layer of [
        "shed-15-peak",
        "shed-15-offpeak",
        "shed-30-peak",
        "shed-30-offpeak",
      ] as const) {
        const res = shedAreasResult(snap, layer);
        expect(res.status).toBe(200);
        const body = res.body as {
          areas: Array<{ hub: string }>;
          builtAtMs: number;
        };
        expect(body.areas).toHaveLength(5);
        expect(new Set(body.areas.map((a) => a.hub))).toEqual(
          new Set(SHED_HUBS),
        );
        expect(body.builtAtMs).toBeGreaterThan(0);
      }
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});
