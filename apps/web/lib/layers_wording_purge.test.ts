// Wording purge (issue #783, slice 2): no user-visible hetkeseis /
// hetktõmmis / LIVE wording survives on any map surface. Slice 1
// (#797) pinned this for the DATEX feeds; this file extends the same
// pattern to the outage observed-window relabel (viimane vaatlus,
// #780 side-by-side contract unchanged) and to every static
// snapshot/extract string (väljavõte, dated). Also pins the dead
// LIVE label removal on the /layers page + layer routes. Hermetic
// (pure copy + source grep); live pulls stay pole-only by
// construction (server-side fetchPoleTable, pinned by
// layers_source.test.ts #762).
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import { LAYERS } from "./layers";
import { overlayLegendFor } from "./overlays";
import { asumediaEmptyStatus } from "./layers_asumedia";
import { gbfsDemoStatus } from "./layers_p4_gbfs";
import { harnoDemoStatus } from "./layers_p4_harno";
import { outageHistoryStatus } from "./layers_p4_outage";
import { sillyDemoStatus, sillySnapshotStatus } from "./layers_p4_silly";
import { skisDemoStatus } from "./layers_p4_skis";
import { paasteDemoStatus } from "./layers_paaste";
import { planktprDemoStatus } from "./layers_planktpr";

const PAGE_SRC = fs.readFileSync(
  new URL("../app/layers/page.tsx", import.meta.url),
  "utf8",
);
const ROUTE_SRC = fs.readFileSync(
  new URL("../app/api/layers/[layer]/route.ts", import.meta.url),
  "utf8",
);
const OVERLAY_ROUTE_SRC = fs.readFileSync(
  new URL("../app/api/layers/[layer]/overlay/route.ts", import.meta.url),
  "utf8",
);

/** Momentary-state wording banned from every user-visible surface. */
const BANNED = ["hetkeseis", "Hetkeseis", "hetktõmmis", "Hetktõmmis", "LIVE"];

/** Every user-visible registry string (layer def surfaces). */
function registrySurfaces(): string[] {
  const out: string[] = [];
  for (const def of LAYERS) {
    out.push(def.title, def.goodLabel, def.badLabel, def.source);
  }
  return out;
}

/** Every overlay legend, keyed by the same registry ids. */
function legendSurfaces(): string[] {
  return LAYERS.map((l) => overlayLegendFor(l.id));
}

/** Every status-line helper output the /layers page can render. */
function statusSurfaces(): string[] {
  const rel = {
    builtAt: "2026-09-20T11:55:00Z",
    windowDays: 28,
    tallinn: {
      nObs: 100,
      faultObs: 3,
      plannedObs: 5,
      upcomingObs: 40,
      faultCustomers: 210,
      plannedCustomers: 90,
      coverage: 0.0124,
    },
    nObsTotal: 100,
  };
  return [
    asumediaEmptyStatus(),
    gbfsDemoStatus(0),
    harnoDemoStatus(0),
    sillySnapshotStatus(1874),
    sillyDemoStatus(2),
    skisDemoStatus(0),
    paasteDemoStatus(0),
    planktprDemoStatus(0),
    outageHistoryStatus(rel) ?? "",
  ];
}

describe("wording purge (#783 slice 2)", () => {
  it("no banned wording on any registry surface", () => {
    expect(LAYERS.length).toBeGreaterThan(100);
    for (const s of registrySurfaces()) {
      for (const word of BANNED) {
        expect(s).not.toContain(word);
      }
    }
  });

  it("no banned wording in any overlay legend", () => {
    for (const s of legendSurfaces()) {
      for (const word of BANNED) {
        expect(s).not.toContain(word);
      }
    }
  });

  it("no banned wording in any status-line helper output", () => {
    for (const s of statusSurfaces()) {
      for (const word of BANNED) {
        expect(s).not.toContain(word);
      }
    }
  });

  it("outage names the observed window as viimane vaatlus, never hetkeseis", () => {
    const def = LAYERS.find((l) => l.id === "outage")!;
    expect(def.title).toContain("viimane vaatlus");
    expect(def.title).toContain("28 pv");
    expect(def.source).toContain("viimane vaatlus");
    expect(def.source).toContain("28 päeva");
    expect(overlayLegendFor("outage")).toContain("viimane vaatlus");
    expect(overlayLegendFor("outage")).toContain("28 pv");
  });

  it("static extracts name the dated väljavõte", () => {
    const silly = LAYERS.find((l) => l.id === "manguvaljakud")!;
    expect(silly.source).toContain("väljavõte 2026-09-12");
    expect(sillySnapshotStatus(1874)).toContain("väljavõte");
  });

  it("/layers page + layer routes carry no banned wording, LIVE stays dead", () => {
    for (const src of [PAGE_SRC, ROUTE_SRC, OVERLAY_ROUTE_SRC]) {
      for (const word of BANNED) {
        expect(src).not.toContain(word);
      }
    }
    expect(PAGE_SRC).toContain("Elektrilevi viimane vaatlus");
    expect(PAGE_SRC).toContain("Kohalik väljavõte (2026-09-12)");
    for (const src of [ROUTE_SRC, OVERLAY_ROUTE_SRC]) {
      expect(src).not.toMatch(/provenance:\s*["']live["']/);
    }
  });
});
