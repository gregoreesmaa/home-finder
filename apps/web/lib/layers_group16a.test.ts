// Group 16 macro/finance-A verdict tests (issue #205): p2/p6/p7/p8/p9/
// p41/p43/p70/p73/p77/p143/p147/p148/p149/p151/p153/p155/p156/p157/
// p159/p160/p185 are ALL documented no-map (OTA PR #131 precedent)
// with scorer dims in services/scoring/dims_group16a.py.
// Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP16A_ALL_PARAMS,
  GROUP16A_CONSIDERED_TAGS,
  GROUP16A_EVIDENCE,
  GROUP16A_HOOK,
  GROUP16A_NO_MAP,
  GROUP16A_SHIPPED_PARAMS,
} from "./layers_group16a";

const EXPECTED_PARAMS = [
  2, 6, 7, 8, 9, 41, 43, 70, 73, 77, 143, 147, 148, 149, 151, 153, 155,
  156, 157, 159, 160, 185,
] as const;

const EXPECTED_DIMS: Record<number, string> = {
  2: "dim_property_taxes",
  6: "dim_mortgage_rates",
  7: "dim_home_insurance",
  8: "dim_closing_costs",
  9: "dim_down_payment",
  41: "dim_historical_appreciation",
  43: "dim_resale_appeal",
  70: "dim_home_insurability",
  73: "dim_special_tax_assessment",
  77: "dim_municipal_fiscal_health",
  143: "dim_assumable_mortgages",
  147: "dim_contractor_availability",
  148: "dim_relocation_incentives",
  149: "dim_market_liquidity",
  151: "dim_tax_reassessment",
  153: "dim_seller_concessions",
  155: "dim_mortgage_portability",
  156: "dim_first_time_buyer",
  157: "dim_rent_back",
  159: "dim_opportunity_zones",
  160: "dim_title_insurance",
  185: "dim_net_metering",
};

describe("group16a verdict registry", () => {
  it("owns exactly the 22 G16-A params and ships zero layers", () => {
    expect([...GROUP16A_ALL_PARAMS]).toEqual([...EXPECTED_PARAMS]);
    expect([...GROUP16A_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP16A_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([
      ...EXPECTED_PARAMS,
    ]);
  });

  it("points every verdict at its scorer dim", () => {
    expect(
      Object.fromEntries(GROUP16A_NO_MAP.map((v) => [v.param, v.dim])),
    ).toEqual(EXPECTED_DIMS);
    for (const v of GROUP16A_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / EI OLE, never guaranteed)", () => {
    for (const v of GROUP16A_NO_MAP) {
      expect(v.reason).toContain("hinnang");
      expect(v.reason).toContain("EI OLE");
    }
    const reasons = GROUP16A_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).not.toMatch(/garanteeritud/i);
    expect(reasons).not.toMatch(/mõõdetud intress|ametlik Euribor siin/i);
  });

  it("never presents national series as an area signal", () => {
    const byParam = Object.fromEntries(
      GROUP16A_NO_MAP.map((v) => [v.param, v.reason]),
    );
    // Euribor, KredEx rules and net-metering law are national: the
    // reasons must say the value does not vary by map point.
    expect(byParam[6]).toMatch(/üleriigili/); // stem: -line/-lised
    expect(byParam[156]).toMatch(/üleriigili/);
    expect(byParam[185]).toMatch(/üleriigili/);
  });

  it("locks the registry reality (no snapshot table, national Euribor)", () => {
    expect(GROUP16A_EVIDENCE.snapshotHasRegistryTable).toBe(false);
    expect(GROUP16A_EVIDENCE.euriborIsNational).toBe(true);
    expect(GROUP16A_EVIDENCE.sources).toContain("Maa-amet tehingud");
    expect(GROUP16A_EVIDENCE.sources).toContain("ECB Euribor 6M");
    expect(GROUP16A_EVIDENCE.sources).toContain("EMTA maamaks");
  });

  it("documents absence (not tags) for every param", () => {
    for (const p of EXPECTED_PARAMS) {
      expect(GROUP16A_CONSIDERED_TAGS[p]).toContain("puudub");
    }
    expect(GROUP16A_CONSIDERED_TAGS[6]).toContain("Euribor");
    expect(GROUP16A_CONSIDERED_TAGS[41]).toContain("HH01");
    expect(GROUP16A_CONSIDERED_TAGS[2]).toContain("EMTA");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP16A_HOOK).toContain("G16A-HOOK");
    expect(GROUP16A_HOOK).toContain("no shared-file wiring");
  });
});
