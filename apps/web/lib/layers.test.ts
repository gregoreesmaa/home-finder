import { describe, expect, it, vi } from "vitest";
import {
  LAYERS,
  fetchLayerPoints,
  fetchParkAreas,
  fetchWindow,
  goodnessAt,
  radiusKmFor,
  layerCacheKey,
  layerHexes,
  overpassQueryFor,
  parseOverpassElements,
  bonusSpecFor,
  snapBBoxForCache,
  stopMode,
  tileForView,
  type BBoxLike,
} from "./layers";

const TALLINN_BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("layer registry", () => {
  it("binds all layers to parameters3 ids", () => {
    expect(LAYERS.map((l) => l.id)).toEqual([
      "parks",
      "transit",
      "schools",
      "walkability",
      "pedinfra",
      "cycling",
      "grocery",
      "healthcare",
      // B1-HOOK(#98): batch B1 ids (sibling batches append theirs here).
      "pets",
      "community",
      "culture",
      "nightlife",
      "libraries",
      // G07B-HOOK (#141): Group 7 env-health B ids.
      "brownsoil",
      "oiltank",
      "agriland",
      // G07D-HOOK (#143): Group 7 env-health D ids.
      "agrifield",
      "wildcorr",
      // G07C-HOOK(#142): Group 7 env-health C id (p257 proxy).
      "vectorhabitat",
      // G07-HOOK (#140): Group 7 env-health ids.
      "industprox",
      "odorsrc",
      // B5-HOOK (#102): Group 14 public-safety ids.
      "safety",
      "emergency",
      "hydrants",
      "evac",
      "dispatch",
      // G11D-HOOK (#135): Group 11 leftover-B ids (p317 is no-map).
      "mailbox",
      "postal",
      "alley",
      "trailprivacy",
      // G06B-HOOK (#139): Group 6 leftover ids.
      "plaster",
      "antiques",
      "woodfire",
      // G11C-HOOK (#134): Group 11 leftover-A ids.
      "schoolbus",
      "recspecial",
      "medspecial",
      "worship",
      "forage",
      // B6-HOOK (#133): mobility/access leftover ids (p220/p270/p386).
      "droneclear",
      "droneviab",
      "rentbleed",
      // G06-HOOK (#138): Group 6 heritage id.
      "heritage",
      // G02B-HOOK (#137): Group 2 batch-B lift-proxy id (p196 hinnang).
      "liftproxy",
      // G03-HOOK (#151): Group 3 cadastre-A drainage id.
      "drainage",
      // G03D-HOOK (#154): Group 3 cadastre-D ids (p332 moorage + p340 shoredist).
      "moorage",
      "shoredist",
      // G08A-HOOK (#167): Group 8 flood/climate A id (p69 wildfire).
      "wildfire",
      // G08D-HOOK (#170): Group 8 flood/climate-D id (p447 vernalpool).
      "vernalpool",
      // G08C-HOOK (#169): Group 8 flood/climate-C ids (p334 surgeroad + p336 slidebuf).
      "surgeroad",
      "slidebuf",
      // G08B-HOOK (#168): Group 8 flood/climate-B ids (p255 windtunnel + p333 saltspray).
      "windtunnel",
      "saltspray",
      // G05B-HOOK (#162): Group 5 plans-B ids (p106 gardens + p146 buildout).
      "gardens",
      "buildout",
      // G05D-HOOK (#164): Group 5 plans-D id (p230 strsat).
      "strsat",
      // G05A-HOOK (#161): Group 5 plans-A ids (p42 ehitus + p44 korterstock).
      "ehitus",
      "korterstock",
      // G05C-HOOK (#163): Group 5 plans-C ids (p223 commbleed + p224 windsolar + p225 viewshed).
      "commbleed",
      "windsolar",
      "viewshed",
      // G05E-HOOK (#165): Group 5 plans-E id (p381 equestrian).
      "equestrian",
      // G05F-HOOK (#166): Group 5 plans-F id (p485 upcycle).
      "upcycle",
      // G10R-HOOK (#171): Group 10 utilities-rest id (p215 skyview).
      "skyview",
      // G18A-HOOK (#172): Group 18 rest-A ids (p34 dayopen + p305 glassglare).
      "dayopen",
      "glassglare",
      // G18B-HOOK (#173): Group 18 rest-B ids (p468 fishbowl + p479 mossrisk + p405 daylight).
      "fishbowl",
      "mossrisk",
      "daylight",
      // G17A-HOOK (#177): Group 17 municipal-services-A ids (p187 compost + p311 gritbin + p312 leafdrop).
      "compost",
      "gritbin",
      "leafdrop",
    ]);
    expect(LAYERS.find((l) => l.id === "parks")?.paramIds).toEqual([19]);
    expect(LAYERS.find((l) => l.id === "transit")?.paramIds).toEqual([15]);
    expect(LAYERS.find((l) => l.id === "schools")?.paramIds).toEqual([12, 123]);
    // G07B-HOOK (#141): env-health B param binding.
    expect(LAYERS.find((l) => l.id === "brownsoil")?.paramIds).toEqual([189]);
    expect(LAYERS.find((l) => l.id === "oiltank")?.paramIds).toEqual([202]);
    expect(LAYERS.find((l) => l.id === "agriland")?.paramIds).toEqual([227]);
    // G07D-HOOK (#143): env-health D param binding.
    expect(LAYERS.find((l) => l.id === "agrifield")?.paramIds).toEqual([409]);
    expect(LAYERS.find((l) => l.id === "wildcorr")?.paramIds).toEqual([450]);
    // G07C-HOOK(#142): env-health C param binding (p257 proxy).
    expect(LAYERS.find((l) => l.id === "vectorhabitat")?.paramIds).toEqual([257]);
    // G07-HOOK (#140): env-health param binding.
    expect(LAYERS.find((l) => l.id === "industprox")?.paramIds).toEqual([61]);
    expect(LAYERS.find((l) => l.id === "odorsrc")?.paramIds).toEqual([62]);
    // G02B-HOOK (#137): lift-proxy param binding.
    expect(LAYERS.find((l) => l.id === "liftproxy")?.paramIds).toEqual([196]);
  });

  it("wires the G02B lift proxy with locked calibration", () => {
    // Drift guard: hook specs must equal G02B_HALVES/G02B_DECAY in
    // layers_group02b.ts and the Python builder (parsed by
    // test_batch_g02b.py).
    expect(bonusSpecFor("liftproxy")).toEqual({ kind: "area", half: 2 });
    expect(radiusKmFor("liftproxy")).toBe(0.3);
    expect(overpassQueryFor("liftproxy", TALLINN_BBOX)).toContain("building:levels");
  });

  it("wires the G03 drainage proxy with locked calibration", () => {
    // Drift guard: hook spec must equal G03_CAL in layers_group03.ts and
    // the Python builder (parsed by test_batch_g03.py).
    expect(bonusSpecFor("drainage")).toEqual({ kind: "quiet", halfM: 300 });
    expect(radiusKmFor("drainage")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "drainage")?.paramIds).toEqual([50]);
    expect(overpassQueryFor("drainage", TALLINN_BBOX)).toContain("coastline");
  });

  it("wires the G03D moorage + shoredist layers with locked calibration", () => {
    // Drift guard: hook specs must equal G03D_CAL in layers_group03d.ts
    // and the Python builder (parsed by test_batch_g03d.py).
    expect(bonusSpecFor("moorage")).toEqual({ kind: "area", half: 1 });
    expect(radiusKmFor("moorage")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "moorage")?.paramIds).toEqual([332]);
    expect(overpassQueryFor("moorage", TALLINN_BBOX)).toContain("marina");
    expect(bonusSpecFor("shoredist")).toEqual({ kind: "quiet", halfM: 100 });
    expect(radiusKmFor("shoredist")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "shoredist")?.paramIds).toEqual([340]);
    expect(overpassQueryFor("shoredist", TALLINN_BBOX)).toContain("coastline");
  });

  it("wires the G08A wildfire proxy with locked calibration", () => {
    // Drift guard: hook spec must equal G08A_CAL in layers_group08a.ts
    // and the Python builder (parsed by test_batch_g08a.py).
    expect(bonusSpecFor("wildfire")).toEqual({ kind: "quiet", halfM: 100 });
    expect(radiusKmFor("wildfire")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "wildfire")?.paramIds).toEqual([69]);
    expect(overpassQueryFor("wildfire", TALLINN_BBOX)).toContain("forest");
  });

  it("wires the G08D vernalpool layer with locked calibration", () => {
    // G08D-HOOK (#170): drift guard — hook spec must equal G08D_CAL in
    // layers_group08d.ts and the Python builder (parsed by
    // test_batch_g08d.py).
    expect(bonusSpecFor("vernalpool")).toEqual({ kind: "quiet", halfM: 300 });
    expect(radiusKmFor("vernalpool")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "vernalpool")?.paramIds).toEqual([447]);
    expect(overpassQueryFor("vernalpool", TALLINN_BBOX)).toContain("intermittent");
  });

  it("wires the G08C surgeroad + slidebuf layers with locked calibration", () => {
    // Drift guard: hook specs must equal G08C_CAL in layers_group08c.ts
    // and the Python builder (parsed by test_batch_g08c_flood.py).
    expect(bonusSpecFor("surgeroad")).toEqual({ kind: "quiet", halfM: 150 });
    expect(radiusKmFor("surgeroad")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "surgeroad")?.paramIds).toEqual([334]);
    expect(overpassQueryFor("surgeroad", TALLINN_BBOX)).toContain("highway");
    expect(bonusSpecFor("slidebuf")).toEqual({ kind: "quiet", halfM: 100 });
    expect(radiusKmFor("slidebuf")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "slidebuf")?.paramIds).toEqual([336]);
    expect(overpassQueryFor("slidebuf", TALLINN_BBOX)).toContain("cliff");
  });

  it("wires the G08B windtunnel + saltspray layers with locked calibration", () => {
    // Drift guard: hook specs must equal G08B_CAL in layers_group08b.ts
    // and the Python builder (parsed by test_batch_g08b.py).
    expect(bonusSpecFor("windtunnel")).toEqual({ kind: "quiet", halfM: 200 });
    expect(radiusKmFor("windtunnel")).toBe(0.2);
    expect(LAYERS.find((l) => l.id === "windtunnel")?.paramIds).toEqual([255]);
    expect(overpassQueryFor("windtunnel", TALLINN_BBOX)).toContain("building:levels");
    expect(bonusSpecFor("saltspray")).toEqual({ kind: "quiet", halfM: 500 });
    expect(radiusKmFor("saltspray")).toBe(0.5);
    expect(LAYERS.find((l) => l.id === "saltspray")?.paramIds).toEqual([333]);
    expect(overpassQueryFor("saltspray", TALLINN_BBOX)).toContain("coastline");
  });

  it("wires the G05D strsat layer with locked calibration", () => {
    // G05D-HOOK (#164): drift guard — hook spec must equal G05D_CAL in
    // layers_group05d.ts and the Python builder (parsed by
    // test_batch_g05d.py).
    expect(bonusSpecFor("strsat")).toEqual({ kind: "avoid", half: 0.35 });
    expect(radiusKmFor("strsat")).toBe(0.5);
    expect(LAYERS.find((l) => l.id === "strsat")?.paramIds).toEqual([230]);
    expect(overpassQueryFor("strsat", TALLINN_BBOX)).toContain("tourism");
  });

  it("scores strsat INVERSELY via the shared avoid branch", () => {
    // G05D-HOOK (#164): near mapped beds = saturated = low score.
    const pts = [{ lat: 59.4366, lon: 24.7449 }];
    expect(goodnessAt(59.4366, 24.7449, pts, "strsat")).toBe(0);
    const half = goodnessAt(59.4366 + 0.35 / 111.2, 24.7449, pts, "strsat") as number;
    expect(Math.abs(half - 50)).toBeLessThanOrEqual(2);
    const far = goodnessAt(59.36, 24.66, pts, "strsat") as number;
    expect(far).toBeGreaterThan(90);
    expect(goodnessAt(59.4366, 24.7449, [], "strsat")).toBeNull();
  });

  it("wires the G05A ehitus + korterstock layers with locked calibration", () => {
    // Drift guard: hook specs must equal G05A_CAL in layers_group05a.ts
    // and the Python builder (parsed by test_batch_g05a.py).
    expect(bonusSpecFor("ehitus")).toEqual({ kind: "area", half: 1 });
    expect(radiusKmFor("ehitus")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "ehitus")?.paramIds).toEqual([42]);
    expect(overpassQueryFor("ehitus", TALLINN_BBOX)).toContain("construction");
    expect(bonusSpecFor("korterstock")).toEqual({ kind: "area", half: 15 });
    expect(radiusKmFor("korterstock")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "korterstock")?.paramIds).toEqual([44]);
    expect(overpassQueryFor("korterstock", TALLINN_BBOX)).toContain("apartments");
  });

  it("wires the G05C commbleed + windsolar + viewshed layers with locked calibration", () => {
    // G05C-HOOK (#163): drift guard — hook specs must equal G05C_CAL in
    // layers_group05c.ts and the Python builder (parsed by
    // test_batch_g05c.py).
    expect(bonusSpecFor("commbleed")).toEqual({ kind: "quiet", halfM: 300 });
    expect(radiusKmFor("commbleed")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "commbleed")?.paramIds).toEqual([223]);
    expect(overpassQueryFor("commbleed", TALLINN_BBOX)).toContain("commercial");
    expect(bonusSpecFor("windsolar")).toEqual({ kind: "quiet", halfM: 800 });
    expect(radiusKmFor("windsolar")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "windsolar")?.paramIds).toEqual([224]);
    expect(overpassQueryFor("windsolar", TALLINN_BBOX)).toContain("generator");
    expect(bonusSpecFor("viewshed")).toEqual({ kind: "area", half: 1 });
    expect(radiusKmFor("viewshed")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "viewshed")?.paramIds).toEqual([225]);
    expect(overpassQueryFor("viewshed", TALLINN_BBOX)).toContain("viewpoint");
  });

  it("wires the G05E equestrian layer with locked calibration", () => {
    // G05E-HOOK (#165): drift guard — hook specs must equal G05E_CAL in
    // layers_group05e.ts and the Python builder (parsed by
    // test_batch_g05e.py).
    expect(bonusSpecFor("equestrian")).toEqual({ kind: "area", half: 1 });
    expect(radiusKmFor("equestrian")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "equestrian")?.paramIds).toEqual([381]);
    expect(overpassQueryFor("equestrian", TALLINN_BBOX)).toContain("horse_riding");
    expect(overpassQueryFor("equestrian", TALLINN_BBOX)).toContain("bridleway");
  });

  it("wires the G05F upcycle layer with locked calibration", () => {
    // G05F-HOOK (#166): drift guard — hook specs must equal G05F_CAL in
    // layers_group05f.ts and the Python builder (parsed by
    // test_batch_g05f.py).
    expect(bonusSpecFor("upcycle")).toEqual({ kind: "area", half: 2 });
    expect(radiusKmFor("upcycle")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "upcycle")?.paramIds).toEqual([485]);
    expect(overpassQueryFor("upcycle", TALLINN_BBOX)).toContain("abandoned");
    // Rezoning stock, not nuisance: never the industprox/brownsoil tags.
    expect(overpassQueryFor("upcycle", TALLINN_BBOX)).not.toContain("industrial");
  });

  it("wires the G10R skyview layer with locked calibration", () => {
    // G10R-HOOK (#171): drift guard — hook specs must equal G10R_CAL in
    // layers_group10rest.ts and the Python builder (parsed by
    // test_batch_g10_rest.py).
    expect(bonusSpecFor("skyview")).toEqual({ kind: "quiet", halfM: 150 });
    expect(radiusKmFor("skyview")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "skyview")?.paramIds).toEqual([215]);
    expect(overpassQueryFor("skyview", TALLINN_BBOX)).toContain("building:levels");
    expect(overpassQueryFor("skyview", TALLINN_BBOX)).toContain("forest");
  });

  it("wires the G18A dayopen + glassglare layers with locked calibration", () => {
    // G18A-HOOK (#172): drift guard — hook specs must equal G18A_CAL in
    // layers_group18resta.ts and the Python builder (parsed by
    // test_batch_g18_resta.py).
    expect(bonusSpecFor("dayopen")).toEqual({ kind: "quiet", halfM: 150 });
    expect(radiusKmFor("dayopen")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "dayopen")?.paramIds).toEqual([34]);
    expect(overpassQueryFor("dayopen", TALLINN_BBOX)).toContain("building:levels");
    expect(bonusSpecFor("glassglare")).toEqual({ kind: "quiet", halfM: 200 });
    expect(radiusKmFor("glassglare")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "glassglare")?.paramIds).toEqual([305]);
    expect(overpassQueryFor("glassglare", TALLINN_BBOX)).toContain("building:material");
  });

  it("wires the G18B fishbowl + mossrisk + daylight layers with locked calibration", () => {
    // G18B-HOOK (#173): drift guard — hook specs must equal G18B_CAL in
    // layers_group18restb.ts and the Python builder (parsed by
    // test_batch_g18_restb.py).
    expect(bonusSpecFor("fishbowl")).toEqual({ kind: "quiet", halfM: 150 });
    expect(radiusKmFor("fishbowl")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "fishbowl")?.paramIds).toEqual([468]);
    expect(overpassQueryFor("fishbowl", TALLINN_BBOX)).toContain("highway");
    expect(bonusSpecFor("mossrisk")).toEqual({ kind: "quiet", halfM: 250 });
    expect(radiusKmFor("mossrisk")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "mossrisk")?.paramIds).toEqual([479]);
    expect(overpassQueryFor("mossrisk", TALLINN_BBOX)).toContain("forest");
    expect(bonusSpecFor("daylight")).toEqual({ kind: "sparse", half: 150 });
    expect(radiusKmFor("daylight")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "daylight")?.paramIds).toEqual([405]);
    expect(overpassQueryFor("daylight", TALLINN_BBOX)).toContain("building");
  });

  it("wires the G17A compost + gritbin + leafdrop layers with locked calibration", () => {
    // G17A-HOOK (#177): drift guard — hook specs must equal G17A_CAL in
    // layers_group17a.ts and the Python builder (parsed by
    // test_batch_g17_a.py).
    expect(bonusSpecFor("compost")).toEqual({ kind: "area", half: 1 });
    expect(radiusKmFor("compost")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "compost")?.paramIds).toEqual([187]);
    expect(overpassQueryFor("compost", TALLINN_BBOX)).toContain("recycling");
    expect(bonusSpecFor("gritbin")).toEqual({ kind: "area", half: 1 });
    expect(radiusKmFor("gritbin")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "gritbin")?.paramIds).toEqual([311]);
    expect(overpassQueryFor("gritbin", TALLINN_BBOX)).toContain("grit_bin");
    expect(bonusSpecFor("leafdrop")).toEqual({ kind: "area", half: 1 });
    expect(radiusKmFor("leafdrop")).toBe(0.3);
    expect(LAYERS.find((l) => l.id === "leafdrop")?.paramIds).toEqual([312]);
    expect(overpassQueryFor("leafdrop", TALLINN_BBOX)).toContain("waste_disposal");
  });

  it("every layer explains green=good / red=bad in Estonian", () => {
    for (const l of LAYERS) {
      expect(l.title.length).toBeGreaterThan(0);
      expect(l.goodLabel.length).toBeGreaterThan(0);
      expect(l.badLabel.length).toBeGreaterThan(0);
      expect(l.source.length).toBeGreaterThan(0);
      expect(l.fallbackPoints.length).toBeGreaterThan(0);
    }
  });
});

describe("overpass queries", () => {
  it("parks query covers the bbox and park tags", () => {
    const q = overpassQueryFor("parks", TALLINN_BBOX);
    expect(q).toContain("24.5");
    expect(q).toContain("59.35");
    expect(q).toContain("leisure");
    expect(q).toContain("park");
  });

  it("transit query asks for stops, not timetables", () => {
    const q = overpassQueryFor("transit", TALLINN_BBOX);
    expect(q).toContain("public_transport");
  });

  it("schools query covers the full ladder (variety bonus needs it)", () => {
    const q = overpassQueryFor("schools", TALLINN_BBOX);
    expect(q).toContain("amenity");
    for (const kind of ["school", "kindergarten", "university", "college"]) {
      expect(q).toContain(kind);
    }
  });
});

describe("overpass response parsing", () => {
  it("takes nodes and centered ways, skips coordless elements", () => {
    const pts = parseOverpassElements({
      elements: [
        { type: "node", id: 1, lat: 59.43, lon: 24.75 },
        { type: "way", id: 2, center: { lat: 59.44, lon: 24.76 } },
        { type: "way", id: 3 },
        { type: "node", id: 4, lat: NaN, lon: 24.75 },
      ],
    });
    expect(pts).toEqual([
      { lat: 59.43, lon: 24.75 },
      { lat: 59.44, lon: 24.76 },
    ]);
  });

  it("rejects non-object payloads", () => {
    expect(parseOverpassElements(null)).toEqual([]);
    expect(parseOverpassElements({})).toEqual([]);
  });
});

describe("goodness scoring", () => {
  const pts = [{ lat: 59.4372, lon: 24.7536 }];

  it("is 100 on top of a feature", () => {
    expect(goodnessAt(59.4372, 24.7536, pts)).toBe(100);
  });

  it("decays monotonically with distance", () => {
    const near = goodnessAt(59.4472, 24.7536, pts) as number;
    const far = goodnessAt(59.5372, 24.7536, pts) as number;
    expect(near).toBeGreaterThan(far);
    expect(far).toBeLessThan(5);
  });

  it("is null without features (no fake precision)", () => {
    expect(goodnessAt(59.43, 24.75, [])).toBeNull();
  });
});

describe("cache tile snapping", () => {
  it("snaps outward to the tile grid so nearby views share entries", () => {
    expect(
      snapBBoxForCache({ minlon: 24.62, minlat: 59.39, maxlon: 24.88, maxlat: 59.47 }, 1),
    ).toEqual({ minlon: 24, minlat: 59, maxlon: 25, maxlat: 60 });
    expect(
      snapBBoxForCache({ minlon: 24.61, minlat: 59.41, maxlon: 24.7, maxlat: 59.44 }, 1),
    ).toEqual({ minlon: 24, minlat: 59, maxlon: 25, maxlat: 60 });
    expect(
      snapBBoxForCache({ minlon: 24.62, minlat: 59.39, maxlon: 24.88, maxlat: 59.47 }, 0.5),
    ).toEqual({ minlon: 24.5, minlat: 59.0, maxlon: 25.0, maxlat: 59.5 });
  });
});

describe("view tiling", () => {
  it("tiles small views, passes large stable views through", () => {
    // Zoomed city view -> shared 1° tile.
    expect(
      tileForView({ minlon: 24.62, minlat: 59.39, maxlon: 24.88, maxlat: 59.47 }),
    ).toEqual({ minlon: 24, minlat: 59, maxlon: 25, maxlat: 60 });
    // Country view -> exact bbox (already cached, never inflated).
    const estonia = { minlon: 21.5, minlat: 57.3, maxlon: 28.5, maxlat: 59.9 };
    expect(tileForView(estonia)).toEqual(estonia);
  });
});

describe("influence radii", () => {
  // Calibrated from Tallinn score histograms so each layer's median sits
  // mid-ramp: streets discriminate instead of blobbing. Scoring uses the
  // same radii.
  it("locks transit/parks/schools radii", () => {
    // Walk-graph kernels run narrower than Euclidean crow-flies ones:
    // true walks are longer, and narrow kernels keep hub/park adjacency
    // from averaging into background green.
    expect(radiusKmFor("transit")).toBeCloseTo(0.2, 5);
    expect(radiusKmFor("parks")).toBeCloseTo(0.25, 5);
    expect(radiusKmFor("schools")).toBeCloseTo(0.8, 5);
  });
});

describe("transit stop modes", () => {
  it("classifies tram, train and bus stops; ignores the rest", () => {
    expect(stopMode({ railway: "tram_stop" })).toBe("tram");
    expect(stopMode({ railway: "station" })).toBe("train");
    expect(stopMode({ highway: "bus_stop" })).toBe("bus");
    expect(stopMode({ public_transport: "platform" })).toBe("bus");
    expect(stopMode({ amenity: "school" })).toBeNull();
    expect(stopMode(undefined)).toBeNull();
    expect(stopMode({})).toBeNull();
  });
});

describe("new layer defs", () => {
  it("maps five new layers to their spec parameter ids", () => {
    const ids = Object.fromEntries(LAYERS.map((l) => [l.id, l.paramIds]));
    expect(ids.walkability).toEqual([14]);
    expect(ids.pedinfra).toEqual([84]);
    expect(ids.cycling).toEqual([102]);
    expect(ids.grocery).toEqual([103]);
    expect(ids.healthcare).toEqual([20]);
  });

  it("locks radii and area halves for the new layers", () => {
    expect(radiusKmFor("walkability")).toBeCloseTo(0.2, 5);
    expect(radiusKmFor("pedinfra")).toBeCloseTo(0.25, 5);
    expect(radiusKmFor("cycling")).toBeCloseTo(0.3, 5);
    expect(radiusKmFor("grocery")).toBeCloseTo(0.3, 5);
    expect(radiusKmFor("healthcare")).toBeCloseTo(0.8, 5);
    expect(bonusSpecFor("grocery")).toEqual({ kind: "area", half: 6 });
    expect(bonusSpecFor("healthcare")).toEqual({ kind: "area", half: 20 });
    // Density halves, histogram-locked (Tallinn median mid-ramp each).
    expect(bonusSpecFor("walkability")).toEqual({ kind: "area", half: 300 });
    expect(bonusSpecFor("pedinfra")).toEqual({ kind: "area", half: 12 });
    expect(bonusSpecFor("cycling")).toEqual({ kind: "area", half: 3 });
  });
});

describe("bonus specs", () => {
  it("rewards park area, transit options and school variety", () => {
    expect(bonusSpecFor("parks")).toEqual({ kind: "area", half: 15 });
    expect(bonusSpecFor("transit")).toEqual({
      kind: "trips",
      half: 1500,
      modeBonus: 10,
      minModes: 2,
    });
    expect(bonusSpecFor("schools").kind).toBe("variety");
  });
});

describe("cache keys", () => {
  it("is stable under float noise and differs per layer", () => {
    const a = layerCacheKey("parks", TALLINN_BBOX);
    const noisy = layerCacheKey("parks", {
      minlon: 24.5000001,
      minlat: 59.3500001,
      maxlon: 24.9000001,
      maxlat: 59.5000001,
    });
    expect(noisy).toBe(a);
    expect(layerCacheKey("transit", TALLINN_BBOX)).not.toBe(a);
    expect(layerCacheKey("parks", { ...TALLINN_BBOX, maxlon: 25.9 })).not.toBe(a);
  });
});

describe("layer fetch via the server proxy", () => {
  const liveBody = {
    points: [{ lat: 59.43, lon: 24.75 }],
    provenance: "live",
    ageMs: 0,
  };

  it("calls our API route with the bbox, not Overpass directly", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(liveBody),
    });
    await fetchLayerPoints("parks", TALLINN_BBOX, fetchImpl);
    const url = String(fetchImpl.mock.calls[0][0]);
    expect(url.startsWith("/api/layers/parks?")).toBe(true);
    expect(url).toContain("24.5");
    expect(url).toContain("59.35");
  });

  it("passes live/cache/stale/snapshot/empty provenance through as real (non-demo) data", async () => {
    for (const provenance of ["live", "cache", "stale", "snapshot", "empty"] as const) {
      const fetchImpl = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ ...liveBody, provenance, ageMs: 123 }),
      });
      const res = await fetchLayerPoints("parks", TALLINN_BBOX, fetchImpl);
      expect(res.live).toBe(true);
      expect(res.provenance).toBe(provenance);
      expect(res.points).toEqual([{ lat: 59.43, lon: 24.75 }]);
    }
  });

  it("passes feature tags, weights and areas through, dropping malformed ones", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          points: [
            { lat: 59.43, lon: 24.75, tags: { amenity: "school" }, t: 974 },
            { lat: 59.44, lon: 24.76, tags: { amenity: 42 }, t: 42 },
            { lat: 59.45, lon: 24.77, t: "heavy" },
            { lat: 59.46, lon: 24.78, a: 57 },
            { lat: 59.47, lon: 24.79, a: -5 },
          ],
          provenance: "live",
          ageMs: 0,
        }),
    });
    const res = await fetchLayerPoints("schools", TALLINN_BBOX, fetchImpl);
    expect(res.points).toEqual([
      { lat: 59.43, lon: 24.75, tags: { amenity: "school" }, t: 974 },
      { lat: 59.44, lon: 24.76, t: 42 },
      { lat: 59.45, lon: 24.77 },
      { lat: 59.46, lon: 24.78, a: 57 },
      { lat: 59.47, lon: 24.79 },
    ]);
  });

  it("passes the walk raster and distance through, dropping malformed rasters", async () => {
    const raster = {
      cols: 2,
      rows: 2,
      bbox: TALLINN_BBOX,
      step_m: 75,
      half: 1500,
      sigma: 0.2,
      per: 0,
      cap: 0,
      unknown: 255,
      dtype: "uint8",
      data: Buffer.from([80, 255, 40, 60]).toString("base64"),
    };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ ...liveBody, raster, distance: "walk" }),
    });
    const res = await fetchLayerPoints("transit", TALLINN_BBOX, fetchImpl);
    expect(res.raster).toEqual(raster);
    expect(res.distance).toBe("walk");
    const badImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ...liveBody, raster: { ...raster, cols: 0 }, distance: "walk" }),
    });
    const bad = await fetchLayerPoints("transit", TALLINN_BBOX, badImpl);
    expect(bad.raster).toBeNull();
    expect(bad.distance).toBe("euclidean");
  });

  it("fetches per-view windows with clamped grids, null on failure", async () => {
    const doc = {
      cols: 64,
      rows: 64,
      bbox: TALLINN_BBOX,
      step_m: 12,
      half: 6,
      sigma: 0.3,
      per: 0,
      cap: 0,
      unknown: 255,
      dtype: "uint8",
      data: Buffer.alloc(64 * 64, 50).toString("base64"),
    };
    const seen: string[] = [];
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      seen.push(url);
      return Promise.resolve({ ok: true, json: () => Promise.resolve(doc) });
    });
    const res = await fetchWindow("grocery", TALLINN_BBOX, fetchImpl);
    expect(res?.cols).toBe(64);
    expect(seen[0]).toContain("/api/layers/grocery/window?");
    expect(seen[0]).toContain("cols=");
    // County-wide view clamps to 512.
    await fetchWindow("grocery", { minlon: 20, minlat: 55, maxlon: 30, maxlat: 62 }, fetchImpl);
    expect(seen[1]).toContain("cols=512");
    // HTTP failure and garbage degrade to null (points-splat fallback).
    const badImpl = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchWindow("grocery", TALLINN_BBOX, badImpl)).toBeNull();
    const throwImpl = vi.fn().mockRejectedValue(new Error("down"));
    expect(await fetchWindow("grocery", TALLINN_BBOX, throwImpl)).toBeNull();
  });

  it("rejects rasters using the wrong wire keys (regression: stepM vs step_m)", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          ...liveBody,
          raster: {
            cols: 2,
            rows: 2,
            bbox: TALLINN_BBOX,
            stepM: 75, // wrong: the Python builder writes step_m
            half: 1500,
            sigma: 0.2,
            per: 0,
            cap: 0,
            unknown: 255,
            dtype: "uint8",
            data: Buffer.from([80, 255, 40, 60]).toString("base64"),
          },
          distance: "walk",
        }),
    });
    const res = await fetchLayerPoints("transit", TALLINN_BBOX, fetchImpl);
    expect(res.raster).toBeNull();
    expect(res.distance).toBe("euclidean");
  });

  it("maps demo answers to honestly-labeled fallback points", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ points: [], provenance: "demo", ageMs: null }),
    });
    const res = await fetchLayerPoints("parks", TALLINN_BBOX, fetchImpl);
    expect(res.live).toBe(false);
    expect(res.provenance).toBe("demo");
    expect(res.points.length).toBeGreaterThan(0);
  });

  it("falls back to demo when the proxy is unreachable", async () => {
    const failing = vi.fn().mockRejectedValue(new Error("boom"));
    const badStatus = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    });
    for (const impl of [failing, badStatus]) {
      const res = await fetchLayerPoints("parks", TALLINN_BBOX, impl);
      expect(res.live).toBe(false);
      expect(res.provenance).toBe("demo");
      expect(res.points.length).toBeGreaterThan(0);
    }
  });
});

describe("layer hexes for the map", () => {
  it("paints a scored grid over the bbox", () => {
    // Tight grid: hex centers must land inside the calibrated kernel or
    // every cell rounds to zero far out on the exponential tail.
    const hexes = layerHexes(
      "parks",
      [{ lat: 59.42, lon: 24.7 }],
      { minlon: 24.69, minlat: 59.41, maxlon: 24.71, maxlat: 59.43 },
      0.005,
    );
    expect(hexes.length).toBeGreaterThan(0);
    for (const h of hexes) {
      expect(h.h3.startsWith("parks-")).toBe(true);
      expect(h.score_goodness).toBeGreaterThanOrEqual(0);
      expect(h.score_goodness).toBeLessThanOrEqual(100);
    }
    const scores = hexes.map((h) => h.score_goodness);
    expect(Math.max(...scores)).toBeGreaterThan(Math.min(...scores));
  });
});

describe("fetchParkAreas", () => {
  const ring = [
    [24.7, 59.41],
    [24.71, 59.41],
    [24.71, 59.42],
  ];
  it("returns cleaned rings, skipping junk entries", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          areas: [
            { b: [24.7, 59.41, 24.71, 59.42], a: 6.4, r: [ring] },
            { b: [0, 0, 1, 1], a: "huge", r: "nope" },
            null,
          ],
        }),
    });
    const areas = await fetchParkAreas(fetchImpl);
    expect(fetchImpl.mock.calls[0][0]).toBe("/api/layers/parks/areas");
    expect(areas).toEqual([{ b: [24.7, 59.41, 24.71, 59.42], a: 6.4, r: [ring] }]);
  });

  it("reads null on HTTP failure, bad shape, or throw", async () => {
    const bad = vi.fn().mockResolvedValue({ ok: false, json: () => Promise.resolve({}) });
    await expect(fetchParkAreas(bad)).resolves.toBeNull();
    const shape = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve({ areas: "nope" }) });
    await expect(fetchParkAreas(shape)).resolves.toBeNull();
    const boom = vi.fn().mockRejectedValue(new Error("down"));
    await expect(fetchParkAreas(boom)).resolves.toBeNull();
  });
});
