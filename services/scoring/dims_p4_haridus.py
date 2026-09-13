"""P4 Haridusamet per-linnaosa dimensions (issues #270 demo + #346 coverage).

Params (this module only — demo + its coverage follow-up share one source):
* P4-011 Lasteaia queue length + perearst nimistu open/closed (batch 1,
  demo in #270)
* P4-025 Micro-liquidity, school open/close plans slice (batch 2,
  coverage in #346)
* P4-052 Turnover wave per building, school-catchment change slice
  (batch 5, coverage in #346)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#270): Tallinna Haridusamet publishes no pollable bulk feed for any of
the three slices above. Polite evidence, 13 tiny requests total
(HEADs + single GETs with a labelled one-off user-agent, headers +
visible-text keyword scope read only, no scraping, no auth attempts,
raw bodies cached at /tmp/hf-haridus-open/ — TTL: one-off check, kept
for the PR record, never committed):
* https://www.tallinn.ee/et/haridus -> 200 (Cloudflare CMS page,
  95 223 B). Visible text names haridusamet (6x) and lasteaia (8x)
  as content navigation, but avaandmed / open data / andmestik /
  masinloetav / csv / json / api / x-tee all score 0 — a content
  portal, not a data feed. Queue application is a per-child
  e-service page (/et/haridus/lasteaiakoha-taotlemine), never a
  per-linnaosa queue-stats table.
* https://haridussilm.ee/ -> 200 but only 41 chars server-rendered
  ("Haridusandmete portaal | HaridusSilm.ee") — a JS app shell with
  no server-rendered statistics and no bulk endpoint advertised at
  storefront level.
* https://andmed.eesti.ee/dataset?q=haridusamet -> 200 JS
  "Teabevärav" shell (12 chars visible), no server-rendered
  results — no trivially pollable national-portal Haridusamet
  dataset (same finding as Elektrilevi #400).
* https://teatmik.haridus.ee/lasteaiad/ -> 200 (HTM directory of
  kindergartens, linked from tallinn.ee): a per-institution
  directory, not a per-linnaosa queue-stats feed — joining it
  would still need per-page scraping, which this repo refuses.
* Tervisekassa GP lists: the guessed directory path answers 404
  ("Lehekülge ei leitud") — no bulk per-linnaosa open/closed table
  found at storefront level; probing stops here rather than
  enumerating URL guesses.
* https://enda.ehis.ee/ -> 200 (authenticated EHIS register): no
  anonymous bulk pull exists, and no auth was attempted.
Pulling any of this anyway would mean driving e-service session
flows or scraping directory/app internals — exactly the scraping
this repo refuses (AGENTS.md section 5). So all three dims return
None for EVERY input including missing origin: a queue band painted
from a one-off hand-check would be fake precision (OTA PR #131
precedent). Reasons say "hinnang" (estimate) and "EI OLE" and point
at the concrete buyer-side check (Haridusameti lasteaiakoha
taotlemise e-teenus, Tervisekassa nimistuotsing, koolivõrgu
arengukava, REL2021 ruudustik, Maa-ameti tehingud, KÜ aruanne,
kohapealne vaatlus) — never a faked area score.

Style mirrors services/scoring/livability.py and sibling batch
dims_group20a.py (#212): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, no Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for a kindergarten queue or a catchment
change, so there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#346) states it extends the demo ingestion ("no new
  plumbing expected unless a param needs it"): P4-025 source (5)
  names "Tallinna Haridusamet school open/close plans per
  linnaosa" and P4-052 source (5) names "Tallinna
  school-catchment changes per asum" — i.e. the Haridusamet feed
  P4-011 demos. With the demo verdict dated-negative there is no
  ingestion to extend, so both coverage slices land in the same
  verdict module rather than a second file importing a pipeline
  that does not exist (same precedent as elektrilevi #264+#344,
  comapps #302+#371, creditinfo #259+#340).
* P4-011 stays NULL even though the HTM teatmik directory lists
  kindergartens: a directory of institutions is not a queue-stats
  table, and per-institution scraping to synthesise linnaosa
  pressure would be exactly the scraping AGENTS.md section 5
  refuses — stated, not hidden.
* P4-025 scores only its school-plans slice as NULL and names the
  openly mappable cousins (REL2021 age/migration/vacancy grids,
  KV DOM medians, tehingute arv) as buyer-side checks: those legs
  belong to their own demos (Statamet, own-store, Maa-amet
  tehingud), and scoring the cousin here would claim the full
  param on a partial signal.
* P4-052 scores only its catchment-change demand-shift reading as
  NULL and keeps BOTH readings convention by naming the tehingud
  + KÜ legs as the buyer-side checks: the turnover question is
  bigger than school catchments, and a catchment-only calm must
  never read as a no-churn calm.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-011/P4-025/P4-052: documented no-map Haridusamet-feed NULLs
# (OTA PR #131 precedent). Kindergarten queue stats per linnaosa,
# school open/close plans, catchment changes per asum, and GP
# nimistu open/closed per linnaosa are content pages, JS app
# shells, or gated registers with no public bulk feed; each scorer
# reports the gap with a concrete buyer-side check instead of a
# faked number.
# ---------------------------------------------------------------------------

def dim_kindergarten_queue_gp(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """P4-011: NULL — queue stats + GP open/closed have no bulk feed."""
    return None, ("Lasteaia järjekorra ja perearsti-nimistu avatuse "
                  "hinnang on linnaosa tabeli hinnang (EI OLE "
                  "avaandmeid): järjekorra statistikat linnaosa/asumi "
                  "kohta avalikus masinvoogus pole, nimistute avatus "
                  "elab otsitavas kataloogis — kontrolli Haridusameti "
                  "lasteaiakoha taotlemise e-teenusest ja Tervisekassa "
                  "nimistuotsingust ning küsi kohapeal, ära feigi ala "
                  "skoori")


def dim_school_plan_liquidity(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """P4-025: NULL — school open/close plans live in docs (no feed)."""
    return None, ("Koolivõrgu avamis/sulgemisplaanide likviidsuse "
                  "hinnang on arengukava dokumendi hinnang (EI OLE "
                  "masinloetavat voogu): plaane linnaosa kohta avalikus "
                  "tabelis pole — loe Tallinna koolivõrgu arengukava, "
                  "võrdle REL2021 vanuse/rände ruudustikku ja KV "
                  "kuulutuste DOM-mediaane, ära feigi müüdavuse skoori")


def dim_catchment_turnover(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-052: NULL — catchment changes per asum unpublished (no feed)."""
    return None, ("Koolivaldade muutuse nõudlusnihke hinnang on "
                  "asumitabeli hinnang (EI OLE avaandmeid): "
                  "teeninduspiirkondade muutusi asumi kohta avalikus "
                  "voogus pole — võrdle Maa-ameti tehingute käivet ja "
                  "KÜ remondifondi dünaamikat ning loe Haridusameti "
                  "teeninduspiirkondade teateid, ära feigi hoone skoori")


P4_HARIDUS_DIMS = (
    ("kindergarten_queue_gp", "P4-011", dim_kindergarten_queue_gp),
    ("school_plan_liquidity", "P4-025", dim_school_plan_liquidity),
    ("catchment_turnover", "P4-052", dim_catchment_turnover),
)


def score_p4_haridus(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All three P4 Haridusamet dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_HARIDUS_DIMS). Every
    value is None by design — unpublished Haridusamet feed, never a
    faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_HARIDUS_DIMS}
