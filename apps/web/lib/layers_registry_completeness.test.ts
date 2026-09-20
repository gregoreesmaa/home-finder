// Registry-completeness gate (issue #802): every layer present with data.
//
// Every id in LAYERS must resolve to three things:
//   1. a def (unique id, human copy, param + fallback shape),
//   2. a fetch path (one serving family: operator-cache / pole-live /
//      dedicated-snapshot / silly-demo / generic-snapshot-file — the same
//      families the /api/layers/[layer] route branches on), and
//   3. at least one covering test file (same-basename module test).
//
// A new layer with no fetch-path test fails this suite: the id->module
// scan below is dynamic (import.meta.glob over ./layers_*.ts), so a new
// module contributes ids that must have a same-basename test, and a new
// id in LAYERS that matches no known module fails loudly.
//
// Hermetic: registry + glob + a repo-text read of pole/api.py only.
// No network, no snapshot, no pole. Fixtures only (AGENTS.md section 5).

/// <reference types="vite/client" />
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { LAYERS, type LayerId } from "./layers";
import { isOutageLayerId, OUTAGE_POLE_DATASET, OUTAGE_RELIABILITY_POLE_DATASET, OUTAGE_TTL_S } from "./layers_p4_outage";
import { isShedLayerId, SHED_LAYER_IDS } from "./layers_p4_tomtom_sheds";
import { SHED_POLE_DATASET, SHED_TTL_S } from "./server/sheds";
import { DATEX_LAYER_IDS, DATEX_POLE_DATASET, DATEX_TTL_S, isDatexLayerId } from "./layers_datex";
import { INCIDENTS_CACHE_FILE, INCIDENTS_POLE_DATASET, INCIDENTS_TTL_S, isIncidentsLayerId } from "./layers_p4_incidents";
import { isSenscomLayerId } from "./layers_p4_senscom";
import { isTerviseLayerId } from "./layers_tervise";
import { isViirsLayerId } from "./layers_p4_viirs";
import { isFloodLayerId } from "./layers_flood";
import { isEelisLayerId } from "./layers_eelis";
import { isMaaParcelLayerId } from "./layers_maaparcel";
import { isSevesoLayerId } from "./layers_p4_seveso";
import { isDelayLayerId } from "./layers_p4_delay";
import { isStatelandLayerId } from "./layers_p4_stateland";
import { isSoilLayerId } from "./layers_p4_soil";
import { isQuarryLayerId } from "./layers_p4_quarry";
import { isMaaparandusLayerId } from "./layers_p4_maaparandus";
import { isEtakLayerId } from "./layers_p4_etak";
import { isReliefLayerId } from "./layers_p4_relief";
import { isCanopyLayerId } from "./layers_p4_canopy";
import { isBuildingsLayerId } from "./layers_p4_buildings";
import { isDensityLayerId } from "./layers_p4_density";
import { isForestLayerId } from "./layers_p4_forest";
import { isHarbourLayerId } from "./layers_p4_harbour";
import { isKpoLayerId } from "./layers_p4_kpo";
import { isNoiseLayerId } from "./layers_p4_noise";
import { isOoklaLayerId } from "./layers_p4_ookla";
import { isSportLayerId } from "./layers_p4_sport";
import { isEhisLayerId } from "./layers_p4_ehis";
import { isMedreLayerId } from "./layers_p4_medre";
import { isOhuseireLayerId } from "./layers_p4_ohuseire";
import { isKliimaLayerId } from "./layers_kliima";
import { isPoiLayerId } from "./layers_p4_poi";
import { isFixitLayerId } from "./layers_p4_fixit";
import { isAccBlackLayerId } from "./layers_accblack";
import { isAsumediaLayerId } from "./layers_asumedia";
import { SILLY_LAYER_IDS } from "./layers_p4_silly";

type Family =
  | "operator-cache"
  | "pole-live"
  | "dedicated-snapshot"
  | "silly-demo"
  | "generic-snapshot-file";

const OPERATOR_CACHE = [isOutageLayerId, isShedLayerId, isIncidentsLayerId];
const POLE_LIVE = [isDatexLayerId];
const DEDICATED_SNAPSHOT = [
  isSenscomLayerId,
  isTerviseLayerId,
  isViirsLayerId,
  isFloodLayerId,
  isEelisLayerId,
  isMaaParcelLayerId,
  isSevesoLayerId,
  isDelayLayerId,
  isStatelandLayerId,
  isSoilLayerId,
  isQuarryLayerId,
  isMaaparandusLayerId,
  isEtakLayerId,
  isReliefLayerId,
  isCanopyLayerId,
  isBuildingsLayerId,
  isDensityLayerId,
  isForestLayerId,
  isHarbourLayerId,
  isKpoLayerId,
  isNoiseLayerId,
  isOoklaLayerId,
  isSportLayerId,
  isEhisLayerId,
  isMedreLayerId,
  isOhuseireLayerId,
  isKliimaLayerId,
  isPoiLayerId,
  isFixitLayerId,
  isAccBlackLayerId,
  isAsumediaLayerId,
];

function familyOf(id: LayerId): Family {
  const hits: Family[] = [];
  if (OPERATOR_CACHE.some((g) => g(id))) hits.push("operator-cache");
  if (POLE_LIVE.some((g) => g(id))) hits.push("pole-live");
  if (DEDICATED_SNAPSHOT.some((g) => g(id))) hits.push("dedicated-snapshot");
  if ((SILLY_LAYER_IDS as string[]).includes(id)) hits.push("silly-demo");
  if (hits.length === 0) hits.push("generic-snapshot-file");
  return hits[0];
}

function familiesOf(id: LayerId): Family[] {
  const hits: Family[] = [];
  if (OPERATOR_CACHE.some((g) => g(id))) hits.push("operator-cache");
  if (POLE_LIVE.some((g) => g(id))) hits.push("pole-live");
  if (DEDICATED_SNAPSHOT.some((g) => g(id))) hits.push("dedicated-snapshot");
  if ((SILLY_LAYER_IDS as string[]).includes(id)) hits.push("silly-demo");
  if (hits.length === 0) hits.push("generic-snapshot-file");
  return hits;
}

/** Core ids defined inline in layers.ts (no owning layers_*.ts module). */
const CORE_IDS = [
  "parks",
  "transit",
  "schools",
  "walkability",
  "pedinfra",
  "cycling",
  "grocery",
  "healthcare",
];

/**
 * Dynamic id -> owning-module scan. Every ./layers_*.ts module is loaded
 * (source only — test files excluded by the negative pattern) and two
 * export shapes are collected:
 * - string[] exports ending in IDS / LAYER_IDS (SILLY_LAYER_IDS, ...), and
 * - def-array exports ending in DEFS / LAYERS / LAYER_DEFS whose items
 *   carry a string .id (BATCH5_DEFS, SPORT_LAYERS, SHED_LAYER_DEFS, ...).
 */
const layerModules = import.meta.glob<Record<string, unknown>>(
  ["./layers_*.ts", "!./layers_*.test.ts"],
  { eager: true },
);

const testFiles = import.meta.glob(["./layers_*.test.ts", "./layers.test.ts"]);

function moduleBasename(path: string): string {
  const file = path.split("/").pop() ?? path;
  return file.replace(/\.ts$/, "");
}

function idsOfModule(ns: Record<string, unknown>): string[] {
  const ids: string[] = [];
  for (const [key, value] of Object.entries(ns)) {
    if (!Array.isArray(value)) continue;
    if (/(^|_)IDS$/.test(key) || /LAYER_IDS$/.test(key)) {
      for (const v of value) if (typeof v === "string") ids.push(v);
      continue;
    }
    if (/(_DEFS|_LAYERS|_LAYER_DEFS)$/.test(key)) {
      for (const v of value) {
        if (typeof v === "object" && v !== null && typeof (v as { id?: unknown }).id === "string") {
          ids.push((v as { id: string }).id);
        }
      }
    }
  }
  return ids;
}

function idToModules(): Map<string, string[]> {
  const map = new Map<string, string[]>();
  for (const [path, value] of Object.entries(layerModules)) {
    const ns = value as Record<string, unknown>;
    const base = moduleBasename(path);
    for (const id of idsOfModule(ns)) {
      const hit = map.get(id) ?? [];
      hit.push(base);
      map.set(id, hit);
    }
  }
  return map;
}

function testBasenames(): Set<string> {
  return new Set(Object.keys(testFiles).map(moduleBasename));
}

/** Repo-text read of pole/api.py DATASETS keys (web<->pole contract). */
function poleDatasetKeys(): string[] {
  const here = dirname(fileURLToPath(import.meta.url));
  // apps/web/lib -> repo root is ../../.. ; pole/api.py lives there.
  const apiPath = resolve(here, "../../../pole/api.py");
  const body = readFileSync(apiPath, "utf8");
  const block = body.slice(body.indexOf("DATASETS = {"), body.indexOf("}\n\napp = "));
  const keys: string[] = [];
  for (const m of block.matchAll(/^\s*"([^"]+)"\s*:/gm)) keys.push(m[1]);
  return keys;
}

describe("registry completeness (#802)", () => {
  it("every LAYERS entry resolves to a well-shaped def", () => {
    expect(LAYERS.length).toBeGreaterThan(0);
    const seen = new Set<string>();
    const problems: string[] = [];
    for (const def of LAYERS) {
      if (typeof def.id !== "string" || def.id.length === 0) problems.push(`empty id`);
      if (seen.has(def.id)) problems.push(`duplicate id ${def.id}`);
      seen.add(def.id);
      for (const field of ["title", "goodLabel", "badLabel", "source"] as const) {
        if (typeof def[field] !== "string" || def[field].length === 0) {
          problems.push(`${def.id}: empty ${field}`);
        }
      }
      if (!Array.isArray(def.paramIds)) problems.push(`${def.id}: paramIds not an array`);
      if (!Array.isArray(def.fallbackPoints)) problems.push(`${def.id}: fallbackPoints not an array`);
      for (const p of def.fallbackPoints) {
        if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) {
          problems.push(`${def.id}: fallback point with non-finite coords`);
        }
      }
    }
    expect(problems).toEqual([]);
  });

  it("every id resolves to exactly one fetch path (serving family)", () => {
    const doubles: string[] = [];
    for (const l of LAYERS) {
      const fams = familiesOf(l.id);
      if (fams.length !== 1) doubles.push(`${l.id} (${fams.join("+") || "none"})`);
      expect(familyOf(l.id)).toBe(fams[0]);
    }
    expect(doubles).toEqual([]);
  });

  it("every id resolves to at least one covering test file", () => {
    const byId = idToModules();
    const tests = testBasenames();
    const missing: string[] = [];
    for (const l of LAYERS) {
      if (CORE_IDS.includes(l.id)) {
        if (!tests.has("layers.test")) missing.push(`${l.id} (core: layers.test.ts absent)`);
        continue;
      }
      const modules = byId.get(l.id) ?? [];
      if (modules.length === 0) {
        missing.push(`${l.id} (no owning layers_*.ts module exports this id)`);
        continue;
      }
      const covered = modules.filter((m) => tests.has(`${m}.test`));
      if (covered.length === 0) {
        missing.push(`${l.id} (modules ${modules.join(",")} have no same-basename test)`);
      }
    }
    expect(missing).toEqual([]);
  });

  it("live layers name a freshness TTL (stale is decidable, never fake-live)", () => {
    expect(OUTAGE_TTL_S).toBeGreaterThan(0);
    expect(INCIDENTS_TTL_S).toBeGreaterThan(0);
    expect(SHED_TTL_S).toBeGreaterThan(0);
    for (const id of DATEX_LAYER_IDS) {
      expect(DATEX_TTL_S[id]).toBeGreaterThan(0);
    }
    for (const l of LAYERS) {
      if (isOutageLayerId(l.id)) expect(OUTAGE_TTL_S).toBe(300);
      if (isIncidentsLayerId(l.id)) expect(INCIDENTS_TTL_S).toBe(6 * 3600);
      if (isShedLayerId(l.id)) expect(SHED_TTL_S).toBe(7 * 24 * 3600);
    }
    expect(SHED_LAYER_IDS.length).toBe(4);
    expect(INCIDENTS_CACHE_FILE.length).toBeGreaterThan(0);
  });

  it("web-referenced pole datasets all exist in pole/api.py", () => {
    const poleKeys = poleDatasetKeys();
    expect(poleKeys.length).toBeGreaterThan(0);
    const referenced = [
      OUTAGE_POLE_DATASET,
      OUTAGE_RELIABILITY_POLE_DATASET,
      INCIDENTS_POLE_DATASET,
      SHED_POLE_DATASET,
      ...DATEX_LAYER_IDS.map((id) => DATEX_POLE_DATASET[id]),
    ];
    const unknown = [...new Set(referenced)].filter((d) => !poleKeys.includes(d));
    expect(unknown).toEqual([]);
  });
});
