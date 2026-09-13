// Group 4 title/legal verdict tests (issue #204): all seventeen
// p76/p80/p139/p144/p229/p242/p248/p271/p274/p276/p279/p361/p362/p364/
// p367/p369/p428 are documented no-map (OTA PR #131 precedent) with
// scorer dims in services/scoring/dims_group04.py.
// Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP04_ALL_PARAMS,
  GROUP04_CONSIDERED_TAGS,
  GROUP04_EVIDENCE,
  GROUP04_HOOK,
  GROUP04_NO_MAP,
  GROUP04_SHIPPED_PARAMS,
} from "./layers_group04";

describe("group04 verdict registry", () => {
  it("owns exactly the seventeen G4 params and ships zero layers", () => {
    expect([...GROUP04_ALL_PARAMS]).toEqual([
      76, 80, 139, 144, 229, 242, 248, 271, 274, 276, 279, 361, 362, 364,
      367, 369, 428,
    ]);
    expect([...GROUP04_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP04_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([
      76, 80, 139, 144, 229, 242, 248, 271, 274, 276, 279, 361, 362, 364,
      367, 369, 428,
    ]);
  });

  it("points every verdict at its scorer dim", () => {
    expect(
      Object.fromEntries(GROUP04_NO_MAP.map((v) => [v.param, v.dim])),
    ).toEqual({
      76: "dim_mineral_timber_rights",
      80: "dim_deed_covenants",
      139: "dim_property_stigma",
      144: "dim_title_cleanliness",
      229: "dim_mineral_severance",
      242: "dim_stigma_laws",
      248: "dim_lease_encumbrance",
      271: "dim_view_covenant",
      274: "dim_air_rights",
      276: "dim_adverse_possession",
      279: "dim_morals_clause",
      361: "dim_trust_llc_transfer",
      362: "dim_probate_delay",
      364: "dim_ground_lease",
      367: "dim_squatter_holdover",
      369: "dim_coop_approval",
      428: "dim_title_cloud",
    });
    for (const v of GROUP04_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / EI OLE, never measured)", () => {
    for (const v of GROUP04_NO_MAP) {
      expect(v.reason).toContain("hinnang");
      expect(v.reason).toContain("EI OLE");
    }
    const reasons = GROUP04_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).not.toMatch(/mõõdetud omand|garanteeritud|puhas omand/i);
  });

  it("names the registry buyer check in every reason", () => {
    const reasons = GROUP04_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).toContain("kinnistusraamat");
    expect(reasons).toContain("notari");
  });

  it("locks the snapshot evidence counts (drift guard)", () => {
    // No deed/lien/mortgage/lease/covenant key exists county-wide.
    expect(GROUP04_EVIDENCE.deedKeys).toBe(0);
    expect(GROUP04_EVIDENCE.lienKeys).toBe(0);
    expect(GROUP04_EVIDENCE.mortgageKeys).toBe(0);
    expect(GROUP04_EVIDENCE.leaseKeys).toBe(0);
    expect(GROUP04_EVIDENCE.covenantKeys).toBe(0);
    // Owner-ish tags are institutional noise, never parcel title.
    expect(GROUP04_EVIDENCE.ownerKeys).toBe(13);
    expect(GROUP04_EVIDENCE.ownershipKeys).toBe(1);
    expect(GROUP04_EVIDENCE.operatorKeys).toBe(7710);
  });

  it("documents evaluated tags for proxy params, absence for NULL dims", () => {
    expect(GROUP04_CONSIDERED_TAGS[76]).toContain("owner");
    expect(GROUP04_CONSIDERED_TAGS[144]).toContain("owner");
    expect(GROUP04_CONSIDERED_TAGS[428]).toContain("owner");
    expect(GROUP04_CONSIDERED_TAGS[80]).toContain("pole");
    expect(GROUP04_CONSIDERED_TAGS[242]).toContain("pole");
    expect(GROUP04_CONSIDERED_TAGS[362]).toContain("Teadaanded");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP04_HOOK).toContain("G04-HOOK");
    expect(GROUP04_HOOK).toContain("no shared-file wiring");
  });
});
