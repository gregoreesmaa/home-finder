"""P4 libs dims (issues #321 demo + #379 coverage).

Demo (#321): Tallinna libraries & culture-hours ingestion (P4-045) —
polite, cached, TTL-stated openness pulls of the Keskraamatukogu +
branch evening-hours pages and the culture-calendar event sources,
wired end-to-end in Tallinn. Coverage (#379): P4-039 wired to the
same demoed ingestion (no new plumbing expected unless a param needs
it; none did, see judgment calls).

Params (this module only — demo + its coverage follow-up share one source):
* P4-045 Third places + keeper effect (demo, batch 4): library
  evening-hours slice, culture-calendar evening-events slice
* P4-039 Civic capital (batch 3, coverage in #379): library /
  youth-centre visits per linnaosa (civic-use leg, taste-match only)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #321): Tallinn publishes no pollable machine-readable feed for
any of the three slices below. Polite evidence, 8 requests total
(seven single GETs + one header-only redirect check, labelled
one-off user-agent, 25 s timeout, no retries, 2 s pacing; headers +
visible-text keyword scope read only, no scraping, no auth, no
service enumeration), raw bodies cached at /tmp/hf-libs-probe/
(TTL: one-off check, kept for the PR record, never committed):
* https://keskraamatukogu.ee/ -> HTTP 302 (145 B, nginx). Bare
  domain is a redirect shell, not a feed.
* Header check on the same URL -> Location:
  https://tallinnaraamatukogud.ee (one redirect check, no body).
* https://tallinnaraamatukogud.ee/ -> HTTP 200 (~176 KB, ~8.2k
  visible chars). Human CMS: branch list, "Kõik lahtiolekuajad"
  page, "Sündmuste kalender" event calendar, newsletter signup.
  Visible-text sweep 0 for csv / geojson / wfs / api /
  masinloetav / andmestik / avaandmed. "lahtioleku" 4x is CMS
  navigation prose, not a feed; the one "külastus" hit is cookie
  prose (külastusharjumusi), not visit statistics; "kalender" 2x
  is the human event-calendar nav.
* https://www.tallinn.ee/et/kultuur -> HTTP 200 (~83 KB, ~4.6k
  visible chars). Institution link hub (Tallinna Raamatukogud,
  event-organiser aid pages, kultuuriinfo newsletter). 0 for csv /
  geojson / wfs / api / masinloetav / andmestik / avaandmed /
  lahtioleku; "üritus" 3x is organiser-aid prose, not an event feed.
* https://kultuurikava.ee/ -> HTTP 200 (1 796 B). JS SPA shell
  ("You need to enable JavaScript"), no server-rendered feed —
  same shell as the #264/#277/#284/#290 national-portal checks.
* https://andmed.eesti.ee/dataset?q=raamatukogu -> HTTP 200
  (~75 KB, 10 visible chars: "Teabevärav" JS shell) — no
  trivially pollable national-portal library dataset (same shell
  as the #264/#277/#284/#290 checks).
* https://www.tallinn.ee/et/otsing?search_api_fulltext=raamatukogude+külastatavus
  -> HTTP 200 (~148 KB, ~10.4k visible chars). 22x "raamatukogu"
  hits are human content; 0 for külastatavus / csv / geojson /
  wfs / masinloetav / andmestik / lahtioleku. The 2x "avaandmed"
  + 4x "statistika" hits are site footer/nav chrome, not a
  library-visits dataset.
So all three dims return None for EVERY input including missing
origin: an evening-hours gradient painted from a one-off hand-read
of human CMS pages would be fake precision (OTA PR #131
precedent). Reasons say "hinnang" (estimate) and "EI OLE" and
point at the concrete buyer-side check (Kõik lahtiolekuajad +
õhtune jalutusring, Sündmuste kalender + kultuuriinfo uudiskiri,
raamatukogu/noortekeskuse külastuspäring) — never a faked area
score. P4-039 stays taste-match only, never an ethnic/wealth
proxy, per parameters4.md.

Style mirrors services/scoring/dims_p4_komun.py (#290/#363, the
verdict-module precedent): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, no Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for the city's unpublished hours tables,
event calendar, or visit counts, so there is nothing for the live
path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#379) states it extends the demoed ingestion (#321) with
  "no new plumbing expected": with the demo verdict
  dated-negative, there is no ingestion to extend, so the coverage
  slice lands in the same verdict module rather than a second file
  importing a pipeline that does not exist (same precedent as TLT
  #277+#351, elektrilevi #264+#344, comapps #302+#371, Elron
  #284+#358, RB #281+#355, komun #290+#363, green #300+#369).
* Pairing rationale (P4-039 names this source in its
  parameters4.md source list, leg 6): "Tallinna
  raamatukogude/noortekeskuste külastus per linnaosa (civic use)"
  — that leg, and only that leg, is scored here. The turnout leg
  (valimiskomisjoni jaoskonna-andmed, no pollable feed), the
  kaasava-eelarve / Teeme Ära participation legs, and the KÜ
  remondifondi leg have no owner in this repo and stay gaps; the
  OSM edit-freshness leg is the dims_p4_osm dim_civic NULL
  (fixme density points the wrong way) and the fondikogumise echo
  is the dims_p4_arireg dim_commons_echo NULL — all named, never
  re-scored (same split-slice precedent as P4-020: ATA notices in
  dims_p4_ata, bureau scores NULL in dims_p4_creditinfo).
* P4-045 is two dims, not one, because its two libraries-feed
  legs are different honest shapes (per-branch evening-hours join
  vs per-asum evening-events calendar) with different buyer
  checks; merging them would blur the NULL into unactionable
  mush. The non-libraries legs stay where they belong: mapped
  sauna/pub/library density genuinely scores in dims_p4_osm
  (dim_thirdplace, TASTE-match), evening access in dims_p4_peatus
  (dim_third_places) and dims_p4_tlt (dim_tlt_evening_access,
  unjoined NULL), belonging demand in dims_p4_rel2021
  (dim_third_place_demand_rel); the keeper-effect leg
  (e-Äriregister >10 yr same-address independents) is not a
  libraries-feed join and has no scorer in this repo — named,
  never re-scored.
* The openness check stopped at landing/search/portal-shell level
  on purpose — no CMS pagination crawling, no event-calendar
  scraping, no newsletter-flow driving, no JS-SPA rendering.
* No fetch_* helper: with a dated-negative verdict there is no
  pollable feed to wrap, and a fetcher around human CMS pages
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
# P4-045 (demo): library evening hours need the Keskraamatukogu +
# branch "Kõik lahtiolekuajad" join per linnaosa. Human CMS page
# only, no pollable feed — the scorer reports the gap with the
# concrete buyer-side check.
# ---------------------------------------------------------------------------

def dim_library_evening_hours(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """P4-045: NULL — haruraamatukogude õhtused lahtiolekuajad
    (Kõik lahtiolekuajad) masinloetavana puuduvad."""
    return None, ("Raamatukogu-õhtute kuuluvus on kolmanda koha hinnang "
                  "(EI OLE masinloetavat lahtioleku-tabelit): Kesk- ja "
                  "haruraamatukogude ajad elavad inimloetaval Kõik "
                  "lahtiolekuajad-lehel — vaata sealt oma haru õhtud ja "
                  "jaluta õhtune ring kuulutusest läbi ning vaata "
                  "kaardistatud tiheduse slice'i dims_p4_osm-ist, ära feigi")


# ---------------------------------------------------------------------------
# P4-045 (demo): culture-calendar evening events per asum need a
# pollable event feed. The city hub is human links, kultuurikava.ee
# is a JS shell, the library Sündmuste kalender is human CMS.
# ---------------------------------------------------------------------------

def dim_culture_evening_events(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """P4-045: NULL — kultuurikalendri õhtuste sündmuste voog
    per asum puudub."""
    return None, ("Kultuuriõhtute kuuluvus on sündmuskalendri-hinnang "
                  "(EI OLE masinloetavat õhtuste sündmuste voogu): "
                  "tallinn.ee kultuurileht on inimloetav linkikogu, "
                  "kultuurikava.ee JS-kest, raamatukogu Sündmuste kalender "
                  "inim-CMS — telli kultuuriinfo uudiskiri ja kontrolli "
                  "ligipääsu-slice'e dims_p4_peatus-ist ja dims_p4_tlt-st "
                  "ning nõudluse-slice'i dims_p4_rel2021-ist, ära feigi")


# ---------------------------------------------------------------------------
# P4-039 (coverage): library / youth-centre visits per linnaosa
# (civic-use leg, taste-match only, never ethnic/wealth proxy).
# No visit table is published — the scorer reports the gap with the
# concrete buyer-side check and names the sibling legs.
# ---------------------------------------------------------------------------

def dim_civic_use_visits(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-039: NULL — raamatukogude/noortekeskuste külastusarv
    per linnaosa (kodaniku-kasutuse slice) puudub."""
    return None, ("Kodaniku-kasutuse ühisvara on maitse-hinnang (EI OLE "
                  "külastatavuse tabelit per linnaosa, ukse-täpsust "
                  "keelab parameters4.md — maitsefilter, mitte rahvus- "
                  "ega jõukusproksi): küsi raamatukogult ja linnaosa "
                  "noortekeskuselt külastusarvu ning vaata värskuse- "
                  "slice'i dims_p4_osm-ist ja fondikaja-slice'i "
                  "dims_p4_arireg-ist, ära feigi")


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_LIBS_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_LIBS_DIMS = (
    ("library_evening_hours", "P4-045", dim_library_evening_hours),
    ("culture_evening_events", "P4-045", dim_culture_evening_events),
    ("civic_use_visits", "P4-039", dim_civic_use_visits),
)


def score_p4_libs(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All three P4 libs dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_LIBS_DIMS). Every value
    is None by design — unpublished library-hours / event / visit
    feeds, never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_LIBS_DIMS}
