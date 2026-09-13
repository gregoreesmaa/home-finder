import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  GTFSSTOPS_BONUS,
  GTFSSTOPS_DECAY,
  GTFSSTOPS_DEFS,
  GTFSSTOPS_LAYER_IDS,
  GTFSSTOPS_NO_METRO,
  GTFSSTOPS_PARAMS,
  GTFSSTOPS_RASTER_FILE,
  GTFSSTOPS_TAGS,
  bonusSpecForGtfsstops,
  isGtfsstopsLayerId,
} from "./layers_gtfsstops";
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

describe("gtfsstops registry (#483)", () => {
  it("defines exactly the GTFS stop overlay layer", () => {
    expect(GTFSSTOPS_LAYER_IDS).toEqual(["gtfsstops"]);
    expect(GTFSSTOPS_DEFS.map((d) => d.id)).toEqual(GTFSSTOPS_LAYER_IDS);
  });

  it("shares p15 with transit (measured-only vs default-filled point set)", () => {
    // fiber/mobile share p51 (see layers_batch10c.ts) — same precedent.
    expect(GTFSSTOPS_PARAMS).toEqual({ gtfsstops: 15 });
    expect(GTFSSTOPS_DEFS[0].paramIds).toEqual([15]);
  });

  it("merges into LAYERS via the GTFS-HOOK", () => {
    const ids = LAYERS.map((l) => l.id);
    expect(ids).toContain("gtfsstops");
    // OSMDAILY-HOOK (#482) rebased in: 77 + 6 daily-life + 1 gtfsstops.
    // RSAFE-HOOK (#481): +1 road-safety.
    // P4-031-HOOK (#484): +senscom DIY-air overlay (86 with gtfsstops + roadsafety + senscom).
    // STATKOV-HOOK (#485): +3 choropleth layers (86 + 3).
    // P4PARK-HOOK (#479): +1 parking layer (89 + 1).
    // MARUKOV-HOOK (#486): +4 MARU KOV choropleths (90 + 4).
    // FLOOD-HOOK (#487): +1 flood-risk polygon overlay (94 + 1) + 2 P4OSM (P4OSM-HOOK #480, 95 + 2).
    // OOKLA-HOOK (#489): +2 quarterly-tile layers (97 + 2).
    // ACCBLACK-HOOK (#490): +1 blackspot layer (99 + 1).
    expect(ids.length).toBe(100);
  });

  it("labels schedules honestly in Estonian (never ridership)", () => {
    const d = GTFSSTOPS_DEFS[0];
    expect(d.title).toContain("GTFS");
    expect(d.source).toContain("sõiduplaan");
    expect(d.source).toContain("mitte täituvus");
    expect(d.source).toContain("peatus.ee");
    expect(d.source).toContain("Elron");
    expect(d.fallbackPoints.length).toBeGreaterThanOrEqual(2);
  });

  it("scores scheduled Wednesday departures (transit parity, half 1500)", () => {
    expect(GTFSSTOPS_BONUS).toEqual({
      gtfsstops: { kind: "trips", half: 1500, modeBonus: 10, minModes: 2 },
    });
    expect(bonusSpecForGtfsstops("gtfsstops")).toEqual(GTFSSTOPS_BONUS.gtfsstops);
    expect(bonusSpecForGtfsstops("transit")).toBeUndefined();
    expect(bonusSpecFor("gtfsstops")).toEqual(GTFSSTOPS_BONUS.gtfsstops);
    expect(isGtfsstopsLayerId("gtfsstops")).toBe(true);
    expect(isGtfsstopsLayerId("transit")).toBe(false);
  });

  it("uses the transit sigma and documents source tags", () => {
    expect(GTFSSTOPS_DECAY).toEqual({ gtfsstops: 0.2 });
    expect(radiusKmFor("gtfsstops")).toBe(0.2);
    expect(GTFSSTOPS_TAGS.gtfsstops).toContain("bus_stop");
    expect(GTFSSTOPS_TAGS.gtfsstops).toContain("railway");
    expect(overpassQueryFor("gtfsstops", TALLINN_BBOX)).toContain("bus_stop");
  });

  it("builds no raster or metro master (overlay-only, Euclidean fallback)", () => {
    expect(GTFSSTOPS_RASTER_FILE).toEqual({
      gtfsstops: "gtfsstops-walk-raster.json",
    });
    expect(GTFSSTOPS_NO_METRO).toBe(true);
  });

  it("serves GTFS + Elron points from a fixture sidecar, unknown stays untagged", async () => {
    const dir = await mkdtemp(join(tmpdir(), "hf-snap-gtfs-"));
    await mkdir(join(dir, "osm"), { recursive: true });
    await writeFile(
      join(dir, "osm", "derived-gtfsstops.json"),
      JSON.stringify([
        { lon: 24.6094, lat: 59.41135, t: 39 },
        { lon: 24.75, lat: 59.44 }, // no Wednesday service: unknown, never 0
        {
          lon: 24.7369,
          lat: 59.4405,
          tags: { railway: "station", public_transport: "station" },
        },
        { lon: "x", lat: 59.44 }, // junk, skipped
      ]),
    );
    try {
      const pts = await loadSnapshotPoints("gtfsstops", TALLINN_BBOX, dir);
      expect(pts).toEqual([
        { lat: 59.41135, lon: 24.6094, t: 39 },
        { lat: 59.44, lon: 24.75 },
        {
          lat: 59.4405,
          lon: 24.7369,
          tags: { railway: "station", public_transport: "station" },
        },
      ]);
      // No raster master: honestly absent, Euclidean fallback downstream.
      const { raster, distance } = await loadLayerRaster("gtfsstops", dir);
      expect(raster).toBeNull();
      expect(distance).toBe("euclidean");
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

describe("gtfsstops overlay (#483)", () => {
  it("has a distinct marker color", () => {
    expect(overlayColorFor("gtfsstops")).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("sizes markers by scheduled departures, Elron stations at one", () => {
    expect(overlayWeight({ lat: 0, lon: 0, t: 974 }, "gtfsstops")).toBe(974);
    expect(overlayWeight({ lat: 0, lon: 0 }, "gtfsstops")).toBe(1);
    expect(
      overlayWeight(
        { lat: 0, lon: 0, tags: { railway: "station" } },
        "gtfsstops",
      ),
    ).toBe(1);
  });

  it("stride-samples stops as points (every stop equal, spread kept)", () => {
    const pts = Array.from({ length: 10 }, (_, i) => ({
      lat: 59 + i / 100,
      lon: 24.7,
      t: 100 - i,
    }));
    const out = selectOverlayPoints(pts, "gtfsstops", 4);
    expect(out).toHaveLength(4);
    expect(out[0]).toEqual({ lon: 24.7, lat: 59, w: 100 });
    expect(selectOverlayPoints(pts, "gtfsstops", 4)).toEqual(out);
    expect(out[3].lat).toBeGreaterThan(59.05);
  });

  it("legends schedules in Estonian, ridership explicitly unknown", () => {
    const legend = overlayLegendFor("gtfsstops");
    expect(legend.length).toBeGreaterThan(10);
    expect(legend).toContain("1500");
    expect(legend).toContain("sõiduplaan");
    expect(legend).toContain("EI OLE");
  });
});
