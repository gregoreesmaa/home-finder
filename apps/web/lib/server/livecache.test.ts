import { describe, expect, it, vi } from "vitest";
import {
  POLE_DEFAULT_URL,
  fetchPoleTable,
  poleBaseUrl,
  readOpCacheFile,
  readOpCacheTable,
} from "./livecache";
import { mkdtemp, rm, utimes, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

describe("livecache pole reads (#763)", () => {
  it("defaults to the LAN tunnel URL, env-overridable", () => {
    expect(POLE_DEFAULT_URL).toBe("http://127.0.0.1:18001");
    expect(poleBaseUrl({})).toBe(POLE_DEFAULT_URL);
    expect(poleBaseUrl({ POLE_BASE_URL: "http://pole:8001" })).toBe(
      "http://pole:8001",
    );
  });

  it("returns the table with the built-at freshness header", async () => {
    const body = { rows: [{ a: 1 }] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "2026-09-19T12:00:00+00:00" },
      json: async () => body,
    });
    const out = await fetchPoleTable("datex-weather", { fetchImpl });
    expect(out?.table).toEqual(body);
    expect(out?.builtAtMs).toBe(Date.parse("2026-09-19T12:00:00+00:00"));
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(String(fetchImpl.mock.calls[0][0])).toContain("/v1/datex-weather");
  });

  it("never throws: 503, 404, transport errors and junk all read null", async () => {
    const bad = { ok: false, status: 503 };
    expect(await fetchPoleTable("x", { fetchImpl: async () => bad as never })).toBeNull();
    const junk = {
      ok: true,
      headers: { get: () => null },
      json: async () => {
        throw new Error("not json");
      },
    };
    expect(await fetchPoleTable("x", { fetchImpl: async () => junk as never })).toBeNull();
    expect(
      await fetchPoleTable("x", {
        fetchImpl: async () => {
          throw new Error("conn refused");
        },
      }),
    ).toBeNull();
  });

  it("rejects non-object bodies (arrays/strings are never tables)", async () => {
    const arr = {
      ok: true,
      headers: { get: () => null },
      json: async () => [1, 2],
    };
    expect(await fetchPoleTable("x", { fetchImpl: async () => arr as never })).toBeNull();
  });
});

describe("livecache operator-cache reads (#763)", () => {
  it("reads a fresh cache file with its mtime as freshness", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-livecache-"));
    try {
      const file = join(dir, "t.json");
      await writeFile(file, JSON.stringify({ a: 1 }));
      const out = await readOpCacheTable(dir, "t.json", 3600, Date.now());
      expect(out?.table).toEqual({ a: 1 });
      expect(typeof out?.builtAtMs).toBe("number");
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("untimed reads ignore TTL (stale callers decide themselves)", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-livecache-"));
    try {
      const file = join(dir, "old.json");
      await writeFile(file, JSON.stringify({ a: 1 }));
      const ancient = new Date(1000);
      await utimes(file, ancient, ancient);
      const out = await readOpCacheFile(dir, "old.json");
      expect(out?.table).toEqual({ a: 1 });
      expect(out?.builtAtMs).toBe(1000);
      expect(await readOpCacheFile(dir, "nope.json")).toBeNull();
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("stale, missing and corrupt caches read null (never served)", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-livecache-"));
    try {
      expect(await readOpCacheTable(dir, "nope.json", 3600, Date.now())).toBeNull();
      const file = join(dir, "old.json");
      await writeFile(file, JSON.stringify({ a: 1 }));
      const ancient = new Date(1000);
      await utimes(file, ancient, ancient);
      expect(await readOpCacheTable(dir, "old.json", 3600, Date.now())).toBeNull();
      const bad = join(dir, "bad.json");
      await writeFile(bad, "{not json");
      expect(await readOpCacheTable(dir, "bad.json", 3600, Date.now())).toBeNull();
      const arr = join(dir, "arr.json");
      await writeFile(arr, "[1,2]");
      expect(await readOpCacheTable(dir, "arr.json", 3600, Date.now())).toBeNull();
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});
