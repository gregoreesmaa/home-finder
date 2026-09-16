// Hermetic tests for the annateada report-pin overlay (issue #623).
// Synthetic fixtures below are FULLY SYNTHETIC (clearly labelled);
// the REAL-DATA pins read the deployed snapshot sidecar shape only
// through fixitPointsIn fixtures (pins live outside the repo in
// ~/hf-data — fixtures only, never live). No network in tests.

import { describe, expect, it } from "vitest";
import {
  LAYERS,
  bonusSpecFor,
  fetchWindow,
  layerParamTag,
  radiusKmFor,
} from "./layers";
import { buildScoredField } from "./distanceField";
import { overlayColorFor, overlayLegendFor } from "./overlays";
import {
  FIXIT_PROBE,
  FIXIT_VINTAGE,
  FIXIT_WINDOW_DAYS,
  fixitBonusSpecFor,
  fixitPointsIn,
  isFixitLayerId,
  type FixitPoint,
} from "./layers_p4_fixit";

/** Frozen now: 2026-09-17T12:00:00Z (matches the harvest vintage). */
const NOW_MS = Date.UTC(2026, 8, 17, 12, 0, 0);
const DAY_S = 86400;
const freshTs = Math.floor(NOW_MS / 1000) - 2 * DAY_S;
const oldTs = Math.floor(NOW_MS / 1000) - 25 * DAY_S;

/** Synthetic Tallinn backyard pins. */
const HOME = { lat: 59.4374, lon: 24.7454 };
function pin(dlat: number, dlon: number, ts: number): FixitPoint {
  return { lat: HOME.lat + dlat, lon: HOME.lon + dlon, handled: false, ts };
}

describe("fixit pins kernel (markers only, never a score)", () => {
  it("locks the pins spec + vintage + window", () => {
    expect(fixitBonusSpecFor("fixit")).toEqual({ kind: "pins" });
    expect(bonusSpecFor("fixit")).toEqual({ kind: "pins" });
    expect(FIXIT_VINTAGE).toBe("2026-09-17");
    expect(FIXIT_WINDOW_DAYS).toBe(19);
    expect(radiusKmFor("fixit")).toBe(0.5);
    expect(isFixitLayerId("fixit")).toBe(true);
    expect(isFixitLayerId("ohuseire")).toBe(false);
  });

  it("serves fresh pins inside the bbox, in wire shape", () => {
    const pts = fixitPointsIn(
      [pin(0.001, 0.001, freshTs)],
      { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 },
      NOW_MS,
    );
    expect(pts).toHaveLength(1);
    expect(Object.keys(pts[0]).sort()).toEqual(["lat", "lon"]);
  });

  it("expires pins older than the rolling window (never current)", () => {
    const pts = fixitPointsIn(
      [pin(0.001, 0.001, freshTs), pin(0.002, 0.002, oldTs)],
      { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 },
      NOW_MS,
    );
    expect(pts).toHaveLength(1);
  });

  it("degrades a fully-stale sidecar to honestly-empty", () => {
    const pts = fixitPointsIn(
      [pin(0.001, 0.001, oldTs)],
      { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 },
      NOW_MS,
    );
    expect(pts).toEqual([]);
  });

  it("clips to the view bbox and skips coordless junk", () => {
    const pts = fixitPointsIn(
      [
        pin(0.001, 0.001, freshTs),
        { lat: 58.0, lon: 24.7, handled: false, ts: freshTs },
        { lat: NaN, lon: NaN, handled: false, ts: freshTs },
      ],
      { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 },
      NOW_MS,
    );
    expect(pts).toHaveLength(1);
  });

  it("paints NO field for pins (all-NaN direct — markers ride the overlay)", () => {
    const spec = fixitBonusSpecFor("fixit");
    if (spec.kind !== "pins") throw new Error("fixit spec must be pins");
    const field = buildScoredField(
      [{ lon: 24.7454, lat: 59.4375 }],
      { minlon: 24.73, minlat: 59.43, maxlon: 24.76, maxlat: 59.445 },
      8,
      8,
      1.0,
      spec,
    );
    expect(field.direct).not.toBeNull();
    for (const v of field.direct!) expect(v).toBeNaN();
  });
});

describe("fixit registry wiring", () => {
  it("registers one layer with no parameters3 id + P4-kaebused label", () => {
    const def = LAYERS.find((l) => l.id === "fixit")!;
    expect(def.paramIds).toEqual([]);
    expect(def.paramLabel).toBe("P4-kaebused");
    expect(layerParamTag(def)).toBe("(P4-kaebused)");
    expect(layerParamTag(LAYERS.find((l) => l.id === "parks")!)).toBe("(p19)");
  });

  it("explains pins-not-quality in Estonian with a demo pin", () => {
    const def = LAYERS.find((l) => l.id === "fixit")!;
    for (const f of [def.title, def.goodLabel, def.badLabel, def.source]) {
      expect(f.length).toBeGreaterThan(0);
    }
    expect(def.fallbackPoints.length).toBeGreaterThan(0);
    expect(def.source).toContain("annateada");
  });

  it("gives fixit a legend stating the reporting bias + window", () => {
    const legend = overlayLegendFor("fixit");
    expect(legend.length).toBeGreaterThan(10);
    expect(legend).toContain("MITTE elukvaliteet");
    expect(legend).toContain("19 päeva");
    expect(legend).toContain("300 teadet");
  });

  it("paints fixit markers notice-orange", () => {
    expect(overlayColorFor("fixit")).toBe("#fdba74");
  });

  it("skips the raster window fetch (no master exists by decision)", async () => {
    const boom = () => {
      throw new Error("pins layers must never fetch a window");
    };
    await expect(
      fetchWindow("fixit", { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 }, boom as unknown as typeof fetch),
    ).resolves.toBeNull();
  });
});

describe("fixit harvest pins (probe 2026-09-17)", () => {
  it("pins the rolling-window tally (builder parity — drift = bug)", () => {
    expect(FIXIT_PROBE.windowDays).toBe(19);
    expect(FIXIT_PROBE.totalPins).toBe(300);
    expect(FIXIT_PROBE.tallinnPins).toBe(173);
    expect(FIXIT_PROBE.handledPins).toBe(120);
    expect(FIXIT_PROBE.unhandledPins).toBe(180);
  });
});
