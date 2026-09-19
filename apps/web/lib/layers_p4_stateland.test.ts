// State-land + auction polygon overlay tests (issue #615): one honest
// class choropleth (polygons only, never a gradient).
// Hermetic: inline area fixtures only, no network, no snapshot files.
import { describe, expect, it, vi } from "vitest";
import {
  STATELAND_ATTRIBUTION,
  STATELAND_BONUS,
  STATELAND_CLASS_FILL,
  STATELAND_CLASS_SCORE,
  STATELAND_CLASSES,
  STATELAND_DECAY,
  STATELAND_DEFS,
  STATELAND_HOOK,
  STATELAND_LAYER_IDS,
  STATELAND_NO_METRO,
  STATELAND_NO_RASTER,
  STATELAND_RASTER_FILE,
  STATELAND_TAGS,
  bonusSpecForStateland,
  fetchStatelandAreas,
  isStatelandArea,
  isStatelandLayerId,
  isStatelandPolygonOnlyLayer,
} from "./layers_p4_stateland";
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
  zone_id: "78401:101:0123",
  nimi: "",
  cls: "state",
  tunnus: "78401:101:0123",
  valitseja: "Kliimaministeerium",
  deadline: "",
  purpose: "",
  url: "",
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

const AUCTION = {
  zone_id: "3244621",
  nimi: "Müük (17.09.2026 kell 10:00)",
  cls: "auction",
  tunnus: "",
  valitseja: "",
  deadline: "17.09.2026",
  purpose: "Müük",
  url: "https://riigimaaoksjon.ee/public/auction/3244503/object/3244",
  b: [24.76, 59.43, 24.77, 59.44] as [number, number, number, number],
  r: [
    [
      [24.76, 59.43],
      [24.77, 59.43],
      [24.77, 59.44],
      [24.76, 59.44],
    ],
  ],
};

describe("stateland registry (#615)", () => {
  it("ships exactly one layer in the parameters4 namespace", () => {
    expect(STATELAND_LAYER_IDS).toEqual(["stateland"]);
    expect(STATELAND_DEFS.map((d) => d.id)).toEqual(["stateland"]);
    expect(STATELAND_DEFS[0].paramIds).toEqual([]);
    expect(STATELAND_DEFS[0].paramLabel).toBe("P4-riigimaa");
  });

  it("merges into LAYERS via the STATELAND-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 124 shipped layers on main (#613 seveso merged) +
    // 1 state/auction overlay (STATELAND-HOOK #615, 124 + 1) +
    // 1 quarry overlay (QUARRY-HOOK #614, 125 + 1) +
    // 1 drainage overlay (DRAINAGE-HOOK #616, 126 + 1) + soil (#617,
    // 127 + 1) + 1 etak overlay (ETAK-HOOK #618, 128 + 1) +
    // 1 relief overlay (RELIEF-HOOK #619, 129 + 1) + 1 canopy overlay
    // (CANOPY-HOOK #620, 130 + 1) + 1 buildings overlay
    // (BUILDINGS-HOOK #621, 131 + 1) + 1 density overlay
    // (DENSITY-HOOK #622, 132 + 1) + 1 forest overlay
    // (FOREST-HOOK #624, 133 + 1 = 134).....
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    // HARNO-HOOK (#687): +1 harno school layer (156 + 1 = 157).
    // VIIRS-HOOK (#719): +1 viirs brightness layer (157 + 1 = 158).
    // OUTAGE-HOOK (#729): +1 outage hetkeseis layer (158 + 1 = 159).
    // BUSMESH-HOOK (#769): +3 transfer-node window layers (159 + 3 = 162).
    expect(ids.length).toBe(162); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    expect(ids).toContain("stateland");
  });

  it("explains green=good / red=bad in Estonian with NO demo points", () => {
    for (const d of STATELAND_DEFS) {
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
    expect(STATELAND_HOOK).toContain("STATELAND-HOOK (#615)");
    expect(STATELAND_RASTER_FILE.stateland).toBe("stateland-walk-raster.json");
    expect(STATELAND_NO_RASTER).toBe(true);
    expect(STATELAND_NO_METRO).toBe(true);
  });
});

describe("stateland honesty (#615)", () => {
  it("frames the layer as an adjacency choropleth, never a state-free claim", () => {
    const def = STATELAND_DEFS[0];
    expect(def.title).toMatch(/Riigimaa/);
    expect(def.badLabel).toMatch(/teadmata, mitte riigimaavaba/);
    expect(def.source).toMatch(/Maa- ja Ruumiamet/);
    expect(def.source).toMatch(/metsasignaali EI OLE/);
  });

  it("carries the outside-unknown caveat in the legend (OTA PR #131 precedent)", () => {
    expect(overlayLegendFor("stateland")).toContain("väljaspool = teadmata, mitte riigimaavaba");
    expect(overlayLegendFor("stateland").length).toBeGreaterThan(10);
  });

  it("paints a distinct polygon color (distinct-color registry covers it)", () => {
    expect(overlayColorFor("stateland")).toBe("#083344");
  });

  it("locks two map classes with scorer parity (facts, never scores)", () => {
    expect(STATELAND_CLASS_FILL).toEqual({
      state: "#4d7c0f",
      auction: "#eab308",
    });
    // Scorer parity: dims_p4_riigimaa (other state land 60, auction
    // warning flag 40; forest 70 unobserved in this harvest).
    expect(STATELAND_CLASS_SCORE).toEqual({ state: 60, auction: 40 });
    expect(STATELAND_CLASSES).toEqual(["state", "auction"]);
  });

  it("attributes Maa- ja Ruumiamet (CC BY 4.0)", () => {
    expect(STATELAND_ATTRIBUTION).toContain("Maa- ja Ruumiamet");
    expect(STATELAND_ATTRIBUTION).toContain("CC BY 4.0");
  });
});

describe("stateland scoring contract (#615)", () => {
  it("locks the inert decay placeholder (polygons only: never evaluated)", () => {
    expect(STATELAND_DECAY).toEqual({ stateland: 0.5 });
    expect(radiusKmFor("stateland")).toBeCloseTo(0.5, 5);
  });

  it("locks the inert bonus placeholder (zero points + null raster)", () => {
    expect(STATELAND_BONUS).toEqual({ stateland: { kind: "area", half: 60 } });
    expect(bonusSpecFor("stateland")).toEqual({ kind: "area", half: 60 });
  });

  it("bonusSpecForStateland answers stateland and ignores other layers", () => {
    expect(bonusSpecForStateland("stateland")).toEqual({ kind: "area", half: 60 });
    expect(bonusSpecForStateland("parks")).toBeUndefined();
    expect(isStatelandLayerId("stateland")).toBe(true);
    expect(isStatelandLayerId("parks")).toBe(false);
    expect(isStatelandPolygonOnlyLayer("stateland")).toBe(true);
    expect(isStatelandPolygonOnlyLayer("parks")).toBe(false);
    expect(isStatelandPolygonOnlyLayer("roadsafety")).toBe(false);
  });
});

describe("stateland source and sidecar (#615)", () => {
  it("documents the KATRI + auction WFS registers (no Overpass source)", () => {
    expect(STATELAND_TAGS.stateland).toContain("state_property_ownership");
    expect(STATELAND_TAGS.stateland).toMatch(/Overpass-uta/);
  });

  it("carries the register provenance through the query builder", () => {
    const q = overpassQueryFor("stateland", TALLINN_BBOX);
    expect(q).toContain("state_property_ownership");
  });

  it("skips the raster window fetch (no master by decision — no designed 500)", async () => {
    const fetchImpl = vi.fn(() => {
      throw new Error("window must not be fetched for polygon-only layers");
    });
    expect(await fetchWindow("stateland", TALLINN_BBOX, fetchImpl)).toBeNull();
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("fetches state + auction parcels through the areas sidecar route", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA, AUCTION] }),
    });
    const areas = await fetchStatelandAreas(fetchImpl);
    expect(String(fetchImpl.mock.calls[0][0])).toBe("/api/layers/stateland/areas");
    expect(areas).toHaveLength(2);
    expect(areas?.[0].tunnus).toBe("78401:101:0123");
    expect(areas?.[1].deadline).toBe("17.09.2026");
    expect(areas?.[1].url).toContain("riigimaaoksjon.ee");
    expect(isStatelandArea(AUCTION)).toBe(true);
  });

  it("drops malformed areas and fails null (never faked)", async () => {
    const bad = { ...AREA, cls: "private", r: [[[24.7]]] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: [AREA, bad, null, 7] }),
    });
    expect(await fetchStatelandAreas(fetchImpl)).toHaveLength(1);
    const failImpl = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchStatelandAreas(failImpl)).toBeNull();
    const shapeImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ areas: "nope" }),
    });
    expect(await fetchStatelandAreas(shapeImpl)).toBeNull();
  });
});
