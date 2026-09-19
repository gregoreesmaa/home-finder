// Drainage-network wetness + outflow overlay tests (issue #616): one
// honest class choropleth (polygons only, never a gradient).
// Hermetic: inline area fixtures only, no network, no snapshot files.
import { describe, expect, it, vi } from "vitest";
import {
  MAAPARANDUS_ATTRIBUTION,
  MAAPARANDUS_BONUS,
  MAAPARANDUS_CLASS_FILL,
  MAAPARANDUS_CLASS_SCORE,
  MAAPARANDUS_CLASSES,
  MAAPARANDUS_DECAY,
  MAAPARANDUS_DEFS,
  MAAPARANDUS_HOOK,
  MAAPARANDUS_LAYER_IDS,
  MAAPARANDUS_NO_METRO,
  MAAPARANDUS_NO_RASTER,
  MAAPARANDUS_RASTER_FILE,
  MAAPARANDUS_TAGS,
  bonusSpecForMaaparandus,
  fetchMaaparandusAreas,
  isMaaparandusArea,
  isMaaparandusLayerId,
  isMaaparandusPolygonOnlyLayer,
} from "./layers_p4_maaparandus";
import {
  LAYERS,
  bonusSpecFor,
  fetchWindow,
  overpassQueryFor,
  radiusKmFor,
  type BBoxLike,
} from "./layers";
import { overlayColorFor, overlayLegendFor } from "./overlays";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

const AREA = {
  zone_id: "5111040011290",
  nimi: "Allika5",
  cls: "network",
  ms_kood: "5111040011290",
  ms_url: "https://portaal.agri.ee/avalik/#/maaparandus/systeem/5111040011290",
  b: [24.74, 59.43, 24.75, 59.44] as [number, number, number, number],
  r: [
    [
      [24.74, 59.43],
      [24.75, 59.43],
      [24.75, 59.44],
      [24.74, 59.44],
    ],
  ],
};

const LINE = {
  zone_id: "7",
  nimi: "Kraav",
  cls: "outflow",
  ms_kood: "1",
  ms_url: "",
  b: [24.76, 59.43, 24.77, 59.44] as [number, number, number, number],
  l: [
    [
      [24.76, 59.43],
      [24.77, 59.44],
    ],
  ],
};

describe("drainage registry (#616)", () => {
  it("ships exactly one layer in the parameters4 namespace", () => {
    expect(MAAPARANDUS_LAYER_IDS).toEqual(["maaparandus"]);
    expect(MAAPARANDUS_DEFS.map((d) => d.id)).toEqual(["maaparandus"]);
    expect(MAAPARANDUS_DEFS[0].paramIds).toEqual([]);
    expect(MAAPARANDUS_DEFS[0].paramLabel).toBe("P4-kuivendus");
  });

  it("merges into LAYERS via the DRAINAGE-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 124 shipped layers on main (#613 seveso merged) + stateland
    // (#615) + quarry (#614) + soil (#617) + 1 drainage overlay
    // (DRAINAGE-HOOK #616, 127 + 1) + 1 etak overlay
    // (ETAK-HOOK #618, 128 + 1) + 1 relief overlay
    // (RELIEF-HOOK #619, 129 + 1) + 1 canopy overlay
    // (CANOPY-HOOK #620, 130 + 1) + 1 buildings overlay
    // (BUILDINGS-HOOK #621, 131 + 1) + 1 density overlay
    // (DENSITY-HOOK #622, 132 + 1) + 1 forest overlay
    // (FOREST-HOOK #624, 133 + 1 = 134).....
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    // HARNO-HOOK (#687): +1 harno school layer (156 + 1 = 157).
    // VIIRS-HOOK (#719): +1 viirs brightness layer (157 + 1 = 158).
    expect(ids.length).toBe(158); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    expect(ids).toContain("maaparandus");
  });

  it("explains green=good / red=bad in Estonian with NO demo points", () => {
    for (const d of MAAPARANDUS_DEFS) {
      expect(d.title.length).toBeGreaterThan(0);
      expect(d.goodLabel.length).toBeGreaterThan(0);
      expect(d.badLabel.length).toBeGreaterThan(0);
      expect(d.source.length).toBeGreaterThan(0);
      // Polygons-only pin: a demo point would paint a fake gradient
      // splat, so the def carries none (generic labels test carves
      // polygon-only layers out of its fallbackPoints assertion).
      expect(d.fallbackPoints).toEqual([]);
    }
  });

  it("pins the hook marker + raster file + no-raster/no-metro verdict", () => {
    expect(MAAPARANDUS_HOOK).toContain("DRAINAGE-HOOK (#616)");
    expect(MAAPARANDUS_RASTER_FILE.maaparandus).toBe("maaparandus-walk-raster.json");
    expect(MAAPARANDUS_NO_RASTER).toBe(true);
    expect(MAAPARANDUS_NO_METRO).toBe(true);
  });
});

describe("drainage honesty (#616)", () => {
  it("frames the layer as a network choropleth, never a dryness claim", () => {
    const def = MAAPARANDUS_DEFS[0];
    expect(def.title).toMatch(/Kuivendus/);
    expect(def.badLabel).toMatch(/teadmata, mitte kuiv/);
    expect(def.source).toMatch(/Kliimaministeerium/);
    expect(def.source).toMatch(/hooldus-kohustust EI OLE/);
  });

  it("carries the outside-unknown caveat in the legend (OTA PR #131 precedent)", () => {
    expect(overlayLegendFor("maaparandus")).toContain("väljaspool = teadmata, mitte kuiv");
    expect(overlayLegendFor("maaparandus").length).toBeGreaterThan(10);
  });

  it("paints a distinct polygon color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("maaparandus")).toBe("#1c1917");
  });

  it("locks three map classes with scorer parity (facts, never scores)", () => {
    expect(MAAPARANDUS_CLASS_FILL).toEqual({
      network: "#2563eb",
      invalid: "#92400e",
      outflow: "#38bdf8",
    });
    // Scorer parity: dims_p4_maaparandus (network 55 / invalid 40 /
    // outflow-near 45; duty always NULL).
    expect(MAAPARANDUS_CLASS_SCORE).toEqual({ network: 55, invalid: 40, outflow: 45 });
    expect(MAAPARANDUS_CLASSES).toEqual(["network", "invalid", "outflow"]);
  });

  it("attributes Kliimaministeerium (CC BY 4.0)", () => {
    expect(MAAPARANDUS_ATTRIBUTION).toContain("Kliimaministeerium");
    expect(MAAPARANDUS_ATTRIBUTION).toContain("CC BY 4.0");
  });
});

describe("drainage scoring contract (#616)", () => {
  it("locks the inert decay placeholder (polygons only: never evaluated)", () => {
    expect(MAAPARANDUS_DECAY).toEqual({ maaparandus: 0.5 });
    expect(radiusKmFor("maaparandus")).toBeCloseTo(0.5, 5);
  });

  it("locks the inert bonus placeholder (zero points + null raster)", () => {
    expect(MAAPARANDUS_BONUS).toEqual({ maaparandus: { kind: "area", half: 60 } });
    expect(bonusSpecFor("maaparandus")).toEqual({ kind: "area", half: 60 });
  });

  it("bonusSpecForMaaparandus answers drainage and ignores other layers", () => {
    expect(bonusSpecForMaaparandus("maaparandus")).toEqual({ kind: "area", half: 60 });
    expect(bonusSpecForMaaparandus("parks")).toBeUndefined();
    expect(isMaaparandusLayerId("maaparandus")).toBe(true);
    expect(isMaaparandusLayerId("parks")).toBe(false);
    expect(isMaaparandusPolygonOnlyLayer("maaparandus")).toBe(true);
    expect(isMaaparandusPolygonOnlyLayer("parks")).toBe(false);
    expect(isMaaparandusPolygonOnlyLayer("roadsafety")).toBe(false);
  });
});

describe("drainage source and sidecar (#616)", () => {
  it("documents the maaparandus WFS registers (no Overpass source)", () => {
    expect(MAAPARANDUS_TAGS.maaparandus).toContain("msr_vork");
    expect(MAAPARANDUS_TAGS.maaparandus).toMatch(/Overpass-uta/);
  });

  it("carries the register provenance through the query builder", () => {
    const q = overpassQueryFor("maaparandus", TALLINN_BBOX);
    expect(q).toContain("msr_vork");
  });

  it("skips the raster window fetch (no master by decision — no designed 500)", async () => {
    const fetchImpl = vi.fn(() => {
      throw new Error("window must not be fetched for polygon-only layers");
    });
    expect(await fetchWindow("maaparandus", TALLINN_BBOX, fetchImpl)).toBeNull();
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("fetches network polygons + outflow lines through the areas sidecar route", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA, LINE] }),
    });
    const areas = await fetchMaaparandusAreas(fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0])).toBe("/api/layers/maaparandus/areas");
    expect(areas).toHaveLength(2);
    expect(areas?.[0].ms_kood).toBe("5111040011290");
    expect(areas?.[1].cls).toBe("outflow");
    expect(isMaaparandusArea(LINE)).toBe(true);
    expect(isMaaparandusArea({ ...LINE, l: [[[24.7]]] })).toBe(false);
  });

  it("drops malformed areas and fails null (never faked)", async () => {
    const bad = { ...AREA, cls: "ditch", r: [[[24.7]]] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA, bad, null, 7] }),
    });
    expect(await fetchMaaparandusAreas(fetchImpl)).toHaveLength(1);
    const failImpl = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchMaaparandusAreas(failImpl)).toBeNull();
    const shapeImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: "nope" }),
    });
    expect(await fetchMaaparandusAreas(shapeImpl)).toBeNull();
  });
});
