"""Group 19 on-site-inspection-C per-listing dimensions (issue #210).

Params (this agent only — sibling batches own disjoint sets):
* p309 microbial/musty scent perception, p310 natural ventilation draft
  pattern
* p321 make-up air unit integration, p322 ductwork zoning dampers,
  p323 attic ventilation balance, p324 condensate line routing,
  p325 main shutoff valve accessibility, p326 combustion appliance
  backdraft, p327 sump pump backup redundancy, p328 thermostatic
  expansion valve, p329 vapor barrier integrity in crawlspace,
  p330 sewer backflow preventer presence
* p341 grocery unloading ergonomics, p344 emergency egress from
  bedroom, p345 stroller/cart navigability, p348 furniture delivery
  clearance
* p357 knob-and-tube wiring presence, p358 coal chute and oil tank
  remnants
* p373 hurricane strap retrofitting, p374 backup generator fuel supply,
  p375 potable water storage tanks, p376 wildfire smoke air-scrubbing,
  p379 tornado wind-load ratings
* p391 lawn equipment access, p392 sprinkler system winterizing,
  p393 pool equipment noise, p396 snow storage space, p399 outdoor
  hose bib placement
* p406 allergen circulation, p407 black mold vulnerability
* p414 perimeter breach points, p415 safe room potential, p416
  driveway choke points

HONESTY (AGENTS.md section 7.2): Group 19 is Tier 4 on-site forensic
walkthrough & mechanical diagnostics (Certified Building Engineer Audit
EVS 932:2017; buyer DIY toolkit: GFCI tester, laser meter, Protimeter).
Every param here is a per-unit forensic fact that needs physical
presence, a meter, or a hand-test in the room — no OSM snapshot area
signal can resolve it, so EVERY scorer returns None with a
buyer/inspector-check reason in Estonian (EI OLE hinnangut). Reasons
name the check the buyer or certified inspector must do instead —
never a faked area score (OTA PR #131 precedent).

Style mirrors sibling batch dims_group19a.py (#208): every scorer is
pure and offline-tested — (origin, pois) -> (None, Estonian reason).
There is deliberately NO Overpass fragment, NO POI-kind mapping and NO
kinds_from_tags here: with zero honest snapshot signal, fetching OSM
kinds for these params would only feed fake precision. A future
central hook imports GROUP19C_DIMS / score_group19c alongside the
sibling batches (same no-cycle precedent as batch B3, PR #100).

Judgment calls (reviewable per AGENTS.md section 7.5):
* ALL 33 dims return None for EVERY input including missing origin:
  inventing a gradient from zero signal would be fake precision.
* p393 (pool equipment noise) stays NULL even though its spec row
  names a noise raster / CNOSSOS-EU fallback: traffic-noise simulation
  cannot hear whether the pool pump runs, on what duty cycle, or how
  loud it is at the terrace — that needs ears + a dBA meter on site.
* p344 (emergency egress) stays NULL even though floorplan parsing
  is named: compliance is sill height + clear opening size measured
  with a tape plus the local fire-code check, never a polygon.
* p357/p358 stay NULL even though building age is mapped: age hints
  risk, never presence — live knob-and-tube needs an electrician's
  eyes, a buried oil tank needs records + a soil check.
* p373/p379 stay NULL even though wind happens everywhere: the fact
  is the BUILDING's straps / ratings in documents, not area climate.
* p341/p345/p348/p416 stay NULL even though streets and driveways
  are mapped: the fact is the unit's walked/driven path (grocery
  route, stroller run, furniture clearances, gate radius), not the
  public road graph.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


def dim_microbial_musty_scent(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """p309: NULL — musty scent is smelled with a nose on site."""
    return None, ("Hallituse/kopituse lõhna tunneb ainult nina kohapeal "
                  "(EI OLE hinnangut — vajab nuusutuskäiku + Protimeter- "
                  "niiskusmõõtmist ja remondiakte, ära feigi)")


def dim_natural_ventilation_draft(origin: Optional[Tuple[float, float]],
                                  pois: Optional[List[dict]]) -> Score:
    """p310: NULL — draft pattern needs a smoke-pencil test indoors."""
    return None, ("Loomuliku tuulutuse tõmbemuster selgub suitsupliiatsiga "
                  "toas (EI OLE hinnangut — vajab DIY-tõmbekontrolli eri "
                  "tuulega, ära feigi)")


def dim_makeup_air_unit(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p321: NULL — make-up air unit is inventoried in the plant room."""
    return None, ("Järelõhu seadme olemasolu ja ühendus selgub tehnoruumis "
                  "(EI OLE hinnangut — vajab inseneri inventuuri + "
                  "hooldusakte, ära feigi)")


def dim_ductwork_zoning(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p322: NULL — zoning dampers are opened and tested on site."""
    return None, ("Õhukanalite tsooniklapid on pööningu/lae-tagune fakt "
                  "(EI OLE hinnangut — vajab klappide avamist ja "
                  "katsetamist kohapeal, ära feigi)")


def dim_attic_ventilation(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p323: NULL — attic balance is judged standing in the attic."""
    return None, ("Pööningu tuulutuse tasakaal (sisse/äravool) hinnatakse "
                  "pööningul seistes (EI OLE hinnangut — vajab inseneri "
                  "kontrolli + niiskusjälgede lugemist, ära feigi)")


def dim_condensate_routing(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p324: NULL — condensate line is traced from unit to drain."""
    return None, ("Kondensaaditoru kulg ja äravool aetakse jälgi kohapeal "
                  "(EI OLE hinnangut — vajab toru jälitamist seadmest "
                  "äravooluni, ära feigi)")


def dim_shutoff_valve_access(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p325: NULL — shutoff findability is proven by hand on site."""
    return None, ("Peakraani leitavus ja keeratavus selgub ainult kätt "
                  "proovides (EI OLE hinnangut — vajab ostja ligipääsu- "
                  "katset kohapeal, ära feigi)")


def dim_combustion_backdraft(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p326: NULL — backdraft needs a CO worst-case depressurization test."""
    return None, ("Põlemisseadme tagasivoolu (vingugaasi riski) mõõdab "
                  "ainult CO-mõõtja halvima alarõhuga (EI OLE hinnangut — "
                  "vajab sertifitseeritud põlemisohutuse testi, ära feigi)")


def dim_sump_pump_backup(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p327: NULL — pump redundancy is start-tested at the pit."""
    return None, ("Kuivenduspumba varutoide (aku + tagavarapump) katsetatakse "
                  "kaevu juures (EI OLE hinnangut — vajab käivitustesti + "
                  "hooldusakte, ära feigi)")


def dim_expansion_valve(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p328: NULL — expansion valve is a nameplate + technician fact."""
    return None, ("Paisumisventiili olemasolu ja töö loetakse nimesildilt "
                  "ja tehnikult (EI OLE hinnangut — vajab külmatehniku "
                  "kohapealset kontrolli, ära feigi)")


def dim_vapor_barrier(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p329: NULL — crawlspace membrane is seen crawling inside."""
    return None, ("Roomiku aurutõkke terviklikkuse näeb roomikusse ronides "
                  "(EI OLE hinnangut — vajab inseneri ülevaatust + "
                  "niiskusmõõtmist, ära feigi)")


def dim_sewer_backflow(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p330: NULL — backflow flap is proven opening the hatch."""
    return None, ("Kanalisatsiooni tagasivooluklapi olemasolu selgub luuki "
                  "avades (EI OLE hinnangut — vajab torumehe kontrolli + "
                  "paigaldusakti, ära feigi)")


def dim_grocery_unloading(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p341: NULL — grocery route is walked with bags on site."""
    return None, ("Poekottidega mahalaadimise mugavus kõnnitakse läbi "
                  "kottidega (EI OLE hinnangut — teekaart treppe ja uksi "
                  "ei kanna, ära feigi)")


def dim_emergency_egress(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p344: NULL — egress compliance is tape-measured at the window."""
    return None, ("Magamistoa avariiväljapääsu (ava, lengi kõrgus) mõõdetakse "
                  "mõõdulindiga (EI OLE hinnangut — põrandaplaan avanevust "
                  "ei näita, ära feigi)")


def dim_stroller_navigation(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p345: NULL — stroller run is pushed through on site."""
    return None, ("Lapsevankri läbitavus (lift, lävepakud, koridorid) "
                  "katsetatakse vankriga (EI OLE hinnangut — vajab ostja "
                  "läbisõitu kohapeal, ära feigi)")


def dim_furniture_clearance(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p348: NULL — furniture clearances are laser-measured indoors."""
    return None, ("Mööbli sissetoomise vabad mõõdud mõõdetakse laseriga "
                  "(EI OLE hinnangut — vajab ostja mõõtmist ustel ja "
                  "trepikojas, ära feigi)")


def dim_knob_tube_wiring(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p357: NULL — knob-and-tube is found lighting the attic/cellar."""
    return None, ("Portselanisolaator-juhtmestik leitakse pööningut/keldrit "
                  "valgustades (EI OLE hinnangut — hoone vanus olemasolu "
                  "ei tõesta, ära feigi)")


def dim_coal_chute_oil_tank(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p358: NULL — chute/tank remnants need cellar, yard + records."""
    return None, ("Söeluugi ja õlimahuti jäänused (sh maetud mahuti "
                  "pinnasereostus) selguvad keldrist/hoovist ja registritest "
                  "(EI OLE hinnangut — vajab keskkonna-kontrolli + EHR "
                  "akte, ära feigi)")


def dim_hurricane_straps(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p373: NULL — strap clips are seen at the rafter foot in the attic."""
    return None, ("Tormiklambrid (sarikakinnitused) näeb pööningul sarikajala "
                  "juurest (EI OLE hinnangut — vajab inseneri kinnituste "
                  "kontrolli, ära feigi)")


def dim_generator_fuel(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p374: NULL — generator fuel store is inventoried + start-tested."""
    return None, ("Varugeneraatori kütusevaru (paak, varu, toide) "
                  "inventeeritakse kohapeal (EI OLE hinnangut — vajab "
                  "ülevaatust + käivitustesti, ära feigi)")


def dim_water_storage_tanks(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p375: NULL — potable tanks are seen + water-sampled on site."""
    return None, ("Joogivee varumahutite olemasolu ja puhtus selgub mahuteid "
                  "nähes (EI OLE hinnangut — vajab inventuuri + veeproovi, "
                  "ära feigi)")


def dim_smoke_air_scrubbing(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p376: NULL — smoke-season filtering is a filter/ventilation fact."""
    return None, ("Suitsuaja õhupuhastusvõime (filtrid, ventilatsioon) on "
                  "seadme-fakt (EI OLE hinnangut — vajab filtrite kontrolli "
                  "+ hooldusakte, ära feigi)")


def dim_tornado_wind_load(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p379: NULL — wind-load rating lives in project documents."""
    return None, ("Tuulekoormuse reiting on hoone dokumentide fakt, mitte "
                  "piirkonna ilm (EI OLE hinnangut — vajab projekti + "
                  "inseneri hinnangut, ära feigi)")


def dim_lawn_equipment_access(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """p391: NULL — gates/shed/slopes are measured in the yard."""
    return None, ("Murutööriistade ligipääs (väravad, kuur, kallakud) "
                  "mõõdetakse hoovis (EI OLE hinnangut — vajab ostja "
                  "kohapealset kontrolli, ära feigi)")


def dim_sprinkler_winterizing(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """p392: NULL — winterizing is proven by valves + blowout records."""
    return None, ("Kastmissüsteemi talvekindlus (tühjendusventiilid, "
                  "puhumisaktid) selgub klapikambrit nähes (EI OLE "
                  "hinnangut — vajab hooldaja akte, ära feigi)")


def dim_pool_equipment_noise(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p393: NULL — pump noise is heard while it runs (no raster hears it)."""
    return None, ("Basseiniseadmete müra (pump, soojuspump) kuuleb ainult "
                  "seadme töötades krundil (EI OLE hinnangut — "
                  "liiklusmüra simulatsioon pumpa ei kuule, ära feigi)")


def dim_snow_storage(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p396: NULL — snow room is judged from plan + winter visit."""
    return None, ("Lume ladustamisruum hoovis selgub plaani ja talvise "
                  "ülevaatuse põhjal (EI OLE hinnangut — vajab ostja "
                  "kohapealset hinnangut, ära feigi)")


def dim_hose_bib_placement(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p399: NULL — outdoor taps are opened and pressure-tested."""
    return None, ("Õuekraanide asukohad ja surve loetakse kraane avades "
                  "(EI OLE hinnangut — vajab DIY-kontrolli + surveproovi, "
                  "ära feigi)")


def dim_allergen_circulation(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p406: NULL — allergen loop is a filter/duct-maintenance fact."""
    return None, ("Allergeenide ringlus (filtrid, kanalipuhastus, niiskus) "
                  "on ventilatsiooni-fakt (EI OLE hinnangut — vajab "
                  "filtrite kontrolli + hooldusakte, ära feigi)")


def dim_black_mold_vulnerability(origin: Optional[Tuple[float, float]],
                                 pois: Optional[List[dict]]) -> Score:
    """p407: NULL — mold vulnerability is measured + read from history."""
    return None, ("Musthallituse haavatavust (niiskusajalugu, külmasillad) "
                  "näitab mõõtmine + ajalugu (EI OLE hinnangut — vajab "
                  "Protimeter-mõõtmist + remondiakte, ära feigi)")


def dim_perimeter_breach(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p414: NULL — weak perimeter points are walked on the plot."""
    return None, ("Perimeetri nõrgad kohad (aiad, hekid, pimedad nurgad) "
                  "kõnnitakse krunt läbi (EI OLE hinnangut — vajab ostja "
                  "turvaülevaatust, ära feigi)")


def dim_safe_room_potential(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p415: NULL — safe-room choice is made judging rooms indoors."""
    return None, ("Varjuruumi potentsiaal (akendeta sisetuba, seinad, uks) "
                  "selgub tubasid hinnates (EI OLE hinnangut — vajab "
                  "ostja/inseneri valikut kohapeal, ära feigi)")


def dim_driveway_choke(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p416: NULL — driveway narrows are driven with a car on site."""
    return None, ("Sissesõidutee kitsaskohad (värav, raadius, kalle) "
                  "sõidetakse läbi autoga (EI OLE hinnangut — teekaart "
                  "hoovi kitsust ei mõõda, ära feigi)")


GROUP19C_DIMS = (
    ("microbial_musty_scent", "p309", dim_microbial_musty_scent),
    ("natural_ventilation_draft", "p310", dim_natural_ventilation_draft),
    ("makeup_air_unit", "p321", dim_makeup_air_unit),
    ("ductwork_zoning", "p322", dim_ductwork_zoning),
    ("attic_ventilation", "p323", dim_attic_ventilation),
    ("condensate_routing", "p324", dim_condensate_routing),
    ("shutoff_valve_access", "p325", dim_shutoff_valve_access),
    ("combustion_backdraft", "p326", dim_combustion_backdraft),
    ("sump_pump_backup", "p327", dim_sump_pump_backup),
    ("expansion_valve", "p328", dim_expansion_valve),
    ("vapor_barrier", "p329", dim_vapor_barrier),
    ("sewer_backflow", "p330", dim_sewer_backflow),
    ("grocery_unloading", "p341", dim_grocery_unloading),
    ("emergency_egress", "p344", dim_emergency_egress),
    ("stroller_navigation", "p345", dim_stroller_navigation),
    ("furniture_clearance", "p348", dim_furniture_clearance),
    ("knob_tube_wiring", "p357", dim_knob_tube_wiring),
    ("coal_chute_oil_tank", "p358", dim_coal_chute_oil_tank),
    ("hurricane_straps", "p373", dim_hurricane_straps),
    ("generator_fuel", "p374", dim_generator_fuel),
    ("water_storage_tanks", "p375", dim_water_storage_tanks),
    ("smoke_air_scrubbing", "p376", dim_smoke_air_scrubbing),
    ("tornado_wind_load", "p379", dim_tornado_wind_load),
    ("lawn_equipment_access", "p391", dim_lawn_equipment_access),
    ("sprinkler_winterizing", "p392", dim_sprinkler_winterizing),
    ("pool_equipment_noise", "p393", dim_pool_equipment_noise),
    ("snow_storage", "p396", dim_snow_storage),
    ("hose_bib_placement", "p399", dim_hose_bib_placement),
    ("allergen_circulation", "p406", dim_allergen_circulation),
    ("black_mold_vulnerability", "p407", dim_black_mold_vulnerability),
    ("perimeter_breach", "p414", dim_perimeter_breach),
    ("safe_room_potential", "p415", dim_safe_room_potential),
    ("driveway_choke", "p416", dim_driveway_choke),
)


def score_group19c(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All 33 Group 19 batch-C dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP19C_DIMS). Every value is
    None by design — the walkthrough fills these facts, never the map."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP19C_DIMS}
