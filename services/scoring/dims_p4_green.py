"""P4 green dims (issues #300 demo + #369 coverage).

Demo (#300): Tallinna green-inventory ingestion (P4-048) — polite,
cached, TTL-stated openness pulls of the Haljasala inventory /
rohealade kava / bench-viewpoint / allotment-queue sources, wired
end-to-end in Tallinn. Coverage (#369): P4-042 + P4-056 wired to the
same demoed ingestion (no new plumbing expected unless a param needs
it; none did, see judgment calls).

Params (this module only — demo + its coverage follow-up share one source):
* P4-048 Small delights + allotment queues (demo, batch 4): bench view
  <3 min slice, green delight <15 min slice, allotment-queue slice
* P4-042 Smell/dawn-chorus map (batch 4, coverage in #369): Haljasala
  seasonality leg (blossom/dawn-chorus anchors, coarse cells)
* P4-056 Enclosed-courtyard trap (batch 5, coverage in #369):
  haljastus courtyard-green-deficit leg (per-parcel join)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #300): Tallinn publishes no pollable machine-readable feed for
any of the five slices below. Polite evidence, 12 requests total
(ten single GETs + two redirect checks, labelled one-off user-agent,
25 s timeout, no retries, 2 s pacing; headers + visible-text keyword
scope read only, no scraping, no auth, no service enumeration),
raw bodies cached at /tmp/hf-green-probe/ (TTL: one-off check, kept
for the PR record, never committed):
* https://www.tallinn.ee/et/keskkond -> HTTP 200 (~99 KB, ~5.9k
  visible chars). Keskkonnaveeb landing (Keskkonnahoid / Linnaloodus
  sections). Visible-text sweep 0 for csv / geojson / wfs /
  masinloetav / andmestik / haljasala / roheala / linnaaed / pink /
  vaatekoht; "api" 2x is page chrome, not a feed.
* https://www.tallinn.ee/et/otsing?search_api_fulltext=haljasala ->
  HTTP 200 (~147 KB, server-rendered). 15x "haljasala" hits are all
  human content: the korrashoid e-service page, project pages
  (Kopliranna haljasala põhiprojekt, Tedre 2b/Kotka 14a põhiprojekt),
  Keskkonnaveeb park pages (Purskkaevu, Pirita keskuse mängupark).
  0 for csv / geojson / wfs / masinloetav / andmestik. The one
  "pinkide" hit is maintenance prose (pargipinkide hoolduse
  korraldamine), not a bench register.
* https://www.tallinn.ee/et/otsing?search_api_fulltext=linnaaed ->
  HTTP 200 (~144 KB, server-rendered). Only content hit is a
  kindergarten photo album (Mustakivi linnaaed = lasteaia mänguaed,
  not an allotment garden). 0 for järjekord / csv / geojson / wfs —
  no allotment-queue table anywhere.
* https://www.tallinn.ee/et/teenused/haljasalade-parkide-teede-ja-vaikeobjektide-korrashoid
  -> HTTP 200 (~148 KB, ~9.9k visible chars; bare /teenused/ URL 301s
  to the /et/ locale). A maintenance e-service description
  (korrashoid-teenus), not a dataset: 0 for csv / geojson / wfs /
  masinloetav / andmestik / inventar / roheala / vaatekoht.
* https://gis.tallinn.ee/ -> HTTP 200 (703 bytes, "IIS Windows
  Server" default page, 20 visible chars). Viewer entry only — no
  WFS/WMS/GeoJSON/CSV endpoint advertised at page level. Enumerating
  its map services would be map-app scraping, which this repo
  refuses (AGENTS.md section 5; same stop-at-shell precedent as
  TLT #277, Elron #284, komun #290).
* https://andmed.eesti.ee/dataset?q=haljasala -> HTTP 200 (~75 KB),
  12 visible characters ("Teabevärav" JS shell) — no trivially
  pollable national-portal haljasala dataset (same shell as the
  #264/#277/#284/#290 national-portal checks).
So all five dims return None for EVERY input including missing
origin: a delight gradient painted from a one-off hand-read of human
project pages would be fake precision (OTA PR #131 precedent).
Reasons say "hinnang" (estimate) and "EI OLE" and point at the
concrete buyer-side check (3-minuti jalutusring Kadriorg/Hirvepark/
Pirita promenaad, 15-minuti isokroon, aiandusühistu järjekorrapäring,
hommikune kohapealne nuusutamine/kuulamine, hoovi-ülevaatus + KÜ
päring) — never a faked area score.

Style mirrors services/scoring/dims_p4_komun.py (#290/#363, the
verdict-module precedent): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, no Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for the city's unpublished bench register,
queue tables, or inventory seasonality, so there is nothing for the
live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#369) states it extends the demoed ingestion (#300): with
  the demo verdict dated-negative, there is no ingestion to extend,
  so the two coverage slices land in the same verdict module rather
  than a second file importing a pipeline that does not exist (same
  precedent as TLT #277+#351, elektrilevi #264+#344, comapps
  #302+#371, Elron #284+#358, RB #281+#355, komun #290+#363).
* Pairing rationale (each coverage param names this source in its
  parameters4.md source list): P4-042 the "Tallinna Haljasala
  inventory (blossom/mädanenud lehed seasonality)" leg — the OSM
  bakery anchors live in dims_p4_osm (dim_smell), the chimney-smoke
  cells in dims_p4_paaste (smoke_chorus), the odour-complaint cells
  in dims_p4_komun (dim_odour_complaint_cells), the smoke-episode
  cross-check in dims_p4_kaur (louna_kaur), the emitter addresses in
  dims_p4_arireg (smell_arireg); all named missing here, never
  re-scored (same split-slice precedent as P4-020: ATA notices in
  dims_p4_ata, bureau scores NULL in dims_p4_creditinfo). P4-056 the
  "Tallinna haljastus inventory (courtyard green deficit)" leg —
  the LiDAR enclosure index lives in dims_p4_maa_lidar
  (dim_courtyard_trap, genuinely scores), the ventilation proxy in
  dims_p4_ilm, the infill change in dims_p4_maa_aerial, the
  fume-hold validation in dims_p4_kaur (sisehoov_kaur), the
  EHR-ratio NULL in dims_p4_ehr; likewise named, never re-scored.
* P4-048 is three dims, not one, because its three green legs are
  different honest shapes (per-listing <3 min bench join vs <15 min
  green-isochrone join vs annual queue table) with different buyer
  checks; merging them would blur the NULL into unactionable mush.
  The non-green legs stay scored where they live: EHR orientation
  breakfast-sun (dims_p4_ehr dim_small_delights), <15 min access
  (dims_p4_peatus dim_delights_access, dims_p4_tlt
  dim_tlt_delight_access), OSM snapshot NULL (dims_p4_osm
  dim_delights — agrees queues/registers are not in the snapshot).
* The openness check stopped at landing/search/service/viewer-shell
  level on purpose — no gis.tallinn.ee service enumeration, no
  e-service flow driving, no allotment-association queue scraping.
* No fetch_* helper: with a dated-negative verdict there is no
  pollable feed to wrap, and a fetcher around human project pages
  would be brittle scraping dressed as ingestion (komun #290
  precedent — verdict modules carry no network code, pinned by
  test_module_adds_no_network_calls).

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-048 (demo): bench view <3 min needs the pinkide/vaatekohtade
# register (Kadriorg, Hirvepark, Pirita promenaad). Human project
# pages only, no pollable register — the scorer reports the gap with
# the concrete buyer-side check.
# ---------------------------------------------------------------------------

def dim_bench_view_3min(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-048: NULL — pinkide/vaatekohtade register (<3 min) puudub."""
    return None, ("Pingi-vaate <3 min jalutusringi-hinnang (EI OLE "
                  "masinloetavat pinkide/vaatekohtade registrit): "
                  "Kadrioru, Hirvepargi ja Pirita promenaadi pingid "
                  "elavad inimloetavatel projektilehtedel — jaluta "
                  "3-minuti ring kuulutusest läbi ja hinda "
                  "hommikupäikese-slice'i dims_p4_ehr-ist, ära feigi")


# ---------------------------------------------------------------------------
# P4-048 (demo): green delight <15 min (RMK seenemetsad, Pirita/
# Stroomi ujulad, gym/ice) needs the rohealade-kava isochrone join.
# The kava lives as planning documents, not a per-listing feed.
# ---------------------------------------------------------------------------

def dim_delight_green_15min(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """P4-048: NULL — rohealade-kava <15 min isokroon-liidestus puudub."""
    return None, ("Rohelise rõõmu <15 min isokroon (seenemets, ujula, "
                  "jõusaal/jää) on päevarõõmu-hinnang (EI OLE "
                  "masinloetavat rohealade-kava liidestust): kava elab "
                  "planeeringudokumentides — mõõda 15-minuti ring "
                  "kaardilt ja kontrolli ligipääsu-slice'e "
                  "dims_p4_peatus-ist ja dims_p4_tlt-st, ära feigi")


# ---------------------------------------------------------------------------
# P4-048 (demo): allotment queues (Lillepi, Pelgu — queues = true
# demand, annual tables) are unpublished. The OSM delights NULL
# agrees: queues and registers are not in the snapshot.
# ---------------------------------------------------------------------------

def dim_allotment_queue(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-048: NULL — linnaaiade järjekorratabelid (Lillepi/Pelgu)
    puuduvad."""
    return None, ("Linnaaia-järjekord (Lillepi, Pelgu — järjekord on "
                  "tegelik nõudlus) on aiamaa-hinnang (EI OLE "
                  "masinloetavat aastast järjekorratabelit): "
                  "linnaaia-otsing andis vaid lasteaia-pildialbumi — "
                  "küsi aiandusühistult järjekorra pikkust ja vaata "
                  "dims_p4_osm delights-NULLi, ära feigi")


# ---------------------------------------------------------------------------
# P4-042 (coverage): Haljasala-seasonality leg (sirel/Kadriorg/
# Hirvepark dawn-chorus anchors, blossom vs mädanenud lehed).
# Coarse hinnang cells per parameters4.md — doorway precision is
# explicitly forbidden. Sibling legs named, never re-scored.
# ---------------------------------------------------------------------------

def dim_blossom_chorus_cells(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """P4-042: NULL — haljasala-hooajalisuse koondrakud puuduvad."""
    return None, ("Õie- ja koidukoori-rakud (sirel/Kadriorg/Hirvepark, "
                  "õitsemine vs mädanenud lehed) on mälumärgi-hinnang "
                  "(EI OLE haljasala-inventari hooajakoondit, ukse- "
                  "täpsust keelab parameters4.md): nuusuta ja kuula "
                  "hommikuti kohapeal ning vaata pagari-slice'i "
                  "dims_p4_osm-ist, suitsu-slice'i dims_p4_paaste-st ja "
                  "kaebuste-slice'i dims_p4_komun-ist, ära feigi")


# ---------------------------------------------------------------------------
# P4-056 (coverage): haljastus courtyard-green-deficit leg
# (per-parcel morphology join). The LiDAR enclosure index genuinely
# scores in dims_p4_maa_lidar — this leg is the green deficit only.
# ---------------------------------------------------------------------------

def dim_courtyard_green_deficit(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """P4-056: NULL — hoovihaljastuse inventar krundi kohta puudub."""
    return None, ("Hoovi rohedefitsiit (kinnine sisehoov: külm + "
                  "heitgaasid + kuumus) on mikrokliima-tasku hinnang "
                  "(EI OLE krundi-põhist haljastusinventari): vaata "
                  "hoov üle kohapeal ja küsi KÜ-lt hooldust ning vaata "
                  "sulundus-slice'i dims_p4_maa_lidar-ist ja tuulutus- "
                  "slice'i dims_p4_ilm-st, ära feigi")


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_GREEN_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_GREEN_DIMS = (
    ("bench_view_3min", "P4-048", dim_bench_view_3min),
    ("delight_green_15min", "P4-048", dim_delight_green_15min),
    ("allotment_queue", "P4-048", dim_allotment_queue),
    ("blossom_chorus_cells", "P4-042", dim_blossom_chorus_cells),
    ("courtyard_green_deficit", "P4-056", dim_courtyard_green_deficit),
)


def score_p4_green(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five P4 green dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_GREEN_DIMS). Every value
    is None by design — unpublished green-inventory feeds, never a
    faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_GREEN_DIMS}
