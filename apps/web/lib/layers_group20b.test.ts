// Group 20 subjective-B verdict tests (issue #213): p168/p170/p239/p281/
// p283/p349/p380/p383/p385/p388/p390/p398/p410/p413/p449/p461/p488/p490/
// p500 are ALL documented no-map (OTA PR #131 precedent) with scorer
// dims in services/scoring/dims_group20b.py. Hermetic: no network, no
// snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP20B_ALL_PARAMS,
  GROUP20B_CONSIDERED_TAGS,
  GROUP20B_HOOK,
  GROUP20B_NO_MAP,
  GROUP20B_SHIPPED_PARAMS,
} from "./layers_group20b";

const ALL_19 = [
  168, 170, 239, 281, 283, 349, 380, 383, 385, 388, 390, 398, 410, 413,
  449, 461, 488, 490, 500,
];

const PARAM_TO_DIM: Record<number, string> = {
  168: "dim_mutual_aid",
  170: "dim_volunteerism",
  239: "dim_garden_sensory",
  281: "dim_work_zones",
  283: "dim_quarantine",
  349: "dim_pet_density",
  380: "dim_disaster_resilience",
  383: "dim_cohousing",
  385: "dim_golf_ball_risk",
  388: "dim_gated_security",
  390: "dim_culture_enclave",
  398: "dim_toxic_planting",
  410: "dim_biophilic",
  413: "dim_surveillance_culture",
  449: "dim_holiday_lights",
  461: "dim_hoarder_neighbor",
  488: "dim_flaw_permanence",
  490: "dim_timeline_desperation",
  500: "dim_gut_veto",
};

describe("group20b verdict registry", () => {
  it("owns exactly the nineteen G20-B params and ships zero layers", () => {
    expect([...GROUP20B_ALL_PARAMS]).toEqual(ALL_19);
    expect([...GROUP20B_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP20B_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual(
      ALL_19,
    );
  });

  it("points every verdict at its scorer dim", () => {
    expect(
      Object.fromEntries(GROUP20B_NO_MAP.map((v) => [v.param, v.dim])),
    ).toEqual(PARAM_TO_DIM);
    for (const v of GROUP20B_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / EI OLE / buyer profile, never faked)", () => {
    const reasons = GROUP20B_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).toContain("hinnang");
    expect(reasons).toContain("EI OLE");
    expect(reasons).toContain("küsimustik");
    for (const v of GROUP20B_NO_MAP) {
      expect(v.reason).toContain("hinnang");
      expect(v.reason).toContain("EI OLE");
    }
    expect(reasons).not.toMatch(/garanteeritud|mõõdetud skoor/i);
  });

  it("documents tag absence for every NULL dim (nothing honest to query)", () => {
    for (const p of ALL_19) {
      const tags =
        GROUP20B_CONSIDERED_TAGS[p as keyof typeof GROUP20B_CONSIDERED_TAGS];
      expect(tags.length).toBeGreaterThan(0);
      expect(tags).toContain("OSM-i fakt");
    }
    // Deliberate rejections name their trap, not just absence.
    expect(GROUP20B_CONSIDERED_TAGS[385]).toContain("tagasi lükatud");
    expect(GROUP20B_CONSIDERED_TAGS[413]).toContain("tagasi lükatud");
    expect(GROUP20B_CONSIDERED_TAGS[390]).toContain("kaardistamata");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP20B_HOOK).toContain("G20B-HOOK");
    expect(GROUP20B_HOOK).toContain("no shared-file wiring");
  });
});
