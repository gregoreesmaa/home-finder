// Repaint-wiring guard (#664): every overlay slice the component owns
// must ride the repaint effect's paintOverlay call AND its dep list.
// The delay layer shipped with data fetching + ladder + status all
// working, yet rendered nothing, because delayAreas/delayBand were
// missing from exactly this call. Source-pinned (no RTL/jsdom in repo).
import { describe, expect, it } from "vitest";
import fs from "node:fs";

const SRC = fs.readFileSync(
  new URL("../components/ValueHeatMap.tsx", import.meta.url),
  "utf8",
);

// Paint-slot slices: call object + dep list must carry every one.
const SLICES = [
  "outlines",
  "floodAreas",
  "maaParcels",
  "eelisAreas",
  "sevesoAreas",
  "statelandAreas",
  "quarryAreas",
  "maaparandusAreas",
  "soilAreas",
  "etakAreas",
  "reliefTint",
  "canopyTint",
  "buildingsTint",
  "densityAreas",
  "forestAreas",
  "noiseAreas",
  "kpoAreas",
  "delayAreas",
  "delayBand",
  "harbourCells",
  "harbourPorts",
  "overlayPoints",
  "usePolygons",
  "overlayColor",
  "showOverlay",
];

function repaintRegion(): string {
  const start = SRC.indexOf("// Overlay rides the map lifecycle");
  expect(start).toBeGreaterThan(-1);
  const end = SRC.indexOf("]);", start);
  expect(end).toBeGreaterThan(start);
  return SRC.slice(start, end);
}

describe("repaint effect wiring", () => {
  it("carries every overlay slice in the paint call and deps", () => {
    const region = repaintRegion();
    for (const s of SLICES) {
      const hits = region.match(new RegExp(`\\b${s}\\b`, "g")) ?? [];
      // once in the paintOverlay object, once in the dep list
      expect(hits.length, `${s} rides call + deps`).toBeGreaterThanOrEqual(2);
    }
  });

  it("has exactly one delay branch in the paint ladder (no dead dupe)", () => {
    const hits =
      SRC.match(/if \(opts\.delayAreas && opts\.delayAreas\.length > 0\)/g) ??
      [];
    expect(hits.length).toBe(1);
  });
});
