import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { LAYERS } from "./layers";
import {
  AGGREGATE_LAYER_IDS,
  AGGREGATE_WINDOW_NOTE,
  CLASS_C_SOURCES,
  LAYER_TEMPORAL,
  POLE_REALTIME_LAYER_IDS,
  STATIC_LAYER_IDS,
} from "./layer_temporal";
// WINDOWED-HOOK (#783) sources of truth: every windowed class-A id
// must name its window in one of these (this test cross-checks).
import { DATEX_WINDOW_ET } from "./layers_datex";
import { SHED_WINDOW_ET } from "./layers_p4_tomtom_sheds";
import { INCIDENTS_WINDOW_ET } from "./layers_p4_incidents";
import {
  OUTAGE_RELIABILITY_WINDOW_DAYS,
  OUTAGE_WINDOW_ET,
} from "./layers_p4_outage";

const sorted = (xs: string[]) => [...xs].sort();

describe("layer temporal classes (#801: no realtime layers)", () => {
  it("classifies every layer exactly once (new layers fail here until classified)", () => {
    const registry = sorted(LAYERS.map((l) => l.id));
    const classified = sorted([
      ...AGGREGATE_LAYER_IDS,
      ...STATIC_LAYER_IDS,
      ...POLE_REALTIME_LAYER_IDS,
    ]);
    // Zero unclassified, zero extras, zero double-booked.
    expect(classified).toEqual(registry);
    expect(new Set(classified).size).toBe(classified.length);
    for (const l of LAYERS) {
      expect(LAYER_TEMPORAL[l.id]).toBeDefined();
    }
  });

  it("pins class C exactly (pole-aggregated realtime only)", () => {
    expect(sorted(POLE_REALTIME_LAYER_IDS)).toEqual(
      sorted([
        "delay-morning",
        "delay-midday",
        "delay-evening",
        "delay-offpeak",
        "delay-worst",
        "gbfs",
      ]),
    );
    // Every class-C member documents window + metric + source + status.
    for (const id of POLE_REALTIME_LAYER_IDS) {
      const src = CLASS_C_SOURCES[id];
      expect(src, `${id} needs a CLASS_C_SOURCES entry`).toBeDefined();
      for (const k of ["window", "metric", "source", "status"] as const) {
        expect(src?.[k]?.length, `${id}.${k}`).toBeGreaterThan(0);
      }
    }
    // First concrete consumer: bus locations -> congestion estimate.
    expect(CLASS_C_SOURCES["delay-morning"]?.status).toMatch(
      /bus locations -> congestion estimate/,
    );
  });

  it("pins the windowed class-A core (DATEX/sheds/incidents/outage)", () => {
    for (const id of [
      "datex-restrictions",
      "datex-srti",
      "datex-weather",
      "datex-counters",
      "datex-cameras",
      "datex-truckpark",
    ]) {
      expect(AGGREGATE_LAYER_IDS).toContain(id);
      expect(Object.keys(DATEX_WINDOW_ET)).toContain(id);
    }
    for (const id of [
      "shed-15-peak",
      "shed-15-offpeak",
      "shed-30-peak",
      "shed-30-offpeak",
    ]) {
      expect(AGGREGATE_LAYER_IDS).toContain(id);
    }
    expect(SHED_WINDOW_ET.length).toBeGreaterThan(0);
    expect(AGGREGATE_LAYER_IDS).toContain("incidents");
    expect(INCIDENTS_WINDOW_ET.length).toBeGreaterThan(0);
    expect(AGGREGATE_LAYER_IDS).toContain("outage");
    expect(OUTAGE_WINDOW_ET.length).toBeGreaterThan(0);
    expect(OUTAGE_RELIABILITY_WINDOW_DAYS).toBe(28);
    // Every class-A id carries an audit-trail window note.
    for (const id of AGGREGATE_LAYER_IDS) {
      expect(
        AGGREGATE_WINDOW_NOTE[id]?.length,
        `${id} needs an AGGREGATE_WINDOW_NOTE`,
      ).toBeGreaterThan(0);
    }
  });

  it("keeps schedule/snapshot layers in B (never realtime)", () => {
    // GTFS STATIC carries schedules, never occupancy: frequency and
    // transfer richness are vintaged snapshots, not observations.
    for (const id of [
      "parks",
      "grocery",
      "transit",
      "gtfsstops",
      "busmesh",
      "busmesh-sat",
      "busmesh-sun",
      "senscom",
      "ohuseire",
      "skis",
      "harno",
    ]) {
      expect(STATIC_LAYER_IDS).toContain(id);
    }
  });

  it("bans browser-direct live fetches (pole-only rule, AGENTS.md s9)", () => {
    // Browser-shipped sources may fetch same-origin /api/* and the
    // first-party scoring backend only. Live third-party pulls belong
    // on the pole (scripts/build + pole/harvesters). lib/server/ is
    // Next.js server code (Overpass proxy lives there) and *.test.ts
    // never ships, so both are out of scope by decision.
    const libRoot = new URL(".", import.meta.url).pathname;
    const roots = [
      libRoot,
      join(libRoot, "../components"),
      join(libRoot, "../app"),
    ];
    const banned = [
      /fetch\(\s*["'`]https?:\/\//,
      /fetch\(\s*[A-Z][A-Z0-9_]*\s*[,)]/,
      /new\s+EventSource\(/,
      /new\s+WebSocket\(/,
    ];
    const hits: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const p = join(dir, name);
        if (statSync(p).isDirectory()) {
          if (name === "server") continue;
          walk(p);
          continue;
        }
        if (!/\.(ts|tsx)$/.test(name) || name.endsWith(".test.ts")) continue;
        const body = readFileSync(p, "utf-8");
        banned.forEach((re, i) => {
          if (re.test(body)) hits.push(`${p} matches pattern ${i} (${re})`);
        });
        // OVERPASS_URL is defined in lib/layers.ts but consumed
        // server-side only (lib/server/overpass.ts) — a browser
        // import of it would be a direct live fetch path.
        if (p !== join(libRoot, "layers.ts") && body.includes("OVERPASS_URL")) {
          hits.push(`${p} references OVERPASS_URL outside lib/server`);
        }
      }
    };
    roots.forEach(walk);
    expect(hits).toEqual([]);
  });
});
