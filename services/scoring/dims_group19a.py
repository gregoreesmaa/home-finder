"""Group 19 on-site-inspection-A per-listing dimensions (issue #208).

Params (this agent only — sibling batches own disjoint sets):
* p10 renovation budget, p31 structural integrity, p38 HVAC systems
* p55 EV charging readiness, p57 plumbing pipe materials, p58 electrical
  service capacity, p59 water pressure and heating
* p91 ceiling height and volume, p95 interior acoustic insulation,
  p96 ventilation and air exchange, p97 basement usability
* p111 hurricane/typhoon readiness, p114 severe winter resilience,
  p115 seismic retrofitting, p116 tornado/storm shelter,
  p120 off-grid capabilities, p150 moving truck accessibility
* p171 foundation type, p172 insulation materials, p173 interior door
  quality, p174 floor joist engineering, p175 cabinet box construction,
  p176 window frame materials, p177 roofing material lifespan,
  p178 exterior cladding maintenance, p179 proprietary smart home lock-in
* p197 whole-home purification, p199 advanced physical security,
  p203 problematic plumbing materials, p205 synthetic stucco (EIFS),
  p206 chimney flue integrity, p207 retaining wall condition,
  p208 unpermitted hidden splices, p209 mold remediation history

HONESTY (AGENTS.md section 7.2): Group 19 is Tier 4 on-site forensic
walkthrough & mechanical diagnostics (Certified Building Engineer Audit
EVS 932:2017; buyer DIY toolkit: GFCI tester, laser meter, Protimeter).
Every param here is a per-unit forensic fact that needs physical
presence or a meter in the room — no OSM snapshot area signal can
resolve it, so EVERY scorer returns None with a buyer/inspector-check
reason in Estonian (EI OLE hinnangut). Reasons name the check the
buyer or certified inspector must do instead — never a faked area
score (OTA PR #131 precedent).

Style mirrors sibling batch dims_group03b.py (#152): every scorer is
pure and offline-tested — (origin, pois) -> (None, Estonian reason).
There is deliberately NO Overpass fragment, NO POI-kind mapping and NO
kinds_from_tags here: with zero honest snapshot signal, fetching OSM
kinds for these params would only feed fake precision. A future
central hook imports GROUP19A_DIMS / score_group19a alongside the
sibling batches (same no-cycle precedent as batch B3, PR #100).

Judgment calls (reviewable per AGENTS.md section 7.5):
* ALL 34 dims return None for EVERY input including missing origin:
  inventing a gradient from zero signal would be fake precision.
* p150 (moving truck access) stays NULL even though streets are
  mapped: the fact is the courtyard's turning radius / height limit /
  parking per unit, not the public road graph.
* p111/p114/p115/p116 (storm/winter/seismic/shelter) stay NULL even
  though weather happens everywhere: the fact is the BUILDING's
  fasteners / envelope / documents, not the area climate.
* p179 stays NULL: vendor lock-in is read from devices and contracts
  on site, never from a map.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


def dim_renovation_budget(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p10: NULL — budget needs on-site scope measurement + quotes."""
    return None, ("Remondieelarve eeldab kohapealset mahtude mõõtmist ja "
                  "töövõtja pakkumisi (EI OLE hinnangut — ala-kaart kulusid "
                  "ei ennusta, ära feigi)")


def dim_structural_integrity(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p31: NULL — structure needs an engineer audit on site."""
    return None, ("Kandekonstruktsiooni seisukord (praod, vajumised) selgub "
                  "ainult kohapeal (EI OLE hinnangut — vajab EVS 932:2017 "
                  "ehitusinseneri auditit, ära feigi)")


def dim_hvac_systems(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p38: NULL — HVAC state is an equipment fact, not an area fact."""
    return None, ("Kütte/ventilatsiooni/jahutuse seisukord on seadme-fakt, "
                  "mida kaart ei mõõda (EI OLE hinnangut — vajab inseneri "
                  "diagnostikat + hooldusraamatut, ära feigi)")


def dim_ev_charging_readiness(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """p55: NULL — EV readiness is a switchboard fact."""
    return None, ("EV-laadimise valmidus on elektrikilbi/liitumise fakt "
                  "(EI OLE hinnangut — vajab elektriku kohapealset "
                  "kontrolli, ära feigi)")


def dim_plumbing_pipe_materials(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """p57: NULL — pipe alloy is seen on pipes or in records only."""
    return None, ("Torude materjal selgub ainult torustikku nähes või "
                  "aktidest (EI OLE hinnangut — vajab torumehe kontrolli "
                  "+ EHR kaetud tööde akte, ära feigi)")


def dim_electrical_service_capacity(origin: Optional[Tuple[float, float]],
                                    pois: Optional[List[dict]]) -> Score:
    """p58: NULL — service capacity is measured at the board."""
    return None, ("Elektripaigaldise võimsus mõõdetakse kilbi juures (EI OLE "
                  "hinnangut — vajab elektriku mõõtmist + liitumisandmeid, "
                  "ära feigi)")


def dim_water_pressure_heating(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """p59: NULL — pressure/heat is measured at the tap."""
    return None, ("Veerõhk ja soe vesi mõõdetakse kraani juures (EI OLE "
                  "hinnangut — vajab ostja DIY-kontrolli kohapeal, "
                  "ära feigi)")


def dim_ceiling_height_volume(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """p91: NULL — ceiling height is laser-measured indoors."""
    return None, ("Lae kõrgus ja ruumimaht mõõdetakse laseriga toas (EI OLE "
                  "hinnangut — kaart lakke ei näe, ära feigi)")


def dim_interior_acoustic_insulation(origin: Optional[Tuple[float, float]],
                                     pois: Optional[List[dict]]) -> Score:
    """p95: NULL — sound insulation is heard/measured on site."""
    return None, ("Heliisolatsiooni kuuleb ja mõõdab ainult kohapeal (EI OLE "
                  "hinnangut — vajab külastust eri kellaaegadel, ära feigi)")


def dim_ventilation_air_exchange(origin: Optional[Tuple[float, float]],
                                 pois: Optional[List[dict]]) -> Score:
    """p96: NULL — air exchange is a room-measurement fact."""
    return None, ("Õhuvahetus selgub CO2/niiskuse mõõtmisest ruumis (EI OLE "
                  "hinnangut — vajab kohapealset mõõtmist + hooldusakte, "
                  "ära feigi)")


def dim_basement_usability(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p97: NULL — basement usability is judged standing in it."""
    return None, ("Keldri kasutatavus (niiskus, kõrgus, ligipääs) hinnatakse "
                  "keldris seistes (EI OLE hinnangut — vajab Protimeter- "
                  "mõõtmist, ära feigi)")


def dim_hurricane_readiness(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p111: NULL — storm fasteners are a roof/facade fact."""
    return None, ("Tormikinnitus on katuse/fassaadi kinnituste fakt (EI OLE "
                  "hinnangut — vajab inseneri kohapealset kontrolli, "
                  "ära feigi)")


def dim_severe_winter_resilience(origin: Optional[Tuple[float, float]],
                                 pois: Optional[List[dict]]) -> Score:
    """p114: NULL — winter resilience is a building-envelope fact."""
    return None, ("Talvekindlus (külmasillad, külmumisrisk, varuküte) on "
                  "hoone-fakt (EI OLE hinnangut — vajab inseneri "
                  "talveauditit + küttekulude ajalugu, ära feigi)")


def dim_seismic_retrofitting(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p115: NULL — seismic retrofit is read from project documents."""
    return None, ("Seismiline tugevdamine selgub ainult projektist (EI OLE "
                  "hinnangut — vajab projektdokumentatsiooni + inseneri "
                  "hinnangut, ära feigi)")


def dim_storm_shelter(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p116: NULL — shelter usability is checked on site."""
    return None, ("Varjumisruumi kasutatavus (kelder/varjend) selgub "
                  "plaanilt ja kohapeal (EI OLE hinnangut — vajab ostja "
                  "kontrolli, ära feigi)")


def dim_off_grid_capabilities(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """p120: NULL — off-grid kit is inventoried on the plot."""
    return None, ("Autonoomsus (kaev, septik, generaator, akud) on krundi "
                  "seadmete fakt (EI OLE hinnangut — vajab inventuuri "
                  "kohapeal + akte, ära feigi)")


def dim_moving_truck_access(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p150: NULL — courtyard turning radius is not the road graph."""
    return None, ("Kolimisveoki ligipääs (pöörderaadius, kõrguspiirang) "
                  "selgub hoovi üle vaadates (EI OLE hinnangut — tänavakaart "
                  "veoki ära ei mahuta, ära feigi)")


def dim_foundation_type(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p171: NULL — foundation is a concealed-structure fact."""
    return None, ("Vundamendi tüüp ja seisukord on kaetud konstruktsiooni "
                  "fakt (EI OLE hinnangut — vajab projekti + sondeerimist, "
                  "ära feigi)")


def dim_insulation_materials(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p172: NULL — insulation is a inside-the-wall fact."""
    return None, ("Soojustuse materjal ja paksus on seina-fakt (EI OLE "
                  "hinnangut — vajab projekti/akte või puurproovi, "
                  "ära feigi)")


def dim_interior_door_quality(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """p173: NULL — door quality is felt by hand on site."""
    return None, ("Siseuste kvaliteeti katsub ostja käega kohapeal (EI OLE "
                  "hinnangut — vajab DIY-ülevaatust, ära feigi)")


def dim_floor_joist_engineering(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """p174: NULL — joists are a concealed-structure fact."""
    return None, ("Vahelae talade lahendus on kaetud konstruktsiooni fakt "
                  "(EI OLE hinnangut — vajab projekti + inseneri avamist, "
                  "ära feigi)")


def dim_cabinet_construction(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p175: NULL — cabinet boxes are opened and tested on site."""
    return None, ("Köögikappide korpuse kvaliteeti näeb uksi avades (EI OLE "
                  "hinnangut — vajab ostja kohapealset kontrolli, "
                  "ära feigi)")


def dim_window_frame_materials(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """p176: NULL — window frames are a visible-on-site fact."""
    return None, ("Aknaraamide materjal ja seisukord on kohapeal nähtav "
                  "fakt (EI OLE hinnangut — vajab DIY-ülevaatust + "
                  "energiamärgist, ära feigi)")


def dim_roofing_lifespan(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p177: NULL — remaining roof life is judged standing on it."""
    return None, ("Katusekatte järelejäänud eluiga hindab katusemeister "
                  "katusel (EI OLE hinnangut — vajab katuse auditit + "
                  "paigaldusakte, ära feigi)")


def dim_exterior_cladding(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p178: NULL — cladding maintenance is seen on the facade."""
    return None, ("Fassaadikatte hooldusvajaduse näeb fassaadi üle vaadates "
                  "(EI OLE hinnangut — vajab inseneri/maalri hinnangut, "
                  "ära feigi)")


def dim_smart_home_lockin(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p179: NULL — vendor lock-in is read from devices + contracts."""
    return None, ("Nutikodu lukustus selgub seadmeid ja lepinguid lugedes "
                  "(EI OLE hinnangut — vajab ostja kontrolli, kas süsteem "
                  "töötab ilma tellimuseta, ära feigi)")


def dim_whole_home_purification(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """p197: NULL — purification kit is inventoried on site."""
    return None, ("Vee/õhu puhastusseadmete olemasolu on seadme-fakt (EI OLE "
                  "hinnangut — vajab kohapealset inventuuri + hooldusakte, "
                  "ära feigi)")


def dim_physical_security(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p199: NULL — doors/locks/bars are inspected on site."""
    return None, ("Füüsilise turvalisuse tase (uksed, lukud, võred) selgub "
                  "kohapeal (EI OLE hinnangut — vajab ostja/inseneri "
                  "ülevaatust, ära feigi)")


def dim_problematic_plumbing(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p203: NULL — lead/zinc steel is found by a plumber + water test."""
    return None, ("Probleemsed torumaterjalid (plii, tsink-teras) tuvastab "
                  "torumees kohapeal (EI OLE hinnangut — vajab auditit + "
                  "veeproovi, ära feigi)")


def dim_synthetic_stucco(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p205: NULL — EIFS moisture risk is sonded behind the wall."""
    return None, ("EIFS-fassaadi niiskusrisk mõõdetakse sondiga seina tagant "
                  "(EI OLE hinnangut — vajab inseneri sondeerimist, "
                  "ära feigi)")


def dim_chimney_flue(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p206: NULL — flue integrity needs a camera survey."""
    return None, ("Korsta lõõri terviklikkust näitab ainult kaamerauuring "
                  "(EI OLE hinnangut — vajab korstnapühkija kaamerakontrolli "
                  "+ akti, ära feigi)")


def dim_retaining_wall(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p207: NULL — retaining wall is judged standing before it."""
    return None, ("Tugimüüri seisukord (kalle, drenaaž, praod) hinnatakse "
                  "müüri ees seistes (EI OLE hinnangut — vajab inseneri "
                  "kontrolli, ära feigi)")


def dim_hidden_splices(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p208: NULL — hidden splices are found opening boards/boxes."""
    return None, ("Loata varjatud elektriühendused leitakse kilpi ja karpe "
                  "avades (EI OLE hinnangut — vajab elektriku auditit + EHR "
                  "kaetud tööde akte, ära feigi)")


def dim_mold_history(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p209: NULL — mold history is smelled/measured + read from records."""
    return None, ("Hallituse ajalugu selgub kohapeal + dokumentidest (EI OLE "
                  "hinnangut — vajab Protimeter-mõõtmist + remondiakte, "
                  "ära feigi)")


GROUP19A_DIMS = (
    ("renovation_budget", "p10", dim_renovation_budget),
    ("structural_integrity", "p31", dim_structural_integrity),
    ("hvac_systems", "p38", dim_hvac_systems),
    ("ev_charging_readiness", "p55", dim_ev_charging_readiness),
    ("plumbing_pipe_materials", "p57", dim_plumbing_pipe_materials),
    ("electrical_service_capacity", "p58", dim_electrical_service_capacity),
    ("water_pressure_heating", "p59", dim_water_pressure_heating),
    ("ceiling_height_volume", "p91", dim_ceiling_height_volume),
    ("interior_acoustic_insulation", "p95", dim_interior_acoustic_insulation),
    ("ventilation_air_exchange", "p96", dim_ventilation_air_exchange),
    ("basement_usability", "p97", dim_basement_usability),
    ("hurricane_readiness", "p111", dim_hurricane_readiness),
    ("severe_winter_resilience", "p114", dim_severe_winter_resilience),
    ("seismic_retrofitting", "p115", dim_seismic_retrofitting),
    ("storm_shelter", "p116", dim_storm_shelter),
    ("off_grid_capabilities", "p120", dim_off_grid_capabilities),
    ("moving_truck_access", "p150", dim_moving_truck_access),
    ("foundation_type", "p171", dim_foundation_type),
    ("insulation_materials", "p172", dim_insulation_materials),
    ("interior_door_quality", "p173", dim_interior_door_quality),
    ("floor_joist_engineering", "p174", dim_floor_joist_engineering),
    ("cabinet_construction", "p175", dim_cabinet_construction),
    ("window_frame_materials", "p176", dim_window_frame_materials),
    ("roofing_lifespan", "p177", dim_roofing_lifespan),
    ("exterior_cladding", "p178", dim_exterior_cladding),
    ("smart_home_lockin", "p179", dim_smart_home_lockin),
    ("whole_home_purification", "p197", dim_whole_home_purification),
    ("physical_security", "p199", dim_physical_security),
    ("problematic_plumbing", "p203", dim_problematic_plumbing),
    ("synthetic_stucco", "p205", dim_synthetic_stucco),
    ("chimney_flue", "p206", dim_chimney_flue),
    ("retaining_wall", "p207", dim_retaining_wall),
    ("hidden_splices", "p208", dim_hidden_splices),
    ("mold_history", "p209", dim_mold_history),
)


def score_group19a(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All 34 Group 19 batch-A dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP19A_DIMS). Every value is
    None by design — the walkthrough fills these facts, never the map."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP19A_DIMS}
