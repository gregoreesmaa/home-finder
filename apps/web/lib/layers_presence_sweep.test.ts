// Live presence sweep (issue #802): every servable layer endpoint present
// with data against compose (pole-backed) — 200-with-data or
// honest-empty-with-reason per layer. Demo-by-outage and 500s fail.
//
// EXPLICITLY-FLAGGED INTEGRATION, NEVER UNIT (AGENTS.md section 7
// hermetic default): this file skips unless HF_PRESENCE_SWEEP=1, so
// `npm test` stays hermetic. Run against compose:
//
//   docker compose up --build            # web :3000, pole via tunnel
//   HF_PRESENCE_SWEEP=1 HF_SWEEP_BASE=http://localhost:3000 \
//     ../../node_modules/.bin/vitest run lib/layers_presence_sweep.test.ts
//
// Contract per layer id (GET /api/layers/<id>?<tallinn bbox>):
// - 200 + points[] + provenance in {snapshot, empty, stale}.
// - points > 0            -> data (serving).
// - empty + empty/stale   -> honest-empty (named reason via provenance).
// - empty + snapshot      -> sidecar-backed (polygons-only / taste-only
//   layers whose bytes ride the areas sidecars, covered by their own
//   module tests — recorded, never flagged).
// - anything else (non-200, error body, provenance demo/live, missing
//   points array) FAILS the sweep: a 500 here is demo-by-outage on the
//   map (the client falls back to labeled demo points).
//
// Pole datasets are swept in pole/tests/test_presence_sweep.py (same
// flag); areas sidecars stay with their per-layer module tests.

import { describe, expect, it } from "vitest";
import { LAYERS } from "./layers";

const RUN = process.env.HF_PRESENCE_SWEEP === "1";
const BASE = process.env.HF_SWEEP_BASE ?? "http://localhost:3000";
const BBOX = "minlon=24.5&minlat=59.3&maxlon=25.0&maxlat=59.6";

const OK_PROVENANCE = new Set(["snapshot", "empty", "stale"]);

interface Row {
  id: string;
  status: number;
  verdict: string;
  detail: string;
}

async function sweepOne(id: string): Promise<Row> {
  const url = `${BASE}/api/layers/${id}?${BBOX}`;
  let res: Response;
  try {
    res = await fetch(url, { signal: AbortSignal.timeout(20000) });
  } catch (e) {
    return { id, status: -1, verdict: "FAIL", detail: `transport: ${String(e).slice(0, 120)}` };
  }
  if (res.status !== 200) {
    let hint: string;
    try {
      hint = JSON.stringify(await res.json()).slice(0, 160);
    } catch {
      hint = "(unparseable body)";
    }
    return { id, status: res.status, verdict: "FAIL", detail: `HTTP ${res.status} ${hint}` };
  }
  const body = (await res.json()) as Record<string, unknown>;
  if (typeof body !== "object" || body === null || !Array.isArray(body.points)) {
    return { id, status: 200, verdict: "FAIL", detail: "200 without a points array" };
  }
  if (typeof body.provenance !== "string" || !OK_PROVENANCE.has(body.provenance)) {
    return {
      id, status: 200, verdict: "FAIL",
      detail: `unlabeled provenance ${JSON.stringify(body.provenance)} (demo-by-outage until labeled)`,
    };
  }
  if ((body as { error?: unknown }).error !== undefined) {
    return { id, status: 200, verdict: "FAIL", detail: `200 carrying error ${JSON.stringify(body.error).slice(0, 120)}` };
  }
  const n = (body.points as unknown[]).length;
  if (n > 0) return { id, status: 200, verdict: "data", detail: `${n} points, ${body.provenance}` };
  if (body.provenance === "snapshot") {
    return { id, status: 200, verdict: "sidecar-backed", detail: "points [] on snapshot provenance (areas sidecar carries data)" };
  }
  return { id, status: 200, verdict: "honest-empty", detail: `points [], provenance ${body.provenance}` };
}

describe.skipIf(!RUN)("live presence sweep (#802, HF_PRESENCE_SWEEP=1)", () => {
  it("every layer serves 200-with-data or honest-empty-with-reason", async () => {
    const rows: Row[] = [];
    for (const l of LAYERS) {
      rows.push(await sweepOne(l.id));
    }
    const fails = rows.filter((r) => r.verdict === "FAIL");
    const data = rows.filter((r) => r.verdict === "data").length;
    const empty = rows.filter((r) => r.verdict === "honest-empty").length;
    const sidecar = rows.filter((r) => r.verdict === "sidecar-backed").length;
    const table = ["id | status | verdict | detail", "--- | --- | --- | ---"];
    for (const r of rows) table.push(`${r.id} | ${r.status} | ${r.verdict} | ${r.detail}`);
    console.log(`\npresence sweep vs ${BASE} (${rows.length} layers):\n${table.join("\n")}\nsummary: ${data} data, ${empty} honest-empty, ${sidecar} sidecar-backed, ${fails.length} FAIL`);
    expect(fails).toEqual([]);
  }, 300000);
});
