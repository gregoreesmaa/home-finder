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
  outageRowToArea,
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
});
