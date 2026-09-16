import { describe, expect, it } from "vitest";
import {
  MARUKOV_BANDS,
  MARUKOV_DEFAULTS,
  MARUKOV_DEFS,
  MARUKOV_GRAIN,
  MARUKOV_LAYER_IDS,
} from "./layers_maru";

describe("marukov intra-city grain (#521)", () => {
  it("states the KOV-grain expectation in every legend source", () => {
    expect(MARUKOV_GRAIN).toContain("ühetooniline");
    expect(MARUKOV_GRAIN).toMatch(/EI VENITATA/);
    for (const d of MARUKOV_DEFS) {
      expect(d.source).toContain(MARUKOV_GRAIN);
    }
  });

  it("does not restretch bands to manufacture contrast", () => {
    // Locked calibration (same rows as layers_maru.test.ts): Tallinn
    // stays one band per layer by construction, never stretched.
    expect(MARUKOV_BANDS).toEqual({
      kovkasv: [[-5, 75], [0, 65], [5, 50], [10, 40]],
      kovkaive: [[300, 80], [100, 65], [30, 50]],
      kovkiirus: [[10, 70], [-10, 55]],
    });
    expect(MARUKOV_DEFAULTS).toEqual({ kovkasv: 30, kovkaive: 35, kovkiirus: 40 });
    expect(MARUKOV_LAYER_IDS).toEqual(["kovkasv", "kovkaive", "kovedas", "kovkiirus"]);
  });

  it("names the missing finer grain instead of faking it", () => {
    const kaive = MARUKOV_DEFS.find((d) => d.id === "kovkaive");
    expect(kaive?.source).toMatch(/linnaosa\/asumi-käivet .* EI OLE/);
  });
});
