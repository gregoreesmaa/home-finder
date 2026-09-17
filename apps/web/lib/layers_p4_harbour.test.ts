// Tests for layers_p4_harbour.ts (issue #627): guards, fetch,
// bbox filter, cell fills. Fixtures only, never live.

import { describe, expect, it } from "vitest";
import {
  HARBOUR_BONUS,
  HARBOUR_CELL_FILL,
  HARBOUR_DECAY,
  HARBOUR_DEFS,
  HARBOUR_HOOK,
  HARBOUR_NO_METRO,
  HARBOUR_NO_RASTER,
  fetchHarbourAreas,
  harbourCellFillKey,
  harbourPointsIn,
  isHarbourCell,
  isHarbourLayerId,
  isHarbourPolygonOnlyLayer,
  isHarbourPort,
} from "./layers_p4_harbour";

const PORT = {
  harbour_id: "port-168",
  name: "PIRITA SADAM",
  function: 2,
  function_label: "väikesadam (tasulised, <24 m)",
  address: "Purje tn 13",
  lon: 24.82345,
  lat: 59.46812,
};

const CELL = { lon: 24.83, lat: 59.47, pleasure: 53, all: 63 };

describe("harbour areas (#627)", () => {
  it("accepts joined ports and cells, refuses bad functions", () => {
    expect(isHarbourPort(PORT)).toBe(true);
    expect(isHarbourPort({ ...PORT, function: 9 })).toBe(false);
    expect(isHarbourCell(CELL)).toBe(true);
    expect(isHarbourCell({ ...CELL, pleasure: "53" })).toBe(false);
    expect(isHarbourPort(null)).toBe(false);
  });

  it("grades pleasure counts pale-to-deep without scaling", () => {
    expect(harbourCellFillKey(53)).toBe("high");
    expect(harbourCellFillKey(12)).toBe("mid");
    expect(harbourCellFillKey(3)).toBe("low");
    expect(harbourCellFillKey(0)).toBe("unknown");
    expect(HARBOUR_CELL_FILL[harbourCellFillKey(53)]).toBe(
      HARBOUR_CELL_FILL.high,
    );
  });

  it("fetches ports + cells from the harbour areas endpoint", async () => {
    const fetchImpl = async () =>
      new Response(
        JSON.stringify({ ports: [PORT, { nope: 1 }], cells: [CELL] }),
      );
    const areas = await fetchHarbourAreas(fetchImpl as typeof fetch);
    expect(areas?.ports).toHaveLength(1);
    expect(areas?.cells).toHaveLength(1);
  });

  it("fails null on transport error or malformed body (never faked)", async () => {
    const boom = async () => {
      throw new Error("down");
    };
    expect(await fetchHarbourAreas(boom as typeof fetch)).toBeNull();
    const bad = async () => new Response(JSON.stringify({ ports: [] }));
    expect(await fetchHarbourAreas(bad as typeof fetch)).toBeNull();
  });

  it("filters ports to the view bbox", () => {
    const pts = harbourPointsIn([PORT], {
      minlon: 24.8,
      minlat: 59.4,
      maxlon: 24.9,
      maxlat: 59.5,
    });
    expect(pts).toEqual([{ lat: 59.46812, lon: 24.82345 }]);
    expect(
      harbourPointsIn([PORT], {
        minlon: 25.0,
        minlat: 59.4,
        maxlon: 25.1,
        maxlat: 59.5,
      }),
    ).toEqual([]);
  });
});

describe("harbour registry (#627)", () => {
  it("is a points+fills P4 layer with no fallback points", () => {
    expect(isHarbourLayerId("harbour")).toBe(true);
    expect(isHarbourPolygonOnlyLayer("harbour")).toBe(false);
    expect(HARBOUR_DEFS[0].paramLabel).toBe("P4-sadam");
    expect(HARBOUR_DEFS[0].fallbackPoints).toEqual([]);
  });

  it("gates the no-value-field rule (page passes [] heat points)", () => {
    // The /layers page passes points={[]} exactly when this gate is
    // true: port dots ride overlayPoints, cells ride harbourCells, and
    // the shader must stay unpainted (outside = NULL, never a red
    // wash). Neighbour layers keep their own heat behavior.
    expect(isHarbourLayerId("harbour")).toBe(true);
    expect(isHarbourLayerId("noise")).toBe(false);
    expect(isHarbourLayerId("parks")).toBe(false);
  });

  it("pins inert placeholders + vintage + hook marker", () => {
    expect(HARBOUR_DECAY.harbour).toBe(1.5);
    expect(HARBOUR_BONUS.harbour.kind).toBe("area");
    expect(HARBOUR_NO_RASTER).toBe(true);
    expect(HARBOUR_NO_METRO).toBe(true);
    expect(HARBOUR_HOOK).toContain("HARBOUR-HOOK (#627)");
  });
});
