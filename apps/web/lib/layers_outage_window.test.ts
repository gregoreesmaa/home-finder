// Windowed outage levels (issue #783, slice 4): the outage layer
// names its 5 min observation window + vintage on every user-visible
// surface (layer def, overlay legend, /layers status line) while the
// #780 contract stays intact — the 28-day observed-reliability history
// rides side by side with the latest-observed point, relabelled never
// removed. Modeled on layers_datex_window.test.ts (slice 1) and
// layers_incidents_sheds_window.test.ts (slice 3). Hermetic (pure copy
// + TTL consts); live pulls stay pole-only by construction
// (server-side fetchPoleTable, pinned by layers_source.test.ts #762).
import { describe, expect, it } from "vitest";
import { LAYERS } from "./layers";
import { overlayLegendFor } from "./overlays";
import {
  OUTAGE_HOOK,
  OUTAGE_LAYER_IDS,
  OUTAGE_RELIABILITY_WINDOW_DAYS,
  OUTAGE_TTL_S,
  OUTAGE_WINDOW_ET,
  outageHistoryStatus,
  outageStatusLine,
} from "./layers_p4_outage";

/** Momentary-state wording banned from outage user copy. */
const BANNED = [
  "täna",
  "hetkel",
  "elustabel",
  "LIVE",
  "hetkeseis",
  "hetktõmmis",
];

/** Every user-visible outage string on every surface. */
function outageSurfaces(): string[] {
  const def = LAYERS.find((l) => l.id === "outage")!;
  return [
    def.title,
    def.goodLabel,
    def.badLabel,
    def.source,
    overlayLegendFor("outage"),
    outageStatusLine(2, "3 min"),
    outageStatusLine(0, null),
  ];
}

describe("outage windowed levels (#783)", () => {
  it("names the 5 min window on every surface", () => {
    expect(OUTAGE_LAYER_IDS).toEqual(["outage"]);
    const def = LAYERS.find((l) => l.id === "outage")!;
    expect(def.source).toContain(OUTAGE_WINDOW_ET);
    expect(overlayLegendFor("outage")).toContain(OUTAGE_WINDOW_ET);
    expect(outageStatusLine(2, "3 min")).toContain(OUTAGE_WINDOW_ET);
  });

  it("window mirrors the serve TTL (harvester parity)", () => {
    expect(OUTAGE_TTL_S).toBe(300);
    expect(OUTAGE_WINDOW_ET).toContain("5 min");
  });

  it("status line carries window + vintage", () => {
    expect(outageStatusLine(2, "3 min")).toBe(
      "Elektrilevi viimane vaatlus (rikkekaart, 5 min aken, 5-min tõmme; vanus 3 min) · 2 punkti",
    );
    expect(outageStatusLine(0, null)).toBe(
      "Elektrilevi viimane vaatlus (rikkekaart, 5 min aken, 5-min tõmme) · 0 punkti",
    );
  });

  it("keeps the #780 history-vs-observation contract (relabel, not remove)", () => {
    // Both windows stay named side by side on every surface.
    const def = LAYERS.find((l) => l.id === "outage")!;
    expect(def.title).toContain("viimane vaatlus");
    expect(def.title).toContain("28 pv");
    expect(def.source).toContain("punkt on viimane vaatlus");
    expect(def.source).toContain("ajalugu on pooluse");
    expect(overlayLegendFor("outage")).toContain("viimane vaatlus");
    expect(overlayLegendFor("outage")).toContain("28 pv");
    expect(overlayLegendFor("outage")).toContain("ajalugu");
    // The history line still formats off the served 28-day window.
    const rel = {
      builtAt: "2026-09-20T11:55:00Z",
      windowDays: OUTAGE_RELIABILITY_WINDOW_DAYS,
      tallinn: {
        nObs: 100, faultObs: 3, plannedObs: 5, upcomingObs: 40,
        faultCustomers: 210, plannedCustomers: 90, coverage: 0.0124,
      },
      nObsTotal: 100,
    };
    const history = outageHistoryStatus(rel);
    expect(history).not.toBeNull();
    expect(history).toContain("ajalugu 28 pv");
    // Observed side and history side never merge into one claim.
    expect(outageStatusLine(2, "3 min")).not.toContain("ajalugu");
    expect(history).not.toContain("viimane vaatlus");
    expect(OUTAGE_HOOK).toContain("WINDOWED-HOOK (#783)");
  });

  it("no momentary-state wording on any outage surface", () => {
    for (const s of outageSurfaces()) {
      for (const word of BANNED) {
        expect(s).not.toContain(word);
      }
    }
  });
});
