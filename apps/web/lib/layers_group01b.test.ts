// Group 1 listing-portal verdict tests, batch B (issue #203):
// p121/p129/p140/p180/p191/p192/p193/p194/p195/p198/p200/p268/
// p285/p286/p288/p289/p290/p300/p412/p489 are ALL documented no-map
// (OTA PR #131 precedent) with scorer dims in
// services/scoring/dims_group01b.py. Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP01B_ALL_PARAMS,
  GROUP01B_CONSIDERED_TAGS,
  GROUP01B_EVIDENCE,
  GROUP01B_HOOK,
  GROUP01B_NO_MAP,
  GROUP01B_SHIPPED_PARAMS,
} from "./layers_group01b";

describe("group01b verdict registry", () => {
  it("owns exactly the twenty G1-B params and ships zero layers", () => {
    expect([...GROUP01B_ALL_PARAMS]).toEqual([
      121, 129, 140, 180, 191, 192, 193, 194, 195, 198, 200, 268, 285,
      286, 288, 289, 290, 300, 412, 489,
    ]);
    expect([...GROUP01B_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP01B_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([
      121, 129, 140, 180, 191, 192, 193, 194, 195, 198, 200, 268, 285,
      286, 288, 289, 290, 300, 412, 489,
    ]);
  });

  it("points every verdict at its scorer dim", () => {
    expect(Object.fromEntries(GROUP01B_NO_MAP.map((v) => [v.param, v.dim]))).toEqual({
      121: "dim_multigen",
      129: "dim_nanny_quarters",
      140: "dim_cosmetic_palette",
      180: "dim_hidden_space",
      191: "dim_radiant_floor",
      192: "dim_spa_recovery",
      193: "dim_acoustic_theater",
      194: "dim_climate_storage",
      195: "dim_scullery",
      198: "dim_motor_court",
      200: "dim_culinary_suite",
      268: "dim_server_closet",
      285: "dim_indoor_outdoor",
      286: "dim_bulk_pantry",
      288: "dim_pet_quarantine",
      289: "dim_hobby_mess",
      290: "dim_micro_spaces",
      300: "dim_flip_indicators",
      412: "dim_package_theft",
      489: "dim_staging_illusions",
    });
    for (const v of GROUP01B_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang + EI OLE in every NULL reason)", () => {
    for (const v of GROUP01B_NO_MAP) {
      expect(v.reason).toContain("hinnang");
      expect(v.reason).toContain("EI OLE");
    }
    const reasons = GROUP01B_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).not.toMatch(/garanteeritud|mõõdetud kaart/i);
  });

  it("locks the verdict counts (drift guard)", () => {
    expect(GROUP01B_EVIDENCE.ownedParams).toBe(20);
    expect(GROUP01B_EVIDENCE.proxyDims).toBe(0);
    expect(GROUP01B_EVIDENCE.nullDims).toBe(20);
    expect(GROUP01B_EVIDENCE.snapshotAreaSignals).toBe(0);
  });

  it("documents rejected near-miss proxies, absence for pure NULL dims", () => {
    // Motor courts and package theft had plausible OSM proxies that
    // were honestly rejected — the record must say what and why.
    expect(GROUP01B_CONSIDERED_TAGS[198]).toContain("parking");
    expect(GROUP01B_CONSIDERED_TAGS[412]).toContain("parcel_locker");
    for (const p of [121, 129, 140, 489] as const) {
      expect(GROUP01B_CONSIDERED_TAGS[p]).toContain("pole");
    }
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP01B_HOOK).toContain("G01B-HOOK");
    expect(GROUP01B_HOOK).toContain("no shared-file wiring");
  });
});
