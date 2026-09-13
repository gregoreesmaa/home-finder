// Group 16 macro/finance-B verdict tests (issue #206): p241/p243/p249/
// p250/p318/p363/p366/p370/p421/p422/p423/p424/p425/p426/p430/p444/
// p481/p482/p483/p484/p486/p487 are ALL documented no-map (OTA PR #131
// precedent) with scorer dims in services/scoring/dims_group16b.py.
// Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP16B_ALL_PARAMS,
  GROUP16B_CONSIDERED_TAGS,
  GROUP16B_EVIDENCE,
  GROUP16B_HOOK,
  GROUP16B_NO_MAP,
  GROUP16B_SHIPPED_PARAMS,
} from "./layers_group16b";

const EXPECTED_PARAMS = [
  241, 243, 249, 250, 318, 363, 366, 370, 421, 422, 423, 424, 425, 426,
  430, 444, 481, 482, 483, 484, 486, 487,
] as const;

const EXPECTED_DIMS: Record<number, string> = {
  241: "dim_nuisance_liability",
  243: "dim_flood_insurance_caps",
  249: "dim_solar_lease_transfer",
  250: "dim_conservation_credits",
  318: "dim_pension_liability",
  363: "dim_exchange_eligibility",
  366: "dim_abatement_expiry",
  370: "dim_transfer_fees",
  421: "dim_appraisal_gap",
  422: "dim_supplemental_tax",
  423: "dim_assessment_district",
  424: "dim_pmi_threshold",
  425: "dim_eem_loan",
  426: "dim_capital_gains",
  430: "dim_escrow_buffer",
  444: "dim_tourist_influx",
  481: "dim_price_ceiling",
  482: "dim_corporate_density",
  483: "dim_shadow_inventory",
  484: "dim_absorption_rate",
  486: "dim_land_improvement_ratio",
  487: "dim_demographic_transition",
};

describe("group16b verdict registry", () => {
  it("owns exactly the 22 G16-B params and ships zero layers", () => {
    expect([...GROUP16B_ALL_PARAMS]).toEqual([...EXPECTED_PARAMS]);
    expect([...GROUP16B_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP16B_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([
      ...EXPECTED_PARAMS,
    ]);
  });

  it("points every verdict at its scorer dim", () => {
    expect(
      Object.fromEntries(GROUP16B_NO_MAP.map((v) => [v.param, v.dim])),
    ).toEqual(EXPECTED_DIMS);
    for (const v of GROUP16B_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (every reason: hinnang + EI OLE)", () => {
    for (const v of GROUP16B_NO_MAP) {
      expect(v.reason).toContain("hinnang");
      expect(v.reason).toContain("EI OLE");
    }
    const reasons = GROUP16B_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).not.toMatch(/garanteeritud/i);
    expect(reasons).not.toMatch(/mõõdetud turu väärtus|ametlik gradient siin/i);
  });

  it("never presents a market-wide series as an area signal", () => {
    const byParam = Object.fromEntries(
      GROUP16B_NO_MAP.map((v) => [v.param, v.reason]),
    );
    // Tourist pulse, ownership aggregate, shadow supply, absorption
    // and demographics are market-wide: the reasons must say so and
    // refuse the gradient.
    for (const p of [444, 482, 483, 484, 487]) {
      expect(byParam[p]).toMatch(/turu-ülene/);
    }
  });

  it("locks the registry reality (no snapshot table, series not signal)", () => {
    expect(GROUP16B_EVIDENCE.snapshotHasRegistryTable).toBe(false);
    expect(GROUP16B_EVIDENCE.marketWideIsNotAreaSignal).toBe(true);
    expect(GROUP16B_EVIDENCE.sources).toContain("Maa-amet tehingud");
    expect(GROUP16B_EVIDENCE.sources).toContain("Statistikaamet HH01/KK11");
    expect(GROUP16B_EVIDENCE.sources).toContain("EMTA maksuregistrid");
  });

  it("documents absence (not tags) for every param", () => {
    for (const p of EXPECTED_PARAMS) {
      expect(GROUP16B_CONSIDERED_TAGS[p]).toContain("puudub");
    }
    expect(GROUP16B_CONSIDERED_TAGS[484]).toContain("turu-ülene");
    expect(GROUP16B_CONSIDERED_TAGS[481]).toContain("Maa-amet");
    expect(GROUP16B_CONSIDERED_TAGS[422]).toContain("EMTA");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP16B_HOOK).toContain("G16B-HOOK");
    expect(GROUP16B_HOOK).toContain("no shared-file wiring");
  });
});
