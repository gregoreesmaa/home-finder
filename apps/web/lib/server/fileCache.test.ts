import { mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it, onTestFinished, vi } from "vitest";
import { cachedQuery } from "./fileCache";

/** Fresh tmp dir per test, always cleaned up (even on failure). */
function freshDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "hf-cache-test-"));
  onTestFinished(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe("generic server file cache", () => {
  it("miss loads once and writes the entry", async () => {
    const dir = freshDir();
    const load = vi.fn().mockResolvedValue([1, 2]);
    const res = await cachedQuery({ cacheDir: dir, key: "k1", ttlMs: 60_000, load });
    expect(res).toMatchObject({ data: [1, 2], provenance: "live" });
    expect(load).toHaveBeenCalledTimes(1);
    expect(readdirSync(dir)).toHaveLength(1);
  });

  it("fresh hit serves cache without reloading", async () => {
    const dir = freshDir();
    const load = vi.fn().mockResolvedValue("v");
    await cachedQuery({ cacheDir: dir, key: "k", ttlMs: 60_000, load });
    const res = await cachedQuery({ cacheDir: dir, key: "k", ttlMs: 60_000, load });
    expect(res.provenance).toBe("cache");
    expect(res.data).toBe("v");
    expect(res.ageMs).toBeGreaterThanOrEqual(0);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("expired entry reloads", async () => {
    const dir = freshDir();
    const load = vi.fn().mockResolvedValue("v");
    await cachedQuery({ cacheDir: dir, key: "k", ttlMs: 20, load });
    await sleep(40);
    const res = await cachedQuery({ cacheDir: dir, key: "k", ttlMs: 20, load });
    expect(res.provenance).toBe("live");
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("failed reload serves stale cache with its age", async () => {
    const dir = freshDir();
    const load = vi.fn().mockResolvedValue("v");
    await cachedQuery({ cacheDir: dir, key: "k", ttlMs: 20, load });
    await sleep(40);
    load.mockRejectedValue(new Error("429 stop signal"));
    const res = await cachedQuery({ cacheDir: dir, key: "k", ttlMs: 20, load });
    expect(res.provenance).toBe("stale");
    expect(res.data).toBe("v");
    expect(res.ageMs).toBeGreaterThanOrEqual(20);
  });

  it("failure without any cache throws (caller falls back to demo)", async () => {
    const dir = freshDir();
    const load = vi.fn().mockRejectedValue(new Error("boom"));
    await expect(
      cachedQuery({ cacheDir: dir, key: "k", ttlMs: 60_000, load }),
    ).rejects.toThrow("boom");
    expect(readdirSync(dir)).toHaveLength(0); // failures are never cached
  });

  it("concurrent misses share one in-flight load", async () => {
    const dir = freshDir();
    let release!: (v: string) => void;
    const load = vi.fn().mockImplementation(
      () => new Promise<string>((r) => { release = r; }),
    );
    const a = cachedQuery({ cacheDir: dir, key: "k", ttlMs: 60_000, load });
    const b = cachedQuery({ cacheDir: dir, key: "k", ttlMs: 60_000, load });
    for (let i = 0; i < 100 && load.mock.calls.length === 0; i++) {
      await sleep(5); // loader starts after async fs hops; both callers queue first
    }
    release("shared");
    expect((await a).data).toBe("shared");
    expect((await b).data).toBe("shared");
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("accepts realistic layer keys with commas and version prefixes", async () => {
    const dir = freshDir();
    const load = vi.fn().mockResolvedValue("v");
    const res = await cachedQuery({
      cacheDir: dir,
      key: "overpass-v1:parks:24.50,59.35,24.90,59.50",
      ttlMs: 60_000,
      load,
    });
    expect(res.provenance).toBe("live");
    expect(readdirSync(dir)).toHaveLength(1);
  });

  it("rejects path-traversal keys", async () => {
    const dir = freshDir();
    const load = vi.fn();
    await expect(
      cachedQuery({ cacheDir: dir, key: "../evil", ttlMs: 60_000, load }),
    ).rejects.toThrow();
    expect(load).not.toHaveBeenCalled();
  });
});
