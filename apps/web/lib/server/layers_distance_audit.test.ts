// 808-HOOK (#808): regression tests for the walk-vs-bird-flight audit.
//
// * Every LAYERS id has an audit row (a new layer without a family fails).
// * No row uses the unclassified-id fallback (families stay exact).
// * The G07-family relabel: contract-passing masters report "euclidean"
//   (the label fix riding in this PR).
// * The audit map column agrees with loadLayerRaster on fixture masters.

import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { LAYERS, type LayerId } from "../layers";
import {
  auditRowFor,
  buildAuditTable,
  toMarkdownTable,
  type AuditVerdict,
} from "./layers_distance_audit";
import { clearSnapshotCache, loadLayerRaster, rasterDistanceLabel } from "./snapshot";

/** Self-contained fixture snapshot (never the real ~/hf-data tree). */
async function fixtureDir(points: unknown, layer = "parks"): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "hf-808-"));
  await mkdir(join(dir, "osm"), { recursive: true });
  await writeFile(join(dir, "osm", `derived-${layer}.json`), JSON.stringify(points));
  return dir;
}

const rasterDoc = (contract: { half?: number | null; sigma: number }) => ({
  cols: 2,
  rows: 2,
  bbox: { minlon: 24.0, minlat: 59.0, maxlon: 24.2, maxlat: 59.1 },
  step_m: 75,
  half: contract.half ?? null,
  sigma: contract.sigma,
  per: 0,
  cap: 0,
  unknown: 255,
  dtype: "uint8",
  data: Buffer.from([80, 255, 40, 60]).toString("base64"),
});

afterEach(async () => {
  clearSnapshotCache();
});

describe("808 distance audit table", () => {
  it("covers every LAYERS id exactly once, with valid verdicts", () => {
    const rows = buildAuditTable();
    expect(rows.map((r) => r.id).sort()).toEqual(LAYERS.map((l) => l.id).sort());
    const verdicts: AuditVerdict[] = ["reasonable", "change"];
    for (const r of rows) {
      expect(verdicts).toContain(r.verdict);
      expect(r.title.length).toBeGreaterThan(0);
      expect(r.rationale.length).toBeGreaterThan(40);
      expect(r.scorerRef.length).toBeGreaterThan(0);
      // Families stay exact: no id may fall through to the fallback row.
      expect(r.rationale).not.toContain("Unclassified id");
    }
  });

  it("marks exactly the G07 grid-Dijkstra family as change", () => {
    const changed = buildAuditTable()
      .filter((r) => r.verdict === "change")
      .map((r) => r.id)
      .sort();
    expect(changed).toEqual(
      ["agrifield", "agriland", "brownsoil", "industprox", "odorsrc", "oiltank", "vectorhabitat", "wildcorr"].sort(),
    );
    for (const id of changed) {
      expect(auditRowFor(id as LayerId).map).toBe("euclidean-raster");
      expect(rasterDistanceLabel(id as LayerId)).toBe("euclidean");
    }
  });

  it("keeps true walk-graph families on the walk label", () => {
    for (const id of ["transit", "parks", "schools", "mailbox", "heritage", "fiber"] as LayerId[]) {
      expect(auditRowFor(id).map).toBe("walk-raster");
      expect(rasterDistanceLabel(id)).toBe("walk");
    }
  });

  it("renders a markdown table with one row per layer", () => {
    const md = toMarkdownTable(buildAuditTable());
    const lines = md.split("\n");
    expect(lines.length).toBe(LAYERS.length + 2);
    expect(lines[0]).toContain("| id | map | scorer | verdict | rationale |");
    expect(md).toContain("| industprox | euclidean-raster | haversine-bands | change |");
    expect(md).toContain("| transit | walk-raster | walk-graph | reasonable |");
  });

  it("shows scorer walk-graph for the #814 migrated families", () => {
    // Core + amenity walk-raster families migrated in #814.
    for (const id of [
      "transit",
      "parks",
      "schools",
      "mailbox",
      "postal",
      "alley",
      "plaster",
      "antiques",
      "heritage",
      "woodfire",
      "trailprivacy",
      "waste",
      "water",
    ] as LayerId[]) {
      const r = auditRowFor(id);
      expect(r.map).toBe("walk-raster");
      expect(r.scorer).toBe("walk-graph");
      expect(r.followUp).toBeUndefined();
      expect(r.scorerRef).toContain("walk_access.py");
    }
    // Migrated dbands register-proximity layers.
    for (const id of ["sport_hall", "medre_gp", "poi_library"] as LayerId[]) {
      const r = auditRowFor(id);
      expect(r.scorer).toBe("walk-graph");
      expect(r.followUp).toBeUndefined();
    }
  });

  it("leaves non-pedestrian layers off the walk-graph scorer", () => {
    // Air-station coverage: Euclidean by design (air does not walk).
    const air = auditRowFor("ohuseire" as LayerId);
    expect(air.scorer).toBe("haversine-bands");
    expect(air.followUp).toBeUndefined();
    // Fiber has no per-listing leg: nothing to route.
    const fiber = auditRowFor("fiber" as LayerId);
    expect(fiber.scorer).toBe("none");
    // Every walk-raster row is either migrated, legless, or attribute.
    for (const r of buildAuditTable()) {
      if (r.map !== "walk-raster") continue;
      expect(["walk-graph", "none", "attribute"]).toContain(r.scorer);
    }
  });
});

describe("808 G07 relabel against fixture masters", () => {
  // Contract halves: industprox/odorsrc 500/0.5, brownsoil/oiltank 500/0.5,
  // agriland 800/0.8, vectorhabitat 300/0.3, agrifield 800/0.8, wildcorr 500/0.5.
  const cases: Array<[LayerId, number, number]> = [
    ["industprox", 500, 0.5],
    ["odorsrc", 500, 0.5],
    ["brownsoil", 500, 0.5],
    ["oiltank", 500, 0.5],
    ["agriland", 800, 0.8],
    ["vectorhabitat", 300, 0.3],
    ["agrifield", 800, 0.8],
    ["wildcorr", 500, 0.5],
  ];
  for (const [id, half, sigma] of cases) {
    it(`labels a contract-passing ${id} master euclidean (grid Dijkstra, never walked)`, async () => {
      const dir = await fixtureDir([{ lat: 59.44, lon: 24.75 }], id);
      await writeFile(join(dir, "osm", `${id}-walk-raster.json`), JSON.stringify(rasterDoc({ half, sigma })));
      try {
        const res = await loadLayerRaster(id, dir);
        expect(res.raster?.half).toBe(half);
        expect(res.distance).toBe("euclidean");
      } finally {
        await rm(dir, { recursive: true, force: true });
      }
    });
  }

  it("keeps the audit map column in agreement with loadLayerRaster", async () => {
    // Walk master present -> walk; Euclidean master present -> euclidean;
    // no master -> euclidean fallback.
    const tdir = await fixtureDir([{ lat: 59.44, lon: 24.75 }], "transit");
    await writeFile(
      join(tdir, "osm", "transit-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 1500, sigma: 0.2 })),
    );
    try {
      expect((await loadLayerRaster("transit", tdir)).distance).toBe("walk");
      expect(auditRowFor("transit").map).toBe("walk-raster");
    } finally {
      await rm(tdir, { recursive: true, force: true });
    }
    const ddir = await fixtureDir([{ lat: 59.47, lon: 24.82 }], "drainage");
    await writeFile(
      join(ddir, "osm", "drainage-walk-raster.json"),
      JSON.stringify(rasterDoc({ half: 300, sigma: 0.3 })),
    );
    try {
      expect((await loadLayerRaster("drainage", ddir)).distance).toBe("euclidean");
      expect(auditRowFor("drainage").map).toBe("euclidean-raster");
    } finally {
      await rm(ddir, { recursive: true, force: true });
    }
    const mdir = await fixtureDir([{ lat: 59.44, lon: 24.75 }], "dailyshop");
    try {
      expect((await loadLayerRaster("dailyshop", mdir)).distance).toBe("euclidean");
      expect(auditRowFor("dailyshop").map).toBe("euclidean-fallback");
    } finally {
      await rm(mdir, { recursive: true, force: true });
    }
  });
});
