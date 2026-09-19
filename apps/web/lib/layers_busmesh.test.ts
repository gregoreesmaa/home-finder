import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  BUSMESH_BONUS,
  BUSMESH_DECAY,
  BUSMESH_DEFS,
  BUSMESH_LAYER_IDS,
  BUSMESH_NO_METRO,
  BUSMESH_PARAMS,
  BUSMESH_RASTER_FILE,
  BUSMESH_TAGS,
  bonusSpecForBusmesh,
  isBusmeshLayerId,
} from "./layers_busmesh";
import {
  LAYERS,
  bonusSpecFor,
  overpassQueryFor,
  radiusKmFor,
} from "./layers";
import { overlayColorFor, overlayLegendFor, overlayWeight, selectOverlayPoints } from "./overlays";
import {
  clearSnapshotCache,
  loadLayerRaster,
  loadSnapshotPoints,
} from "./server/snapshot";

const TALLINN_BBOX = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

afterEach(() => {
  clearSnapshotCache();
});

describe("busmesh registry (#769)", () => {
  it("defines exactly the three window layers", () => {
    expect(BUSMESH_LAYER_IDS).toEqual(["busmesh", "busmesh-sat", "busmesh-sun"]);
    expect(BUSMESH_DEFS.map((d) => d.id)).toEqual(BUSMESH_LAYER_IDS);
  });

  it("shares p15 with transit + gtfsstops (third leg: transfer richness)", () => {
    // transit bakes default-filled departure density, gtfsstops
    // measured-only departure density, busmesh transfer richness —
    // same parameter, different legs, never double-scored.
    expect(BUSMESH_PARAMS).toEqual({ busmesh: 15, "busmesh-sat": 15, "busmesh-sun": 15 });
    for (const d of BUSMESH_DEFS) expect(d.paramIds).toEqual([15]);
  });

  it("merges into LAYERS via the BUSMESH-HOOK", () => {
    const ids = LAYERS.map((l) => l.id);
    expect(ids).toContain("busmesh");
    expect(ids).toContain("busmesh-sat");
    expect(ids).toContain("busmesh-sun");
    // BUSMESH-HOOK (#769): +3 transfer-node window layers (159 + 3 = 162).
    expect(ids.length).toBe(162);
  });

  it("labels schedules honestly in Estonian (never occupancy)", () => {
    for (const d of BUSMESH_DEFS) {
      expect(d.title).toContain("Ümberistumissõlmed");
      expect(d.source).toContain("sõiduplaan");
      expect(d.source).toContain("mitte täituvus");
      expect(d.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
    expect(BUSMESH_DEFS[0].source).toContain("437");
    expect(BUSMESH_DEFS[1].source).toContain("426");
    expect(BUSMESH_DEFS[2].source).toContain("423");
  });

  it("scores transfer richness (route counts, half 5, kicker off)", () => {
    for (const id of BUSMESH_LAYER_IDS) {
      expect(BUSMESH_BONUS[id]).toEqual({ kind: "trips", half: 5, modeBonus: 0, minModes: 2 });
      expect(bonusSpecForBusmesh(id)).toEqual(BUSMESH_BONUS[id]);
      expect(bonusSpecFor(id)).toEqual(BUSMESH_BONUS[id]);
      expect(isBusmeshLayerId(id)).toBe(true);
    }
    expect(bonusSpecForBusmesh("transit")).toBeUndefined();
    expect(isBusmeshLayerId("gtfsstops")).toBe(false);
  });

  it("uses the gtfsstops sigma and documents source tags", () => {
    expect(BUSMESH_DECAY).toEqual({ busmesh: 0.2, "busmesh-sat": 0.2, "busmesh-sun": 0.2 });
    expect(radiusKmFor("busmesh-sat")).toBe(0.2);
    expect(BUSMESH_TAGS.busmesh).toContain("bus_stop");
    expect(overpassQueryFor("busmesh", TALLINN_BBOX)).toContain("bus_stop");
  });

  it("builds no raster or metro master (overlay-only, Euclidean fallback)", () => {
    expect(BUSMESH_RASTER_FILE).toEqual({
      busmesh: "busmesh-walk-raster.json",
      "busmesh-sat": "busmesh-sat-walk-raster.json",
      "busmesh-sun": "busmesh-sun-walk-raster.json",
    });
    expect(BUSMESH_NO_METRO).toBe(true);
  });

  it("serves node points from a fixture sidecar, unknown stays out", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-snap-busmesh-"));
    await mkdir(join(dir, "osm"), { recursive: true });
    await writeFile(
      join(dir, "osm", "derived-busmesh.json"),
      JSON.stringify([
        { lon: 24.7369, lat: 59.4405, t: 30 },
        { lon: 24.75, lat: 59.44, t: 2 },
        { lon: "x", lat: 59.44 }, // junk, skipped
      ]),
    );
    try {
      const pts = await loadSnapshotPoints("busmesh", TALLINN_BBOX, dir);
      expect(pts).toEqual([
        { lat: 59.4405, lon: 24.7369, t: 30 },
        { lat: 59.44, lon: 24.75, t: 2 },
      ]);
      // No raster master: honestly absent, Euclidean fallback downstream.
      const { raster, distance } = await loadLayerRaster("busmesh", dir);
      expect(raster).toBeNull();
      expect(distance).toBe("euclidean");
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("busmesh overlay (#769)", () => {
  it("has distinct window-graded marker colors", () => {
    expect(overlayColorFor("busmesh")).toBe("#ff6d00");
    expect(overlayColorFor("busmesh-sat")).toBe("#ff9e00");
    expect(overlayColorFor("busmesh-sun")).toBe("#ffc300");
    for (const id of BUSMESH_LAYER_IDS) {
      expect(overlayColorFor(id)).toMatch(/^#[0-9a-f]{6}$/);
    }
  });

  it("sizes markers by route count", () => {
    expect(overlayWeight({ lat: 0, lon: 0, t: 30 }, "busmesh")).toBe(30);
    expect(overlayWeight({ lat: 0, lon: 0 }, "busmesh-sat")).toBe(1);
  });

  it("stride-samples nodes as points (every node equal, spread kept)", () => {
    const pts = Array.from({ length: 10 }, (_, i) => ({
      lat: 59 + i / 100,
      lon: 24.7,
      t: 10 - i,
    }));
    const out = selectOverlayPoints(pts, "busmesh-sun", 4);
    expect(out).toHaveLength(4);
    expect(out[0]).toEqual({ lon: 24.7, lat: 59, w: 10 });
    expect(selectOverlayPoints(pts, "busmesh-sun", 4)).toEqual(out);
    expect(out[3].lat).toBeGreaterThan(59.05);
  });

  it("legends transfer richness in Estonian, occupancy explicitly unknown", () => {
    for (const id of BUSMESH_LAYER_IDS) {
      const legend = overlayLegendFor(id);
      expect(legend.length).toBeGreaterThan(10);
      expect(legend).toContain("marsruut");
      expect(legend).toContain("sõiduplaan");
    }
  });
});
