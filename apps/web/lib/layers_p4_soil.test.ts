import { describe, expect, it } from "vitest";
import { LAYERS } from "./layers";
import {
  SOIL_ATTRIBUTION,
  SOIL_BONUS,
  SOIL_CLASSES,
  SOIL_CLASS_FILL,
  SOIL_CLASS_SCORE,
  SOIL_DECAY,
  SOIL_DEFS,
  SOIL_HOOK,
  SOIL_NO_METRO,
  SOIL_NO_RASTER,
  SOIL_RASTER_FILE,
  SOIL_TAGS,
  bonusSpecForSoil,
  decodeSoilFamily,
  fetchSoilAreas,
  isSoilArea,
  isSoilLayerId,
  isSoilPolygonOnlyLayer,
  soilClassForFamily,
  type SoilArea,
} from "./layers_p4_soil";

describe("soil family decode (#617)", () => {
  it("decodes §V Tabel 1 texture tokens (subscripts normalized)", () => {
    expect(decodeSoilFamily("ls₂;l50-100/s", "Go")).toBe("liivsavi");
    expect(decodeSoilFamily("sl", "Lk")).toBe("saviliiv");
    expect(decodeSoilFamily("l", "LkIg")).toBe("liiv");
    expect(decodeSoilFamily("l200", "LII")).toBe("liiv");
    expect(decodeSoilFamily("pl", "LG")).toBe("liiv");
    expect(decodeSoilFamily("s", "S")).toBe("savi");
  });
  it("decodes memoir-diagnostic families (case-sensitive L vs l)", () => {
    expect(decodeSoilFamily("L", "Lk")).toBe("leede");
    expect(decodeSoilFamily("Kh", "K")).toBe("paepealne");
    expect(decodeSoilFamily("r₃ls₁", "Kr")).toBe("rähkne");
    expect(decodeSoilFamily("t₃40/l", "M’")).toBe("turvas");
    expect(decodeSoilFamily("Go", "Go")).toBe("glei");
  });
  it("keeps the gleyic qualifier out of the family (stated limitation)", () => {
    // gml_name 'l' with a glei-flavoured label stays liiv: the qualifier
    // is carried on the row for the tooltip, never guessed into a band.
    expect(decodeSoilFamily("l", "LkG")).toBe("liiv");
    expect(decodeSoilFamily("l", "Go")).toBe("liiv");
  });
  it("refuses water/settlement/undetermined and undecoded prefixes (never guessed)", () => {
    expect(decodeSoilFamily(" ", "Veeala, asustus või määramata")).toBeNull();
    expect(decodeSoilFamily("", "")).toBeNull();
    expect(decodeSoilFamily("v⁰₁ls₁40/p", "Korg")).toBeNull();
  });
});

describe("soil class bands (#617)", () => {
  it("matches the scorer SOIL_BANDS byte-for-byte (85→25)", () => {
    expect(SOIL_CLASS_SCORE).toEqual({
      saviliiv: 85,
      liiv: 70,
      liivsavi: 65,
      leede: 55,
      paepealne: 50,
      savi: 40,
      glei: 30,
      turvas: 25,
    });
  });
  it("folds rähkne into the paepealne 50 band (scorer parity, tooltip keeps family)", () => {
    expect(soilClassForFamily("rähkne")).toBe("paepealne");
    expect(SOIL_CLASS_SCORE[soilClassForFamily("saviliiv")]).toBe(85);
  });
  it("gives every class a fill (map paints classes, never numbers)", () => {
    for (const cls of SOIL_CLASSES) expect(SOIL_CLASS_FILL[cls]).toMatch(/^#[0-9a-f]{6}$/);
  });
});

describe("soil registry (#617)", () => {
  it("merges into LAYERS via the SOIL-HOOK (page + routes serve it)", () => {
    const ids = LAYERS.map((l) => l.id);
    // 127 shipped layers on main (#616 maaparandus) + 1 soil overlay
    // (SOIL-HOOK #617, 127 + 1) + 1 etak overlay (ETAK-HOOK #618,
    // 128 + 1) + 1 relief overlay (RELIEF-HOOK #619, 129 + 1) + 1 canopy overlay
    // (CANOPY-HOOK #620, 130 + 1) + 1 buildings overlay
    // (BUILDINGS-HOOK #621, 131 + 1) + 1 density overlay
    // (DENSITY-HOOK #622, 132 + 1) + 1 forest overlay
    // (FOREST-HOOK #624, 133 + 1 = 134).....
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    expect(ids.length).toBe(156); // KPO (#626): 136 shipped + kpo = 137. // HARBOUR (#627): 135 shipped + harbour = 136.
    // DELAY-HOOK (#629): + 5 delay band overlays (137 + 5 = 142). // SILLY-HOOK (#711): +12 silly-bundle layers (142 + 12 = 154).
    expect(ids).toContain("soil");
  });
  it("rides paramLabel with empty paramIds (polygons only, no parameters3 number)", () => {
    expect(SOIL_DEFS[0]?.paramIds).toEqual([]);
    expect(SOIL_DEFS[0]?.paramLabel).toBe("P4-muld");
    expect(SOIL_DEFS[0]?.fallbackPoints).toEqual([]);
  });
  it("guards by id, never by literal", () => {
    expect(isSoilLayerId("soil")).toBe(true);
    expect(isSoilLayerId("seveso")).toBe(false);
    expect(isSoilPolygonOnlyLayer("soil")).toBe(true);
    expect(isSoilPolygonOnlyLayer("parks")).toBe(false);
    expect(bonusSpecForSoil("soil")).toEqual(SOIL_BONUS.soil);
    expect(bonusSpecForSoil("parks")).toBeUndefined();
  });
  it("pins inert placeholders + attribution + hook marker", () => {
    expect(SOIL_DECAY.soil).toBe(0.5);
    expect(SOIL_NO_RASTER).toBe(true);
    expect(SOIL_NO_METRO).toBe(true);
    expect(SOIL_RASTER_FILE.soil).toContain("soil");
    expect(SOIL_TAGS.soil).not.toContain("node(");
    expect(SOIL_ATTRIBUTION).toContain("CC BY 4.0");
    expect(SOIL_HOOK).toContain("SOIL-HOOK (#617)");
  });
});

describe("soil area guard + fetch (#617)", () => {
  const AREA: SoilArea = {
    zone_id: "muld_0062DCE0",
    family: "liivsavi",
    cls: "liivsavi",
    score: 65,
    code: "ls₂;l50-100/s",
    b: [24.6, 59.28, 24.7, 59.33],
    r: [
      [
        [24.6, 59.28],
        [24.7, 59.28],
        [24.7, 59.33],
        [24.6, 59.28],
      ],
    ],
  };
  it("accepts well-formed areas, rejects malformed (never faked)", () => {
    expect(isSoilArea(AREA)).toBe(true);
    expect(isSoilArea({ ...AREA, cls: "chernozem" })).toBe(false);
    expect(isSoilArea({ ...AREA, r: [] })).toBe(false);
    expect(isSoilArea(null)).toBe(false);
  });
  it("fetches the viewport bbox from the soil areas endpoint", async () => {
    const seen: string[] = [];
    const fetchImpl = (async (url: string) => {
      seen.push(url);
      return { ok: true, json: async () => ({ areas: [AREA] }) };
    }) as unknown as typeof fetch;
    const res = await fetchSoilAreas(
      { minlon: 24.6, minlat: 59.28, maxlon: 24.7, maxlat: 59.33 },
      fetchImpl,
    );
    expect(seen).toHaveLength(1);
    expect(seen[0]).toContain("/api/layers/soil/areas?bbox=24.6%2C59.28%2C24.7%2C59.33");
    expect(res?.areas).toHaveLength(1);
    expect(res?.note).toBeNull();
  });
  it("is null on any transport failure (errors never cached as data)", async () => {
    const failing = (async () => {
      throw new Error("down");
    }) as unknown as typeof fetch;
    await expect(
      fetchSoilAreas({ minlon: 0, minlat: 0, maxlon: 1, maxlat: 1 }, failing),
    ).resolves.toBeNull();
  });
});
