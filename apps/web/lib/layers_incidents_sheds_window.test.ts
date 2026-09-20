// Windowed incidents + sheds levels (issue #783, slice 3): neither
// layer serves unwindowed momentary state — incidents names its 6 h
// window, sheds their shared 7-day window, each + vintage on every
// user-visible surface (layer def, overlay legend, /layers status
// line), and no momentary-state wording (täna/hetkel/elustabel/LIVE/
// hetkeseis/hetktõmmis) survives on those surfaces. Modeled on
// layers_datex_window.test.ts (slice 1). Hermetic (pure copy + TTL
// consts); live pulls stay pole-only by construction (server-side
// fetchPoleTable, pinned by layers_source.test.ts #762).
import { describe, expect, it } from "vitest";
import {
  INCIDENTS_DEFS,
  INCIDENTS_LAYER_IDS,
  INCIDENTS_TTL_S,
  INCIDENTS_WINDOW_ET,
  incidentsStatusLine,
} from "./layers_p4_incidents";
import {
  SHED_DEFS,
  SHED_LAYER_DEFS,
  SHED_LAYER_IDS,
  SHED_WINDOW_ET,
  shedStatusLine,
} from "./layers_p4_tomtom_sheds";
import { SHED_TTL_S } from "./server/sheds";
import { overlayLegendFor } from "./overlays";

/** Momentary-state wording banned from incidents/sheds user copy. */
const BANNED = [
  "täna",
  "hetkel",
  "elustabel",
  "LIVE",
  "hetkeseis",
  "hetktõmmis",
];

/** Every user-visible incidents string on every surface. */
function incidentsSurfaces(): string[] {
  const def = INCIDENTS_DEFS[0];
  return [
    def.title,
    def.goodLabel,
    def.badLabel,
    def.source,
    overlayLegendFor("incidents"),
    incidentsStatusLine(5, "3 h"),
    incidentsStatusLine(0, null),
  ];
}

/** Every user-visible sheds string on every surface. */
function shedsSurfaces(): string[] {
  const out: string[] = [];
  for (const id of SHED_LAYER_IDS) {
    const def = SHED_DEFS.find((d) => d.id === id);
    const reg = SHED_LAYER_DEFS.find((d) => d.id === id);
    if (!def || !reg) continue;
    out.push(def.title, def.goodLabel, def.badLabel, def.source, reg.source);
    out.push(overlayLegendFor(id));
  }
  out.push(shedStatusLine(4, "3 pv"));
  out.push(shedStatusLine(4, null));
  return out;
}

describe("incidents windowed levels (#783)", () => {
  it("names the 6 h window on every surface", () => {
    expect(INCIDENTS_LAYER_IDS).toEqual(["incidents"]);
    expect(INCIDENTS_DEFS.map((d) => d.id)).toEqual(INCIDENTS_LAYER_IDS);
    expect(INCIDENTS_DEFS[0].source).toContain(INCIDENTS_WINDOW_ET);
    expect(overlayLegendFor("incidents")).toContain(INCIDENTS_WINDOW_ET);
    expect(incidentsStatusLine(5, "3 h")).toContain(INCIDENTS_WINDOW_ET);
  });

  it("window mirrors the serve TTL (harvester parity)", () => {
    expect(INCIDENTS_TTL_S).toBe(6 * 3600);
    expect(INCIDENTS_WINDOW_ET).toContain("6 h");
  });

  it("status line carries window + vintage", () => {
    expect(incidentsStatusLine(5, "3 h")).toBe(
      "Intsidendid (TomTomi 6 h aken; vanus 3 h) · 5 punkti",
    );
    expect(incidentsStatusLine(0, null)).toBe(
      "Intsidendid (TomTomi 6 h aken) · 0 punkti",
    );
  });

  it("no momentary-state wording on any incidents surface", () => {
    for (const s of incidentsSurfaces()) {
      for (const word of BANNED) {
        expect(s).not.toContain(word);
      }
    }
  });
});

describe("sheds windowed levels (#783)", () => {
  it("names the shared 7-day window on every surface per layer", () => {
    expect(SHED_DEFS.map((d) => d.id)).toEqual(SHED_LAYER_IDS);
    expect(SHED_LAYER_DEFS.map((d) => d.id)).toEqual(SHED_LAYER_IDS);
    for (const id of SHED_LAYER_IDS) {
      const def = SHED_DEFS.find((d) => d.id === id);
      const reg = SHED_LAYER_DEFS.find((d) => d.id === id);
      expect(def?.source).toContain(SHED_WINDOW_ET);
      expect(reg?.source).toContain(SHED_WINDOW_ET);
      expect(overlayLegendFor(id)).toContain(SHED_WINDOW_ET);
    }
    expect(shedStatusLine(4, "3 pv")).toContain(SHED_WINDOW_ET);
  });

  it("window mirrors the serve TTL (harvester parity)", () => {
    expect(SHED_TTL_S).toBe(7 * 24 * 3600);
    expect(SHED_WINDOW_ET).toContain("7-päeva");
  });

  it("status line carries window + vintage", () => {
    expect(shedStatusLine(4, "3 pv")).toBe(
      "TomTomi tööulatus (5 hubi, 7-päeva aken, nädalatõmme; vanus 3 pv) · 4 polügooni",
    );
    expect(shedStatusLine(4, null)).toBe(
      "TomTomi tööulatus (5 hubi, 7-päeva aken, nädalatõmme) · 4 polügooni",
    );
  });

  it("no momentary-state wording on any sheds surface", () => {
    for (const s of shedsSurfaces()) {
      for (const word of BANNED) {
        expect(s).not.toContain(word);
      }
    }
  });
});
