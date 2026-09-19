// Serving-family audit (issue #762): every layer declares WHERE its
// bytes come from, so no layer can silently gain a live third-party
// dependency. Families mirror the /api/layers/[layer] route branches:
//
// - operator-cache: outage + sheds + incidents (git-ignored operator
//   files, TTL-enforced, never committed, never live third-party).
// - pole-live: DATEX x6 (pole /v1/datex-* tables, per-feed TTLs, no
//   committed sidecars — SHORT-TERM CACHE ONLY verdict).
// - dedicated-snapshot-branch: offline-built sidecars (snapshot dir or
//   committed harvest, never live).
// - generic-snapshot-file: osm/derived-<layer>.json (+walk rasters);
//   missing file reads 500 -> LABELED demo (never silent). Includes the
//   silly x12 (demo fallback points are REAL mapped points, labeled).
//
// A new layer id fails this test until its family is declared here.
// Live-path grep evidence lives in docs/snapshot_audit.md (2026-09-19
// sweep: 143 snapshot / 27 demo-labeled-500 / 3 honestly-empty, zero
// browser-direct or server-live third-party calls).

import { describe, expect, it } from "vitest";
import { LAYERS } from "./layers";
import type { LayerId } from "./layers";
import { isOutageLayerId } from "./layers_p4_outage";
import { isShedLayerId } from "./layers_p4_tomtom_sheds";
import { isDatexLayerId } from "./layers_datex";
import { isIncidentsLayerId } from "./layers_p4_incidents";
import { isSenscomLayerId } from "./layers_p4_senscom";
import { isTerviseLayerId } from "./layers_tervise";
import { isViirsLayerId } from "./layers_p4_viirs";
import { isFloodLayerId } from "./layers_flood";
import { isEelisLayerId } from "./layers_eelis";
import { isMaaParcelLayerId } from "./layers_maaparcel";
import { isSevesoLayerId } from "./layers_p4_seveso";
import { isDelayLayerId } from "./layers_p4_delay";
import { isStatelandLayerId } from "./layers_p4_stateland";
import { isSoilLayerId } from "./layers_p4_soil";
import { isQuarryLayerId } from "./layers_p4_quarry";
import { isMaaparandusLayerId } from "./layers_p4_maaparandus";
import { isEtakLayerId } from "./layers_p4_etak";
import { isReliefLayerId } from "./layers_p4_relief";
import { isCanopyLayerId } from "./layers_p4_canopy";
import { isBuildingsLayerId } from "./layers_p4_buildings";
import { isDensityLayerId } from "./layers_p4_density";
import { isForestLayerId } from "./layers_p4_forest";
import { isHarbourLayerId } from "./layers_p4_harbour";
import { isKpoLayerId } from "./layers_p4_kpo";
import { isNoiseLayerId } from "./layers_p4_noise";
import { isOoklaLayerId } from "./layers_p4_ookla";
import { isSportLayerId } from "./layers_p4_sport";
import { isEhisLayerId } from "./layers_p4_ehis";
import { isMedreLayerId } from "./layers_p4_medre";
import { isOhuseireLayerId } from "./layers_p4_ohuseire";
import { isKliimaLayerId } from "./layers_kliima";
import { isPoiLayerId } from "./layers_p4_poi";
import { isFixitLayerId } from "./layers_p4_fixit";
import { isAccBlackLayerId } from "./layers_accblack";
import { isAsumediaLayerId } from "./layers_asumedia";
import { SILLY_LAYER_IDS } from "./layers_p4_silly";

const OPERATOR_CACHE = [isOutageLayerId, isShedLayerId, isIncidentsLayerId];
const POLE_LIVE = [isDatexLayerId];
const DEDICATED_SNAPSHOT = [
  isSenscomLayerId,
  isTerviseLayerId,
  isViirsLayerId,
  isFloodLayerId,
  isEelisLayerId,
  isMaaParcelLayerId,
  isSevesoLayerId,
  isDelayLayerId,
  isStatelandLayerId,
  isSoilLayerId,
  isQuarryLayerId,
  isMaaparandusLayerId,
  isEtakLayerId,
  isReliefLayerId,
  isCanopyLayerId,
  isBuildingsLayerId,
  isDensityLayerId,
  isForestLayerId,
  isHarbourLayerId,
  isKpoLayerId,
  isNoiseLayerId,
  isOoklaLayerId,
  isSportLayerId,
  isEhisLayerId,
  isMedreLayerId,
  isOhuseireLayerId,
  isKliimaLayerId,
  isPoiLayerId,
  isFixitLayerId,
  isAccBlackLayerId,
  isAsumediaLayerId,
];

function familyOf(id: LayerId): string {
  const hits: string[] = [];
  if (OPERATOR_CACHE.some((g) => g(id))) hits.push("operator-cache");
  if (POLE_LIVE.some((g) => g(id))) hits.push("pole-live");
  if (DEDICATED_SNAPSHOT.some((g) => g(id))) hits.push("dedicated-snapshot");
  if ((SILLY_LAYER_IDS as string[]).includes(id)) hits.push("silly-demo");
  if (hits.length === 0) hits.push("generic-snapshot-file");
  return hits.join("+");
}

describe("serving families (#762)", () => {
  it("pins the family census (a new layer updates this with its family)", () => {
    const fams: Record<string, number> = {};
    for (const l of LAYERS) {
      const f = familyOf(l.id);
      fams[f] = (fams[f] ?? 0) + 1;
    }
    // 762-HOOK (#762): 103 generic + 6 operator-cache + 6 pole-live +
    // 46 dedicated-snapshot + 12 silly-demo = 173.
    expect(fams).toEqual({
      "generic-snapshot-file": 103,
      "operator-cache": 6,
      "pole-live": 6,
      "dedicated-snapshot": 46,
      "silly-demo": 12,
    });
  });

  it("no layer belongs to two families (guards stay disjoint)", () => {
    const doubles: string[] = [];
    for (const l of LAYERS) {
      const fam = familyOf(l.id);
      if (fam.includes("+")) doubles.push(`${l.id} (${fam})`);
    }
    expect(doubles).toEqual([]);
  });

  it("live families are closed sets (nothing joins undeclared)", () => {
    const op = LAYERS.map((l) => l.id).filter((id) =>
      OPERATOR_CACHE.some((g) => g(id)),
    );
    expect(op.sort()).toEqual(
      ["incidents", "outage", "shed-15-offpeak", "shed-15-peak", "shed-30-offpeak", "shed-30-peak"].sort(),
    );
    const pole = LAYERS.map((l) => l.id).filter((id) =>
      POLE_LIVE.some((g) => g(id)),
    );
    expect(pole.sort()).toEqual(
      [
        "datex-cameras",
        "datex-counters",
        "datex-restrictions",
        "datex-srti",
        "datex-truckpark",
        "datex-weather",
      ].sort(),
    );
  });

  it("silly demo layers carry real fallback points (labeled, never silent)", () => {
    for (const id of SILLY_LAYER_IDS) {
      const def = LAYERS.find((l) => l.id === id);
      expect(def).toBeDefined();
      expect(def?.fallbackPoints.length).toBeGreaterThan(0);
    }
  });
});
