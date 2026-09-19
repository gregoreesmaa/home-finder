// Windowed DATEX levels (issue #783, slice 1): no DATEX layer serves
// unwindowed momentary state — every feed names its observation window
// + vintage on every user-visible surface (layer def, overlay legend,
// /layers status line), and no momentary-state wording
// (hetkel/elustabel/LIVE/hetkeseis/hetktõmmis) survives on those
// surfaces. Also pins the dead live-provenance removal: no route emits
// it, and the /layers page carries no live label anymore. Hermetic
// (pure copy + source grep); live pulls stay pole-only by construction
// (server-side fetchPoleTable, pinned by layers_source.test.ts #762).
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import {
  DATEX_DEFS,
  DATEX_LAYER_IDS,
  DATEX_TTL_S,
  DATEX_WINDOW_ET,
  datexStatusLine,
} from "./layers_datex";
import { overlayLegendFor } from "./overlays";

const PAGE_SRC = fs.readFileSync(
  new URL("../app/layers/page.tsx", import.meta.url),
  "utf8",
);
const ROUTE_SRC = fs.readFileSync(
  new URL("../app/api/layers/[layer]/route.ts", import.meta.url),
  "utf8",
);
const OVERLAY_ROUTE_SRC = fs.readFileSync(
  new URL("../app/api/layers/[layer]/overlay/route.ts", import.meta.url),
  "utf8",
);

/** Momentary-state wording banned from DATEX user-visible copy. */
const BANNED = ["hetkel", "elustabel", "LIVE", "hetkeseis", "hetktõmmis"];

/** Every user-visible DATEX string on every surface. */
function datexSurfaces(): string[] {
  const out: string[] = [];
  for (const id of DATEX_LAYER_IDS) {
    const def = DATEX_DEFS.find((d) => d.id === id);
    if (!def) continue;
    out.push(def.title, def.goodLabel, def.badLabel, def.source);
    out.push(overlayLegendFor(id));
    out.push(datexStatusLine(id, 5, "3 h"));
    out.push(datexStatusLine(id, 0, null));
  }
  return out;
}

describe("datex windowed levels (#783)", () => {
  it("names the observation window on every surface per feed", () => {
    expect(DATEX_DEFS.map((d) => d.id)).toEqual(DATEX_LAYER_IDS);
    for (const id of DATEX_LAYER_IDS) {
      const def = DATEX_DEFS.find((d) => d.id === id);
      expect(def).toBeDefined();
      const window = DATEX_WINDOW_ET[id];
      expect(def?.source).toContain(window);
      expect(overlayLegendFor(id)).toContain(window);
      expect(datexStatusLine(id, 5, "3 h")).toContain(window);
    }
  });

  it("windows mirror the serve TTLs (harvester parity)", () => {
    expect(Object.keys(DATEX_WINDOW_ET).sort()).toEqual(
      Object.keys(DATEX_TTL_S).sort(),
    );
    expect(DATEX_WINDOW_ET["datex-restrictions"]).toContain("24 h");
    expect(DATEX_WINDOW_ET["datex-srti"]).toContain("6 h");
    for (const id of DATEX_LAYER_IDS.filter((l) =>
      ["datex-weather", "datex-counters", "datex-cameras"].includes(l),
    )) {
      expect(DATEX_WINDOW_ET[id]).toContain("1 h");
    }
    expect(DATEX_WINDOW_ET["datex-truckpark"]).toContain("30-päeva");
  });

  it("status line carries window + vintage, geometry-less stays honest", () => {
    expect(datexStatusLine("datex-counters", 5, "3 h")).toBe(
      "TarkTee DATEX loendurid (1 h aken, tunni tõmme; vanus 3 h) · 5 punkti",
    );
    expect(datexStatusLine("datex-restrictions", 0, null)).toBe(
      "TarkTee DATEX piirangud (24 h aken, öine tõmme) · olukorrad geomeetriata",
    );
  });

  it("no momentary-state wording on any DATEX surface", () => {
    for (const s of datexSurfaces()) {
      for (const word of BANNED) {
        expect(s).not.toContain(word);
      }
    }
  });

  it("dead live provenance is gone (no emitter, no label)", () => {
    for (const src of [ROUTE_SRC, OVERLAY_ROUTE_SRC]) {
      expect(src).not.toMatch(/provenance:\s*["']live["']/);
    }
    expect(PAGE_SRC).not.toContain("LIVE:");
    expect(PAGE_SRC).not.toContain('provenance === "live"');
  });
});
