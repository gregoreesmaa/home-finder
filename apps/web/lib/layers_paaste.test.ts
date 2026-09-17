// Hermetic tests for the Päästeamet komando overlay (issue #493). The
// feed verdict is dated-NEGATIVE (no machine feed — see docs/p4_paaste.md
// §6), so every fixture below is FULLY SYNTHETIC (clearly labelled):
// real observed values (street addresses WITHOUT coordinates) appear
// only in the docs, never as ingested points. No network in tests.

import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  LAYERS,
  bonusSpecFor,
  fetchWindow,
  layerParamTag,
  overpassQueryFor,
  radiusKmFor,
} from "./layers";
import { buildScoredField } from "./distanceField";
import {
  overlayColorFor,
  overlayLegendFor,
  overlayWeight,
  selectOverlayPoints,
} from "./overlays";
import {
  clearSnapshotCache,
  loadLayerRaster,
  loadSnapshotPoints,
  SnapshotUnavailable,
} from "./server/snapshot";
import {
  PAASTE_BANDS,
  PAASTE_DECAY,
  PAASTE_FAR_M,
  PAASTE_HOOK,
  PAASTE_LAYERS,
  PAASTE_PARAM_LABEL,
  PAASTE_TAGS,
  isPaasteLayerId,
  paasteBonusSpecFor,
  paasteCoveredAt,
  paasteBandForCount,
  paasteNearby,
  type PaastePoint,
} from "./layers_paaste";

const TALLINN_BBOX = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

/** Synthetic Tallinn home + synthetic komando points (metres via true haversine). */
const HOME = { lat: 59.4374, lon: 24.7454 };
const M_PER_DEG_LAT = 111194.9;
function northOf(m: number): PaastePoint {
  return { lat: HOME.lat + m / M_PER_DEG_LAT, lon: HOME.lon };
}

afterEach(() => {
  clearSnapshotCache();
});

describe("paaste coverage kernel (scorer parity)", () => {
  it("pins the radius to the dims_p4_paaste scorer (drift = bug)", () => {
    // Parity with STATION_FAR_KM in services/scoring/dims_p4_paaste.py
    // (the scorer's only station distance: straight-line penalty past
    // 5 km). Flat 60: response comes from the nearest komando — extra
    // stations in radius do NOT stack coverage.
    expect(PAASTE_FAR_M).toBe(5000);
    expect({ ...PAASTE_BANDS }).toEqual({ one: 60, twoThree: 60, fourPlus: 60 });
  });

  it("maps komando counts to flat-60 coverage, unknown stays null (never zero)", () => {
    expect(paasteBandForCount(0)).toBeNull();
    expect(paasteBandForCount(-1)).toBeNull();
    expect(paasteBandForCount(NaN)).toBeNull();
    expect(paasteBandForCount(1)).toBe(60);
    expect(paasteBandForCount(2)).toBe(60);
    expect(paasteBandForCount(4)).toBe(60);
    expect(paasteBandForCount(40)).toBe(60);
  });

  it("scores one nearby synthetic komando 60 (hinnang, never EI OLE territory)", () => {
    expect(paasteCoveredAt(HOME.lat, HOME.lon, [northOf(100)])).toBe(60);
  });

  it("stays flat 60 as synthetic komandos accumulate (nearest responds)", () => {
    const stations = [northOf(100), northOf(2000), northOf(3000), northOf(4000)];
    expect(paasteCoveredAt(HOME.lat, HOME.lon, stations.slice(0, 1))).toBe(60);
    expect(paasteCoveredAt(HOME.lat, HOME.lon, stations.slice(0, 2))).toBe(60);
    expect(paasteCoveredAt(HOME.lat, HOME.lon, stations)).toBe(60);
  });

  it("applies the HARD 5 km cutoff (a 6 km komando covers nothing)", () => {
    expect(paasteCoveredAt(HOME.lat, HOME.lon, [northOf(4000)])).toBe(60);
    expect(paasteCoveredAt(HOME.lat, HOME.lon, [northOf(6000)])).toBeNull();
    expect(paasteCoveredAt(HOME.lat, HOME.lon, [northOf(100), northOf(6000)])).toBe(60);
  });

  it("orders synthetic komandos nearest-first", () => {
    const near = paasteNearby(HOME.lat, HOME.lon, [northOf(4000), northOf(100)]);
    expect(near).toHaveLength(2);
    expect(near[0].distM).toBeLessThan(near[1].distM);
    expect(near[0].distM).toBeGreaterThan(0);
  });

  it("stays null with no komandos (scorer NULL: hinnang + EI OLE, never a faked score)", () => {
    expect(paasteCoveredAt(HOME.lat, HOME.lon, [])).toBeNull();
  });

  it("skips coordless junk instead of scoring absence", () => {
    const junk = [
      { lat: NaN, lon: HOME.lon },
      { lat: HOME.lat, lon: Infinity },
    ] as unknown as PaastePoint[];
    expect(paasteCoveredAt(HOME.lat, HOME.lon, junk)).toBeNull();
    expect(paasteCoveredAt(HOME.lat, HOME.lon, [...junk, northOf(100)])).toBe(60);
  });
});

describe("paaste registry wiring (#493)", () => {
  it("registers one layer with no parameters3 id + the P4-012 slice label", () => {
    expect(PAASTE_LAYERS.map((l) => l.id)).toEqual(["paaste"]);
    expect(isPaasteLayerId("paaste")).toBe(true);
    expect(isPaasteLayerId("parks")).toBe(false);
    const def = LAYERS.find((l) => l.id === "paaste");
    expect(def?.paramIds).toEqual([]);
    expect(def?.paramLabel).toBe(PAASTE_PARAM_LABEL);
    expect(PAASTE_PARAM_LABEL).toBe("P4-012");
    // parameters3 p12 is schools (Koolid ja lasteaiad): the overlay
    // must never claim it.
    expect(LAYERS.find((l) => l.id === "paaste")?.paramIds).not.toContain(12);
  });

  it("merges into LAYERS (107 + paaste)", () => {
    const ids = LAYERS.map((l) => l.id);
    expect(ids).toContain("paaste");
    // PAASTE-HOOK (#493): +1 honest-empty komando overlay (107 + 1).
    // (Rebased onto main at #513: 107 shipped layers + paaste.)
    expect(ids.length).toBe(137); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
  });

  it("tags the layer button (P4-012), leaving parameters3 tags untouched", () => {
    const def = LAYERS.find((l) => l.id === "paaste");
    expect(layerParamTag(def!)).toBe("(P4-012)");
    expect(layerParamTag(LAYERS.find((l) => l.id === "parks")!)).toBe("(p19)");
  });

  it("locks the bands spec + radius (map kernel == scorer station leg)", () => {
    expect(paasteBonusSpecFor("paaste")).toEqual({
      kind: "bands",
      radiusM: 5000,
      one: 60,
      twoThree: 60,
      fourPlus: 60,
    });
    expect(bonusSpecFor("paaste")).toEqual(paasteBonusSpecFor("paaste"));
    expect(PAASTE_DECAY).toEqual({ paaste: 5.0 });
    expect(radiusKmFor("paaste")).toBe(5.0);
  });

  it("ships ZERO fallback points (never invent stations)", () => {
    const def = LAYERS.find((l) => l.id === "paaste")!;
    expect(def.fallbackPoints).toEqual([]);
    // The demo fallback therefore plots zero markers — absence renders
    // as absence, never as placed stations.
    expect(def.source).toContain("EI OLE");
    expect(def.source).toContain("hinnang");
  });

  it("carries NO Overpass fragment (Päästeamet data is not OSM data)", () => {
    expect(PAASTE_TAGS.paaste.length).toBeGreaterThan(10);
    for (const frag of ["n[", "node[", "way[", "rel[", "amenity="]) {
      expect(PAASTE_TAGS.paaste).not.toContain(frag);
    }
    expect(overpassQueryFor("paaste", TALLINN_BBOX)).not.toContain("amenity=");
  });

  it("keeps the wiring contract greppable", () => {
    expect(PAASTE_HOOK).toContain("PAASTE-HOOK (#493)");
  });
});

describe("paaste overlay (#493)", () => {
  it("paints paaste markers deep ember (red-950 — red-900 went to accblack on main #490)", () => {
    expect(overlayColorFor("paaste")).toBe("#450a0a");
    expect(overlayColorFor("paaste")).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("weights empty-layer points 1 (no t/a fields on komando points)", () => {
    expect(overlayWeight({ lat: 0, lon: 0 }, "paaste")).toBe(1);
    expect(selectOverlayPoints([], "paaste", 4)).toEqual([]);
  });

  it("legends coverage in Estonian with the dated-negative reason", () => {
    const legend = overlayLegendFor("paaste");
    expect(legend.length).toBeGreaterThan(10);
    expect(legend).toContain("5 km");
    expect(legend).toContain("60");
    expect(legend).toContain("EI OLE");
  });

  it("skips the raster window fetch (no master exists by decision)", async () => {
    const boom = () => {
      throw new Error("bands layers must never fetch a window");
    };
    await expect(
      fetchWindow("paaste", TALLINN_BBOX, boom as unknown as typeof fetch),
    ).resolves.toBeNull();
  });

  it("degrades honestly with no sidecar: SnapshotUnavailable, no raster (designed 500 path)", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-snap-paaste-"));
    try {
      await expect(loadSnapshotPoints("paaste", TALLINN_BBOX, dir)).rejects.toBeInstanceOf(
        SnapshotUnavailable,
      );
      // No raster master: honestly absent, Euclidean fallback downstream.
      const { raster, distance } = await loadLayerRaster("paaste", dir);
      expect(raster).toBeNull();
      expect(distance).toBe("euclidean");
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("paaste coverage field (client render path)", () => {
  const bbox = { minlon: 24.73, minlat: 59.43, maxlon: 24.76, maxlat: 59.445 };
  const spec = paasteBonusSpecFor("paaste");
  if (spec.kind !== "bands") throw new Error("paaste spec must be bands");

  it("renders all-unknown when nothing loaded (never a faked field)", () => {
    const field = buildScoredField([], bbox, 8, 8, 5.0, spec);
    expect(field.direct).not.toBeNull();
    for (const v of field.direct!) expect(v).toBeNaN();
  });

  it("renders flat-60 cover under a synthetic komando, unknown beyond 5 km", () => {
    const pts = [{ lon: 24.7454, lat: 59.4375 }];
    const field = buildScoredField(pts, bbox, 24, 12, 5.0, spec);
    expect(field.direct).not.toBeNull();
    const vals = [...field.direct!].filter((v) => !Number.isNaN(v));
    // 5 km radius over a ~3x1.6 km window covers every cell.
    expect(vals.length).toBe(24 * 12);
    for (const v of vals) expect(v).toBe(60);
  });
});
