import { describe, expect, it, vi } from "vitest";
import {
  OVERLAY_CAP,
  fetchGraphOverlay,
  needsGraphOverlay,
  overlayColorFor,
  overlayLegendFor,
  overlayWeight,
  selectOverlayPoints,
} from "./overlays";
import { LAYERS, type LayerId } from "./layers";

const BBOX = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("overlay layer routing", () => {
  it("sends only density layers to the graph sidecar", () => {
    expect(needsGraphOverlay("walkability")).toBe(true);
    expect(needsGraphOverlay("pedinfra")).toBe(true);
    expect(needsGraphOverlay("cycling")).toBe(true);
    for (const l of ["parks", "transit", "schools", "grocery", "healthcare"] as const) {
      expect(needsGraphOverlay(l)).toBe(false);
    }
  });
});

describe("overlay weights", () => {
  it("sizes transit by GTFS weekday trips, zero when unknown", () => {
    expect(overlayWeight({ lat: 0, lon: 0, t: 974 }, "transit")).toBe(974);
    expect(overlayWeight({ lat: 0, lon: 0 }, "transit")).toBe(0);
  });

  it("passes area through where the spec scores it", () => {
    expect(overlayWeight({ lat: 0, lon: 0, a: 6.4 }, "parks")).toBe(6.4);
    expect(overlayWeight({ lat: 0, lon: 0, a: 1 }, "grocery")).toBe(1);
  });

  it("weighs unweighted layers at one", () => {
    expect(overlayWeight({ lat: 0, lon: 0, tags: { amenity: "school" } }, "schools")).toBe(1);
  });
});

describe("selectOverlayPoints", () => {
  it("keeps transit hubs first under the cap", () => {
    const pts = [
      { lat: 59.43, lon: 24.75, t: 5 },
      { lat: 59.44, lon: 24.76, t: 3000 },
      { lat: 59.45, lon: 24.77, t: 100 },
    ];
    const out = selectOverlayPoints(pts, "transit", 2);
    expect(out.map((p) => p.w)).toEqual([3000, 100]);
    expect(out).toHaveLength(2);
  });

  it("stride-samples other layers deterministically within the cap", () => {
    const pts = Array.from({ length: 10 }, (_, i) => ({ lat: 59 + i / 100, lon: 24.7 }));
    const out = selectOverlayPoints(pts, "schools", 4);
    expect(out).toHaveLength(4);
    expect(out[0]).toEqual({ lon: 24.7, lat: 59, w: 1 });
    // Same input, same sample (stable across renders/views).
    expect(selectOverlayPoints(pts, "schools", 4)).toEqual(out);
    // Spread, not just the head: last sample comes from the tail half.
    expect(out[3].lat).toBeGreaterThan(59.05);
  });

  it("passes small sets through and drops coordless junk", () => {
    const pts = [
      { lat: 59.43, lon: 24.75 },
      { lat: NaN, lon: 24.76 },
      { lat: 59.45, lon: Infinity },
    ];
    expect(selectOverlayPoints(pts, "grocery")).toHaveLength(1);
  });

  it("caps a Harju-wide tile (performance)", () => {
    const pts = Array.from({ length: 8049 }, (_, i) => ({
      lat: 59 + (i % 1000) / 2000,
      lon: 24 + (i % 1000) / 2000,
      t: i,
    }));
    expect(selectOverlayPoints(pts, "transit")).toHaveLength(OVERLAY_CAP);
  });
});

describe("overlay legend + colors", () => {
  it("explains every layer's markers and weights in Estonian", () => {
    const ids = LAYERS.map((l) => l.id);
    // G07C-HOOK(#142): vectorhabitat joins the registry.
    // G03D-HOOK (#154): moorage + shoredist join the registry.
    // G08A-HOOK (#167): wildfire joins the registry.
    // G08D-HOOK (#170): vernalpool joins the registry.
    // G08C-HOOK (#169): surgeroad + slidebuf join the registry.
    // G08B-HOOK (#168): windtunnel + saltspray join the registry.
    // G05B-HOOK (#162): gardens + buildout join the registry.
    // G05D-HOOK (#164): strsat joins the registry.
    // G05A-HOOK (#161): ehitus + korterstock join the registry.
    // G05C-HOOK (#163): commbleed + windsolar + viewshed join the registry.
    // G05E-HOOK (#165): equestrian joins the registry.
    // G05F-HOOK (#166): upcycle joins the registry.
    // G10R-HOOK (#171): skyview joins the registry.
    // G18A-HOOK (#172): dayopen + glassglare join the registry.
    // G18B-HOOK (#173): fishbowl + mossrisk + daylight join the registry.
    // G17A-HOOK (#177): compost + gritbin + leafdrop join the registry.
    // G17B-HOOK (#178): lawncare joins the registry.
    // G17R-HOOK (#196): privroad joins the registry.
    // B10C-HOOK (#230): water + waste + fiber + mobile join the registry.
    // OSMDAILY-HOOK (#482): dailyshop + activity + herd + thirdplace +
    // taxidoor + lastshop join the registry.
    // GTFS-HOOK (#483): gtfsstops joins the registry.
    // RSAFE-HOOK (#481): roadsafety joins the registry.
    // P4-031-HOOK (#484): senscom joins the registry.
    // STATKOV-HOOK (#485): kovmigr + kovehit + kovfisc join the registry (86 + 3).
    // P4PARK-HOOK (#479): parking joins the registry. (89 + 1).
    // MARUKOV-HOOK (#486): kovkasv + kovkaive + kovedas + kovkiirus join the registry (90 + 4).
    // FLOOD-HOOK (#487): floodzone joins the registry (89 + 1). (94 + 1).
    // P4OSM-HOOK (#480): blockwalk + darkness join the registry. (95 + 2).
    // OOKLA-HOOK (#489): ookla_fixed + ookla_mobile join the registry (97 + 2).
    // ACCBLACK-HOOK (#490): accblack joins the registry (99 + 1).
    // MAAPARCEL-HOOK (#491): maaparcel joins the registry (100 + 1).

    // EELIS-HOOK (#488): eeliskaitse + eelisniit + eelisraie join the registry (101 + 3).
    // PLANKTPR-HOOK (#492): planktpr joins the registry (104 + 1).
    // TERVISE-HOOK (#494): tervise joins the registry. (105 + 1).
    // ASUMEDIA-HOOK (#495): asumedia joins the registry (106 + 1).
    // PAASTE-HOOK (#493): paaste joins the registry (107 + 1).
    // SPORT-HOOK (#607): sport_hall/field/pool join the registry (108 + 3).
    // EHIS-HOOK (#608): ehis_school/kindergarten/hobby join the registry (111 + 3).
    // MEDRE-HOOK (#609): medre_gp/clinic join the registry (114 + 2).
    // OHUSEIRE-HOOK (#610): ohuseire joins the registry (116 + 1).
    // KLIIMA-HOOK (#611): kliima_frost/wet join the registry (117 + 2).
    // POI-HOOK (#612): poi_library/post/pharmacy join the registry (119 + 3).
    // FIXIT-HOOK (#623): fixit joins the registry (122 + 1).
    // SEVESO-HOOK (#613): seveso joins the registry (123 + 1).
    // STATELAND-HOOK (#615): stateland joins the registry (124 + 1).
    // QUARRY-HOOK (#614): quarry joins the registry (125 + 1).
    // DRAINAGE-HOOK (#616): drainage joins the registry (126 + 1).
    // SOIL-HOOK (#617): soil joins the registry (127 + 1).
    // ETAK-HOOK (#618): etak joins the registry (128 + 1).
    // RELIEF-HOOK (#619): relief joins the registry (129 + 1).
    // BUILDINGS-HOOK (#621) is in; DENSITY-HOOK (#622): density joins the registry (132 + 1).
    // DENSITY-HOOK (#622) is in; FOREST-HOOK (#624): forest joins the registry (133 + 1).
    // FOREST-HOOK (#624) is in; NOISE-HOOK (#625): noise joins the registry (134 + 1).
    // NOISE-HOOK (#625) is in; HARBOUR-HOOK (#627): harbour joins the registry (135 + 1).
    // HARBOUR-HOOK (#627) is in; KPO-HOOK (#626): kpo joins the registry (136 + 1).
    // KPO-HOOK (#626) is in; DELAY-HOOK (#629): delay-morning/midday/evening/offpeak/worst join the registry (137 + 5).
    // SILLY-HOOK (#711): silly-bundle x12 join the registry (142 + 12).
    // MERGE (#613+#614+#615+#616+#617+#618+#619+#620+#621+#622+#624+#625+#627+#626+#629): 123 shipped + seveso + stateland + quarry + maaparandus + soil + etak + relief + canopy + buildings + density + forest + noise + harbour + kpo + delay x5 = 142.
    // SILLY-HOOK (#711): twelve silly-bundle pins join the registry (142 + 12).
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    // HARNO-HOOK (#687): +1 harno school layer (156 + 1 = 157).
    // VIIRS-HOOK (#719): +1 viirs brightness layer (157 + 1 = 158).
    expect(ids).toHaveLength(158);
    for (const id of ids) {
      const legend = overlayLegendFor(id);
      expect(legend.length).toBeGreaterThan(10);
    }
    // Weights match the scoring spec halves/bonuses (see bonusSpecFor).
    expect(overlayLegendFor("transit")).toContain("1500");
    expect(overlayLegendFor("parks")).toContain("15 ha");
    expect(overlayLegendFor("schools")).toContain("+12");
    expect(overlayLegendFor("walkability")).toContain("300");
    expect(overlayLegendFor("pedinfra")).toContain("12 km");
    expect(overlayLegendFor("cycling")).toContain("3 km");
    expect(overlayLegendFor("grocery")).toContain("6");
    expect(overlayLegendFor("healthcare")).toContain("20");
    // Batch B1 halves (see B1_BONUS in layers_batch1.ts).
    expect(overlayLegendFor("pets")).toContain("5,7");
    expect(overlayLegendFor("community")).toContain("3,3");
    expect(overlayLegendFor("culture")).toContain("4,5");
    expect(overlayLegendFor("nightlife")).toContain("7,5");
    expect(overlayLegendFor("libraries")).toContain("(küllastus 3)");
    // Batch B5 halves (see B5_BONUS in layers_batch5.ts).
    expect(overlayLegendFor("safety")).toContain("küllastus 1");
    expect(overlayLegendFor("emergency")).toContain("küllastus 2");
    expect(overlayLegendFor("hydrants")).toContain("küllastus 6");
    expect(overlayLegendFor("evac")).toContain("2 km");
    expect(overlayLegendFor("dispatch")).toContain("küllastus 3");
    // Batch G07B halves (see g07bBonusSpecFor in layers_group07b.ts).
    expect(overlayLegendFor("brownsoil")).toContain("500 m");
    expect(overlayLegendFor("oiltank")).toContain("500 m");
    expect(overlayLegendFor("agriland")).toContain("800 m");
    // G11D halves (see G11D_BONUS in layers_group11d.ts).
    expect(overlayLegendFor("mailbox")).toContain("2,5");
    expect(overlayLegendFor("postal")).toContain("küllastus 12");
    expect(overlayLegendFor("alley")).toContain("0,3 km");
    expect(overlayLegendFor("trailprivacy")).toContain("PÖÖRATUD");
    // Batch G07D halves (see g07dBonusSpecFor in layers_group07d.ts).
    expect(overlayLegendFor("agrifield")).toContain("800 m");
    expect(overlayLegendFor("wildcorr")).toContain("500 m");
    // G07C-HOOK(#142): p257 half (see G07C_BONUS in layers_group07c.ts).
    expect(overlayLegendFor("vectorhabitat")).toContain("300 m");
    // Group G06B halves (see GROUP06B_BONUS in layers_group06b.ts).
    expect(overlayLegendFor("plaster")).toContain("küllastus 6");
    expect(overlayLegendFor("antiques")).toContain("küllastus 1");
    expect(overlayLegendFor("woodfire")).toContain("pöördskaala");
    // Batch G11C halves (see G11C_BONUS in layers_group11c.ts).
    expect(overlayLegendFor("schoolbus")).toContain("küllastus 4");
    expect(overlayLegendFor("schoolbus")).toContain("hinnang");
    expect(overlayLegendFor("recspecial")).toContain("küllastus 8");
    expect(overlayLegendFor("medspecial")).toContain("küllastus 5");
    expect(overlayLegendFor("worship")).toContain("2,5");
    expect(overlayLegendFor("forage")).toContain("küllastus 12");
    // Batch B6 halves/tiers (see B6_CAL in layers_batch6.ts).
    expect(overlayLegendFor("droneclear")).toContain("1300 m");
    expect(overlayLegendFor("droneviab")).toContain("800 m");
    expect(overlayLegendFor("rentbleed")).toContain("800 m");
    expect(overlayLegendFor("droneclear")).toContain("mitte EANS DroneMap");
    expect(overlayLegendFor("rentbleed")).toContain("mitte üüriregister");
    // Batch G07 halves (see g07BonusSpecFor in layers_group07.ts).
    expect(overlayLegendFor("industprox")).toContain("500 m");
    expect(overlayLegendFor("odorsrc")).toContain("500 m");
    // Group G06 half (see GROUP06_BONUS in layers_group06.ts).
    expect(overlayLegendFor("heritage")).toContain("küllastus 2");
    // Batch G02B half (see G02B_BONUS in layers_group02b.ts).
    expect(overlayLegendFor("liftproxy")).toContain("küllastus 2");
    expect(overlayLegendFor("liftproxy")).toContain("hinnang");
    // Batch G03 half (see G03_CAL in layers_group03.ts).
    expect(overlayLegendFor("drainage")).toContain("300 m");
    expect(overlayLegendFor("drainage")).toContain("drenaažiproksi");
    // Batch G03D halves (see G03D_CAL in layers_group03d.ts).
    expect(overlayLegendFor("moorage")).toContain("küllastus 1");
    expect(overlayLegendFor("moorage")).toContain("hinnang");
    expect(overlayLegendFor("shoredist")).toContain("100 m");
    expect(overlayLegendFor("shoredist")).toContain("hinnang");
    // Batch G08A half (see G08A_CAL in layers_group08a.ts).
    expect(overlayLegendFor("wildfire")).toContain("100 m");
    expect(overlayLegendFor("wildfire")).toContain("hinnang");
    // NOISE-HOOK (#625): noise legend states modelled-not-measured +
    // NULL-outside (never quiet); toggle dot is deep siren rose.
    expect(overlayLegendFor("noise")).toContain("MUDEL");
    expect(overlayLegendFor("noise")).toContain("MITTE vaikne");
    expect(overlayColorFor("noise")).toBe("#500f28");
    // HARBOUR-HOOK (#627): harbour legend states joined ports + AIS
    // pleasure cells, season-free annual, NULL-outside (never calm);
    // toggle dot is emerald-950 deep sea.
    expect(overlayLegendFor("harbour")).toContain("sadamaregister");
    expect(overlayLegendFor("harbour")).toContain("MITTE rahulik");
    expect(overlayColorFor("harbour")).toBe("#115e59");
    // KPO-HOOK (#626): kpo legend states joined zones + bands +
    // vintage + CC-BY source + parcel-window coverage + NULL-outside
    // (never clean title); toggle dot is burnt sienna.
    expect(overlayLegendFor("kpo")).toContain("CC-BY 4.0");
    expect(overlayLegendFor("kpo")).toContain("MITTE puhas omand");
    expect(overlayColorFor("kpo")).toBe("#4a044e");    // Batch G08D half (see G08D_CAL in layers_group08d.ts).
    expect(overlayLegendFor("vernalpool")).toContain("300 m");
    expect(overlayLegendFor("vernalpool")).toContain("proksi");
    // Batch G08C halves (see G08C_CAL in layers_group08c.ts).
    expect(overlayLegendFor("surgeroad")).toContain("150 m");
    expect(overlayLegendFor("surgeroad")).toContain("hinnang");
    expect(overlayLegendFor("slidebuf")).toContain("100 m");
    expect(overlayLegendFor("slidebuf")).toContain("hinnang");
    // Batch G08B halves (see G08B_CAL in layers_group08b.ts).
    expect(overlayLegendFor("windtunnel")).toContain("200 m");
    expect(overlayLegendFor("windtunnel")).toContain("hinnang");
    expect(overlayLegendFor("saltspray")).toContain("500 m");
    expect(overlayLegendFor("saltspray")).toContain("hinnang");
    // Batch G05B halves (see G05B_CAL in layers_group05b.ts).
    expect(overlayLegendFor("gardens")).toContain("küllastus 1");
    expect(overlayLegendFor("gardens")).toContain("hinnang");
    expect(overlayLegendFor("buildout")).toContain("küllastus 2");
    expect(overlayLegendFor("buildout")).toContain("hinnang");
    // Batch G05D half (see G05D_CAL in layers_group05d.ts).
    expect(overlayLegendFor("strsat")).toContain("350 m");
    expect(overlayLegendFor("strsat")).toContain("hinnang");
    // Batch G05C halves (see G05C_CAL in layers_group05c.ts).
    expect(overlayLegendFor("commbleed")).toContain("300 m");
    expect(overlayLegendFor("commbleed")).toContain("hinnang");
    expect(overlayLegendFor("windsolar")).toContain("800 m");
    expect(overlayLegendFor("windsolar")).toContain("hinnang");
    expect(overlayLegendFor("viewshed")).toContain("küllastus 1");
    expect(overlayLegendFor("viewshed")).toContain("hinnang");
    // G05E-HOOK (#165): equestrian joins the registry.
    expect(overlayLegendFor("equestrian")).toContain("küllastus 1");
    expect(overlayLegendFor("equestrian")).toContain("hinnang");
    // Batch G05F half (see G05F_CAL in layers_group05f.ts).
    expect(overlayLegendFor("upcycle")).toContain("küllastus 2");
    expect(overlayLegendFor("upcycle")).toContain("hinnang");
    // Batch G10R half (see G10R_CAL in layers_group10rest.ts).
    // G10R-HOOK (#171): skyview joins the registry.
    expect(overlayLegendFor("skyview")).toContain("150 m");
    expect(overlayLegendFor("skyview")).toContain("hinnang");
    // G18A-HOOK (#172): dayopen + glassglare legends carry halves + honesty.
    expect(overlayLegendFor("dayopen")).toContain("150 m");
    expect(overlayLegendFor("dayopen")).toContain("hinnang");
    expect(overlayLegendFor("glassglare")).toContain("200 m");
    expect(overlayLegendFor("glassglare")).toContain("hinnang");
    // Batch G18B halves (see G18B_CAL in layers_group18restb.ts).
    expect(overlayLegendFor("fishbowl")).toContain("150 m");
    expect(overlayLegendFor("fishbowl")).toContain("hinnang");
    expect(overlayLegendFor("mossrisk")).toContain("250 m");
    expect(overlayLegendFor("mossrisk")).toContain("hinnang");
    expect(overlayLegendFor("daylight")).toContain("150");
    expect(overlayLegendFor("daylight")).toContain("hinnang");
    // Batch G17A halves (see G17A_CAL in layers_group17a.ts).
    expect(overlayLegendFor("compost")).toContain("küllastus 1");
    expect(overlayLegendFor("compost")).toContain("hinnang");
    expect(overlayLegendFor("gritbin")).toContain("küllastus 1");
    expect(overlayLegendFor("gritbin")).toContain("hinnang");
    expect(overlayLegendFor("leafdrop")).toContain("küllastus 1");
    expect(overlayLegendFor("leafdrop")).toContain("hinnang");
    // G17B-HOOK (#178): lawncare joins the registry.
    expect(overlayLegendFor("lawncare")).toContain("küllastus 20");
    expect(overlayLegendFor("lawncare")).toContain("hinnang");
    // G17R-HOOK (#196): privroad joins the registry.
    expect(overlayLegendFor("privroad")).toContain("200 m");
    expect(overlayLegendFor("privroad")).toContain("hinnang");
    // B10C-HOOK (#230): utility halves (see BATCH10C_BONUS).
    expect(overlayLegendFor("water")).toContain("küllastus 1");
    expect(overlayLegendFor("waste")).toContain("küllastus 6");
    expect(overlayLegendFor("fiber")).toContain("küllastus 50");
    expect(overlayLegendFor("mobile")).toContain("mitte mastid");
    // OSMDAILY-HOOK (#482): daily-life halves (see OSMDAILY_BONUS).
    expect(overlayLegendFor("dailyshop")).toContain("küllastus 8");
    expect(overlayLegendFor("dailyshop")).toContain("hinnang");
    expect(overlayLegendFor("activity")).toContain("küllastus 12");
    expect(overlayLegendFor("activity")).toContain("mitte turvalisus");
    expect(overlayLegendFor("herd")).toContain("küllastus 3");
    expect(overlayLegendFor("herd")).toContain("maitse-hinnang");
    expect(overlayLegendFor("thirdplace")).toContain("küllastus 12");
    expect(overlayLegendFor("thirdplace")).toContain("hinnang");
    expect(overlayLegendFor("taxidoor")).toContain("küllastus 30");
    expect(overlayLegendFor("taxidoor")).toContain("hinnang");
    expect(overlayLegendFor("lastshop")).toContain("küllastus 12");
    expect(overlayLegendFor("lastshop")).toContain("HOIATUS");
    // GTFS-HOOK (#483): gtfsstops legend carries the half + honesty
    // (schedules, never ridership — see GTFSSTOPS_BONUS).
    expect(overlayLegendFor("gtfsstops")).toContain("1500");
    expect(overlayLegendFor("gtfsstops")).toContain("sõiduplaan");
    expect(overlayLegendFor("gtfsstops")).toContain("EI OLE");
    // RSAFE-HOOK (#481): roadsafety half + usage-not-safety caveat.
    expect(overlayLegendFor("roadsafety")).toContain("küllastus 60");
    expect(overlayLegendFor("roadsafety")).toContain("kasutus-hinnang");
    // P4-031-HOOK (#484): senscom bands (see SENSCOM_BANDS).
    expect(overlayLegendFor("senscom")).toContain("500 m");
    expect(overlayLegendFor("senscom")).toContain("kalibreerimata");
    // STATKOV-HOOK (#485): choropleth bands (see STATKOV_BANDS).
    expect(overlayLegendFor("kovmigr")).toContain("hinnang");
    expect(overlayLegendFor("kovmigr")).toContain("EI OLE");
    expect(overlayLegendFor("kovehit")).toContain("lagi 70");
    expect(overlayLegendFor("kovfisc")).toContain("lagi 70");
    // P4PARK-HOOK (#479): parking joins the registry.
    expect(overlayLegendFor("parking")).toContain("küllastus 75");
    expect(overlayLegendFor("parking")).toContain("hinnang");
    // MARUKOV-HOOK (#486): choropleth bands (see MARUKOV_BANDS).
    expect(overlayLegendFor("kovkasv")).toContain("hinnang");
    expect(overlayLegendFor("kovkasv")).toContain("EI OLE");
    expect(overlayLegendFor("kovkaive")).toContain("hinnang");
    expect(overlayLegendFor("kovedas")).toContain("EI OLE");
    expect(overlayLegendFor("kovkiirus")).toContain("lagi 70");
    // FLOOD-HOOK (#487): floodzone choropleth + outside-unknown caveat
    // (polygons only, never a gradient).
    expect(overlayLegendFor("floodzone")).toContain("tsoonis = hinnang");
    expect(overlayLegendFor("floodzone")).toContain("väljaspool = teadmata");
    // P4OSM-HOOK (#480): walkability + darkness halves (see P4OSM_BONUS).
    expect(overlayLegendFor("blockwalk")).toContain("küllastus 1000");
    expect(overlayLegendFor("blockwalk")).toContain("hinnang");
    expect(overlayLegendFor("darkness")).toContain("küllastus 500");
    expect(overlayLegendFor("darkness")).toContain("hinnang");

    // MAAPARCEL-HOOK (#491): parcel classes + outside-unknown caveat
    // (facts, never suspicion scores — see MAAPARCEL_CLASS_FILL).
    expect(overlayLegendFor("maaparcel")).toContain("omandivormi");
    expect(overlayLegendFor("maaparcel")).toContain("väljaspool = teadmata, mitte tühi");
    expect(overlayLegendFor("maaparcel")).toContain("RIK hoonestuse kontroll");


    // PLANKTPR-HOOK (#492): planktpr legend carries the bands + the
    // dated WFS negative (polygons, never OSM landuse — see
    // PLANKTPR_USE_BANDS).
    expect(overlayLegendFor("planktpr")).toContain("hinnang");
    expect(overlayLegendFor("planktpr")).toContain("EI OLE");
    expect(overlayLegendFor("planktpr")).toContain("2026-09-13");
    expect(overlayLegendFor("planktpr")).toContain("elamu");

    // ASUMEDIA-HOOK (#495): asumedia legend carries the dated negative
    // (0/84 asums at MIN_N=5 — thin asums never faked, see
    // ASUMEDIA_VERDICT).
    expect(overlayLegendFor("asumedia")).toContain("ootel-hinnang");
    expect(overlayLegendFor("asumedia")).toContain("EI FEIGITA");
    expect(overlayLegendFor("asumedia")).toContain("2026-09-14");
    expect(overlayLegendFor("asumedia")).toContain("0/84");
    // PAASTE-HOOK (#493): paaste legend carries the radius + honesty
    // (coverage, never response time — see PAASTE_BANDS).
    expect(overlayLegendFor("paaste")).toContain("5 km");
    expect(overlayLegendFor("paaste")).toContain("60");
    expect(overlayLegendFor("paaste")).toContain("EI OLE");
    // SPORT-HOOK (#607): sport legends carry the bands + the
    // linnulennult honesty (see SPORT_EDGES_M).
    expect(overlayLegendFor("sport_hall")).toContain("≤500 m -> 80");
    expect(overlayLegendFor("sport_hall")).toContain("linnulennult");
    expect(overlayLegendFor("sport_field")).toContain("≤2 km -> 50");
    expect(overlayLegendFor("sport_pool")).toContain("veekvaliteeti ei hinnata");
    // EHIS-HOOK (#608): ehis legends carry the bands + the
    // linnulennult honesty (see EHIS_EDGES_M).
    expect(overlayLegendFor("ehis_school")).toContain("≤500 m -> 80");
    expect(overlayLegendFor("ehis_school")).toContain("õppekeel teadmata");
    expect(overlayLegendFor("ehis_kindergarten")).toContain("kohtade arv teadmata");
    expect(overlayLegendFor("ehis_hobby")).toContain("õhuke valim");
    // MEDRE-HOOK (#609): medre legends say EI OLE + uinuv (Step-1
    // honest-empty — linkage_rate 0, stated, never faked).
    expect(overlayLegendFor("medre_gp")).toContain("EI OLE liitmist");
    expect(overlayLegendFor("medre_gp")).toContain("avatud-olek teadmata");
    expect(overlayLegendFor("medre_clinic")).toContain("eriarstiabi väljas");
    // OHUSEIRE-HOOK (#610): station legend names the 3 stations + the
    // flat-60 thinness (see OHUSEIRE_EDGES_M).
    expect(overlayLegendFor("ohuseire")).toContain("Rahu / Liivalaia / Õismäe");
    expect(overlayLegendFor("ohuseire")).toContain("2+ jaama 70 ainult skooris");
  });

  it("gives every layer a distinct marker color", () => {
    const seen = new Set((LAYERS.map((l) => l.id) as LayerId[]).map(overlayColorFor));
    // G08D-HOOK (#170): vernalpool joins the registry.
    // G08C-HOOK (#169): surgeroad + slidebuf join the registry.
    // G08B-HOOK (#168): windtunnel + saltspray join the registry.
    // G05B-HOOK (#162): gardens + buildout join the registry.
    // G05D-HOOK (#164): strsat joins the registry.
    // G05A-HOOK (#161): ehitus + korterstock join the registry.
    // G05C-HOOK (#163): commbleed + windsolar + viewshed join the registry.
    // G05E-HOOK (#165): equestrian joins the registry.
    // G05F-HOOK (#166): upcycle joins the registry.
    // G10R-HOOK (#171): skyview joins the registry.
    // G18A-HOOK (#172): dayopen + glassglare join the registry.
    // G18B-HOOK (#173): fishbowl + mossrisk + daylight join the registry.
    // G17A-HOOK (#177): compost + gritbin + leafdrop join the registry.
    // G17B-HOOK (#178): lawncare joins the registry.
    // G17R-HOOK (#196): privroad joins the registry.
    // B10C-HOOK (#230): water + waste + fiber + mobile join the registry.
    // OSMDAILY-HOOK (#482): six daily-life layers join the registry.
    // GTFS-HOOK (#483): gtfsstops joins the registry.
    // RSAFE-HOOK (#481): roadsafety joins the registry.
    // P4-031-HOOK (#484): senscom joins the registry.
    // STATKOV-HOOK (#485): kovmigr + kovehit + kovfisc join the registry (86 + 3).
    // P4PARK-HOOK (#479): parking joins the registry. (89 + 1).
    // MARUKOV-HOOK (#486): kovkasv + kovkaive + kovedas + kovkiirus join the registry (90 + 4).
    // FLOOD-HOOK (#487): floodzone joins the registry (89 + 1). (94 + 1).
    // P4OSM-HOOK (#480): blockwalk + darkness join the registry. (95 + 2).
    // OOKLA-HOOK (#489): ookla_fixed + ookla_mobile join the registry (97 + 2).
    // ACCBLACK-HOOK (#490): accblack joins the registry (99 + 1).
    // MAAPARCEL-HOOK (#491): maaparcel joins the registry (100 + 1).

    // EELIS-HOOK (#488): eeliskaitse + eelisniit + eelisraie join the registry (101 + 3).
    // PLANKTPR-HOOK (#492): planktpr joins the registry (104 + 1).
    // TERVISE-HOOK (#494): tervise joins the registry. (105 + 1).
    // ASUMEDIA-HOOK (#495): asumedia joins the registry (106 + 1).
    // PAASTE-HOOK (#493): paaste joins the registry (107 + 1).
    // SPORT-HOOK (#607): sport_hall/field/pool join the registry (108 + 3).
    // EHIS-HOOK (#608): ehis_school/kindergarten/hobby join the registry (111 + 3).
    // MEDRE-HOOK (#609): medre_gp/clinic join the registry (114 + 2).
    // OHUSEIRE-HOOK (#610): ohuseire joins the registry (116 + 1).
    // KLIIMA-HOOK (#611): kliima_frost/wet join the registry (117 + 2).
    // POI-HOOK (#612): poi_library/post/pharmacy join the registry (119 + 3).
    // FIXIT-HOOK (#623): fixit joins the registry (122 + 1).
    // SEVESO-HOOK (#613): seveso joins the registry (123 + 1).
    // STATELAND-HOOK (#615): stateland joins the registry (124 + 1).
    // QUARRY-HOOK (#614): quarry joins the registry (125 + 1).
    // DRAINAGE-HOOK (#616): drainage joins the registry (126 + 1).
    // SOIL-HOOK (#617): soil joins the registry (127 + 1).
    // ETAK-HOOK (#618): etak joins the registry (128 + 1).
    // RELIEF-HOOK (#619): relief joins the registry (129 + 1).
    // MERGE (#613+#614+#615): 123 shipped + seveso + stateland + quarry = 126.
    // GBFS-HOOK (#688): +1 gbfs bike-share layer (154 + 1 = 155).
    // SKIS-HOOK (#692): +1 skis track layer (155 + 1 = 156).
    // HARNO-HOOK (#687): +1 harno school layer (156 + 1 = 157).
    // VIIRS-HOOK (#719): +1 viirs brightness layer (157 + 1 = 158).
    expect(seen.size).toBe(158); // SILLY (#711): 142 shipped + silly x12 = 154.
    for (const c of seen) expect(c).toMatch(/^#[0-9a-f]{6}$/);
  });
});

describe("fetchGraphOverlay", () => {
  it("calls the overlay endpoint with bbox + cap, cleaning junk", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          points: [
            { lon: 24.75, lat: 59.43, w: 1 },
            { lon: 24.76, lat: 59.44 },
            { lon: "x", lat: 59.44 },
            { lon: 24.77, lat: 59.45, w: -3 },
            null,
          ],
        }),
    });
    const pts = await fetchGraphOverlay("walkability", BBOX, 800, fetchImpl);
    const url = String(fetchImpl.mock.calls[0][0]);
    expect(url.startsWith("/api/layers/walkability/overlay?")).toBe(true);
    expect(url).toContain("cap=800");
    expect(pts).toEqual([
      { lon: 24.75, lat: 59.43, w: 1 },
      { lon: 24.76, lat: 59.44 },
      { lon: 24.77, lat: 59.45 },
    ]);
  });

  it("clamps the cap and reads null on failure", async () => {
    const seen: string[] = [];
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      seen.push(url);
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ points: [] }) });
    });
    await fetchGraphOverlay("cycling", BBOX, 99999, fetchImpl);
    expect(seen[0]).toContain("cap=2000");
    const bad = vi.fn().mockResolvedValue({ ok: false });
    await expect(fetchGraphOverlay("pedinfra", BBOX, 800, bad)).resolves.toBeNull();
    const shape = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve({ points: "nope" }) });
    await expect(fetchGraphOverlay("pedinfra", BBOX, 800, shape)).resolves.toBeNull();
    const boom = vi.fn().mockRejectedValue(new Error("down"));
    await expect(fetchGraphOverlay("pedinfra", BBOX, 800, boom)).resolves.toBeNull();
  });
});
