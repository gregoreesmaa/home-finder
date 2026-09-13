"""Group 19 on-site inspection per-listing dimensions, batch B (issue #209).

Params (this agent only — sibling batches own disjoint sets):
* p210 sewer line intrusion (ALWAYS None — pipe-camera fact, do not fake)
* p212 smart home cybersecurity (ALWAYS None — on-site audit, do not fake)
* p217 integrated battery backup (ALWAYS None — nameplate/acts, do not fake)
* p218 hardwired network infrastructure (ALWAYS None — cable runs, do not fake)
* p219 smart irrigation efficiency (ALWAYS None — controller, do not fake)
* p232 staircase ergonomics (ALWAYS None — laser tape, do not fake)
* p233 customized countertop height (ALWAYS None — tape, do not fake)
* p235 heavy-duty ceiling joists (ALWAYS None — engineer, do not fake)
* p236 threshold flushness (ALWAYS None — level, do not fake)
* p237 visual alarm pre-wiring (ALWAYS None — panel, do not fake)
* p238 allergen-trapping architecture (ALWAYS None — walkthrough, do not fake)
* p240 colorblind-friendly finishes (ALWAYS None — buyer eyes, do not fake)
* p261 wiring conduit availability (ALWAYS None — electrician, do not fake)
* p263 biometric security readiness (ALWAYS None — lock check, do not fake)
* p264 EV charging scale (ALWAYS None — panel kW, do not fake)
* p266 automated shading potential (ALWAYS None — wiring, do not fake)
* p267 home automation lock-in (ALWAYS None — hub audit, do not fake)
* p269 backup water cisterns (ALWAYS None — tanks/pump, do not fake)
* p284 heavy home gym capacity (ALWAYS None — engineer, do not fake)
* p291 flat roof drainage (ALWAYS None — roof review, do not fake)
* p292 cantilevered structural stress (ALWAYS None — engineer, do not fake)
* p293 radiant heat repairability (ALWAYS None — manifold/acts, do not fake)
* p294 below-grade window wells (ALWAYS None — drains, do not fake)
* p295 custom glazing costs (ALWAYS None — supplier quote, do not fake)
* p296 exposed architectural steel (ALWAYS None — sight check, do not fake)
* p297 vaulted ceiling energy waste (ALWAYS None — bills, do not fake)
* p298 adaptive reuse quirks (ALWAYS None — history/EHR, do not fake)
* p299 salvaged material delicacy (ALWAYS None — sight check, do not fake)
* p302 thermal bridge sensation (ALWAYS None — thermal camera, do not fake)
* p303 acoustic resonance between floors (ALWAYS None — listen, do not fake)
* p304 echo and room reverb (ALWAYS None — listen, do not fake)
* p306 plumbing water hammer (ALWAYS None — listen, do not fake)
* p307 HVAC register whistle (ALWAYS None — listen loaded, do not fake)
* p308 subtle tilt and floor slope (ALWAYS None — level, do not fake)

HONESTY (AGENTS.md section 7.2): parameters3.md section 5.19's own
protocol names the source — a certified building engineer audit (EVS
932:2017) + a buyer DIY walkthrough toolkit (GFCI tester, laser
meter, Protimeter moisture meter) + EHR concealed-work records
(kaetud toode aktid) + hydrostatic tests. NONE of these feeds is in
the 2026-09-12 snapshot (OSM PBF + Maa-amet WFS + derived area
rasters), so every dim stays NULL with an inspector-check reason.
Reasons say "hinnang" (estimate) and name the missing check — never
a camera finding, a kW reading, a thermal image, or a listening test.

Style mirrors services/scoring/dims_group18restc.py NULL dims
(#197): pure (origin, pois) -> (None, Estonian reason), hermetic
tests. No helpers are needed (no livability import, no local
copies): NULL dims take no measurements. Network lives only in
livability.fetch_pois; this module adds no network calls and no
Overpass fragment — NULL dims need no fetch.

Tag verification (2026-09-13, done once by the author with osmium
tags-filter/export against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout):
* amenity=charging_station: 341 objects county-wide (local tagging
  variant) — an area amenity that says nothing about THIS
  property's panel kW, so p264 stays NULL (consuming it would
  relabel neighbourhood amenity as per-property capacity).
* man_made=pipeline: 4501 objects — network geometry that says
  nothing about root intrusion in the property's own lateral (only
  a pipe camera does), so p210 stays NULL.
* sewer key: ZERO objects county-wide — no OSM sewer-condition
  signal exists at all.
* Snapshot inventory filename sweep: zero audit/inspect/NDT/
  walkthrough/interior/forensic feeds (the lone "ndt" hit is
  "windtunnel") — Tier-4 walkthrough facts have no snapshot feed
  by construction.

Judgment calls (reviewable per AGENTS.md section 7.5):
* All 34 return None for EVERY input including missing origin:
  inventing a gradient from zero signal (relabeling chargers as
  panel capacity, pipelines as lateral condition, or silence as
  good acoustics) would be fake precision (OTA PR #131
  precedent). The reasons point at the on-site check the buyer or
  inspector must do instead.
* p240 (colorblind-friendly finishes) is the buyer's own eyes, not
  an inspector meter — the reason says so instead of sending an
  engineer. p295 (glazing costs) points at a supplier quote, p298
  at EHR/history research: the check named is the honest one for
  that param, not a generic "visit".

Integration (deliberately NOT done here): rebalancing
livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be one
joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# p210: sewer line intrusion (pipe-camera fact — always None).
# ---------------------------------------------------------------------------

def dim_sewer_intrusion(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p210: NULL — root intrusion needs a pipe camera (no map)."""
    return None, ("Kanalisatsioonitorustiku läbikasv teadmata (vajab torukaamera "
                  "uuringut — hetktõmmises pole torustiku hinnangut; 4501 "
                  "kaardistatud pipeline-objekti on võrgu geomeetria, mitte haru "
                  "seisund — EI OLE kaamera-hinnangut, ära feigi; küsi kaetud "
                  "tööde aktid)")


# ---------------------------------------------------------------------------
# p212: smart home cybersecurity (on-site network audit — always None).
# ---------------------------------------------------------------------------

def dim_smart_cybersecurity(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p212: NULL — firmware/network audit happens on site (no map)."""
    return None, ("Nutikodu küberturve teadmata (vajab püsivara/võrgu auditit "
                  "kohapeal — hetktõmmises pole seadmete hinnangut — EI OLE "
                  "turva-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p217: integrated battery backup (nameplate/acts — always None).
# ---------------------------------------------------------------------------

def dim_battery_backup(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p217: NULL — battery capacity is a nameplate/acts fact (no map)."""
    return None, ("Akuvarutoite maht teadmata (kontrolli inverteri/akude nimesilte "
                  "ja paigaldusakti — hetktõmmises pole elektripaigaldise hinnangut "
                  "— EI OLE mahu-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p218: hardwired network infrastructure (cable runs — always None).
# ---------------------------------------------------------------------------

def dim_hardwired_network(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p218: NULL — Ethernet runs are a walkthrough fact (no map)."""
    return None, ("Kaabelvõrgu olemasolu ja läbilase teadmata (kontrolli kaabliteid "
                  "ja pistikuid kohapeal — hetktõmmises pole sisevõrgu hinnangut "
                  "— EI OLE läbilaske-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p219: smart irrigation efficiency (controller zones — always None).
# ---------------------------------------------------------------------------

def dim_smart_irrigation(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p219: NULL — irrigation zones are a walkthrough fact (no map)."""
    return None, ("Nutikastmise tõhusus teadmata (kontrolli kontrollerit ja tsoone "
                  "kohapeal — hetktõmmises pole kastmissüsteemi hinnangut — EI OLE "
                  "tõhususe hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p232: staircase ergonomics (laser tape — always None).
# ---------------------------------------------------------------------------

def dim_staircase_ergonomics(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p232: NULL — riser/tread needs a laser tape on site (no map)."""
    return None, ("Trepi ergonoomika teadmata (mõõda astme kõrgus ja sügavus "
                  "laseriga kohapeal — hetktõmmises pole trepi mõõtude hinnangut "
                  "— EI OLE sammu-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p233: customized countertop height (tape — always None).
# ---------------------------------------------------------------------------

def dim_countertop_height(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p233: NULL — counter height needs a tape on site (no map)."""
    return None, ("Töötasapinna kõrguse sobivus teadmata (mõõda kohapeal — "
                  "hetktõmmises pole köögimõõtude hinnangut — EI OLE kõrguse "
                  "hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p235: heavy-duty ceiling joists (engineer/attic — always None).
# ---------------------------------------------------------------------------

def dim_ceiling_joists(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p235: NULL — joist capacity needs attic/engineer review (no map)."""
    return None, ("Laetalade kandevõime teadmata (vajab pööningu ülevaatust või "
                  "inseneri auditit — hetktõmmises pole konstruktsiooni hinnangut "
                  "— EI OLE kandevõime hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p236: threshold flushness (level — always None).
# ---------------------------------------------------------------------------

def dim_threshold_flushness(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p236: NULL — threshold trip risk needs a level on site (no map)."""
    return None, ("Lävepakkude tasasus teadmata (kontrolli nivelliiri või "
                  "mõõdulindiga kohapeal — hetktõmmises pole viimistluse hinnangut "
                  "— EI OLE tasasuse hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p237: visual alarm pre-wiring (panel — always None).
# ---------------------------------------------------------------------------

def dim_visual_alarm(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p237: NULL — strobe pre-wire needs a panel check (no map)."""
    return None, ("Visuaalalarmide eeljuhtmestus teadmata (kontrolli kilpi ja "
                  "kaableid kohapeal — hetktõmmises pole nõrkvoolu valmiduse "
                  "hinnangut — EI OLE valmiduse hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p238: allergen-trapping architecture (walkthrough — always None).
# ---------------------------------------------------------------------------

def dim_allergen_arch(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p238: NULL — materials/ventilation need a walkthrough (no map)."""
    return None, ("Allergeene kinni pidav arhitektuur teadmata (hinda materjale ja "
                  "ventilatsiooni kohapeal — hetktõmmises pole siseõhuallika "
                  "hinnangut — EI OLE allergeeni-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p240: colorblind-friendly finishes (buyer eyes — always None).
# ---------------------------------------------------------------------------

def dim_colorblind_finishes(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p240: NULL — finish suitability is the buyer's own eyes (no map)."""
    return None, ("Värvipimedatele sobivad viimistlused teadmata (ostja enda silmade "
                  "küsimus — hetktõmmises pole viimistlusvaliku hinnangut — EI OLE "
                  "sobivuse hinnangut, ära feigi; vali kohapealsel külastusel)")


# ---------------------------------------------------------------------------
# p261: wiring conduit availability (electrician — always None).
# ---------------------------------------------------------------------------

def dim_wiring_conduit(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p261: NULL — conduit passability needs an electrician (no map)."""
    return None, ("Kaablitorude olemasolu ja läbitavus teadmata (kontrolli kilbi ja "
                  "avade kaudu kohapeal — hetktõmmises pole paigaldise hinnangut "
                  "— EI OLE läbitavuse hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p263: biometric security readiness (lock check — always None).
# ---------------------------------------------------------------------------

def dim_biometric_security(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p263: NULL — fingerprint-lock fit needs a door check (no map)."""
    return None, ("Biomeetrilise turva valmidus teadmata (kontrolli ukse ja luku "
                  "ühilduvust kohapeal — hetktõmmises pole lukustuse hinnangut "
                  "— EI OLE valmiduse hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p264: EV charging scale (panel kW — always None).
# ---------------------------------------------------------------------------

def dim_ev_scale(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p264: NULL — charge power is a panel/contract fact (no map)."""
    return None, ("EV-laadimise võimsus teadmata (kontrolli ampse ja faase kilbist "
                  "ning liitumislepingust — hetktõmmises pole laadimisvõimsuse "
                  "hinnangut; 341 kaardistatud laadijat on piirkonna mugavus, mitte "
                  "kilbi võimsus — EI OLE kW-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p266: automated shading potential (shading wiring — always None).
# ---------------------------------------------------------------------------

def dim_automated_shading(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p266: NULL — blind-motor wiring needs a site check (no map)."""
    return None, ("Automaatvarjustuse potentsiaal teadmata (hinda aknaajamite "
                  "juhtmestikku kohapeal — hetktõmmises pole varjustuse hinnangut "
                  "— EI OLE potentsiaali hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p267: home automation lock-in (hub audit — always None).
# ---------------------------------------------------------------------------

def dim_automation_lockin(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p267: NULL — vendor lock-in needs a hub audit (no map)."""
    return None, ("Nutikodu tootjalukustus teadmata (kontrolli protokolle ja jaoturit "
                  "kohapeal — hetktõmmises pole ökosüsteemi hinnangut — EI OLE "
                  "lukustuse hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p269: backup water cisterns (tanks/pump — always None).
# ---------------------------------------------------------------------------

def dim_backup_cisterns(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p269: NULL — cistern volume needs a tanks check (no map)."""
    return None, ("Varuveemahutite olemasolu ja maht teadmata (kontrolli mahuteid ja "
                  "pumpa kohapeal — hetktõmmises pole veevaru hinnangut — EI OLE "
                  "mahu-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p284: heavy home gym capacity (engineer — always None).
# ---------------------------------------------------------------------------

def dim_home_gym(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p284: NULL — gym floor load needs an engineer (no map)."""
    return None, ("Raske kodujõusaali kandevõime teadmata (vajab inseneri "
                  "koormus-hinnangut — hetktõmmises pole põranda kandevõime "
                  "hinnangut — EI OLE koormuse hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p291: flat roof drainage (roof review — always None).
# ---------------------------------------------------------------------------

def dim_flatroof_drainage(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p291: NULL — falls/outlets need a roof review (no map)."""
    return None, ("Lamekatuse drenaaž teadmata (kontrolli kaldeid ja neelusid "
                  "katuse-ülevaatusel või vihmase ilmaga — hetktõmmises pole "
                  "katusevee hinnangut — EI OLE äravoolu-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p292: cantilevered structural stress (engineer — always None).
# ---------------------------------------------------------------------------

def dim_cantilever_stress(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p292: NULL — cantilever statics need an engineer (no map)."""
    return None, ("Konsoolse konstruktsiooni pingeseisund teadmata (vajab inseneri "
                  "staatika-auditit — hetktõmmises pole staatika hinnangut — EI OLE "
                  "kandevõime hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p293: radiant heat repairability (manifold/acts — always None).
# ---------------------------------------------------------------------------

def dim_radiant_repair(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p293: NULL — loops/access need manifold + concealed acts (no map)."""
    return None, ("Põrandakütte remonditavus teadmata (kontrolli jaotuskollektorit ja "
                  "kaetud tööde akte — hetktõmmises pole küttesüsteemi hinnangut "
                  "— EI OLE remondi-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p294: below-grade window wells (drains — always None).
# ---------------------------------------------------------------------------

def dim_window_wells(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p294: NULL — well drains/covers need a site check (no map)."""
    return None, ("Soklikorruse aknakaevude drenaaž ja katted teadmata (kontrolli "
                  "kohapeal — hetktõmmises pole kaevude hinnangut — EI OLE "
                  "äravoolu-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p295: custom glazing costs (supplier quote — always None).
# ---------------------------------------------------------------------------

def dim_glazing_costs(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p295: NULL — custom glass cost needs a supplier quote (no map)."""
    return None, ("Eritellimus-klaaside maksumus teadmata (küsi klaasifirmalt "
                  "pakkumine — hetktõmmises pole hinnakalkulatsiooni — EI OLE "
                  "kulu-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p296: exposed architectural steel (sight check — always None).
# ---------------------------------------------------------------------------

def dim_exposed_steel(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p296: NULL — corrosion/fireproofing need a sight check (no map)."""
    return None, ("Paljandatud terase seisukord teadmata (kontrolli korrosiooni ja "
                  "tulekatet visuaalselt kohapeal — hetktõmmises pole terase "
                  "hinnangut — EI OLE seisundi-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p297: vaulted ceiling energy waste (bills — always None).
# ---------------------------------------------------------------------------

def dim_vaulted_ceiling(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p297: NULL — volume heating cost needs bills/logic (no map)."""
    return None, ("Kõrge lae energiakulu teadmata (uuri kütteloogikat ja arveid — "
                  "hetktõmmises pole ruumimahu kulu-hinnangut — EI OLE "
                  "kulu-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p298: adaptive reuse quirks (history/EHR — always None).
# ---------------------------------------------------------------------------

def dim_adaptive_reuse(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p298: NULL — rebuild quirks need history/EHR research (no map)."""
    return None, ("Taaskasutatud hoone eripärad teadmata (uuri ümberehituse ajalugu "
                  "ja EHR-i — hetktõmmises pole ajaloo hinnangut — EI OLE eripärade "
                  "hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p299: salvaged material delicacy (sight check — always None).
# ---------------------------------------------------------------------------

def dim_salvaged_material(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p299: NULL — salvaged wear needs a sight check (no map)."""
    return None, ("Taaskasutatud materjalide õrnus ja kulumine teadmata (hinda "
                  "visuaalselt kohapeal — hetktõmmises pole materjali seisundi "
                  "hinnangut — EI OLE vastupidavuse hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p302: thermal bridge sensation (thermal camera — always None).
# ---------------------------------------------------------------------------

def dim_thermal_bridge(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p302: NULL — heat leaks need a thermal camera (no map)."""
    return None, ("Külmasillad teadmata (mõõda termokaameraga kütteperioodil — "
                  "hetktõmmises pole soojusleke hinnangut — EI OLE "
                  "termopildi-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p303: acoustic resonance between floors (listen — always None).
# ---------------------------------------------------------------------------

def dim_acoustic_resonance(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p303: NULL — inter-floor resonance needs listening (no map)."""
    return None, ("Korrustevaheline heliresonants teadmata (kuula kohapeal vaikses "
                  "majas — hetktõmmises pole akustika mõõtmist — EI OLE "
                  "heli-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p304: echo and room reverb (listen — always None).
# ---------------------------------------------------------------------------

def dim_echo_reverb(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p304: NULL — reverb needs listening in the room (no map)."""
    return None, ("Kaja ja järelkõla teadmata (kuula kohapeal, soovitavalt tühjas "
                  "ruumis — hetktõmmises pole akustika mõõtmist — EI OLE järelkõla "
                  "hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p306: plumbing water hammer (listen — always None).
# ---------------------------------------------------------------------------

def dim_water_hammer(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p306: NULL — hammer knocks need listening at taps (no map)."""
    return None, ("Torustiku veelöögid teadmata (kuula kraanide sulgemisel kohapeal "
                  "— hetktõmmises pole torustiku heli-hinnangut — EI OLE "
                  "löögi-hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p307: HVAC register whistle (listen loaded — always None).
# ---------------------------------------------------------------------------

def dim_register_whistle(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p307: NULL — grille whistle needs full-load listening (no map)."""
    return None, ("Ventilatsioonirestide vilin teadmata (kuula HVAC-i täisvõimsusel "
                  "kohapeal — hetktõmmises pole müramõõtmist — EI OLE mürataseme "
                  "hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p308: subtle tilt and floor slope (level — always None).
# ---------------------------------------------------------------------------

def dim_floor_slope(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p308: NULL — settlement slope needs a level on site (no map)."""
    return None, ("Põranda kalle ja viltusus teadmata (mõõda nivelliiri või pika "
                  "latiga kohapeal — hetktõmmises pole tasasuse mõõtmist — EI OLE "
                  "kalde-hinnangut, ära feigi)")


GROUP19B_DIMS = (
    ("sewer_intrusion", "p210", dim_sewer_intrusion),
    ("smart_cybersecurity", "p212", dim_smart_cybersecurity),
    ("battery_backup", "p217", dim_battery_backup),
    ("hardwired_network", "p218", dim_hardwired_network),
    ("smart_irrigation", "p219", dim_smart_irrigation),
    ("staircase_ergonomics", "p232", dim_staircase_ergonomics),
    ("countertop_height", "p233", dim_countertop_height),
    ("ceiling_joists", "p235", dim_ceiling_joists),
    ("threshold_flushness", "p236", dim_threshold_flushness),
    ("visual_alarm", "p237", dim_visual_alarm),
    ("allergen_arch", "p238", dim_allergen_arch),
    ("colorblind_finishes", "p240", dim_colorblind_finishes),
    ("wiring_conduit", "p261", dim_wiring_conduit),
    ("biometric_security", "p263", dim_biometric_security),
    ("ev_scale", "p264", dim_ev_scale),
    ("automated_shading", "p266", dim_automated_shading),
    ("automation_lockin", "p267", dim_automation_lockin),
    ("backup_cisterns", "p269", dim_backup_cisterns),
    ("home_gym", "p284", dim_home_gym),
    ("flatroof_drainage", "p291", dim_flatroof_drainage),
    ("cantilever_stress", "p292", dim_cantilever_stress),
    ("radiant_repair", "p293", dim_radiant_repair),
    ("window_wells", "p294", dim_window_wells),
    ("glazing_costs", "p295", dim_glazing_costs),
    ("exposed_steel", "p296", dim_exposed_steel),
    ("vaulted_ceiling", "p297", dim_vaulted_ceiling),
    ("adaptive_reuse", "p298", dim_adaptive_reuse),
    ("salvaged_material", "p299", dim_salvaged_material),
    ("thermal_bridge", "p302", dim_thermal_bridge),
    ("acoustic_resonance", "p303", dim_acoustic_resonance),
    ("echo_reverb", "p304", dim_echo_reverb),
    ("water_hammer", "p306", dim_water_hammer),
    ("register_whistle", "p307", dim_register_whistle),
    ("floor_slope", "p308", dim_floor_slope),
)


def score_group19b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All 34 Group 19 batch-B dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP19B_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP19B_DIMS}
