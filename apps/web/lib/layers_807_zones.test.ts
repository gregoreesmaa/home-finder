import { describe, expect, it } from "vitest";
import { bonusSpecFor, type BBoxLike } from "./layers";
import {
  ZONES807_HOOK,
  buildZoneField,
  delayZones,
  densifyLine,
  discZone,
  eelisZones,
  etakZones,
  floodZones,
  forestZones,
  harbourZones,
  kpoZones,
  maaparandusZones,
  noiseZones,
  planktprZones,
  quarryZones,
  ringsBbox,
  sevesoZones,
  shedZones,
  soilZones,
  statelandZones,
  zonePointInRing,
  zoneScoreAt,
  zonesForLayer,
  type Zone,
} from "./zones807";
import { FLOOD_ZONE_SCORE } from "./layers_flood";
import { EELIS_KIND_SCORE } from "./layers_eelis";
import { SEVESO_DANGER_SCORE } from "./layers_p4_seveso";
import { QUARRY_CLASS_SCORE } from "./layers_p4_quarry";
import { STATELAND_CLASS_SCORE } from "./layers_p4_stateland";
import { MAAPARANDUS_CLASS_SCORE } from "./layers_p4_maaparandus";
import { FOREST_CLASS_SCORE } from "./layers_p4_forest";
import { noiseScoreForArea } from "./layers_p4_noise";
import { harbourCellScoreFor, harbourPortBands } from "./layers_p4_harbour";
import { kpoScoreForZone } from "./layers_p4_kpo";
import { DELAY_BAND_SCORE } from "./layers_p4_delay";
import { SHED_BUDGET_SCORE } from "./layers_p4_tomtom_sheds";
import { planktprBandForColor } from "./layers_planktpr";
import type { FloodArea } from "./layers_flood";
import type { SevesoArea } from "./layers_p4_seveso";
import type { DelayArea } from "./layers_p4_delay";
import type { MaaparandusArea } from "./layers_p4_maaparandus";
import type { HarbourCell, HarbourPort } from "./layers_p4_harbour";

// 1x1 km square zone centred on (24.75, 59.44): half-side in degrees.
const C_LON = 24.75;
const C_LAT = 59.44;
const H = 0.0045; // ~250 m lat, ~255 m lon
const SQUARE: number[][][] = [
  [
    [C_LON - H, C_LAT - H],
    [C_LON + H, C_LAT - H],
    [C_LON + H, C_LAT + H],
    [C_LON - H, C_LAT + H],
    [C_LON - H, C_LAT - H],
  ],
];
const SQUARE_BBOX = ringsBbox(SQUARE)!;
const FAR = { lat: 58.0, lon: 23.0 };

function mkZone(score: number, rings: number[][][] = SQUARE): Zone {
  return { score, rings, bbox: ringsBbox(rings)! };
}

const ZONES_LAYERS = [
  "floodzone",
  "eeliskaitse",
  "eelisniit",
  "eelisraie",
  "seveso",
  "stateland",
  "quarry",
  "maaparandus",
  "soil",
  "etak",
  "forest",
  "noise",
  "harbour",
  "kpo",
  "delay-morning",
  "delay-midday",
  "delay-evening",
  "delay-offpeak",
  "delay-worst",
  "shed-15-peak",
  "shed-15-offpeak",
  "shed-30-peak",
  "shed-30-offpeak",
  "planktpr",
] as const;

describe("807 zones plumbing", () => {
  it("pins the hook marker", () => {
    expect(ZONES807_HOOK).toContain("807-HOOK (#807)");
  });

  it("every decided polygon layer returns the zones spec from bonusSpecFor", () => {
    for (const id of ZONES_LAYERS) {
      expect(bonusSpecFor(id), id).toEqual({ kind: "zones" });
    }
  });

  it("ray-casts inside vs outside (holes fail towards over-coverage)", () => {
    const ring = SQUARE[0];
    expect(zonePointInRing(C_LON, C_LAT, ring)).toBe(true);
    expect(zonePointInRing(FAR.lon, FAR.lat, ring)).toBe(false);
    expect(zonePointInRing(C_LON, C_LAT, [])).toBe(false);
    expect(zonePointInRing(C_LON, C_LAT, [[0, 0]])).toBe(false);
  });

  it("zoneScoreAt takes the worst covering zone; outside is unknown", () => {
    const zones = [mkZone(80), mkZone(30)];
    expect(zoneScoreAt(C_LAT, C_LON, zones)).toBe(30);
    expect(zoneScoreAt(C_LAT, C_LON, [mkZone(80)])).toBe(80);
    expect(zoneScoreAt(FAR.lat, FAR.lon, zones)).toBeNull();
    expect(zoneScoreAt(C_LAT, C_LON, [])).toBeNull();
    // Bbox prefilter: a far-away huge score never leaks in.
    expect(zoneScoreAt(C_LAT, C_LON, [{ score: 5, rings: [[[FAR.lon, FAR.lat]]], bbox: [23, 58, 23.001, 58.001] }])).toBeNull();
  });

  it("buildZoneField agrees with zoneScoreAt (indexed path)", () => {
    const bbox: BBoxLike = { minlon: 24.7, minlat: 59.4, maxlon: 24.8, maxlat: 59.48 };
    const small: number[][][] = [
      [
        [24.79, 59.47],
        [24.795, 59.47],
        [24.795, 59.475],
        [24.79, 59.475],
        [24.79, 59.47],
      ],
    ];
    const zones = [mkZone(35), mkZone(70, small)];
    const cols = 9;
    const rows = 9;
    const grid = buildZoneField(zones, bbox, cols, rows);
    let scored = 0;
    let unknown = 0;
    for (let iy = 0; iy < rows; iy++) {
      for (let ix = 0; ix < cols; ix++) {
        const lon = bbox.minlon + (ix / (cols - 1)) * (bbox.maxlon - bbox.minlon);
        const lat = bbox.minlat + (iy / (rows - 1)) * (bbox.maxlat - bbox.minlat);
        const want = zoneScoreAt(lat, lon, zones);
        const got = grid[iy * cols + ix];
        if (want === null) {
          expect(got).toBeNaN();
          unknown++;
        } else {
          expect(got).toBe(want);
          scored++;
        }
      }
    }
    expect(scored).toBeGreaterThan(0);
    expect(unknown).toBeGreaterThan(0);
  });

  it("empty zones stay all-unknown (never a faked zero)", () => {
    const bbox: BBoxLike = { minlon: 24.7, minlat: 59.4, maxlon: 24.8, maxlat: 59.48 };
    const grid = buildZoneField([], bbox, 4, 4);
    expect(grid.length).toBe(16);
    for (const v of grid) expect(v).toBeNaN();
  });

  it("discZone degrades null on garbage; densifyLine walks long segments", () => {
    expect(discZone(NaN, C_LAT, 500, 50)).toBeNull();
    expect(discZone(C_LON, C_LAT, -5, 50)).toBeNull();
    const disc = discZone(C_LON, C_LAT, 500, 45)!;
    expect(zoneScoreAt(C_LAT, C_LON, [disc])).toBe(45);
    expect(zoneScoreAt(58.0, 23.0, [disc])).toBeNull();
    // ~1 km line densified every 50 m yields 20+ points, endpoints kept.
    const line = [
      [24.7, 59.44],
      [24.72, 59.44],
    ];
    const dense = densifyLine(line, 50);
    expect(dense.length).toBeGreaterThanOrEqual(20);
    expect(dense[0]).toEqual(line[0]);
    expect(dense[dense.length - 1]).toEqual(line[1]);
    expect(densifyLine([], 50)).toEqual([]);
  });
});

describe("807 zones assemblers (direction + decay + unknown)", () => {
  it("floodzone: inside 35, outside unknown", () => {
    expect(FLOOD_ZONE_SCORE).toBe(35);
    const areas = [{ b: SQUARE_BBOX, r: SQUARE } as FloodArea];
    const zones = floodZones(areas);
    expect(zones).toHaveLength(1);
    expect(zoneScoreAt(C_LAT, C_LON, zones)).toBe(35);
    expect(zoneScoreAt(FAR.lat, FAR.lon, zones)).toBeNull();
    expect(floodZones(null)).toEqual([]);
    expect(floodZones([])).toEqual([]);
  });

  it("eelis: kind bands (kaitse/niit 55, raie 45)", () => {
    expect(EELIS_KIND_SCORE).toEqual({ kaitse: 55, niit: 55, raie: 45 });
    const areas = [{ kiht: "kaitse", b: SQUARE_BBOX, r: SQUARE } as unknown as import("./layers_eelis").EelisArea];
    expect(zoneScoreAt(C_LAT, C_LON, eelisZones("eeliskaitse", areas))).toBe(55);
    expect(zoneScoreAt(C_LAT, C_LON, eelisZones("eelisniit", areas))).toBe(55);
    expect(zoneScoreAt(C_LAT, C_LON, eelisZones("eelisraie", areas))).toBe(45);
    expect(zoneScoreAt(FAR.lat, FAR.lon, eelisZones("eeliskaitse", areas))).toBeNull();
    expect(eelisZones("parks", areas)).toEqual([]);
    expect(eelisZones("eeliskaitse", null)).toEqual([]);
  });

  it("seveso/quarry/stateland: class bands, min-wins", () => {
    expect(SEVESO_DANGER_SCORE).toEqual({ toxic: 20, heat: 35, overpressure: 35, combustion: 50, unknown: 30 });
    expect(QUARRY_CLASS_SCORE).toEqual({ active: 25, exploration: 55 });
    expect(STATELAND_CLASS_SCORE).toEqual({ state: 60, auction: 40 });
    const sev = [{ danger: "toxic", b: SQUARE_BBOX, r: SQUARE } as unknown as SevesoArea];
    expect(zoneScoreAt(C_LAT, C_LON, sevesoZones(sev))).toBe(20);
    const sevHeat = [{ danger: "heat", b: SQUARE_BBOX, r: SQUARE } as unknown as SevesoArea];
    expect(zoneScoreAt(C_LAT, C_LON, sevesoZones(sevHeat))).toBe(35);
    expect(zoneScoreAt(FAR.lat, FAR.lon, sevesoZones(sev))).toBeNull();
    const active = [{ cls: "active", b: SQUARE_BBOX, r: SQUARE } as unknown as import("./layers_p4_quarry").QuarryArea];
    expect(zoneScoreAt(C_LAT, C_LON, quarryZones(active))).toBe(25);
    const watch = [{ cls: "exploration", b: SQUARE_BBOX, r: SQUARE } as unknown as import("./layers_p4_quarry").QuarryArea];
    expect(zoneScoreAt(C_LAT, C_LON, quarryZones(watch))).toBe(55);
    expect(zoneScoreAt(FAR.lat, FAR.lon, quarryZones(active))).toBeNull();
    const state = [{ cls: "state", b: SQUARE_BBOX, r: SQUARE } as unknown as import("./layers_p4_stateland").StatelandArea];
    expect(zoneScoreAt(C_LAT, C_LON, statelandZones(state))).toBe(60);
    const auction = [{ cls: "auction", b: SQUARE_BBOX, r: SQUARE } as unknown as import("./layers_p4_stateland").StatelandArea];
    expect(zoneScoreAt(C_LAT, C_LON, statelandZones(auction))).toBe(40);
    expect(zoneScoreAt(FAR.lat, FAR.lon, statelandZones(state))).toBeNull();
  });

  it("soil/etak: server-stamped score reused verbatim; garbage skipped", () => {
    const soil = [{ cls: "saviliiv", score: 85, b: SQUARE_BBOX, r: SQUARE } as unknown as import("./layers_p4_soil").SoilArea];
    expect(zoneScoreAt(C_LAT, C_LON, soilZones(soil))).toBe(85);
    const bad = [{ cls: "saviliiv", score: 999, b: SQUARE_BBOX, r: SQUARE } as unknown as import("./layers_p4_soil").SoilArea];
    expect(soilZones(bad)).toEqual([]);
    const etak = [{ cls: "yard_green", score: 70, b: SQUARE_BBOX, r: SQUARE } as unknown as import("./layers_p4_etak").EtakArea];
    expect(zoneScoreAt(C_LAT, C_LON, etakZones(etak))).toBe(70);
    expect(zoneScoreAt(FAR.lat, FAR.lon, etakZones(etak))).toBeNull();
  });

  it("forest: age-class cores (fresh 30, 3-10a 60, >10a 70)", () => {
    expect(FOREST_CLASS_SCORE).toEqual({ 1: 70, 2: 60, 3: 30 });
    const mk = (cls: number) => [{ cls, b: SQUARE_BBOX, r: SQUARE } as unknown as import("./layers_p4_forest").ForestArea];
    expect(zoneScoreAt(C_LAT, C_LON, forestZones(mk(3)))).toBe(30);
    expect(zoneScoreAt(C_LAT, C_LON, forestZones(mk(2)))).toBe(60);
    expect(zoneScoreAt(C_LAT, C_LON, forestZones(mk(1)))).toBe(70);
    expect(forestZones(mk(9))).toEqual([]);
  });

  it("noise: leg bands with min-wins (binding leg)", () => {
    expect(noiseScoreForArea("Lden", 45)).toBe(85);
    expect(noiseScoreForArea("Lden", 55)).toBe(65);
    expect(noiseScoreForArea("Lden", 65)).toBe(40);
    expect(noiseScoreForArea("Lden", 80)).toBe(20);
    expect(noiseScoreForArea("Lnight", 40)).toBe(85);
    expect(noiseScoreForArea("Lnight", 70)).toBe(20);
    expect(noiseScoreForArea("Lmax", 55)).toBeNull();
    const areas = [
      { leg: "Lden", band_db: 45, b: SQUARE_BBOX, r: SQUARE },
      { leg: "Lnight", band_db: 70, b: SQUARE_BBOX, r: SQUARE },
    ] as unknown as import("./layers_p4_noise").NoiseArea[];
    // Binding (lowest) leg wins: min(85, 20) = 20.
    expect(zoneScoreAt(C_LAT, C_LON, noiseZones(areas))).toBe(20);
    expect(zoneScoreAt(FAR.lat, FAR.lon, noiseZones(areas))).toBeNull();
  });

  it("harbour: nested port discs + cell quads", () => {
    expect(harbourPortBands(1)).toEqual([[500, 45], [1500, 65]]);
    expect(harbourPortBands(2)).toEqual([[500, 70], [1500, 80]]);
    expect(harbourPortBands(3)).toEqual([[500, 75], [1500, 85]]);
    expect(harbourPortBands(9)).toBeNull();
    expect(harbourCellScoreFor(50)).toBe(70);
    expect(harbourCellScoreFor(10)).toBe(80);
    expect(harbourCellScoreFor(1)).toBe(85);
    expect(harbourCellScoreFor(0)).toBeNull();
    const ports = [{ function: 1, lon: C_LON, lat: C_LAT } as HarbourPort];
    const zones = harbourZones(ports, []);
    expect(zones.length).toBe(2);
    // On the port: min(45, 65) = 45.
    expect(zoneScoreAt(C_LAT, C_LON, zones)).toBe(45);
    const cells = [{ lon: C_LON, lat: C_LAT, pleasure: 60, all: 100 } as HarbourCell];
    expect(zoneScoreAt(C_LAT, C_LON, harbourZones([], cells))).toBe(70);
    // Marina amenity beats nothing: fn3 on top reads 75, min-wins.
    const marina = [{ function: 3, lon: C_LON, lat: C_LAT } as HarbourPort];
    expect(zoneScoreAt(C_LAT, C_LON, harbourZones(marina, []))).toBe(75);
    expect(harbourZones(null, null)).toEqual([]);
  });

  it("kpo: ban/conditioned keywords, unknown stays unscored", () => {
    expect(kpoScoreForZone("Ehituskeeld")).toBe(20);
    expect(kpoScoreForZone("Tagasilöök 4 m")).toBe(35);
    expect(kpoScoreForZone("Tingimuslik ehitus")).toBe(50);
    expect(kpoScoreForZone("Teavitusega ala")).toBe(65);
    expect(kpoScoreForZone("Elektripaigaldise kaitsevöönd")).toBe(50);
    expect(kpoScoreForZone(" suvaline ", "muinsuskaitse")).toBe(50);
    expect(kpoScoreForZone("müstiline vöönd")).toBeNull();
    // Ban wins over conditioned wording in one label.
    expect(kpoScoreForZone("Ehituskeeluvöönd, kooskõlastus")).toBe(20);
    const areas = [{ voond: "Ehituskeeld", family: "", b: SQUARE_BBOX, r: SQUARE } as unknown as import("./layers_p4_kpo").KpoArea];
    expect(zoneScoreAt(C_LAT, C_LON, kpoZones(areas))).toBe(20);
    const unknown = [{ voond: "müstiline", family: "", b: SQUARE_BBOX, r: SQUARE } as unknown as import("./layers_p4_kpo").KpoArea];
    expect(kpoZones(unknown)).toEqual([]);
  });

  it("delay: hour-band ribbons; thin cells emit no zone (scorer NULL parity)", () => {
    const mk = (factor: number | null) =>
      [{ corridor: "c1", factors: { "hommikune tipp": factor }, ns: {}, rep: null, b: SQUARE_BBOX, r: SQUARE } as unknown as DelayArea];
    expect(zoneScoreAt(C_LAT, C_LON, delayZones("delay-morning", mk(1.0)))).toBe(DELAY_BAND_SCORE.free);
    expect(zoneScoreAt(C_LAT, C_LON, delayZones("delay-morning", mk(1.2)))).toBe(DELAY_BAND_SCORE.steady);
    expect(zoneScoreAt(C_LAT, C_LON, delayZones("delay-morning", mk(1.5)))).toBe(DELAY_BAND_SCORE.slow);
    expect(zoneScoreAt(C_LAT, C_LON, delayZones("delay-morning", mk(2.0)))).toBe(DELAY_BAND_SCORE.jammed);
    // Thin/missing factor: no zone (unknown, never free-flow).
    expect(delayZones("delay-morning", mk(null))).toEqual([]);
    // Wrong hour key for the layer: no zone.
    expect(delayZones("delay-midday", mk(1.0))).toEqual([]);
    expect(delayZones("parks", mk(1.0))).toEqual([]);
  });

  it("maaparandus: network/invalid polygons + outflow line buffers", () => {
    expect(MAAPARANDUS_CLASS_SCORE).toEqual({ network: 55, invalid: 40, outflow: 45 });
    const net = [{ cls: "network", b: SQUARE_BBOX, r: SQUARE } as unknown as MaaparandusArea];
    expect(zoneScoreAt(C_LAT, C_LON, maaparandusZones(net))).toBe(55);
    const inv = [{ cls: "invalid", b: SQUARE_BBOX, r: SQUARE } as unknown as MaaparandusArea];
    expect(zoneScoreAt(C_LAT, C_LON, maaparandusZones(inv))).toBe(40);
    // Outflow centerline: buffered discs score 45 along the line.
    const out = [{ cls: "outflow", b: SQUARE_BBOX, l: [[[C_LON, C_LAT], [C_LON + 0.001, C_LAT]]] } as unknown as MaaparandusArea];
    const zones = maaparandusZones(out);
    expect(zones.length).toBeGreaterThan(0);
    expect(zoneScoreAt(C_LAT, C_LON, zones)).toBe(45);
    expect(zoneScoreAt(FAR.lat, FAR.lon, zones)).toBeNull();
    expect(maaparandusZones(null)).toEqual([]);
  });

  it("sheds: [lat, lon] rings flip to GeoJSON; budget bands", () => {
    expect(SHED_BUDGET_SCORE).toEqual({ 900: 80, 1800: 70 });
    // Ring in [lat, lon] order (shed wire order).
    const latlon = SQUARE[0].map(([lon, lat]) => [lat, lon]) as Array<[number, number]>;
    const areas = [{ hub: "Kesklinn", ring: latlon }];
    expect(zoneScoreAt(C_LAT, C_LON, shedZones("shed-15-peak", areas))).toBe(80);
    expect(zoneScoreAt(C_LAT, C_LON, shedZones("shed-30-peak", areas))).toBe(70);
    expect(zoneScoreAt(FAR.lat, FAR.lon, shedZones("shed-15-peak", areas))).toBeNull();
    expect(shedZones("shed-15-peak", null)).toEqual([]);
    expect(shedZones("shed-15-peak", [{ hub: "x", ring: [[59.4, 24.7]] }])).toEqual([]);
  });

  it("planktpr: band rides back off the fill color; unknown colors skipped", () => {
    expect(planktprBandForColor("#16a34a")).toBe(80);
    expect(planktprBandForColor("#a3a32b")).toBe(60);
    expect(planktprBandForColor("#ea580c")).toBe(35);
    expect(planktprBandForColor("#dc2626")).toBe(20);
    expect(planktprBandForColor("#ffffff")).toBeNull();
    expect(planktprBandForColor(null)).toBeNull();
    const fills = [{ rings: SQUARE, color: "#16a34a" }];
    expect(zoneScoreAt(C_LAT, C_LON, planktprZones(fills))).toBe(80);
    expect(planktprZones([{ rings: SQUARE, color: "#ffffff" }])).toEqual([]);
    expect(planktprZones(null)).toEqual([]);
  });

  it("zonesForLayer dispatches per layer; points layers read []", () => {
    const ctx = { floodAreas: [{ b: SQUARE_BBOX, r: SQUARE } as FloodArea] };
    expect(zonesForLayer("floodzone", ctx)).toHaveLength(1);
    expect(zonesForLayer("parks", ctx)).toEqual([]);
    expect(zonesForLayer("fixit", ctx)).toEqual([]);
    expect(zonesForLayer("relief", ctx)).toEqual([]);
    expect(zonesForLayer("floodzone")).toEqual([]);
  });
});
