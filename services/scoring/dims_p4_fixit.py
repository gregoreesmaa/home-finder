"""P4 fix-it channels dims (issues #301 demo + #370 coverage).

Demo (#301): Tallinna fix-it channels ingestion (P4-026) — polite,
cached, TTL-stated pulls of the abiliin/e-teenused reports plus the
Munitsipaalpolitsei/KÜ complaint-stats end-to-end in Tallinn.
Coverage (#370): P4-062 wired to the same demoed ingestion (no new
plumbing expected unless a param needs it; none did, see judgment
calls).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #301): Tallinn publishes no pollable machine-readable feed for
either slice below. Polite evidence, 7 tiny requests total (seven
single GETs with a labelled one-off user-agent, headers +
visible-text keyword scope read only, no scraping, no auth, no form
driving, no viewer-internals enumeration), raw bodies cached at
/tmp/hf-fixit-probe/ (TTL: one-off check, kept for the PR record,
never committed):
* https://www.tallinn.ee/ -> HTTP 301 (162 bytes) to the storefront;
  followed once -> HTTP 200 (~138 KB, cloudflare, ~8.3k visible
  chars). Links the Mupo page (/et/tallinna-munitsipaalpolitsei-amet),
  the open-data page (/avaandmed/), /et/lumi and the geoportal.
  Sweep 0 for csv / geojson / wfs / api / andmestik / masinloetav.
* https://www.tallinn.ee/et/abiliin -> HTTP 404 (~123 KB,
  "Lehekülge ei leitud" shell): no dedicated abiliin machine page.
  Intake is the 14410 / 661 9860 helpline, per the Mupo page below.
* https://annateada.ee/ -> HTTP 200 (~24 KB, ~4.1k visible chars).
  Human reporting app ("Teavita heakorraprobleemist, Märgi koht
  kaardil", Andmevara/Maanteeamet marks, mobile-app links) — no
  API/docs/data endpoint advertised at page level. Driving its map
  form report-by-report would be scraping a human publication, not
  polling a feed (AGENTS.md section 5).
* https://www.tallinn.ee/et/tallinna-munitsipaalpolitsei-amet ->
  HTTP 200 (~159 KB, ~14.5k visible chars). Complaint intake is
  phone 14410 / 661 9860 (24/7 helpline, 7 hits) plus e-post
  (mupo@tallinnlv.ee — weekend letters are treated as call-outs,
  not answered); the kaebus hits (4x) are a DOC-form + e-post
  address, never a per-linnaosa stats table. The avaandmed (3x) /
  statistika (5x) hits are site-nav chrome ("Uuringud ja
  statistika", "Avaandmed" menu items), not a feed. Sweep 0 for
  csv / geojson / json / wfs / api / andmestik / masinloetav.
* https://tarktee.ee/ -> HTTP 200 (~66 KB) with 18 visible
  characters ("Tark Tee 37.26.8.2"): JS shell, no server-rendered
  incident feed (same shell as the #264/#277/#284 national-portal
  checks). Reading its internals would be map-app scraping, which
  this repo refuses (AGENTS.md section 5; same stop-at-shell
  precedent as TLT #277 and Elron #284).
* https://andmed.eesti.ee/dataset?q=abiliin -> HTTP 200 (~75 KB)
  with 10 visible characters ("Teabevärav" JS shell): no
  server-rendered results — no trivially pollable national-portal
  abiliin/fix-it dataset.
So both dims return None for EVERY input including missing origin:
a hex rate painted from a one-off hand-read of human pages would be
fake precision (OTA PR #131 precedent). Reasons say "hinnang"
(estimate) and "EI OLE" and point at the concrete buyer-side check
(14410/661 9860 helpline, annateada.ee report map, Mupo e-post,
KÜ aruanded, kohapealne vaatlus) — never a faked area score.

Style mirrors services/scoring/dims_p4_tervise.py (#289/#362): every
scorer is pure and offline-tested — (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for the channels' unpublished lag tables or
per-linnaosa complaint counts, so there is nothing for the live
path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#370) states it extends the demoed ingestion (#301): with
  the demo verdict dated-negative, there is no ingestion to extend,
  so the coverage slice lands in the same verdict module rather
  than a second file importing a pipeline that does not exist
  (same precedent as Terviseamet #289+#362, Elron #284+#358, TLT
  #277+#351, elektrilevi #264+#344, comapps #302+#371, RB #281+#355).
* Pairing rationale (each param names this source in its
  parameters4.md source list): P4-026 source 1 is the
  abiliin/e-teenused fix-it reports leg (valgustus, augud, lumi,
  grafiti) and source 3 the Mupo/KÜ kaebuste-statistika leg — both
  are this module's demo slice. P4-062 source 4 is the explicit
  P4-026 join (this module's fix-it lag per hex), so the rat/ice
  channel flags that ride the same intake belong here as the
  coverage slice.
* Sibling legs stay scored where they live, named never re-scored
  (same split-slice precedent as P4-020: ATA notices in
  dims_p4_ata, bureau scores NULL in dims_p4_creditinfo): the
  Keskkonna- ja Kommunaalamet heakorra-teated + removal-lag leg
  (dims_p4_komun dim_fixit_responsiveness) and rotikaebused hex leg
  (dims_p4_komun dim_rat_icefall_hex, #290/#363); the OSM
  fixme/edit-freshness cross-check (dims_p4_osm dim_fixit) and
  waste-disposal coverage cross-check (dims_p4_osm dim_rats,
  #354); the Paasteamet ice-warning slice (dims_p4_paaste, #276,
  scores only inside a caller-supplied hex-watch flag); the KÜ
  hoolduskulu/prügiveo-kulu echos (dims_p4_arireg
  dim_maintenance_echo / dim_waste_echo). Each reason names its
  scored cousins so the buyer knows which half is already joined.
* P4-026 (fix-it LAG rate) vs P4-062 (complaint COUNT flags):
  different honest shapes (hex responsiveness rate vs hex
  operational flags, never addresses), both NULL — no
  double-scoring by construction (same shape split as komun
  #290/#363).
* The openness check stopped at storefront/page/shell level on
  purpose — no annateada form driving, no Tark Tee service
  enumeration, no DOC-form parsing, no complaint-form probing.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-026/P4-062: documented no-map fix-it-channel NULLs (OTA PR #131
# precedent). Abiliin/e-teenused reports and Mupo/KÜ complaint stats
# are human intake channels (helpline, e-post, report-map app) with
# no public lag table or per-linnaosa stats feed; each scorer
# reports the gap with a concrete buyer-side check instead of a
# faked number.
# ---------------------------------------------------------------------------

def dim_fixit_channel_responsiveness(origin: Optional[Tuple[float, float]],
                                     pois: Optional[List[dict]]) -> Score:
    """P4-026: NULL — abiliin/Mupo fix-it lag rate per hex is unpublished."""
    return None, ("KOV-i parandamiskiirus abiliini/e-teenuste-kanalites "
                  "(valgustus, augud, lumi, grafiti) on hooldaja-hinnang "
                  "(EI OLE parandatud/eemaldatud-viibe tabelit heksi "
                  "kaupa): abiliin (14410 / 661 9860), Mupo e-post ja "
                  "annateada.ee teavituskaart on inimkanalid — küsi "
                  "linnaosast eemaldamisviivet, hinda trepikoja hooldust "
                  "KÜ aruandest ja vaata heakorra-teadete slice'i "
                  "dims_p4_komun-ist (dim_fixit_responsiveness), OSM "
                  "fixme-ristkontrolli dims_p4_osm-ist (dim_fixit) ning "
                  "KÜ hoolduskulu-kaja dims_p4_arireg-ist "
                  "(dim_maintenance_echo), ära feigi")


def dim_rat_icefall_channel_flags(origin: Optional[Tuple[float, float]],
                                  pois: Optional[List[dict]]) -> Score:
    """P4-062: NULL — roti-/jääkaebuste heksi-lipud kanalite kaupa puuduvad."""
    return None, ("Heksi roti- ja jää-kukkumis-lipud abiliini-kanalite "
                  "kaudu (prügidistsipliin + katuse-hooldamatus, kunagi "
                  "mitte aadressid) on hooletusse-jäetud kvartali hinnang "
                  "(EI OLE heksi-põhist kaebuste-koondit): abiliini "
                  "parandusviibe-jalg (P4-026 join) on samuti avaldamata, "
                  "jäätmeveo-rikkumised ja rotikaebused elavad "
                  "inimloetavate teadetena — hinda prügimajade seisu "
                  "kohapealsel vaatlusel, küsi KÜ-lt prüviveo-kulusid ning "
                  "vaata Päästeameti jää-hoiatuste slice'i dims_p4_paaste-st, "
                  "rotikaebuste-slice'i dims_p4_komun-ist "
                  "(dim_rat_icefall_hex), OSM jäätmepunktide-ristkontrolli "
                  "dims_p4_osm-ist (dim_rats) ja KÜ prügi-hoolduskulu-kaja "
                  "dims_p4_arireg-ist (dim_waste_echo), ära feigi")


P4_FIXIT_DIMS = (
    ("fixit_channel_responsiveness", "P4-026", dim_fixit_channel_responsiveness),
    ("rat_icefall_channel_flags", "P4-062", dim_rat_icefall_channel_flags),
)


def score_p4_fixit(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both P4 fix-it channel dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_FIXIT_DIMS). Every value
    is None by design — unpublished fix-it channels, never a faked
    area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_FIXIT_DIMS}
