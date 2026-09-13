"""P4 veebi dims (issues #304 demo + #373 coverage).

Demo (#304): Tallinna veebikaart + lighting ingestion (P4-035) — polite,
cached, TTL-stated openness pulls of the veebikaart service + the
tänavavalgustuse inventory / valgustatud-teede kaart / lamp-register
sources, wired end-to-end in Tallinn. Coverage (#373): P4-029 + P4-032
+ P4-040 wired to the same demoed ingestion (no new plumbing expected
unless a param needs it; none did, see judgment calls).

Params (this module only — demo + its coverage follow-up share one source):
* P4-035 December darkness (demo, batch 3): lamp inventory × VIIRS ×
  sun hours — the veebikaart/lighting legs (per-street inventory/kaart
  + radiance input), per-listing dim
* P4-029 Street-imagery block observer (batch 3, coverage in #373):
  veebikaart orthophoto-history-per-street leg (per-listing dim with
  photo date)
* P4-032 Activity heat as usage proxy (batch 3, coverage in #373):
  valgustatud-teede lit-street usage-proxy leg (hex usage hinnang,
  labelled usage-not-safety)
* P4-040 Last-200 m arrival sequence (batch 4, coverage in #373):
  valgustatud-teede + lit-window-density November 23:00 leg
  (per-listing dim with photo date)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #304): Tallinn publishes no pollable machine-readable feed for
any of the four legs below. Polite evidence, 6 requests total (five
single GETs + one redirect resolution, kaart.tallinn.ee 301 counted
in its final-URL fetch, labelled one-off user-agent, 25 s timeout,
no retries, 3 s pacing; headers + visible-text keyword scope read
only, no scraping, no auth, no service enumeration), raw bodies
cached at /tmp/hf-veebi-probe/ (TTL: one-off check, kept for the PR
record, never committed):
* https://kaart.tallinn.ee/ -> 301 to https://gis.tallinn.ee/veebikaart/
  -> HTTP 200 (5 023 B, 21 visible chars, "Tallinna veebikaart" JS app
  shell). No WFS/WMS/GeoJSON/CSV endpoint advertised at page level;
  enumerating the JS app's internal map services would be map-app
  scraping, which this repo refuses (AGENTS.md section 5; same
  stop-at-shell precedent as TLT #277, Elron #284, komun #290, green
  #300). 0 for csv / geojson / wfs / wms / masinloetav / andmestik.
* https://gis.tallinn.ee/ -> HTTP 200 (703 B, "IIS Windows Server"
  default page, 20 visible chars). Viewer entry only (same shell as
  the green #300 check).
* https://www.tallinn.ee/et/otsing?search_api_fulltext=valgustus ->
  HTTP 200 (~147 KB, ~10.3k visible chars). All 4 "valgustus" hits are
  one human news page (Hirvepargi uued valgustuslahendused — a park
  lighting-design eskiisprojekt, human content). 0 for csv / geojson /
  wfs / wms / masinloetav / andmestik / lamp — no lamp inventory, no
  lit-street table anywhere.
* https://www.tallinn.ee/et/otsing?search_api_fulltext=veebikaart ->
  HTTP 200 (~145 KB, ~9.6k visible chars). All 8 "veebikaart" hits are
  human service pages (Teenus Veebikaart: kaart + aerofoto +
  aadressiotsing + infokihid + reisiplaneerija in the map app; Nõmme
  vaba aja kaart). 0 for csv / geojson / wfs / wms / masinloetav /
  andmestik — theme layers live inside the app, not as feeds.
* https://www.tallinn.ee/et/otsing?search_api_fulltext=valgustatud%20teede
  -> HTTP 200 (~147 KB, ~9.8k visible chars). 0 for valgustatud / lamp /
  csv / geojson / wfs / wms — the parameters4.md "valgustatud teede
  kaart" layer name has no pollable page at search level.
* https://andmed.eesti.ee/dataset?q=valgustus -> HTTP 200 (~76 KB,
  12 visible characters, "Teabevärav" JS shell) — no trivially
  pollable national-portal lighting dataset (same shell as the
  #264/#277/#284/#290/#300 national-portal checks).
So all four dims return None for EVERY input including missing
origin: a darkness gradient painted from a one-off hand-read of human
project pages would be fake precision (OTA PR #131 precedent).
Reasons say "hinnang" (estimate) and "EI OLE" and point at the
concrete buyer-side check (detsembri-kohapealne 15:30 jalutuskäik,
tänava-ülevaatus foto kuupäevaga, õhtune 20–22 kasutusjalutus,
novembri 23:00 saabumiskäik) — never a faked area score.

Style mirrors services/scoring/dims_p4_green.py (#300/#369, the
verdict-module precedent): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, no Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for the city's unpublished lamp inventory,
lit-street usage proxy, or orthophoto-history join, so there is
nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#373) states it extends the demoed ingestion ("no new plumbing
  expected") — with the demo verdict dated-negative, there is no
  ingestion to extend, so all four dims land in the same verdict
  module rather than a second file importing a pipeline that does not
  exist (same precedent as TLT #277+#351, Elron #284+#358, komun
  #290+#363, green #300+#369).
* Pairing rationale (each coverage param names this source in its
  parameters4.md source list): P4-029 the "Tallinna veebikaart
  orthophoto history per street" leg — the Mapillary/KartaView imagery
  leg genuinely scores in dims_p4_maa_aerial
  (dim_street_block_observer) and the OSM sidewalk/surface
  cross-check in dims_p4_osm (dim_block_observer); both named missing
  here, never re-scored. P4-032 the "Tallinna valgustatud teede kaart
  (lit-street usage proxy)" leg — the OSM evening-anchor density
  proxy lives in dims_p4_osm (dim_activity, usage-not-safety), the
  Elron/TLT evening-ridership legs stay NULL in dims_p4_elron /
  dims_p4_tlt, rattaloendurid are unpublished; all named, never
  re-scored (same split-slice precedent as P4-020: ATA notices in
  dims_p4_ata, bureau scores NULL in dims_p4_creditinfo). P4-040 the
  "Tallinna valgustatud teede + lit-window density proxy (November
  23:00 check)" leg — the mapped approach proxy lives in dims_p4_osm
  (dim_arrival) and the enclosure/green arrival legs in
  dims_p4_maa_aerial (dim_courtyard_trap); likewise named, never
  re-scored.
* P4-035 is one dim, not three, because its two veebi legs (lamp
  inventory/kaart per street + VIIRS radiance input) share one honest
  shape (per-listing dim) and one buyer check (detsembri-kohapealne
  jalutuskäik); the non-veebi legs stay scored where they live: EHR
  orientation/floor/window light model (dims_p4_ehr dim_darkness,
  capped), December sun-hours baseline (dims_p4_ilm
  dim_december_darkness, capped), LiDAR courtyard shading
  (dims_p4_maa_lidar dim_darkness_shading), OSM lit proxy (dims_p4_osm
  dim_darkness — which itself names the veebikaart/VIIRS gap).
* P4-032 keeps the usage-not-safety label explicitly (PPA/Päästeamet
  explicitly NOT a source per parameters4.md): a lit-street count is
  a lived-in-evening proxy, never a safety verdict. P4-040 likewise
  names arrival-feel ≠ safety claim (Päästeamet/PPA teadlikult
  kasutamata).
* The openness check stopped at landing/search/service/viewer-shell
  level on purpose — no gis.tallinn.ee service enumeration, no
  veebikaart JS-app traffic sniffing, no lighting-design PDF parsing.
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
# P4-035 (demo): December darkness — the veebikaart/lighting legs (lamp
# inventory/kaart per street + VIIRS radiance input). JS-app shell +
# human project pages only, no pollable feed — the scorer reports the
# gap with the concrete buyer-side check.
# ---------------------------------------------------------------------------

def dim_december_darkness_veebi(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """P4-035: NULL — lampide inventar/kaart + VIIRS-sisend puuduvad."""
    return None, ("Detsembri-pimedus (lambid × VIIRS × päikesetunnid) on "
                  "korteri-hinnang (EI OLE masinloetavat tänavavalgustuse "
                  "inventari/kaarti ega VIIRS-sisendit): veebikaart on "
                  "JS-rakendus, valgustusotsing annab vaid Hirvepargi "
                  "eskiisprojekti — külasta detsembris kell 15:30 kohapeal "
                  "ja vaata päevavalguse-slice'e dims_p4_ehr-ist, "
                  "päikesetundide-slice'i dims_p4_ilm-st, varjutuse-slice'i "
                  "dims_p4_maa_lidar-ist ja lit-slice'i dims_p4_osm-ist, "
                  "ära feigi")


# ---------------------------------------------------------------------------
# P4-029 (coverage): veebikaart orthophoto-history-per-street leg
# (per-listing dim with photo date). The Mapillary/KartaView imagery
# leg scores in dims_p4_maa_aerial, the OSM sidewalk/surface
# cross-check in dims_p4_osm — this leg is the history join only.
# ---------------------------------------------------------------------------

def dim_street_ortho_history(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """P4-029: NULL — veebikaardi ortofoto-ajaloo liidestus tänava kohta
    puudub."""
    return None, ("Tänava ortofoto-ajalugu (veebikaardi aerofoto-vintaažid "
                  "tänava kohta, foto kuupäevaga) on silmakõrguse-hinnang "
                  "(EI OLE masinloetavat ajalooliidestust): kaardirakendus "
                  "pakub aerofotot vaid inimloetava kihina — jaluta tänav "
                  "läbi ja vaata kaadri-slice'i dims_p4_maa_aerial-ist ning "
                  "kõnnitee-slice'i dims_p4_osm-ist, ära feigi")


# ---------------------------------------------------------------------------
# P4-032 (coverage): valgustatud-teede lit-street usage-proxy leg (hex
# usage hinnang, labelled usage-not-safety). PPA/Päästeamet explicitly
# NOT a source — a lamp count is a lived-in-evening proxy, never a
# safety verdict.
# ---------------------------------------------------------------------------

def dim_lit_street_usage(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-032: NULL — valgustatud-teede kasutusproksi (õhtune kasutus,
    mitte turvalisus) puudub."""
    return None, ("Valgustatud-tänavate õhtune kasutus (kasutus-hinnang, "
                  "mitte turvalisus — PPA/Päästeamet teadlikult "
                  "kasutamata) on elava-tänava hinnang (EI OLE "
                  "masinloetavat valgustatud-teede kihti): kihi nimi ei "
                  "anna otsingus ühtegi loetavat lehte — jaluta õhtul "
                  "20–22 kohapeal ja vaata ankru-slice'i dims_p4_osm-ist "
                  "ning õhtuse-täituvuse NULL-e dims_p4_elron-ist ja "
                  "dims_p4_tlt-st, ära feigi")


# ---------------------------------------------------------------------------
# P4-040 (coverage): valgustatud-teede + lit-window-density November
# 23:00 leg (per-listing dim with photo date). Arrival feel is not a
# safety claim — Päästeamet/PPA teadlikult kasutamata.
# ---------------------------------------------------------------------------

def dim_arrival_lighting(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-040: NULL — saabumise valgusjalg (novembri 23:00 kontroll,
    foto kuupäevaga) puudub."""
    return None, ("Viimase 200 m saabumisjada valgus (valgustatud teed + "
                  "valgustatud akende tihedus, novembri 23:00 kontroll, "
                  "foto kuupäevaga) on saabumis-hinnang (EI OLE "
                  "masinloetavat valguskihti ega aknatiheduse proksit): "
                  "saabumistunne ei ole turvaväide (Päästeamet/PPA "
                  "teadlikult kasutamata) — kõnni novembriõhtul marsruut "
                  "läbi ja vaata lähenemis-slice'i dims_p4_osm-ist ning "
                  "sulundus/haljastuse-slice'e dims_p4_maa_aerial-ist, "
                  "ära feigi")


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_VEEBI_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_VEEBI_DIMS = (
    ("december_darkness", "P4-035", dim_december_darkness_veebi),
    ("street_ortho_history", "P4-029", dim_street_ortho_history),
    ("lit_street_usage", "P4-032", dim_lit_street_usage),
    ("arrival_lighting", "P4-040", dim_arrival_lighting),
)


def score_p4_veebi(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All four P4 veebi dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_VEEBI_DIMS). Every value
    is None by design — unpublished veebikaart/lighting feeds, never a
    faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_VEEBI_DIMS}
