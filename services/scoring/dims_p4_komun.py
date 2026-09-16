"""P4 komun dims (issues #290 demo + #363 coverage).

Demo (#290): Tallinna Keskkonna- ja Kommunaalamet ingestion (P4-018)
— polite, cached, TTL-stated pulls of the winter-maintenance class
feed plus an honest-shape per-parcel road-class join end-to-end in
Tallinn. Coverage (#363): P4-007, P4-010, P4-016, P4-017, P4-024,
P4-026, P4-030, P4-042, P4-047, P4-053, P4-054, P4-055, P4-057,
P4-058, P4-059, P4-060, P4-062 wired to the same demoed ingestion
(no new plumbing expected unless a param needs it; none did, see
judgment calls).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #290): the department publishes no pollable machine-readable
feed for any of the eighteen slices below. Polite evidence, 6 tiny
requests total (six single GETs with a labelled one-off user-agent,
headers + visible-text keyword scope read only, no scraping, no
auth), raw bodies cached at /tmp/hf-komun-probe/ (TTL: one-off
check, kept for the PR record, never committed):
* https://www.tallinn.ee/ -> HTTP 200 (~138 KB, cloudflare).
  Storefront links the department page (/et/keskkonna-ja-
  kommunaalamet), the open-data page (/avaandmed/), the snow page
  (/et/lumi) and the geoportal (gis.tallinn.ee/veebikaart).
* https://www.tallinn.ee/et/keskkonna-ja-kommunaalamet -> HTTP 200
  (~219 KB). Human e-service pages (teenused/raieluba,
  kvartalisiseste-teede-hooldus, korraldatud-jaatmevedu) plus
  /et/lumi. Visible-text sweep (~25.9k chars) 0 for csv / geojson /
  wfs / andmestik / masinloetav; "api" 1x is page chrome, not a
  feed. Complaint intake is phone 14410 / 661 9860 and the
  annateada.ee app — human channels, never a lag table.
* https://www.tallinn.ee/avaandmed/ -> HTTP 200 (~76 KB) with 12
  visible characters: JS shell, no server-rendered datasets (same
  shell as the #264/#277/#284 national-portal checks).
* https://www.tallinn.ee/et/lumi -> HTTP 200 (~57 KB). 2025/2026
  winter-maintenance human page ("ühtlane hooldustase",
  lumekoristus news links); the maintenance-area map is an embedded
  human viewer (iframe gis.tallinn.ee/lumekaart/), not a feed —
  0 for csv / geojson / wfs / api / masinloetav.
* https://gis.tallinn.ee/lumekaart/ -> HTTP 200 (~5 KB,
  Microsoft-IIS). ArcGIS Experience Builder runtime shell
  ("Talihoolduse kaart", jimu-core/init.js, base ./cdn/1/); no
  WFS/WMS/GeoJSON/CSV endpoint advertised at page level. The
  2026-09-16 re-dig (see RE-DIG above) chased it one level deeper
  per AGENTS.md section 7.7 — static config.json 404s, keyless
  services directory open, maintenance AREAS layer found (no
  class attributes), city-wide hooldus/ folder key-gated.
* https://andmed.eesti.ee/dataset?q=talihooldus -> HTTP 200
  (~76 KB), 12 visible characters ("Teabevärav" JS shell) — no
  trivially pollable national-portal talihooldus dataset.

RE-DIG 2026-09-16 (re-open contract on #290, AGENTS.md section 7.7:
"open JS shells, don't file them"). 12 paced single GETs, same
labelled UA, HTTP 429 = stop (none seen), raw bodies kept at
/tmp/hf-komun-dig/ (PR record, never committed). Findings:
* The viewer is now an ArcGIS Experience Builder runtime shell
  (jimu-core/init.js, base ./cdn/1/), NOT Web AppBuilder: there is
  no static config.json — /lumekaart/config/config.json and
  /lumekaart/cdn/1/config/config.json both 404, and neither the
  loader (48 KB) nor the app entry (48 KB) bakes in service URLs.
  The app config is assembled at runtime, so the config.json step
  of the dig ends here (documented boundary, not a refusal).
* The ArcGIS services directory itself IS keyless and open
  (https://gis.tallinn.ee/arcgis/rest/services?f=json, ArcGIS
  Server 11.5, 23 folders / 70 root services).
* veebikaart/Teehoolduspiirkonnad_veebikaart MapServer (keyless)
  carries layer 0 'teehoolduspiirkonnad' (Feature Layer, polygons,
  displayField nimetus, Tallinn EPSG:3301 extent): Kommunaalameti
  hoolduspiirkonnad, "uuendatakse jooksvalt läbi Hoolduse
  kaardirakenduse". Fields are objectid/nimetus/markused/shape
  (+ area/length) — AREAS ONLY, no winter-maintenance class
  attribute (no tase/klass/level field), so the P4-018 per-street
  class join cannot be measured off it. No editingInfo timestamps
  are exposed, so there is no machine-readable vintage to cache —
  cadence is "jooksvalt" by description only. Field inventory is
  transcribed to tests/fixtures/komun_teehooldus_layer.json.
* The city-wide maintenance folder hooldus/ is KEY-GATED:
  /arcgis/rest/services/hooldus?f=json -> {"error": {"code":
  499, "message": "Token Required"}}. The class levels behind the
  lumekaart viewer live there (or behind an equivalent credentialed
  path) — refused territory per the issue contract, endpoint name
  pasted here as the deliverable.
* Root-level Pirita_hooldus ("Teehooldus hooldajatele": Pirita
  parklad/kõnniteed/tänavad + tables) is district-scoped
  contractor data — it cannot support a city-wide P4-018 join.
* Coordination with #536 (teeregister WFS, Transpordiamet, DAILY,
  CC-BY-4.0): the class join's honest future is the teeregister
  pull owned there, NOT this viewer. dim_winter_road_class in
  dims_p4_trans stays the fixture-codelist owner ("remap on first
  pull"); this module's snow_maintenance_class stays the
  street/sidewalk-class NULL leg beside the TLT winter-bus leg —
  no double-scoring by construction, nothing here graduates until
  a keyless class feed appears.
So all eighteen dims return None for EVERY input including missing
origin: a per-parcel class painted from a one-off hand-read of the
human viewer would be fake precision (OTA PR #131 precedent).
Reasons say "hinnang" (estimate) and "EI OLE" and point at the
concrete buyer-side check (tallinn.ee/et/lumi snow page, lumekaart
viewer, helpline 14410, raieloa e-teenus, kohapealne vaatlus) —
never a faked area score.

Style mirrors services/scoring/dims_p4_elron.py (#284/#358): every
scorer is pure and offline-tested — (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for the department's unpublished class tables,
complaint counts, or duty rosters, so there is nothing for the live
path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#363) states it extends the demoed ingestion (#290): with
  the demo verdict dated-negative, there is no ingestion to extend,
  so the seventeen coverage slices land in the same verdict module
  rather than a second file importing a pipeline that does not
  exist (same precedent as TLT #277+#351, elektrilevi #264+#344,
  comapps #302+#371, Elron #284+#358, RB #281+#355).
* Pairing rationale (each coverage param names this department in
  its parameters4.md source list): P4-007/P4-010 the Kommunaalamet
  KÜ-toetused legs; P4-016 the "Tallinna ÜVK + sademevee kaardid"
  septic cross-check leg (the EGT/Maa-amet geology legs live in
  dims_p4_maa_subsurface); P4-017 the ÜVK-arengukava
  liitumispiirkonnad leg (complement of the Tallinna Vesi utility
  zone table in dims_p4_tvesi); P4-024 the farm-odour kaebused leg;
  P4-026 the heakorra-teated + removal-lag leg; P4-030 the
  raieload/hooldusraie leg; P4-042/P4-053 the odour-complaint legs
  (cells vs wind sectors — different honest shapes, both NULL);
  P4-047 the mürakaebused + talihoolduse-veograafik calendar legs;
  P4-054/P4-055/P4-057 the mürakaebused validation legs;
  P4-058 the jääpurikate/lume-eemaldamise kohustused leg; P4-059
  the tahkekütte-piirangualad notices leg; P4-060 the Kommunaalamet
  sademevee/soodustuste-teated leg (complement of the Tallinna
  Vesi fee table in dims_p4_tvesi); P4-062 the rotikaebused hex
  leg. The non-komun legs stay scored where they live and are
  named missing here, never re-scored (same split-slice precedent
  as P4-020: ATA notices in dims_p4_ata, bureau scores NULL in
  dims_p4_creditinfo).
* P4-018 vs dims_p4_tlt winter-bus leg (#351): same buyer winter
  question, COMPLEMENTARY legs, not a duplicate. TLT reads the
  winter timetable (bus cuts); this dim reads the street/sidewalk
  maintenance class (plow burial). The OSM winter_service honest
  proxy stays in dims_p4_osm. The central hook joins one source
  per parcel later — one joint change.
* P4-026 (fix-it LAG rate) vs P4-062 (complaint COUNT flags):
  different honest shapes (hex responsiveness rate vs hex
  operational flags), both NULL — no double-scoring by
  construction.
* The 2026-09-13 openness check stopped at storefront/page/
  viewer-shell level on purpose; the 2026-09-16 re-dig superseded
  that stop per the #290 re-open contract (config.json chase +
  one keyless directory read per service, metadata only). Still
  refused throughout: credentialed endpoints (hooldus/ 499),
  per-record queries/exports, e-service flow driving, and
  complaint-form probing.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-018 (demo): snow/road maintenance class needs the per-parcel
# road-class join (teeregister + talihoolduse tasemed). The lumekaart
# viewer is human-only: no pollable class feed at page level, so the
# scorer reports the gap with the concrete buyer-side check.
# ---------------------------------------------------------------------------

def dim_snow_maintenance_class(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """P4-018: NULL — winter-trap class needs the maintenance-class feed.

    2026-09-16 re-dig: the keyless Teehoolduspiirkonnad areas layer
    carries nimetus/markused only (no class attribute) and the
    city-wide hooldus/ folder is token-gated, so the class join
    stays unmeasurable; the honest future is the teeregister pull
    owned by #536, whose fixture-codelist owner dim_winter_road_class
    in dims_p4_trans stays untouched here (no double-scoring)."""
    return None, ("Tänava talihooldusklass on talvise lõksu hinnang (EI OLE "
                  "masinloetavat klassitabelit): teede ja kõnniteede "
                  "hoolduspiirkonnad elavad inimloetaval lumekaardil "
                  "(tallinn.ee/et/lumi, gis.tallinn.ee/lumekaart) — "
                  "avalik veebikaart/Teehoolduspiirkonnad-teenus "
                  "kannab vaid alasid (nimetus/markused, klassiväljadeta) "
                  "ja hooldus-kaust küsib võtit, nii et klassiliidestust "
                  "pole — kontrolli oma tänava piirkonda kaardilt ja talvist "
                  "bussikärbe-slice'i dims_p4_tlt-st ning OSM "
                  "winter_service-proxy't dims_p4_osm-ist, ära feigi")


# ---------------------------------------------------------------------------
# P4-007/P4-010 (coverage): Kommunaalamet KÜ-toetused legs of the
# bill/renovation questions. The Äriregister/EIS/Creditinfo legs live
# in their own modules and are named, never re-scored here.
# ---------------------------------------------------------------------------

def dim_ku_loan_support(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-007: NULL — KÜ-toetuste tabel KÜ kohta on avaldamata (no map)."""
    return None, ("KÜ laenu- ja remondifondi-tõe Kommunaalameti-jalg on "
                  "arvehinnang (EI OLE KÜ-põhist toetuste-tabelit): "
                  "Tallinna Kommunaalameti KÜ-toetused elavad inimloetavate "
                  "teadetena — kontrolli KÜ majandusaasta aruannet "
                  "e-Äriregistrist ja krediidijalga dims_p4_creditinfo-st, "
                  "ära feigi")


def dim_renovation_grant_queue(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """P4-010: NULL — renoveerimistoetuste järjekord hoone kohta puudub."""
    return None, ("Hoone renoveerimistoetuse-järjekord on 5-kohalise arve "
                  "hinnang (EI OLE hoone-põhist järjekorra-voogu): "
                  "Kommunaalameti KÜ-renoveerimistoetused elavad "
                  "inimloetavate teadetena — kontrolli EIS-i "
                  "renoveerimistoetuste registrist ja EHR-i "
                  "renoveerimislubade-slice'i, ära feigi")


# ---------------------------------------------------------------------------
# P4-016/P4-017 (coverage): ÜVK-side legs. The EGT/Maa-amet geology
# legs (P4-016) and the Tallinna Vesi utility zone table (P4-017)
# live in dims_p4_maa_subsurface / dims_p4_tvesi respectively.
# ---------------------------------------------------------------------------

def dim_geology_uvk_crosscheck(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """P4-016: NULL — ÜVK/sademevee ristkontrolli-kiht puudub (no map)."""
    return None, ("Insenergeoloogia ÜVK-ristkontroll (septiku-teostatavus) "
                  "on vundamendihinna hinnang (EI OLE masinloetavat "
                  "ÜVK/sademevee-kihti): Tallinna ÜVK- ja sademevee-kaardid "
                  "elavad inimloetavalt — kontrolli EGT geoloogia-slice'i "
                  "dims_p4_maa_subsurface-ist ja ÜVK-arengukava, ära feigi")


def dim_uvk_development_plan(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """P4-017: NULL — ÜVK-arengukava liitumispiirkond krundi kohta puudub."""
    return None, ("ÜVK-arengukava liitumispiirkond (Nõmme/Pirita/Merivälja) "
                  "on 5-kohalise liitumise hinnang (EI OLE krundi-põhist "
                  "arengukava-liidestust): Keskkonna- ja Kommunaalameti "
                  "ÜVK-arengukava elab dokumendina — kontrolli Tallinna "
                  "Vesi tsoonitabeli-slice'i dims_p4_tvesi-st ja "
                  "iseteenindusest tehnilisi tingimusi, ära feigi")


# ---------------------------------------------------------------------------
# P4-024/P4-042/P4-053 (coverage): smell/nuisance complaint legs.
# Coarse hinnang cells (P4-024/P4-042) vs wind-sector calendar
# (P4-053) — different honest shapes, all unpublished, all NULL.
# ---------------------------------------------------------------------------

def dim_farm_odour_cells(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-024: NULL — farm-odour kaebuste koondrakud puuduvad (no map)."""
    return None, ("Põllu- ja loomapidamis-haisuse (Paljassaare) koondrakud "
                  "on laste/koerte-ohutuse hinnang (EI OLE kaebuste-koondit "
                  "masinloetavalt): Keskkonnaameti farm-haisuse kaebused "
                  "elavad inimloetavate teadetena — hinda tuulealust "
                  "asukohta kohapealsel vaatlusel, ära feigi")


def dim_fixit_responsiveness(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """P4-026: NULL — heakorra-remondi viivitusmäär heksi kohta puudub."""
    return None, ("KOV-i parandamiskiirus (valgustus, augud, lumi, grafiti) "
                  "on hooldaja-hinnang (EI OLE parandatud/eemaldatud-viibe "
                  "tabelit): abiliin/e-teenused (14410, annateada.ee) on "
                  "inimkanalid — küsi linnaosast eemaldamisviivet ja hinda "
                  "trepikoja hooldust KÜ aruandest, ära feigi")


def dim_tree_felling_flag(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-030: NULL — raielubade/hooldusraie teated linnaosa kohta puuduvad."""
    return None, ("Raielubade-muutuslipp (kaov salu, uus naaber, prügimägi) "
                  "on satelliidi-muutuse inimkontroll-hinnang (EI OLE "
                  "masinloetavat raielubade-voogu): Keskkonnaameti "
                  "raieload/hooldusraie elavad teadete ja raieloa-teenusena "
                  "— kontrolli Maa-ameti aerofoto-vintse ja EHR-i "
                  "ehituslubade-slice'i, ära feigi")


def dim_odour_complaint_cells(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """P4-042: NULL — haisu/koorikaebuste koondrakud puuduvad (no map)."""
    return None, ("Haisu- ja koidukoori-rakud (pagari/kala-suits vs sirel) "
                  "on mälumärgi-hinnang (EI OLE kaebuste-koondit, ukse- "
                  "täpsust keelab parameters4.md): Keskkonnaameti "
                  "haisu-kaebused (suits/prügimajad) elavad inimloetavalt "
                  "— nuusuta hommikuti kohapeal, ära feigi")


def dim_small_horrors_calendar(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """P4-047: NULL — väikeste õuduste kalender (müra + sahk) puudub."""
    return None, ("Väikeste õuduste kalender (kajakad, lehepuhurid, 4-hommikune "
                  "sahamatmine, mopeedid/ilutulestik) on 2-nädalase "
                  "diil-breakeri hinnang (EI OLE mürakaebuste- ega "
                  "sahagraafiku-kalendrit): talihoolduse veograafik ja "
                  "mürakaebused elavad inimloetavalt — kontrolli oma tänava "
                  "sahagraafikut tallinn.ee/et/lumi-lehelt ja kuula nädalavahetusel "
                  "kohapeal, ära feigi")


def dim_odour_rose_sectors(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-053: NULL — tuule-sageduse haisuroos sektorite kaupa puudub."""
    return None, ("Haisuroos tuule-sageduse järgi (Paljassaare, asfalt, "
                  "pruulikoda, kalasuits) on allatuule-päevade hinnang "
                  "(EI OLE sektori-põhist kaebuste-voogu, ring-puhvrit "
                  "keelab parameters4.md): Keskkonnaameti sektori-kaebused "
                  "elavad inimloetavalt — kontrolli Ilmateenistuse "
                  "Tallinn-Harku tuuleroosi ja ela üks tuuline nädal "
                  "kohapeal, ära feigi")


# ---------------------------------------------------------------------------
# P4-054/P4-055/P4-057 (coverage): mürakaebused validation legs.
# Timetable + buffer (P4-054), schedulable-noise calendar (P4-055),
# weak heating-type hinnang (P4-057) — the Sadam/EANS/Männiku/Elron
# timetable legs live in their own source issues and dims_p4_elron.
# ---------------------------------------------------------------------------

def dim_quarry_blast_season(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """P4-054: NULL — karjääri-lõhkamiste ajagraafik + veomarsruudid puuduvad."""
    return None, ("Karjääri-lõhkamiste ja veokite hooaeg (Maardu/Harku pae- "
                  "karjäärid, Pirita/Lasnamäe serv) on teisipäev-7-hommiku "
                  "hinnang (EI OLE lõhkamisgraafiku- ega veomarsruudi-"
                  "voogu): Keskkonnaameti mürakaebused elavad "
                  "inimloetavalt — kontrolli Maa-ameti maardlate-registrit "
                  "ja Tark Tee veokiliiklust, ära feigi")


def dim_schedulable_noise_calendar(origin: Optional[Tuple[float, float]],
                                   pois: Optional[List[dict]]) -> Score:
    """P4-055: NULL — ajatatava müra kalender (komun-validatsioon) puudub."""
    return None, ("Ajatatava müra kalender (udu-viled, jäämurdjad, Ämari "
                  "mürin, Männiku paugud) on graafikupõhise müra hinnang "
                  "(EI OLE masinloetavat mürakalendrit): Keskkonnaameti "
                  "mürakaebused valideerivad inimloetavalt — kontrolli "
                  "Tallinna Sadama laevagraafikut, EANS-i lennuinfot ja "
                  "raudteemüra-ööakende slice'i dims_p4_elron-ist, "
                  "ära feigi")


def dim_heatpump_hum(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """P4-057: NULL — soojuspumba-düni koridoride kaebused puuduvad."""
    return None, ("Soojuspumba-düni koridorid (Nõmme/Pirita/Merivälja "
                  "väliseadmed vs magamistoa aknad) on nõrk naabri-düni "
                  "hinnang (EI OLE masinloetavat mürakaebuste-voogu): "
                  "Keskkonnaameti düni-kaebused elavad inimloetavalt — "
                  "kontrolli EHR-i kütte-liigi muutuste-slice'i ja kuula "
                  "õhtuti kohapeal, ära feigi")


# ---------------------------------------------------------------------------
# P4-058/P4-059 (coverage): per-parcel rule/duty dims with dates.
# Falling-ice duties per street (P4-058) and solid-fuel restriction
# zones (P4-059) — both human notices, both NULL.
# ---------------------------------------------------------------------------

def dim_icefall_duty_warnings(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """P4-058: NULL — jääpurika-kohustused/hoiatused tänava kaupa puuduvad."""
    return None, ("Jääpurikate/lume-eemaldamise kohustused ja hoiatused "
                  "tänava kaupa on talvise vastutuse hinnang (EI OLE "
                  "masinloetavat kohustuste-kalendrit): Keskkonna- ja "
                  "Kommunaalameti hoiatused elavad inimloetavate teadetena "
                  "— kontrolli EHR-i katuse-tüübi slice'i ja Päästeameti "
                  "jää-kukkumiste teateid, ära feigi")


def dim_woodburning_zones(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-059: NULL — tahkekütte-piirangualad krundi kohta puuduvad."""
    return None, ("Tahkekütte-piiranguala (Kesklinn/Vanalinn eelis) on "
                  "stranded-pliidi hinnang (EI OLE krundi-põhist reegli-"
                  "liidestust): Keskkonnaameti + Keskkonna- ja "
                  "Kommunaalameti piiranguteated elavad inimloetavalt — "
                  "kontrolli EHR-i kütte-liigi slice'i ja Tallinna "
                  "kliimakava kütte-ülemineku tsoone, ära feigi")


# ---------------------------------------------------------------------------
# P4-060/P4-062 (coverage): fee/queue zone table (P4-060) and hex
# operational flags (P4-062). Complements of the Tallinna Vesi fee
# table (dims_p4_tvesi) and the P4-026 lag rate — named, never
# re-scored.
# ---------------------------------------------------------------------------

def dim_stormwater_notices(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-060: NULL — Kommunaalameti sademevee/soodustuste teated puuduvad."""
    return None, ("Tulevase arve vs toetuse sademevee-jalg on arvehinnang "
                  "(EI OLE masinloetavat teadete-voogu): Kommunaalameti "
                  "sademevee/soodustuste teated elavad inimloetavalt — "
                  "kontrolli Tallinna Vesi sademeveetasu-slice'i "
                  "dims_p4_tvesi-st ja EIS-i toetuste-järjekorda, "
                  "ära feigi")


def dim_rat_icefall_hex(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-062: NULL — roti-/jääkaebuste heksi-lipud puuduvad (no map)."""
    return None, ("Heksi roti- ja jää-kukkumis-lipud (prügidistsipliin + "
                  "katuse-hooldamatus, kunagi mitte aadressid) on "
                  "hooletusse-jäetud kvartali hinnang (EI OLE heksi-põhist "
                  "kaebuste-koondit): Keskkonnaameti rotikaebused ja "
                  "Päästeameti jää-hoiatused elavad inimloetavalt — hinda "
                  "prügimajade seisu kohapealsel vaatlusel ja küsi KÜ-lt "
                  "prügiveo-kulusid, ära feigi")


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_KOMUN_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_KOMUN_DIMS = (
    ("snow_maintenance_class", "P4-018", dim_snow_maintenance_class),
    ("ku_loan_support", "P4-007", dim_ku_loan_support),
    ("renovation_grant_queue", "P4-010", dim_renovation_grant_queue),
    ("geology_uvk_crosscheck", "P4-016", dim_geology_uvk_crosscheck),
    ("uvk_development_plan", "P4-017", dim_uvk_development_plan),
    ("farm_odour_cells", "P4-024", dim_farm_odour_cells),
    ("fixit_responsiveness", "P4-026", dim_fixit_responsiveness),
    ("tree_felling_flag", "P4-030", dim_tree_felling_flag),
    ("odour_complaint_cells", "P4-042", dim_odour_complaint_cells),
    ("small_horrors_calendar", "P4-047", dim_small_horrors_calendar),
    ("odour_rose_sectors", "P4-053", dim_odour_rose_sectors),
    ("quarry_blast_season", "P4-054", dim_quarry_blast_season),
    ("schedulable_noise_calendar", "P4-055", dim_schedulable_noise_calendar),
    ("heatpump_hum", "P4-057", dim_heatpump_hum),
    ("icefall_duty_warnings", "P4-058", dim_icefall_duty_warnings),
    ("woodburning_zones", "P4-059", dim_woodburning_zones),
    ("stormwater_notices", "P4-060", dim_stormwater_notices),
    ("rat_icefall_hex", "P4-062", dim_rat_icefall_hex),
)


def score_p4_komun(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All eighteen P4 komun dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_KOMUN_DIMS). Every value
    is None by design — unpublished department feeds, never a faked
    area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_KOMUN_DIMS}
