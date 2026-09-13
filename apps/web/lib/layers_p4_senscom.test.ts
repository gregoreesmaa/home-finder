// Hermetic tests for the P4-031 senscom overlay (issue #484). All sensor
// fixtures below are FULLY SYNTHETIC (clearly labelled) — real observed
// values (2026-09-13: 1 Tallinn location) appear only in
// docs/p4_senscom.md, never as ingested data. No network in tests.

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
  SENSCOM_BANDS,
  SENSCOM_LAYERS,
  SENSCOM_PARAM_LABEL,
  SENSCOM_RADIUS_M,
  isSenscomLayerId,
  senscomBandAt,
  senscomBandForCount,
  senscomBonusSpecFor,
  type SenscomPoint,
} from "./layers_p4_senscom";

/** Synthetic Tallinn backyard + synthetic DIY witnesses (metres via true haversine). */
const HOME = { lat: 59.4374, lon: 24.7454 };
const M_PER_DEG_LAT = 111194.9;
function northOf(m: number): SenscomPoint {
  return { lat: HOME.lat + m / M_PER_DEG_LAT, lon: HOME.lon };
}

describe("senscom band kernel (scorer parity)", () => {
  it("pins the radius + bands to the dims_p4_senscom scorer (drift = bug)", () => {
    // Byte parity with SENSCOM_RADIUS_M / _band_density in
    // services/scoring/dims_p4_senscom.py: 1 -> 60, 2-3 -> 70, 4+ -> 80.
    expect(SENSCOM_RADIUS_M).toBe(500);
    expect({ ...SENSCOM_BANDS }).toEqual({ one: 60, twoThree: 70, fourPlus: 80 });
  });

  it("maps witness counts to bands, unknown stays null (never zero)", () => {
    expect(senscomBandForCount(0)).toBeNull();
    expect(senscomBandForCount(-1)).toBeNull();
    expect(senscomBandForCount(NaN)).toBeNull();
    expect(senscomBandForCount(1)).toBe(60);
    expect(senscomBandForCount(2)).toBe(70);
    expect(senscomBandForCount(3)).toBe(70);
    expect(senscomBandForCount(4)).toBe(80);
    expect(senscomBandForCount(40)).toBe(80);
  });

  it("scores one nearby synthetic witness 60 (hinnang, never EI OLE territory)", () => {
    expect(senscomBandAt(HOME.lat, HOME.lon, [northOf(100)])).toBe(60);
  });

  it("climbs 60 -> 70 -> 80 as synthetic witnesses accumulate in radius", () => {
    const witnesses = [northOf(100), northOf(200), northOf(300), northOf(400)];
    expect(senscomBandAt(HOME.lat, HOME.lon, witnesses.slice(0, 1))).toBe(60);
    expect(senscomBandAt(HOME.lat, HOME.lon, witnesses.slice(0, 2))).toBe(70);
    expect(senscomBandAt(HOME.lat, HOME.lon, witnesses.slice(0, 3))).toBe(70);
    expect(senscomBandAt(HOME.lat, HOME.lon, witnesses.slice(0, 4))).toBe(80);
  });

  it("applies the HARD 500 m cutoff (a 600 m witness is not a witness)", () => {
    expect(senscomBandAt(HOME.lat, HOME.lon, [northOf(400)])).toBe(60);
    expect(senscomBandAt(HOME.lat, HOME.lon, [northOf(600)])).toBeNull();
    expect(senscomBandAt(HOME.lat, HOME.lon, [northOf(100), northOf(600)])).toBe(60);
  });

  it("stays null with no witnesses (scorer NULL: hinnang + EI OLE, never a faked score)", () => {
    expect(senscomBandAt(HOME.lat, HOME.lon, [])).toBeNull();
  });

  it("skips coordless junk instead of scoring absence", () => {
    const junk = [
      { lat: NaN, lon: HOME.lon },
      { lat: HOME.lat, lon: Infinity },
    ] as unknown as SenscomPoint[];
    expect(senscomBandAt(HOME.lat, HOME.lon, junk)).toBeNull();
    expect(senscomBandAt(HOME.lat, HOME.lon, [...junk, northOf(100)])).toBe(60);
  });
});

describe("senscom registry wiring", () => {
  it("registers one layer with no parameters3 id + the P4-031 slice label", () => {
    expect(SENSCOM_LAYERS.map((l) => l.id)).toEqual(["senscom"]);
    expect(isSenscomLayerId("senscom")).toBe(true);
    expect(isSenscomLayerId("parks")).toBe(false);
    const def = LAYERS.find((l) => l.id === "senscom");
    expect(def?.paramIds).toEqual([]);
    expect(def?.paramLabel).toBe(SENSCOM_PARAM_LABEL);
    expect(SENSCOM_PARAM_LABEL).toBe("P4-031");
    // parameters3 p31 is Structural integrity (inspection no-map): the
    // overlay must never claim it.
    expect(LAYERS.find((l) => l.id === "senscom")?.paramIds).not.toContain(31);
  });

  it("tags the layer button (P4-031), leaving parameters3 tags untouched", () => {
    const def = LAYERS.find((l) => l.id === "senscom");
    expect(layerParamTag(def!)).toBe("(P4-031)");
    expect(layerParamTag(LAYERS.find((l) => l.id === "parks")!)).toBe("(p19)");
    // OSMDAILY-HOOK (#482) regression guard: P4 layers with empty
    // paramIds and no paramLabel render NO tag, not "(p)".
    expect(layerParamTag(LAYERS.find((l) => l.id === "dailyshop")!)).toBe("");
  });

  it("locks the bands spec + radius (map kernel == scorer kernel)", () => {
    expect(senscomBonusSpecFor("senscom")).toEqual({
      kind: "bands",
      radiusM: 500,
      one: 60,
      twoThree: 70,
      fourPlus: 80,
    });
    expect(bonusSpecFor("senscom")).toEqual(senscomBonusSpecFor("senscom"));
    expect(radiusKmFor("senscom")).toBe(0.5);
  });

  it("explains green=good / red=bad in Estonian with demo points", () => {
    const def = LAYERS.find((l) => l.id === "senscom")!;
    for (const f of [def.title, def.goodLabel, def.badLabel, def.source]) {
      expect(f.length).toBeGreaterThan(0);
    }
    expect(def.fallbackPoints.length).toBeGreaterThan(0);
    expect(def.source).toContain("hinnang");
  });

  it("gives senscom a legend naming the bands + the unmeasured truth", () => {
    const legend = overlayLegendFor("senscom");
    expect(legend.length).toBeGreaterThan(10);
    expect(legend).toContain("500 m");
    expect(legend).toContain("60");
    expect(legend).toContain("70");
    expect(legend).toContain("80");
    expect(legend).toContain("kalibreerimata");
  });

  it("paints senscom markers air-cyan", () => {
    expect(overlayColorFor("senscom")).toBe("#06b6d4");
  });

  it("skips the raster window fetch (no master exists by decision)", async () => {
    const boom = () => {
      throw new Error("bands layers must never fetch a window");
    };
    await expect(
      fetchWindow("senscom", { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 }, boom as unknown as typeof fetch),
    ).resolves.toBeNull();
  });
});

describe("senscom band field (client render path)", () => {
  const bbox = { minlon: 24.73, minlat: 59.43, maxlon: 24.76, maxlat: 59.445 };
  const spec = senscomBonusSpecFor("senscom");
  if (spec.kind !== "bands") throw new Error("senscom spec must be bands");

  it("renders the witness band under the sensor, unknown far away", () => {
    const pts = [{ ...northOf(0), lon: 24.7454, lat: 59.4375 }];
    const field = buildScoredField(pts, bbox, 24, 12, 0.5, spec);
    expect(field.direct).not.toBeNull();
    const vals = [...field.direct!].filter((v) => !Number.isNaN(v));
    expect(vals.length).toBeGreaterThan(0);
    for (const v of vals) expect(v).toBe(60);
    // Far corner cells (south-west, >500 m out) stay unknown, never zero.
    expect(field.direct![0]).toBeNaN();
  });

  it("renders 70/80 where synthetic witnesses cluster", () => {
    const cluster = [
      { lat: 59.4375, lon: 24.7454 },
      { lat: 59.4376, lon: 24.7455 },
      { lat: 59.4374, lon: 24.7453 },
      { lat: 59.4377, lon: 24.7456 },
    ];
    const field = buildScoredField(cluster, bbox, 24, 12, 0.5, spec);
    const vals = [...field.direct!].filter((v) => !Number.isNaN(v));
    expect(vals.length).toBeGreaterThan(0);
    // Band-shaped output only (a disc-edge cell may catch fewer of the
    // four witnesses — the kernel counts honestly per cell); the cell
    // under the cluster (ix 12, iy 5 fencepost) sees all four (80 cap).
    for (const v of vals) expect([60, 70, 80]).toContain(v);
    expect(field.direct![5 * 24 + 12]).toBe(80);
  });

  it("renders all-unknown when nothing loaded (never a faked open field)", () => {
    const field = buildScoredField([], bbox, 8, 8, 0.5, spec);
    expect(field.direct).not.toBeNull();
    for (const v of field.direct!) expect(v).toBeNaN();
  });
});
