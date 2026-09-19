// Hermetic tests for the outage sidecar loader (issue #729). No
// network: temp files only, never the real /tmp/hf-outage tree. The
// fixture repeats the live SHAPE with the observed 2026-09-19
// Tallinn counters (facts, tiny); staleness is pinned against an
// injected clock (no time dependence).

import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  OUTAGE_SNAPSHOT_NAME,
  loadOutageSnapshot,
  outageCacheDir,
  outagePointsIn,
  outageReliabilityAreaToTallinn,
  outageReliabilityFromBody,
  outageRowToArea,
  outageSnapshotFromBody,
  outageSnapshotPath,
  outageSnapshotToPoint,
} from "./outage";

let dirs: string[] = [];
afterEach(async () => {
  for (const d of dirs) await rm(d, { recursive: true, force: true });
  dirs = [];
});

async function fixtureFile(body: unknown): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "hf-outage-"));
  dirs.push(dir);
  const file = join(dir, OUTAGE_SNAPSHOT_NAME);
  await writeFile(file, typeof body === "string" ? body : JSON.stringify(body));
  return file;
}

const NOW = Date.parse("2026-09-19T15:30:00Z");

/** Live-shaped sidecar (observed Tallinn row, fresh stamp). */
function freshSidecar(pulledAt = "2026-09-19T15:29:00Z") {
  return {
    pulled_at: pulledAt,
    ttl_s: 300,
    areas: [
      { cid: 7639, fc: 0, fcc: 0, id: 454883598, label: "Tallinn", pc: 0, pcc: 0, uc: 27, ucc: 3169 },
      { cid: 7638, fc: 0, fcc: 0, id: 454746528, label: "Harju maakond", pc: 0, pcc: 0, uc: 96, ucc: 5766 },
    ],
    n_dynareas: 0,
    outage_tallies: { u: 514, f: 1, p: 1 },
  };
}

const TALLINN_BBOX = { minlon: 24.5, maxlon: 25.0, minlat: 59.3, maxlat: 59.6 };

describe("outage loader", () => {
  it("serves the fresh Tallinn row as a city point", async () => {
    const snap = await loadOutageSnapshot(await fixtureFile(freshSidecar()), NOW);
    expect(snap?.tallinn.label).toBe("Tallinn");
    const pt = outageSnapshotToPoint(snap!);
    expect(pt?.q).toBe(70);
    expect(pt?.tags?.uc).toBe("27");
    expect(pt?.tags?.ucc).toBe("3169");
    expect(outagePointsIn(snap!, TALLINN_BBOX)).toHaveLength(1);
  });

  it("returns null when stale, Tallinn-less, corrupt or missing", async () => {
    const stale = await loadOutageSnapshot(
      await fixtureFile(freshSidecar("2026-09-19T15:20:00Z")),
      NOW,
    );
    expect(stale).toBeNull();
    const noTallinn = freshSidecar();
    noTallinn.areas = noTallinn.areas.filter((a) => a.label !== "Tallinn");
    expect(await loadOutageSnapshot(await fixtureFile(noTallinn), NOW)).toBeNull();
    expect(await loadOutageSnapshot(await fixtureFile("{not json"), NOW)).toBeNull();
    expect(await loadOutageSnapshot(join(tmpdir(), "hf-outage-nope", OUTAGE_SNAPSHOT_NAME), NOW)).toBeNull();
  });

  it("clips the city point to the view bbox", async () => {
    const snap = await loadOutageSnapshot(await fixtureFile(freshSidecar()), NOW);
    expect(outagePointsIn(snap!, { minlon: 26, maxlon: 27, minlat: 58, maxlat: 59 })).toEqual([]);
  });

  it("skips labelless rows, never fakes a region", () => {
    expect(outageRowToArea({ fc: 1 })).toBeNull();
    expect(outageRowToArea(null)).toBeNull();
    expect(outageRowToArea({ label: "Tallinn", uc: 27 })?.uc).toBe(27);
  });

  it("keeps cache-dir defaults greppable", () => {
    expect(outageCacheDir()).toContain("hf-outage");
    expect(OUTAGE_SNAPSHOT_NAME).toBe("outage-table.json");
    expect(outageSnapshotPath()).toContain(OUTAGE_SNAPSHOT_NAME);
  });

  it("validates pole-table bodies through the same pure parser (#775)", () => {
    // The pole serves the same sidecar shape plus envelope extras;
    // extras ride along ignored, the Tallinn row still resolves.
    const poleBody = {
      ...freshSidecar(),
      source: "https://rikkekaart.elektrilevi.ee/geoserver-api/GetApplicationData",
    };
    const snap = outageSnapshotFromBody(poleBody, NOW);
    expect(snap?.tallinn.label).toBe("Tallinn");
    expect(outageSnapshotToPoint(snap!)?.q).toBe(70);
    expect(outagePointsIn(snap!, TALLINN_BBOX)).toHaveLength(1);
  });

  it("rejects stale, Tallinn-less and non-object pole bodies (#775)", () => {
    expect(outageSnapshotFromBody(freshSidecar("2026-09-19T15:20:00Z"), NOW)).toBeNull();
    const noTallinn = freshSidecar();
    noTallinn.areas = [];
    expect(outageSnapshotFromBody(noTallinn, NOW)).toBeNull();
    expect(outageSnapshotFromBody(null, NOW)).toBeNull();
    expect(outageSnapshotFromBody([1, 2], NOW)).toBeNull();
    expect(outageSnapshotFromBody("ok: DATEX voog", NOW)).toBeNull();
    expect(outageSnapshotFromBody({ pulled_at: "not-a-date", areas: [] }, NOW)).toBeNull();
  });
});

describe("outage reliability (#780)", () => {
  const REL_NOW = Date.parse("2026-09-20T12:00:00Z");

  /** Served reliability-table shape (pole `outage-reliability`). */
  function freshReliability(builtAt = "2026-09-20T11:55:00Z", windowDays = 28) {
    return {
      built_at: builtAt,
      window_days: windowDays,
      metric: "vaadeldud töökindlus",
      expected_pulls_per_day: 288,
      n_obs_total: 100,
      areas: {
        Tallinn: {
          n_obs: 100, fault_obs: 3, planned_obs: 5, upcoming_obs: 40,
          fault_customers: 210, planned_customers: 90, coverage: 0.0124,
        },
      },
    };
  }

  it("serves the fresh Tallinn window with its aggregates", () => {
    const rel = outageReliabilityFromBody(freshReliability(), REL_NOW);
    expect(rel?.windowDays).toBe(28);
    expect(rel?.tallinn.faultObs).toBe(3);
    expect(rel?.tallinn.plannedObs).toBe(5);
    expect(rel?.tallinn.faultCustomers).toBe(210);
    expect(rel?.nObsTotal).toBe(100);
  });

  it("falls back to the Tallinn row count when the total is unshaped", () => {
    const body = freshReliability();
    delete (body as Record<string, unknown>).n_obs_total;
    expect(outageReliabilityFromBody(body, REL_NOW)?.nObsTotal).toBe(100);
  });

  it("returns null when stale, wrong-window, Tallinn-less or corrupt", () => {
    // Older than the 1-day reliability TTL: a gap, never data.
    expect(outageReliabilityFromBody(
      freshReliability("2026-09-19T11:00:00Z"), REL_NOW)).toBeNull();
    // A build for another window is never served as the 28-day one.
    expect(outageReliabilityFromBody(freshReliability("2026-09-20T11:55:00Z", 7), REL_NOW)).toBeNull();
    const noTallinn = freshReliability();
    (noTallinn as { areas: Record<string, unknown> }).areas = {};
    expect(outageReliabilityFromBody(noTallinn, REL_NOW)).toBeNull();
    expect(outageReliabilityFromBody(null, REL_NOW)).toBeNull();
    expect(outageReliabilityFromBody([1, 2], REL_NOW)).toBeNull();
    expect(outageReliabilityFromBody({ built_at: "not-a-date" }, REL_NOW)).toBeNull();
  });

  it("rejects unshaped Tallinn aggregates, never fakes a window", () => {
    expect(outageReliabilityAreaToTallinn({ n_obs: 1 })).toBeNull();
    expect(outageReliabilityAreaToTallinn(null)).toBeNull();
    expect(outageReliabilityAreaToTallinn({
      n_obs: 100, fault_obs: 3, planned_obs: 5, upcoming_obs: 40,
      fault_customers: 210, planned_customers: 90, coverage: 0.0124,
    })).toEqual({
      nObs: 100, faultObs: 3, plannedObs: 5, upcomingObs: 40,
      faultCustomers: 210, plannedCustomers: 90, coverage: 0.0124,
    });
  });
});
