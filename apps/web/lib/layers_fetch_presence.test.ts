// Data-fetching behavior per read path (issue #802): pole-first + TTL +
// fallback + provenance + honest-empty-vs-demo pins through the REAL
// /api/layers/[layer] route — same bar as the sheds/incidents/outage/
// datex pins. Table stakes: stale fixture -> stale/empty, never
// fake-live; missing fixture -> labeled demo/empty with reason, never
// 500-by-config (every expected status below is the documented family
// contract; the error body always names the missing piece).
//
// Hermetic: env points at tmp fixture dirs, the pole is a localhost
// stub server (or a dead port for pole-down), no external network.
// Fixtures are tiny hand-written facts, never scraped dumps (AGENTS.md
// section 5). Live presence against compose lives in
// layers_presence_sweep.test.ts (env-flagged, never unit).

import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { createServer, type Server } from "node:http";
import { mkdtemp, rm, utimes, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { GET } from "../app/api/layers/[layer]/route";
import { INCIDENTS_CACHE_FILE } from "./layers_p4_incidents";
import { SHED_CACHE_FILE } from "./server/sheds";

const BBOX = "minlon=24.5&minlat=59.3&maxlon=25.0&maxlat=59.6";
const TALLINN = { lat: 59.4372, lon: 24.7536 };

const SAVED_ENV = { ...process.env };

function setEnv(patch: Record<string, string>): void {
  for (const [k, v] of Object.entries(patch)) process.env[k] = v;
}

afterEach(() => {
  process.env = { ...SAVED_ENV };
});

/** Call the real route GET for one layer id. */
async function getLayer(layer: string): Promise<{ status: number; body: Record<string, unknown> }> {
  const res = await GET(new Request(`http://test/api/layers/${layer}?${BBOX}`), {
    params: { layer },
  });
  return { status: res.status, body: (await res.json()) as Record<string, unknown> };
}

function pointsOf(body: Record<string, unknown>): unknown[] {
  expect(Array.isArray(body.points)).toBe(true);
  return body.points as unknown[];
}

/** Localhost stub pole: per-dataset { status, body, builtAt } or 503. */
const stubTables = new Map<string, { status: number; body: unknown; builtAt: string | null }>();
let stub: Server;
let stubBase = "";

beforeAll(async () => {
  stub = createServer((req, res) => {
    const name = (req.url ?? "").replace("/v1/", "").split("?")[0];
    const hit = stubTables.get(name);
    if (!hit) {
      res.writeHead(503, { "content-type": "application/json" });
      res.end(JSON.stringify({ detail: "not built yet" }));
      return;
    }
    if (hit.builtAt) res.setHeader("X-Pole-Built-At", hit.builtAt);
    res.writeHead(hit.status, { "content-type": "application/json" });
    res.end(JSON.stringify(hit.body));
  });
  await new Promise<void>((resolve) => stub.listen(0, "127.0.0.1", resolve));
  const addr = stub.address();
  const port = typeof addr === "object" && addr ? addr.port : 0;
  stubBase = `http://127.0.0.1:${port}`;
});

afterAll(async () => {
  await new Promise<void>((resolve) => stub.close(() => resolve()));
});

const freshIso = () => new Date().toISOString();
const oldIso = (msAgo: number) => new Date(Date.now() - msAgo).toISOString();

describe("fetch plumbing (#802)", () => {
  it("unknown layer 404s and bad bbox 400s (never 500-by-config)", async () => {
    setEnv({ POLE_BASE_URL: stubBase });
    const unknown = await getLayer("no-such-layer");
    expect(unknown.status).toBe(404);
    const bad = await GET(new Request(`http://test/api/layers/parks?minlon=1`), {
      params: { layer: "parks" },
    });
    expect(bad.status).toBe(400);
  });

  it("provenance vocabulary stays closed (snapshot|empty|stale, never demo/live)", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    try {
      setEnv({
        HF_SNAPSHOT_DIR: dir,
        SENSCOM_SNAPSHOT_PATH: join(dir, "nope.json"),
        OOKLA_SNAPSHOT_PATH: join(dir, "nope.json"),
        OUTAGE_SNAPSHOT_PATH: join(dir, "nope.json"),
        SHED_CACHE_DIR: join(dir, "sheds"),
        INCIDENTS_CACHE_DIR: join(dir, "incidents"),
        POLE_BASE_URL: "http://127.0.0.1:9",
      });
      const seen = new Set<string>();
      for (const id of ["asumedia", "accblack", "medre_gp", "sport_hall", "floodzone", "shed-15-peak"]) {
        const { status, body } = await getLayer(id);
        expect(status).toBe(200);
        if (typeof body.provenance === "string") seen.add(body.provenance);
      }
      for (const p of seen) expect(["snapshot", "empty", "stale"]).toContain(p);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("honest-empty without fixtures (#802)", () => {
  it("asumedia / accblack / medre serve 200-empty, never 500 and never demo", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    try {
      setEnv({
        HF_SNAPSHOT_DIR: dir,
        POLE_BASE_URL: "http://127.0.0.1:9",
        INCIDENTS_CACHE_DIR: join(dir, "incidents"),
      });
      for (const id of ["asumedia", "accblack", "medre_gp", "sport_hall", "paaste"]) {
        const { status, body } = await getLayer(id);
        if (id === "paaste") {
          // Generic-snapshot family: no points file and no raster in an
          // empty snapshot reads 500 -> the client's labeled verdict
          // (paasteDemoStatus names EI OLE + rescue.ee check, pinned in
          // layers_p4_honest_empty.test.ts) — the 500 names the layer.
          expect(status).toBe(500);
          expect(String((body as { error?: unknown }).error)).toContain("paaste");
          continue;
        }
        expect(status).toBe(200);
        expect(pointsOf(body)).toEqual([]);
        expect(body.provenance).toBe("empty");
      }
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("polygons-only floodzone answers 200 on snapshot provenance (sidecar carries data)", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    try {
      setEnv({ HF_SNAPSHOT_DIR: dir, POLE_BASE_URL: "http://127.0.0.1:9" });
      const { status, body } = await getLayer("floodzone");
      expect(status).toBe(200);
      expect(pointsOf(body)).toEqual([]);
      expect(body.provenance).toBe("snapshot");
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("missing extracts read 500-with-reason, never silent (#802)", () => {
  it("senscom / ookla / parks name the missing piece", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    try {
      setEnv({
        HF_SNAPSHOT_DIR: dir,
        SENSCOM_SNAPSHOT_PATH: join(dir, "nope.json"),
        OOKLA_SNAPSHOT_PATH: join(dir, "nope.json"),
        POLE_BASE_URL: "http://127.0.0.1:9",
      });
      for (const [id, needle] of [
        ["senscom", "senscom"],
        ["ookla_fixed", "ookla"],
        ["parks", "parks"],
      ] as const) {
        const { status, body } = await getLayer(id);
        expect(status).toBe(500);
        expect(String((body as { error?: unknown }).error)).toContain(needle);
      }
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("extract positives serve 200-with-data (#802)", () => {
  it("senscom + ookla fixtures plot (present with data)", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    try {
      const sensPath = join(dir, "senscom.json");
      await writeFile(
        sensPath,
        JSON.stringify({ fetched: "2026-09-14", sensors: [{ lat: 59.44, lon: 24.75 }] }),
      );
      const ooklaPath = join(dir, "ookla.json");
      await writeFile(
        ooklaPath,
        JSON.stringify({
          quarter: "2026Q1",
          fixed: [{ tile_x: 24.75, tile_y: 59.44, avg_d_kbps: 50000, tests: 12 }],
          mobile: [],
        }),
      );
      setEnv({
        HF_SNAPSHOT_DIR: dir,
        SENSCOM_SNAPSHOT_PATH: sensPath,
        OOKLA_SNAPSHOT_PATH: ooklaPath,
        POLE_BASE_URL: "http://127.0.0.1:9",
      });
      const sens = await getLayer("senscom");
      expect(sens.status).toBe(200);
      expect(pointsOf(sens.body)).toHaveLength(1);
      expect(sens.body.provenance).toBe("snapshot");
      const ookla = await getLayer("ookla_fixed");
      expect(ookla.status).toBe(200);
      expect(pointsOf(ookla.body)).toHaveLength(1);
      expect(ookla.body.provenance).toBe("snapshot");
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("pole-first datex TTL + fallback (#802)", () => {
  it("fresh pole table serves snapshot; stale reads 500, never fake-live", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    try {
      setEnv({
        HF_SNAPSHOT_DIR: dir,
        POLE_BASE_URL: stubBase,
        INCIDENTS_CACHE_DIR: join(dir, "incidents"),
      });
      stubTables.set("datex-weather", {
        status: 200,
        body: { rows: [{ lat: 59.44, lon: 24.75 }] },
        builtAt: freshIso(),
      });
      const fresh = await getLayer("datex-weather");
      expect(fresh.status).toBe(200);
      expect(pointsOf(fresh.body)).toHaveLength(1);
      expect(fresh.body.provenance).toBe("snapshot");
      expect(Number.isFinite(fresh.body.ageMs)).toBe(true);
      // Stale past the 1h TTL: gap, never served as live.
      stubTables.set("datex-weather", {
        status: 200,
        body: { rows: [{ lat: 59.44, lon: 24.75 }] },
        builtAt: oldIso(2 * 3600 * 1000),
      });
      const stale = await getLayer("datex-weather");
      expect(stale.status).toBe(500);
      expect(String((stale.body as { error?: unknown }).error)).toContain("datex-weather");
    } finally {
      stubTables.delete("datex-weather");
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("geometry-less restrictions answer liveness-gated empty when the pole is up", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    try {
      setEnv({ HF_SNAPSHOT_DIR: dir, POLE_BASE_URL: stubBase });
      stubTables.set("datex-restrictions", {
        status: 200,
        body: { rows: [{ id: "r1" }] },
        builtAt: freshIso(),
      });
      const { status, body } = await getLayer("datex-restrictions");
      expect(status).toBe(200);
      expect(pointsOf(body)).toEqual([]);
      expect(body.provenance).toBe("empty");
    } finally {
      stubTables.delete("datex-restrictions");
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("incidents pole-first + cache fallback (#802)", () => {
  const poleBody = { incidents: [{ magnitude: 3, points: [[59.44, 24.75]] }] };
  const cacheBody = {
    incidents: [{ properties: { magnitudeOfDelay: 2 }, geometry: { coordinates: [[24.75, 59.44]] } }],
  };

  it("pole wins when fresh; cache serves when the pole is down; both down reads 500", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    const cacheDir = join(dir, "incidents");
    try {
      const { mkdir } = await import("node:fs/promises");
      await mkdir(cacheDir, { recursive: true });
      await writeFile(join(cacheDir, INCIDENTS_CACHE_FILE), JSON.stringify(cacheBody));
      // Pole fresh: pole leg serves, cache ignored.
      stubTables.set("incidents", { status: 200, body: poleBody, builtAt: freshIso() });
      setEnv({ HF_SNAPSHOT_DIR: dir, POLE_BASE_URL: stubBase, INCIDENTS_CACHE_DIR: cacheDir });
      const viaPole = await getLayer("incidents");
      expect(viaPole.status).toBe(200);
      expect(pointsOf(viaPole.body)).toHaveLength(1);
      expect(viaPole.body.provenance).toBe("snapshot");
      expect(viaPole.body.source).toBe("pole");
      // Pole down: operator cache fallback serves, labeled cache.
      setEnv({ HF_SNAPSHOT_DIR: dir, POLE_BASE_URL: "http://127.0.0.1:9", INCIDENTS_CACHE_DIR: cacheDir });
      const viaCache = await getLayer("incidents");
      expect(viaCache.status).toBe(200);
      expect(pointsOf(viaCache.body)).toHaveLength(1);
      expect(viaCache.body.source).toBe("cache");
      // Both down: 500-with-reason -> labeled demo, never silent.
      await rm(join(cacheDir, INCIDENTS_CACHE_FILE), { force: true });
      const down = await getLayer("incidents");
      expect(down.status).toBe(500);
      expect(String((down.body as { error?: unknown }).error)).toContain("incidents");
    } finally {
      stubTables.delete("incidents");
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("stale cache serves the stale provenance (visible age, never as live)", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    const cacheDir = join(dir, "incidents");
    try {
      const { mkdir } = await import("node:fs/promises");
      await mkdir(cacheDir, { recursive: true });
      const file = join(cacheDir, INCIDENTS_CACHE_FILE);
      await writeFile(file, JSON.stringify(cacheBody));
      const ancient = new Date(Date.now() - 10 * 3600 * 1000);
      await utimes(file, ancient, ancient);
      setEnv({ HF_SNAPSHOT_DIR: dir, POLE_BASE_URL: "http://127.0.0.1:9", INCIDENTS_CACHE_DIR: cacheDir });
      const { status, body } = await getLayer("incidents");
      expect(status).toBe(200);
      expect(body.provenance).toBe("stale");
      expect(Number.isFinite(body.ageMs)).toBe(true);
      expect((body.ageMs as number)).toBeGreaterThan(6 * 3600 * 1000);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("outage pole-first + sidecar fallback (#802)", () => {
  const tallinnRow = {
    label: "Tallinn",
    fc: 0, fcc: 0, pc: 0, pcc: 0, uc: 0, ucc: 0,
  };

  it("fresh pole serves the city point; stale reads 500, never a faked calm", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    try {
      setEnv({
        HF_SNAPSHOT_DIR: dir,
        POLE_BASE_URL: stubBase,
        OUTAGE_SNAPSHOT_PATH: join(dir, "nope.json"),
      });
      stubTables.set("outage", {
        status: 200,
        body: { pulled_at: freshIso(), areas: [tallinnRow] },
        builtAt: freshIso(),
      });
      const fresh = await getLayer("outage");
      expect(fresh.status).toBe(200);
      expect(pointsOf(fresh.body)).toHaveLength(1);
      expect(fresh.body.provenance).toBe("snapshot");
      // Stale past the 5-min TTL with no sidecar: gap, never served.
      stubTables.set("outage", {
        status: 200,
        body: { pulled_at: oldIso(10 * 60 * 1000), areas: [tallinnRow] },
        builtAt: freshIso(),
      });
      const stale = await getLayer("outage");
      expect(stale.status).toBe(500);
      expect(String((stale.body as { error?: unknown }).error)).toContain("outage");
    } finally {
      stubTables.delete("outage");
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("pole down + fresh sidecar serves (fallback), pole down + stale sidecar 500s", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    try {
      const sidecar = join(dir, "outage-table.json");
      await writeFile(
        sidecar,
        JSON.stringify({ pulled_at: freshIso(), areas: [{ ...tallinnRow, uc: 27, ucc: 3169 }] }),
      );
      setEnv({
        HF_SNAPSHOT_DIR: dir,
        POLE_BASE_URL: "http://127.0.0.1:9",
        OUTAGE_SNAPSHOT_PATH: sidecar,
      });
      const viaSidecar = await getLayer("outage");
      expect(viaSidecar.status).toBe(200);
      expect(pointsOf(viaSidecar.body)).toHaveLength(1);
      // Stale the sidecar past TTL: gap on both legs reads 500.
      await writeFile(
        sidecar,
        JSON.stringify({ pulled_at: oldIso(10 * 60 * 1000), areas: [tallinnRow] }),
      );
      // Bust the server-side snapshot mtime cache by pointing at a copy.
      const staleCopy = join(dir, "outage-stale.json");
      await writeFile(
        staleCopy,
        JSON.stringify({ pulled_at: oldIso(10 * 60 * 1000), areas: [tallinnRow] }),
      );
      setEnv({
        HF_SNAPSHOT_DIR: dir,
        POLE_BASE_URL: "http://127.0.0.1:9",
        OUTAGE_SNAPSHOT_PATH: staleCopy,
      });
      const stale = await getLayer("outage");
      expect(stale.status).toBe(500);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("sheds operator cache (#802)", () => {
  const ring = {
    reachableRange: {
      boundary: [
        { latitude: 59.44, longitude: 24.75 },
        { latitude: 59.45, longitude: 24.76 },
        { latitude: 59.46, longitude: 24.75 },
        { latitude: 59.44, longitude: 24.75 },
      ],
    },
  };

  it("missing cache reads honestly-empty (never demo polygons); fresh cache serves snapshot", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-802-"));
    const sheds = join(dir, "sheds");
    try {
      const { mkdir } = await import("node:fs/promises");
      await mkdir(sheds, { recursive: true });
      setEnv({ HF_SNAPSHOT_DIR: dir, POLE_BASE_URL: "http://127.0.0.1:9", SHED_CACHE_DIR: sheds });
      const missing = await getLayer("shed-15-peak");
      expect(missing.status).toBe(200);
      expect(pointsOf(missing.body)).toEqual([]);
      expect(missing.body.provenance).toBe("empty");
      expect(missing.body.ageMs).toBeNull();
      await writeFile(join(sheds, SHED_CACHE_FILE("city-center", "900", "rush")), JSON.stringify(ring));
      const fresh = await getLayer("shed-15-peak");
      expect(fresh.status).toBe(200);
      expect(fresh.body.provenance).toBe("snapshot");
      expect(Number.isFinite(fresh.body.ageMs)).toBe(true);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("tallinn fixture guard (#802)", () => {
  it("the shared fixture point sits inside the test bbox", () => {
    expect(TALLINN.lat).toBeGreaterThan(59.3);
    expect(TALLINN.lat).toBeLessThan(59.6);
    expect(TALLINN.lon).toBeGreaterThan(24.5);
    expect(TALLINN.lon).toBeLessThan(25.0);
  });
});
