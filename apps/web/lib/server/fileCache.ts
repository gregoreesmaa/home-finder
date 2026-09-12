// Generic server-side query cache for parameter layers (and the other 497
// parameters to come): any caller supplies a string key, a TTL and an
// async loader. Only successful loads are written; upstream failures are
// never cached as data — a failed reload serves the stale entry (labeled)
// or throws so the caller can fall back to demo points.

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

export type CacheProvenance = "live" | "cache" | "stale";

export interface CachedResult<T> {
  data: T;
  provenance: CacheProvenance;
  ageMs: number;
}

interface CacheEntry<T> {
  at: number;
  data: T;
}

// Flat filenames only: no slashes, no parent refs, must start
// alphanumerically. Commas are allowed (bbox in layer keys) — they are
// filename-safe everywhere and never traverse.
const SAFE_KEY = /^[A-Za-z0-9][A-Za-z0-9:_.,-]*$/;

/** In-flight loads, so concurrent misses share one upstream request. */
const inflight = new Map<string, Promise<CachedResult<unknown>>>();

export async function cachedQuery<T>(args: {
  cacheDir: string;
  key: string;
  ttlMs: number;
  load: () => Promise<T>;
}): Promise<CachedResult<T>> {
  const { cacheDir, key, ttlMs, load } = args;
  if (!SAFE_KEY.test(key) || key.includes("..")) {
    throw new Error(`unsafe cache key: ${key}`);
  }
  await mkdir(cacheDir, { recursive: true });
  const path = join(cacheDir, `${key}.json`);

  const readEntry = async (): Promise<CacheEntry<T> | null> => {
    try {
      const entry = JSON.parse(await readFile(path, "utf8")) as Partial<CacheEntry<T>>;
      if (typeof entry?.at !== "number" || !("data" in (entry as object))) return null;
      return entry as CacheEntry<T>;
    } catch {
      return null;
    }
  };

  const now = Date.now();
  const cached = await readEntry();
  if (cached && now - cached.at <= ttlMs) {
    return { data: cached.data, provenance: "cache", ageMs: now - cached.at };
  }

  const running = inflight.get(path);
  if (running) return running as Promise<CachedResult<T>>;

  const task: Promise<CachedResult<T>> = (async () => {
    try {
      const data = await load();
      await writeFile(path, JSON.stringify({ at: Date.now(), data }), "utf8");
      return { data, provenance: "live" as const, ageMs: 0 };
    } catch (err) {
      // Upstream died (429 stop-signal, timeout, …): serve stale truth
      // over demo fiction; throw only when nothing was ever cached.
      const stale = await readEntry();
      if (stale) {
        return { data: stale.data, provenance: "stale" as const, ageMs: Date.now() - stale.at };
      }
      throw err;
    } finally {
      inflight.delete(path);
    }
  })();
  inflight.set(path, task as Promise<CachedResult<unknown>>);
  return task;
}
