import { describe, expect, it } from "vitest";
import {
  bonusAt,
  buildDistanceField,
  buildScoredField,
  fieldResolution,
  fieldToRgba,
  proximityAt,
  sampleField,
  sampleScored,
  scoredAt,
} from "./distanceField";
import type { AreaSpec, BBoxLike, BonusSpec } from "./layers";

const BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

/** 11x11 unit grid: (0.5, 0.5) sits exactly on node (5, 5). */
const UNIT: BBoxLike = { minlon: 0, minlat: 0, maxlon: 1, maxlat: 1 };
const AREA: AreaSpec = { kind: "area", half: 3 };

describe("area-proportional score (parks)", () => {
  it("two 10-ha parks equal one 20-ha park at the same spot", () => {
    const pair = buildScoredField(
      [
        { lon: 0.5, lat: 0.5, a: 10 },
        { lon: 0.5, lat: 0.5, a: 10 },
      ],
      UNIT, 11, 11, 0.35, AREA,
    );
    const single = buildScoredField([{ lon: 0.5, lat: 0.5, a: 20 }], UNIT, 11, 11, 0.35, AREA);
    // 100·20/23 ≈ 87 on the node, identical both ways.
    expect(sampleScored(pair, 0.5, 0.5)?.value).toBeCloseTo(87, 0);
    expect(sampleScored(single, 0.5, 0.5)?.value).toBeCloseTo(87, 0);
  });

  it("saturates toward 100 for huge areas, tiny areas read near zero", () => {
    const huge = buildScoredField([{ lon: 0.5, lat: 0.5, a: 1000 }], UNIT, 11, 11, 0.35, AREA);
    const hugeV = sampleScored(huge, 0.5, 0.5)?.value ?? NaN;
    expect(hugeV).toBeLessThanOrEqual(100);
    expect(hugeV).toBeGreaterThan(99);
    // A lone pocket playground (0.1 ha) peaks just above the noise floor.
    const pocket = buildScoredField([{ lon: 0.5, lat: 0.5, a: 0.1 }], UNIT, 11, 11, 0.35, AREA);
    expect(sampleScored(pocket, 0.5, 0.5)?.value).toBeCloseTo(3.2, 0);
  });

  it("far from everything reads null, never zero", () => {
    const s = buildScoredField([{ lon: 0.5, lat: 0.5, a: 57 }], UNIT, 11, 11, 0.35, AREA);
    expect(sampleScored(s, 0.02, 0.02)).toBeNull();
    expect(scoredAt(s, 0, 0)).toBeNull();
  });
});
describe("area halo (parks)", () => {
  it("a big park grades from green core to amber edge over ~2 sigma", () => {
    // Micro grid (~9 m cells, sigma ~40 cells): center node (116, 116).
    const micro: BBoxLike = { minlon: 24.7, minlat: 59.4, maxlon: 24.736, maxlat: 59.4185 };
    const s = buildScoredField([{ lon: 24.718, lat: 59.40925, a: 57 }], micro, 233, 233, 0.35, AREA);
    // On top of 57 ha: 100·57/60 = 95.
    expect(scoredAt(s, 116, 116)).toBeCloseTo(95, 0);
    // ~2 sigma out the halo reads mid-amber, still defined.
    const edge = scoredAt(s, 196, 116) ?? NaN;
    expect(edge).toBeGreaterThan(60);
    expect(edge).toBeLessThan(85);
  });

  it("sub-hectare scraps below the noise floor read as no-data", () => {
    const s = buildScoredField([{ lon: 0.5, lat: 0.5, a: 0.01 }], UNIT, 11, 11, 0.35, AREA);
    expect(scoredAt(s, 5, 5)).toBeNull();
  });
});

describe("trips-weighted transit", () => {
  // Score = 100·S/(S+500) over nearby weekday departures: frequency is the
  // resource being summed (like park hectares), not a multiplier.
  const trips: BonusSpec = { kind: "trips", half: 500, modeBonus: 10, minModes: 2 };

  it("is linear in departures: two half-busy stops equal one busy stop", () => {
    const lon = 24.5 + (50 / 99) * (BBOX.maxlon - BBOX.minlon);
    const lat = 59.35 + (18 / 39) * (BBOX.maxlat - BBOX.minlat);
    const solo = buildScoredField(
      [{ lon, lat, t: 974, tags: { highway: "bus_stop" } }],
      BBOX, 100, 40, 0.35, trips,
    );
    const pair = buildScoredField(
      [
        { lon, lat, t: 500, tags: { highway: "bus_stop" } },
        { lon, lat, t: 500, tags: { highway: "bus_stop" } },
      ],
      BBOX, 100, 40, 0.35, trips,
    );
    expect(scoredAt(solo, 50, 18)).toBeCloseTo(66.1, 0);
    expect(scoredAt(pair, 50, 18)).toBeCloseTo(66.7, 0);
    expect(Math.abs((scoredAt(pair, 50, 18) ?? 0) - (scoredAt(solo, 50, 18) ?? 0))).toBeLessThan(2);
  });

  it("a rare stop next door reads ~5; a hub 200 m out reads 10x better", () => {
    const lon = 24.5 + (50 / 99) * (BBOX.maxlon - BBOX.minlon);
    const lat = 59.35 + (18 / 39) * (BBOX.maxlat - BBOX.minlat);
    const rare = buildScoredField(
      [{ lon, lat, t: 42, tags: { highway: "bus_stop" } }],
      BBOX, 100, 40, 0.35, trips,
    );
    const hub = buildScoredField(
      [{ lon, lat, t: 5000, tags: { highway: "bus_stop" } }],
      BBOX, 100, 40, 0.35, trips,
    );
    // Glued to a rare stop: barely above the noise floor.
    expect(scoredAt(rare, 50, 18)).toBeCloseTo(7.7, 0);
    // One node over (~229 m): the hub dwarfs the next-door rare stop.
    const hubFar = scoredAt(hub, 51, 18) ?? 0;
    expect(hubFar).toBeGreaterThan(75);
    expect(hubFar).toBeGreaterThan(10 * (scoredAt(rare, 50, 18) ?? 0));
    // And the rare stop 200 m out is no worse in any meaningful sense.
    const rareFar = scoredAt(rare, 51, 18) ?? -1;
    expect(rareFar).toBeGreaterThan(3);
    expect(Math.abs(rareFar - (scoredAt(rare, 50, 18) ?? 0))).toBeLessThan(2);
  });

  it("caps at 100 and reads no-data without departures", () => {
    const lon = 24.5 + (50 / 99) * (BBOX.maxlon - BBOX.minlon);
    const lat = 59.35 + (18 / 39) * (BBOX.maxlat - BBOX.minlat);
    const mega = buildScoredField(
      [{ lon, lat, t: 1e6, tags: { highway: "bus_stop" } }],
      BBOX, 100, 40, 0.35, trips,
    );
    expect(scoredAt(mega, 50, 18)).toBeLessThanOrEqual(100);
    expect(scoredAt(mega, 50, 18)).toBeGreaterThan(99);
    const unknown = buildScoredField(
      [{ lon, lat, tags: { highway: "bus_stop" } }],
      BBOX, 100, 40, 0.35, trips,
    );
    expect(scoredAt(unknown, 50, 18)).toBeNull();
  });
});

describe("distance field", () => {
  it("is zero at a feature and rises with distance", () => {
    const f = buildDistanceField([{ lon: 24.7, lat: 59.42 }], BBOX, 200, 75);
    const ix = Math.round(((24.7 - BBOX.minlon) / (BBOX.maxlon - BBOX.minlon)) * (f.cols - 1));
    const iy = Math.round(((59.42 - BBOX.minlat) / (BBOX.maxlat - BBOX.minlat)) * (f.rows - 1));
    expect(f.distKm[iy * f.cols + ix]).toBeLessThan(0.2);
    expect(proximityAt(f, ix, iy, 1.0)).toBeGreaterThan(90);
    // ~2 km east: deep red, but defined (wash, not transparent).
    // (<25, not <20: the nearest node sits wherever the lattice puts it.)
    const jx = Math.round(((24.73 - BBOX.minlon) / (BBOX.maxlon - BBOX.minlon)) * (f.cols - 1));
    const v = proximityAt(f, jx, iy, 1.0) as number;
    expect(v).toBeLessThan(25);
    expect(v).toBeGreaterThan(0);
  });

  it("matches brute force within half a cell diagonal", () => {
    const pts = [
      { lon: 24.6, lat: 59.4 },
      { lon: 24.75, lat: 59.45 },
    ];
    const f = buildDistanceField(pts, BBOX, 80, 30);
    const cellKm = Math.hypot(
      ((BBOX.maxlon - BBOX.minlon) * 111.32 * Math.cos(59.42 * (Math.PI / 180))) / 80,
      ((BBOX.maxlat - BBOX.minlat) * 110.57) / 30,
    );
    let worst = 0;
    for (let iy = 0; iy < f.rows; iy += 3) {
      for (let ix = 0; ix < f.cols; ix += 3) {
        const lon = BBOX.minlon + (ix / (f.cols - 1)) * (BBOX.maxlon - BBOX.minlon);
        const lat = BBOX.minlat + (iy / (f.rows - 1)) * (BBOX.maxlat - BBOX.minlat);
        const brute = Math.min(
          ...pts.map((p) => {
            const dx = (lon - p.lon) * 111.32 * Math.cos(lat * (Math.PI / 180));
            const dy = (lat - p.lat) * 110.57;
            return Math.hypot(dx, dy);
          }),
        );
        worst = Math.max(worst, Math.abs(f.distKm[iy * f.cols + ix] - brute));
      }
    }
    expect(worst).toBeLessThan(cellKm / 2 + 1e-9);
  });

  it("empty input is transparent everywhere (nothing known)", () => {
    const f = buildDistanceField([], BBOX, 40, 15);
    const rgba = fieldToRgba(f, 1.0);
    for (let i = 3; i < rgba.length; i += 4) expect(rgba[i]).toBe(0);
  });

  it("known bbox washes opaque (far = bad, not unknown)", () => {
    const f = buildDistanceField([{ lon: 24.7, lat: 59.42 }], BBOX, 40, 15);
    const rgba = fieldToRgba(f, 1.0);
    const corner = ((f.rows - 1) * f.cols + (f.cols - 1)) * 4;
    expect(rgba[corner + 3]).toBe(255); // far corner painted, dark red
    const [r, g] = [rgba[corner], rgba[corner + 1]];
    expect(r).toBeGreaterThan(g);
  });

  it("hover sample is null outside the bbox", () => {
    // Fine grid: the point falls between nodes ~0.15 km out, reading
    // high green (exact 100 only lands on a node).
    const f = buildDistanceField([{ lon: 24.7, lat: 59.42 }], BBOX, 200, 75);
    expect(sampleField(f, 24.7, 59.42, 1.0)?.value).toBeGreaterThan(80);
    expect(sampleField(f, 0, 0, 1.0)).toBeNull();
  });

  it("area direct score saturates on an exact node", () => {
    const lon = 24.5 + (50 / 99) * (BBOX.maxlon - BBOX.minlon);
    const lat = 59.35 + (18 / 39) * (BBOX.maxlat - BBOX.minlat);
    const big = buildScoredField([{ lon, lat, a: 57 }], BBOX, 100, 40, 1.2, AREA);
    expect(scoredAt(big, 50, 18)).toBeCloseTo(95, 0);
    const small = buildScoredField([{ lon, lat, a: 3 }], BBOX, 100, 40, 1.2, AREA);
    expect(scoredAt(small, 50, 18)).toBeCloseTo(50, 0);
    // Coarse grid: between-nodes readback lands high green, never above 100.
    const hit = sampleScored(big, 24.7, 59.42);
    expect(hit?.value).toBeGreaterThan(80);
    expect(hit?.value).toBeLessThanOrEqual(100);
  });

  it("transit adds a mode kicker only for multi-mode service", () => {
    const spec: BonusSpec = { kind: "trips", half: 500, modeBonus: 10, minModes: 2 };
    const bus = { tags: { highway: "bus_stop" } };
    const tram = { tags: { railway: "tram_stop" } };
    const twoBus = buildScoredField(
      [
        { lon: 24.7, lat: 59.42, t: 400, ...bus },
        { lon: 24.703, lat: 59.42, t: 400, ...bus },
      ],
      BBOX,
      100,
      40,
      0.8,
      spec,
    );
    const mixed = buildScoredField(
      [
        { lon: 24.7, lat: 59.42, t: 400, ...bus },
        { lon: 24.703, lat: 59.42, t: 400, ...tram },
      ],
      BBOX,
      100,
      40,
      0.8,
      spec,
    );
    const at = (s: { field: { cols: number } }, lon: number) =>
      bonusAt(
        s as Parameters<typeof bonusAt>[0],
        Math.round(((lon - BBOX.minlon) / (BBOX.maxlon - BBOX.minlon)) * 99),
        18,
      );
    // Same departures; only the mode mix differs.
    expect(at(twoBus, 24.7015)).toBe(0);
    expect(at(mixed, 24.7015)).toBe(10);
  });

  it("school variety beats kindergarten monoculture", () => {
    const spec: BonusSpec = {
      kind: "variety",
      key: "amenity",
      values: ["school", "kindergarten", "university", "college"],
      per: 12,
      cap: 36,
    };
    const mono = buildScoredField(
      [
        { lon: 24.7, lat: 59.42, tags: { amenity: "kindergarten" } },
        { lon: 24.703, lat: 59.42, tags: { amenity: "kindergarten" } },
      ],
      BBOX,
      100,
      40,
      1.5,
      spec,
    );
    const ladder = buildScoredField(
      [
        { lon: 24.7, lat: 59.42, tags: { amenity: "kindergarten" } },
        { lon: 24.703, lat: 59.42, tags: { amenity: "school" } },
        { lon: 24.706, lat: 59.42, tags: { amenity: "university" } },
      ],
      BBOX,
      100,
      40,
      1.5,
      spec,
    );
    const at = (s: Parameters<typeof bonusAt>[0], lon: number) =>
      bonusAt(
        s,
        Math.round(((lon - BBOX.minlon) / (BBOX.maxlon - BBOX.minlon)) * (s.field.cols - 1)),
        18,
      );
    expect(at(mono, 24.7015)).toBeLessThan(1);
    expect(at(ladder, 24.703)).toBeGreaterThan(20);
    expect(at(ladder, 24.703)).toBeLessThanOrEqual(36);
  });

  it("combined score never exceeds 100", () => {
    const s = buildScoredField(
      Array.from({ length: 6 }, () => ({ lon: 24.7, lat: 59.42, a: 100 })),
      BBOX,
      100,
      40,
      1.2,
      AREA,
    );
    expect(scoredAt(s, 50, 20) ?? -1).toBeLessThanOrEqual(100);
    expect(sampleScored(s, 24.7, 59.42)?.value).toBeLessThanOrEqual(100);
  });

  it("resolution adapts to view span and clamps sanely", () => {
    const wide = fieldResolution(
      { minlon: 21.5, minlat: 57.3, maxlon: 28.5, maxlat: 59.9 },
      1.2,
    );
    expect(wide.cols).toBeLessThanOrEqual(2048);
    expect(wide.cols).toBeGreaterThan(400);
    const city = fieldResolution(
      { minlon: 24.6, minlat: 59.38, maxlon: 24.9, maxlat: 59.5 },
      1.2,
    );
    expect(city.cols).toBeGreaterThanOrEqual(128);
    expect(city.cols).toBeLessThan(wide.cols);
    expect(city.rows).toBeGreaterThan(0);
  });
});

describe("quiet-kind cleanliness (G07D env-health)", () => {
  const QUIET: BonusSpec = { kind: "quiet", halfM: 500 };

  it("reads 0 on the source, ~50 at halfM, near 100 when far", () => {
    // Source at grid centre; UNIT degree ~ 57x110 km so halfM=500 m is
    // sub-cell: use a Tallinn-scale bbox instead for real distances.
    const box: BBoxLike = { minlon: 24.69, minlat: 59.46, maxlon: 24.71, maxlat: 59.47 };
    const s = buildScoredField([{ lon: 24.7, lat: 59.465 }], box, 41, 41, 0.5, QUIET);
    expect(scoredAt(s, 20, 20)).toBe(0);
    const half = sampleScored(s, 24.7 + 0.5 / 57.29, 59.465);
    expect(half?.value).toBeCloseTo(50, 0);
    const far = sampleScored(s, 24.69, 59.47);
    expect(far?.value).toBeGreaterThan(60);
  });

  it("agrifield halves at 800 m (drift scale)", () => {
    // Wider box: 800 m east of the source must stay inside the view.
    const box: BBoxLike = { minlon: 24.69, minlat: 59.46, maxlon: 24.72, maxlat: 59.47 };
    const s = buildScoredField([{ lon: 24.7, lat: 59.465 }], box, 41, 41, 0.8, {
      kind: "quiet",
      halfM: 800,
    });
    const half = sampleScored(s, 24.7 + 0.8 / 57.29, 59.465);
    expect(half?.value).toBeCloseTo(50, 0);
  });

  it("never exceeds 100 and reads null where nothing is known", () => {
    const box: BBoxLike = { minlon: 24.69, minlat: 59.46, maxlon: 24.71, maxlat: 59.47 };
    const s = buildScoredField([{ lon: 24.7, lat: 59.465 }], box, 21, 21, 0.5, QUIET);
    for (let iy = 0; iy < 21; iy++) {
      for (let ix = 0; ix < 21; ix++) {
        expect(scoredAt(s, ix, iy) ?? -1).toBeLessThanOrEqual(100);
      }
    }
    // Points outside the view: the field is all +Inf -> null, never faked.
    const empty = buildScoredField([{ lon: 0, lat: 0 }], box, 11, 11, 0.5, QUIET);
    expect(scoredAt(empty, 5, 5)).toBeNull();
  });
});
