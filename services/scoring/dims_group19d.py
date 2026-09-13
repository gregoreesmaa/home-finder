"""Group 19 on-site inspection dimensions, batch D (issue #211).

Params (this agent only — sibling batches own disjoint sets):
* p417 smart lock compatibility, p418 exterior motion lighting
* p431 post-tension slab foundation, p432 unconventional rooflines,
  p433 staircase width and pitch, p434 pocket door framing,
  p435 sunken living rooms (conversion), p436 skylight leak history,
  p437 radiator footprint, p438 spray-foam inspection hurdle,
  p439 un-grounded electrical outlets, p440 soffit and fascia rot
* p451 modern vehicle clearance, p452 appliance cut-out constraints,
  p453 closet depth, p454 staircase headroom, p455 kitchen exhaust
  routing, p456 window treatment viability, p457 subfloor squeaks
  under finished floor, p458 ceiling fan junction boxes,
  p459 bathroom ventilation methods, p460 interior paint finish
* p472 gutter downspout termination, p473 exterior outlet scarcity,
  p474 driveway material maintenance, p475 water heater placement
  liability, p477 patio slope and settling, p478 exterior hose bib
  pressure
* p492 pet urine subfloor saturation, p494 chimney draft inversions,
  p496 dry-rot under decking, p497 galvanized steel pipe corrosion,
  p498 fireplace structural separation

HONESTY (load-bearing, AGENTS.md §7.2): Group 19 is Tier 4
(on-site forensic walkthrough & mechanical diagnostics —
parameters3.md §5.19: certified building engineer audit EVS 932:2017,
buyer DIY walkthrough toolkit with GFCI tester / laser meter /
Protimeter moisture meter, EHR concealed-work records). Every param
in this batch is a per-property physical-presence fact: a thing an
inspector or the buyer must touch, measure, open, walk on, or test
with a meter in THAT unit. No OSM snapshot area signal can resolve
any of them, so ALL 33 dims return None with a concrete
inspector/buyer-check reason — never a faked area score (OTA PR #131
precedent). Unknown (origin or POI list missing) stays None too.

Style mirrors services/scoring/dims_group18restc.py NULL dims
(#197): pure (origin, pois) -> (None, Estonian reason), hermetic
tests. No helpers are needed (no livability import, no local
copies): NULL dims take no measurements. Network lives only in
livability.fetch_pois; this module adds no network calls and no
Overpass fragment — NULL dims need no fetch.

Tag verification: none applies — these params have no OSM tag
surface by construction (a GFCI reading, a laser-measured headroom,
a Protimeter percentage, or a chimney smoke test cannot be read off
map geometry). The verdict registry documenting this lives in
apps/web/lib/layers_group19d.ts (GROUP19D_NO_MAP).

Judgment calls (reviewable per AGENTS.md §7.5):
* All 33 stay NULL for EVERY input, including a fully populated POI
  list: inventing a gradient from zero signal would be fake
  precision. The reasons point at the walkthrough/inspector check
  the buyer must do instead (toolkit item or expert named).
* Reasons say "EI OLE hinnangut" and end "ära feigi" so a future
  integrator grepping for faked scores finds the guard.
* Truncated English names in the parameters3.md §5.19 table
  (p435/p438/p439/p452/p457/p474/p475/p492/p497/p498 cells cut at
  ~30 chars) are completed from the DB column slug in the same row
  (e.g. p435_sunken_living_rooms_conve -> conversion); the
  completion is noted per-dim below.

Integration (deliberately NOT done here): rebalancing
livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be one
joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# p417: smart lock compatibility (door-measurement fact — always None).
# ---------------------------------------------------------------------------

def dim_smart_lock(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p417: NULL — lock fit needs the door measured on site (do not fake)."""
    return None, ("Nutuluku sobivus (ukse paksus, lukukorpuse mõõt, backset) "
                  "selgub ainult kohapeal ust mõõtes — vajab ostja ja "
                  "korteriühistu kontrolli (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p418: exterior motion lighting (dusk-visit fact — always None).
# ---------------------------------------------------------------------------

def dim_motion_lighting(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p418: NULL — motion-light coverage needs a dark-hours visit."""
    return None, ("Õue liikumisvalgustuse olemasolu ja katvus selguvad ainult "
                  "pimedas kohapealsel külastusel — vajab ostja õhtust "
                  "kontrolli (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p431: post-tension slab foundation (document + engineer fact — None).
# ---------------------------------------------------------------------------

def dim_posttension_slab(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p431: NULL — tensioned cables need drawings + engineer (do not fake)."""
    return None, ("Järelpingestatud plaatvundamendi olemasolu ja kaablite kulg "
                  "selguvad ainult ehitusdokumentidest/EHR-ist ja inseneri "
                  "kohapealsel hinnangul — ilma kaartideta puurimine lõhub "
                  "kaableid (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p432: unconventional rooflines (roof-walk fact — always None).
# ---------------------------------------------------------------------------

def dim_rooflines(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p432: NULL — roofline leak risk needs a physical roof survey."""
    return None, ("Ebatavaliste katusejoonte (orud, läbiviigud, liited) "
                  "lekkirisk selgub ainult katuse füüsilisel kohapealsel "
                  "ülevaatusel — vajab katusemeistri või inseneri kontrolli "
                  "(EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p433: staircase width and pitch (tape-measure fact — always None).
# ---------------------------------------------------------------------------

def dim_stair_geometry(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p433: NULL — stair width/pitch need a tape measure on site."""
    return None, ("Trepi laiuse ja kalde vastavus selgub ainult kohapeal "
                  "mõõdulindiga mõõtes — vajab ostja DIY-kontrolli (EI OLE "
                  "hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p434: pocket door framing (operate-and-listen fact — always None).
# ---------------------------------------------------------------------------

def dim_pocket_door(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p434: NULL — pocket-door track wear needs operating the door."""
    return None, ("Taskuukse raami seisukord ja siinide kulumine selguvad "
                  "ainult kohapeal ust liigutades — vajab ostja kontrolli "
                  "(EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p435: sunken living rooms (visit + permit fact — always None).
# Table name truncated ("Sunken living rooms (convers"); completed from
# the DB column slug p435_sunken_living_rooms_conve -> conversion.
# ---------------------------------------------------------------------------

def dim_sunken_living(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p435: NULL — sunken-room trip risk/conversion needs visit + permit."""
    return None, ("Süvistatud elutoa astme komistusrisk ja ümberehituse "
                  "võimalus selguvad ainult kohapealsel külastusel — vajab "
                  "ostja ja ehitusloa kontrolli (EI OLE hinnangut — ära "
                  "feigi)")


# ---------------------------------------------------------------------------
# p436: skylight leak history (frame-and-ceiling fact — always None).
# ---------------------------------------------------------------------------

def dim_skylight_leaks(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p436: NULL — skylight seals need frame + interior ceiling check."""
    return None, ("Katuseakende lekked ja tihendite seisukord selguvad ainult "
                  "kohapeal raami ja siselae jälgi kontrollides — vajab "
                  "vihmajärgset külastust või inseneri (EI OLE hinnangut — "
                  "ära feigi)")


# ---------------------------------------------------------------------------
# p437: radiator footprint (laser-measure fact — always None).
# ---------------------------------------------------------------------------

def dim_radiator_footprint(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p437: NULL — radiator footprint needs rooms measured on site."""
    return None, ("Radiaatorite tegelik jalajälg ja möbleerimispiirang "
                  "selguvad ainult kohapeal ruume mõõtes — vajab ostja "
                  "laser-mõõtja kontrolli (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p438: spray-foam inspection hurdle (concealment fact — always None).
# Table name truncated ("Spray-foam inspection hurdle"); completed from
# the DB column slug p438_spray_foam_inspection_hur -> hurdle.
# ---------------------------------------------------------------------------

def dim_sprayfoam_hurdle(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p438: NULL — foam hides rafters/leak marks from any remote read."""
    return None, ("Pritsvahu taha peidetud konstruktsiooni kontrollitavus "
                  "selgub ainult inseneri kohapealsel hinnangul — vaht varjab "
                  "sarikaid ja lekkejälgi (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p439: un-grounded electrical outlets (tester fact — always None).
# Table name truncated ("Un-grounded electrical outle"); completed from
# the DB column slug p439_un_grounded_electrical_ou -> outlets.
# ---------------------------------------------------------------------------

def dim_ungrounded_outlets(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p439: NULL — grounding needs a GFCI/plug tester in each socket."""
    return None, ("Maandamata pistikupesad selguvad ainult GFCI-testri või "
                  "pistikutestriga kohapeal — vajab ostja DIY-komplekti "
                  "kontrolli (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p440: soffit and fascia rot (ladder-and-prod fact — always None).
# ---------------------------------------------------------------------------

def dim_soffit_fascia(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p440: NULL — eaves rot needs touch/prod from a ladder."""
    return None, ("Räästaaluse ja otsalaua mädanik selgub ainult redelilt "
                  "katsudes ja torkides — vajab kohapealset ülevaatust "
                  "(EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p451: modern vehicle clearance (measure + test-drive fact — None).
# ---------------------------------------------------------------------------

def dim_vehicle_clearance(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p451: NULL — garage/gate clearance needs measuring + test drive."""
    return None, ("Garaaži ja värava läbipääs kaasaegsele autole (kõrgus, "
                  "laius, pöörderaadius) selgub ainult kohapeal mõõtes ja "
                  "proovisõidul — vajab ostja kontrolli (EI OLE hinnangut — "
                  "ära feigi)")


# ---------------------------------------------------------------------------
# p452: appliance cut-out constraints (niche-measure fact — always None).
# Table name truncated ("Appliance cut-out constraint"); completed from
# the DB column slug p452_appliance_cut_out_constra -> constraints.
# ---------------------------------------------------------------------------

def dim_appliance_cutout(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p452: NULL — appliance niche sizes need measuring on site."""
    return None, ("Kodumasinate paigaldusavade mõõdud ja ventilatsioon "
                  "selguvad ainult kohapeal mõõtes — vajab ostja mõõdulindi "
                  "kontrolli (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p453: closet depth (tape-measure fact — always None).
# ---------------------------------------------------------------------------

def dim_closet_depth(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p453: NULL — closet depth needs a tape measure on site."""
    return None, ("Kappide tegelik sügavus ja kasutusmugavus selguvad ainult "
                  "kohapeal mõõtes — vajab ostja kontrolli (EI OLE hinnangut "
                  "— ära feigi)")


# ---------------------------------------------------------------------------
# p454: staircase headroom (on-stair measure fact — always None).
# ---------------------------------------------------------------------------

def dim_stair_headroom(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p454: NULL — stair headroom needs measuring on the stairs."""
    return None, ("Trepi läbikäigukõrgus selgub ainult kohapeal trepil mõõtes "
                  "— vajab ostja DIY-kontrolli (EI OLE hinnangut — ära "
                  "feigi)")


# ---------------------------------------------------------------------------
# p455: kitchen exhaust routing (cabinet-and-duct fact — always None).
# ---------------------------------------------------------------------------

def dim_kitchen_exhaust(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p455: NULL — exhaust routing needs cabinets/ducts checked."""
    return None, ("Köögi väljatõmbe kanaliseerimine (välja või "
                  "retsirkulatsioon, kanali kulg) selgub ainult kohapeal "
                  "kappe ja kanaleid kontrollides — vajab inseneri või ostja "
                  "kontrolli (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p456: window treatment viability (opening-and-wall fact — always None).
# ---------------------------------------------------------------------------

def dim_window_treatment(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p456: NULL — curtain/blind fixing needs openings checked."""
    return None, ("Aknakatte (kardinapuud, rulood) kinnitusvõimalus selgub "
                  "ainult kohapeal aknaavasid ja seinamaterjali kontrollides "
                  "— vajab ostja külastust (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p457: subfloor squeaks under finished floor (walk fact — always None).
# Table name truncated ("Subfloor squeaks under finis"); completed from
# the DB column slug p457_subfloor_squeaks_under_fi -> finished floor.
# ---------------------------------------------------------------------------

def dim_subfloor_squeak(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p457: NULL — subfloor squeak needs walking the floor."""
    return None, ("Aluspõranda nagin viimistluse all selgub ainult kohapeal "
                  "põrandal kõndides — vajab ostja külastust (EI OLE "
                  "hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p458: ceiling fan junction boxes (electrician fact — always None).
# ---------------------------------------------------------------------------

def dim_fan_boxes(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p458: NULL — fan-box rating needs an electrician opening the box."""
    return None, ("Laeventilaatori harukarpide kandevõime selgub ainult "
                  "elektriku kohapealsel kontrollil (karbi avamine) — tavaline "
                  "valgustikarp ventilaatorit ei kanna (EI OLE hinnangut — "
                  "ära feigi)")


# ---------------------------------------------------------------------------
# p459: bathroom ventilation methods (moisture-check fact — always None).
# ---------------------------------------------------------------------------

def dim_bath_ventilation(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p459: NULL — bath ventilation needs on-site moisture/pull check."""
    return None, ("Vannitoa ventilatsioon (aken või ventilaator, kanali tõmme) "
                  "selgub ainult kohapeal — vajab niiskusmõõtja kontrolli "
                  "(EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p460: interior paint finish (daylight-look fact — always None).
# ---------------------------------------------------------------------------

def dim_paint_finish(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p460: NULL — paint finish quality needs daylight viewing."""
    return None, ("Sisevärvi viimistluse kvaliteet ja kulumine selguvad ainult "
                  "kohapeal päevavalguses seini vaadates — vajab ostja "
                  "külastust (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p472: gutter downspout termination (rain-visit fact — always None).
# ---------------------------------------------------------------------------

def dim_downspout_term(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p472: NULL — downspout discharge needs a rain/damp visit."""
    return None, ("Vihmaveetorude suubumine (vundamendist eemale või äärde) "
                  "selgub ainult kohapeal vihma ajal või järel — vajab ostja "
                  "kontrolli (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p473: exterior outlet scarcity (walk-around fact — always None).
# ---------------------------------------------------------------------------

def dim_exterior_outlets(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p473: NULL — exterior socket count needs walking the house."""
    return None, ("Õue pistikupesade olemasolu ja kaugus selguvad ainult "
                  "kohapeal maja ümber käies — vajab ostja kontrolli (EI OLE "
                  "hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p474: driveway material maintenance (surface-survey fact — None).
# Table name truncated ("Driveway material maintenanc"); completed from
# the DB column slug p474_driveway_material_mainten -> maintenance.
# ---------------------------------------------------------------------------

def dim_driveway_material(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p474: NULL — driveway surface wear needs an on-site survey."""
    return None, ("Sissesõidutee katte materjal ja hooldusvajadus (praod, "
                  "vajumine) selguvad ainult kohapealsel ülevaatusel — vajab "
                  "ostja külastust (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p475: water heater placement liability (plant-room fact — always None).
# Table name truncated ("Water heater placement liabi"); completed from
# the DB column slug p475_water_heater_placement_li -> liability.
# ---------------------------------------------------------------------------

def dim_water_heater_place(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p475: NULL — heater leak risk needs the plant room inspected."""
    return None, ("Boileri paigutusest tulenev lekkirisk (korrus, äravool, "
                  "alus) selgub ainult kohapeal tehnoruumi kontrollides — "
                  "vajab inseneri hinnangut (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p477: patio slope and settling (level-and-measure fact — always None).
# ---------------------------------------------------------------------------

def dim_patio_slope(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p477: NULL — patio fall/settling needs a level on site."""
    return None, ("Terrassi kalle (majast eemale) ja vajumine selguvad ainult "
                  "kohapeal vesiloodiga mõõtes — vajab ostja DIY-kontrolli "
                  "(EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p478: exterior hose bib pressure (tap-open fact — always None).
# ---------------------------------------------------------------------------

def dim_hosebib_pressure(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p478: NULL — hose-bib flow needs the tap opened on site."""
    return None, ("Õue veekraani surve ja külmakindlus selguvad ainult "
                  "kohapeal kraani avades — vajab ostja kontrolli (EI OLE "
                  "hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p492: pet urine subfloor saturation (meter + UV fact — always None).
# Table name truncated ("Pet urine subfloor saturatio"); completed from
# the DB column slug p492_pet_urine_subfloor_satura -> saturation.
# ---------------------------------------------------------------------------

def dim_pet_urine(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p492: NULL — urine saturation needs a moisture meter + UV lamp."""
    return None, ("Lemmiklooma uriini imbumine aluspõrandasse selgub ainult "
                  "niiskusmõõtja (Protimeter) ja UV-lambiga kohapeal — vaiba "
                  "all peidus (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p494: chimney draft inversions (heating-season fact — always None).
# ---------------------------------------------------------------------------

def dim_chimney_draft(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p494: NULL — draft inversions need a heating-season smoke test."""
    return None, ("Korstna tõmbe pöördumised selguvad ainult küttehooajal "
                  "kohapeal suitsukatsel — vajab korstnapühkija või inseneri "
                  "akti (EI OLE hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p496: dry-rot under decking (lift-and-prod fact — always None).
# ---------------------------------------------------------------------------

def dim_deck_dryrot(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p496: NULL — under-deck rot needs boards lifted/prodded."""
    return None, ("Terrassilaua-alune maja-vamm selgub ainult laudu tõstes ja "
                  "katsudes kohapeal — vajab inseneri kontrolli (EI OLE "
                  "hinnangut — ära feigi)")


# ---------------------------------------------------------------------------
# p497: galvanized steel pipe corrosion (plumber fact — always None).
# Table name truncated ("Galvanized steel pipe corros"); completed from
# the DB column slug p497_galvanized_steel_pipe_cor -> corrosion.
# ---------------------------------------------------------------------------

def dim_galv_pipe(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p497: NULL — internal galv corrosion needs pressure/camera test."""
    return None, ("Tsingitud terastorude sisemine korrosioon ja ummistus "
                  "selguvad ainult torumehe kohapealsel surveproovil või "
                  "kaamerauuringul — väljast paistab terve (EI OLE hinnangut "
                  "— ära feigi)")


# ---------------------------------------------------------------------------
# p498: fireplace structural separation (structural fact — always None).
# Table name truncated ("Fireplace structural separat"); completed from
# the DB column slug p498_fireplace_structural_sepa -> separation.
# ---------------------------------------------------------------------------

def dim_fireplace_separation(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p498: NULL — hearth separation needs a structural engineer."""
    return None, ("Kamina konstruktiivne eraldatus hoonest (praod, vajumine) "
                  "selgub ainult inseneri kohapealsel hinnangul — vajab "
                  "ehitusekspertiisi (EI OLE hinnangut — ära feigi)")


GROUP19D_DIMS = (
    ("smart_lock", "p417", dim_smart_lock),
    ("motion_lighting", "p418", dim_motion_lighting),
    ("posttension_slab", "p431", dim_posttension_slab),
    ("rooflines", "p432", dim_rooflines),
    ("stair_geometry", "p433", dim_stair_geometry),
    ("pocket_door", "p434", dim_pocket_door),
    ("sunken_living", "p435", dim_sunken_living),
    ("skylight_leaks", "p436", dim_skylight_leaks),
    ("radiator_footprint", "p437", dim_radiator_footprint),
    ("sprayfoam_hurdle", "p438", dim_sprayfoam_hurdle),
    ("ungrounded_outlets", "p439", dim_ungrounded_outlets),
    ("soffit_fascia", "p440", dim_soffit_fascia),
    ("vehicle_clearance", "p451", dim_vehicle_clearance),
    ("appliance_cutout", "p452", dim_appliance_cutout),
    ("closet_depth", "p453", dim_closet_depth),
    ("stair_headroom", "p454", dim_stair_headroom),
    ("kitchen_exhaust", "p455", dim_kitchen_exhaust),
    ("window_treatment", "p456", dim_window_treatment),
    ("subfloor_squeak", "p457", dim_subfloor_squeak),
    ("fan_boxes", "p458", dim_fan_boxes),
    ("bath_ventilation", "p459", dim_bath_ventilation),
    ("paint_finish", "p460", dim_paint_finish),
    ("downspout_term", "p472", dim_downspout_term),
    ("exterior_outlets", "p473", dim_exterior_outlets),
    ("driveway_material", "p474", dim_driveway_material),
    ("water_heater_place", "p475", dim_water_heater_place),
    ("patio_slope", "p477", dim_patio_slope),
    ("hosebib_pressure", "p478", dim_hosebib_pressure),
    ("pet_urine", "p492", dim_pet_urine),
    ("chimney_draft", "p494", dim_chimney_draft),
    ("deck_dryrot", "p496", dim_deck_dryrot),
    ("galv_pipe", "p497", dim_galv_pipe),
    ("fireplace_separation", "p498", dim_fireplace_separation),
)


def score_group19d(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All 33 Group 19 batch-D dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP19D_DIMS). Every value is
    None by design — on-site facts, never faked area scores."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP19D_DIMS}
