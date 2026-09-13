// Group 20 subjective-A verdict tests (issue #212): p18/p81/p85/p90/
// p98/p104/p105/p122/p126/p127/p128/p131/p133/p134/p136/p161/p163/
// p164/p165 are ALL documented no-map (OTA PR #131 precedent) with
// scorer dims in services/scoring/dims_group20a.py. Hermetic: no
// network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP20A_ALL_PARAMS,
  GROUP20A_CONSIDERED_TAGS,
  GROUP20A_HOOK,
  GROUP20A_NO_MAP,
  GROUP20A_SHIPPED_PARAMS,
} from "./layers_group20a";

const OWNED = [
  18, 81, 85, 90, 98, 104, 105, 122, 126, 127, 128, 131, 133, 134, 136,
  161, 163, 164, 165,
] as const;

describe("group20a verdict registry", () => {
  it("owns exactly the nineteen G20-A params and ships zero layers", () => {
    expect([...GROUP20A_ALL_PARAMS]).toEqual([...OWNED]);
    expect([...GROUP20A_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP20A_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual(
      [...OWNED].sort((a, b) => a - b),
    );
  });

  it("points every verdict at its scorer dim", () => {
    expect(Object.fromEntries(GROUP20A_NO_MAP.map((v) => [v.param, v.dim]))).toEqual({
      18: "dim_neighborhood_vibe",
      81: "dim_pride_of_ownership",
      85: "dim_demographic_balance",
      90: "dim_civic_engagement",
      98: "dim_universal_design",
      104: "dim_entertaining_capacity",
      105: "dim_studio_potential",
      122: "dim_child_safety",
      126: "dim_pet_architecture",
      127: "dim_downsizing",
      128: "dim_cobuying",
      131: "dim_architectural_style",
      133: "dim_design_philosophy",
      134: "dim_emotional_resonance",
      136: "dim_tech_privacy",
      161: "dim_civic_alignment",
      163: "dim_holiday_decor",
      164: "dim_trick_or_treat",
      165: "dim_transient_neighbors",
    });
    for (const v of GROUP20A_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / EI OLE, buyer-side input, never measured)", () => {
    for (const v of GROUP20A_NO_MAP) {
      expect(v.reason).toContain("hinnang");
      expect(v.reason).toContain("EI OLE");
    }
    const reasons = GROUP20A_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).toMatch(/ostjaprofiil|küsimustik|vaatlus|kuulutus|KÜ/);
    expect(reasons).not.toMatch(/mõõdetud|garanteeritud|ala skoor on/i);
  });

  it("documents tag absence for every param (no OSM proxy consumed)", () => {
    for (const p of OWNED) {
      expect(GROUP20A_CONSIDERED_TAGS[p]).toContain("puudub");
    }
    expect(GROUP20A_CONSIDERED_TAGS[85]).toContain("REL2021");
    expect(GROUP20A_CONSIDERED_TAGS[165]).toContain("KÜ");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP20A_HOOK).toContain("G20A-HOOK");
    expect(GROUP20A_HOOK).toContain("no shared-file wiring");
  });
});
