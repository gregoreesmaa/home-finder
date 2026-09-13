"""P4 Tervisekassa demo dims (issue #272).

Demo (#272): Tervisekassa perearstide nimistud (avatud/suletud) for
P4-011 end-to-end in Tallinn — the GP-list leg of "Lasteaia queue
length + perearst nimistu open/closed" (parameters4.md batch 1).
There is no follow-up coverage issue: P4-011's remaining legs are
already scored in sibling modules (see SIBLING OVERLAP), so the
"remaining 0 params" clause of #272 holds and this demo ships alone.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #272): Tervisekassa publishes the GP lists as a PowerBI-embedded
interactive report, not a pollable per-linnaosa bulk table. Polite
evidence, 6 requests total (labelled one-off user-agent
`home-finder openness probe #272 (one-off, single GETs; contact via
GitHub home-finder)`, 2 s pacing between GETs, headers +
visible-text keyword scope read only, no scraping, no auth, no form
driving, no report-token extraction, no PowerBI API calls), raw
bodies cached at /tmp/hf-tkas-probe/ (TTL: one-off check, kept for
the PR record, never committed):
* GET https://www.tervisekassa.ee/ -> HTTP 301 (466 bytes) to
  https://tervisekassa.ee/ (transport note, not data).
* GET https://www.tervisekassa.ee/et -> HTTP 301 (465 bytes) to
  https://tervisekassa.ee/et (transport note, not data).
* GET https://tervisekassa.ee/et -> HTTP 301 (250 bytes,
  "Redirecting to /", Drupal x-redirect-id 300) to / (transport
  note, not data).
* GET https://tervisekassa.ee/ -> HTTP 200, 68 346 bytes (~5.8k
  visible chars, title "Tervisekassa", 93 links, Drupal CMS page).
  Sweep 0 for csv / xlsx / andmestik / masinloetav / avaandmed /
  allalaadi / opendata; the single `api` hit is page chrome, not a
  data feed. One GP-care section link: /perearstiabi.
* GET https://tervisekassa.ee/perearstiabi -> HTTP 200, 97 301
  bytes (~14.8k visible chars, title "Perearstiabi | Tervisekassa",
  91 links). `nimistu` 31x as prose navigation, but `avatud` /
  `suletud` 0x and sweep 0 for csv / xlsx / andmestik /
  masinloetav / avaandmed / api / json / allalaadi — guidance
  prose, not a feed. One directory link:
  /perearstiabi/koik-eestis-nimistuga-tegutsevad-perearstid.
* GET .../koik-eestis-nimistuga-tegutsevad-perearstid -> HTTP 200,
  70 495 bytes, but the <main> content is 628 visible chars only
  (section nav + a feedback webform): no <table>, no per-GP rows,
  no `avatud` / `suletud` / `vaba`, no `linnaosa` / `tallinn`,
  sweep 0 for every bulk marker. The list itself is a
  `paragraph--type--powerbi-report` embed
  (powerbi.embed(... app.powerbi.com/reportEmbed ...) with a page
  JWT accessToken) — a JS-rendered BI report, not a pollable
  table. Extracting the token or driving the PowerBI API would be
  exactly the app-internals scraping this repo refuses (AGENTS.md
  section 5), so the probe stops here.
So the dim returns None for EVERY input including missing origin:
a PowerBI embed is not a per-linnaosa open/closed table, and
painting a GP-availability score from a one-off hand-read of the
prose pages would be fake precision (OTA PR #131 precedent).
Reasons say "hinnang" (estimate) and "EI OLE" and point at the
concrete buyer-side check (Tervisekassa perearstiabi nimistuotsing
+ perearsti vahetusavaldus, kohapealne küsimine) — never a faked
availability score.

SIBLING OVERLAP (read first, not edited): P4-011's non-GP legs are
already scored where they live — this module owns ONLY the
Tervisekassa nimistu open/closed leg and never re-scores them:
* HaridusSilm/EHIS school-capacity slice — dims_p4_ehis
  dim_school_pressure (key school_pressure, scored utilization
  bands, demo #271).
* REL2021 0-6 age demand-pressure slice — dims_p4_rel2021
  dim_kindergarten_pressure_rel (key kindergarten_pressure_rel,
  scored cohort bands).
* Tallinna Haridusamet queue-stats half — dims_p4_haridus
  dim_kindergarten_queue_gp (key kindergarten_queue_gp, NULL,
  demo #270; its reason already bundles the GP half and points
  at the same nimistuotsing — the two NULLs agree, and this
  module gives the Tervisekassa source its own key so a future
  per-linnaosa nimistu bulk graduates exactly one dim).

Style mirrors services/scoring/dims_p4_notar.py (#253): every
scorer is pure and offline-tested — (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for GP-list openness, so there is nothing for the
live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo with NO coverage issue: #272 states the
  remaining 0 params using this source need the follow-up coverage
  issue "created after this demo" — but P4-011's non-GP legs are
  already scored (ehis #271, rel2021 grid, both merged before this
  probe; haridus queue half NULL in #270), so there is nothing
  left to cover and no follow-up issue is opened. The sibling legs
  are named, never re-scored (same split-slice precedent as
  P4-020: ATA notices in dims_p4_ata, bureau scores NULL in
  dims_p4_creditinfo).
* (origin, pois) signature instead of a per-linnaosa join
  signature: with the dated-negative verdict there is no
  ingestion and hence no join input — the dim reports the
  nimistu gap for any listing, the same shape as the haridus
  P4-011 NULL (#270) and the notar dated-negative NULL (#253).
* A PowerBI embed can never be polled politely, even if its rows
  became readable: driving the embed means replaying page tokens
  against app.powerbi.com on every pull — app-internals scraping
  by construction. Only a first-party per-linnaosa bulk table (or
  a Teabevärav nimistu dataset) graduates this dim; the
  per-GP interactive lookup alone never qualifies without
  scraping, and linnaosa aggregation from per-GP rows would still
  need the open/closed flag the embed does not server-render.
* The openness check stopped at storefront + perearstiabi +
  directory-page level on purpose — no PowerBI token reuse, no
  report-API probing, no ankeet/survey driving, no Teabevärav
  re-probe (the #301 precedent — andmed.eesti.ee/dataset is a JS
  shell with no server-rendered results — is not re-hammered for
  this probe), no deeper URL guessing.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-011: documented no-map Tervisekassa GP-list NULL (OTA PR #131
# precedent). The nimistu open/closed per linnaosa lives in a
# PowerBI-embedded interactive report with no public bulk feed; the
# scorer reports the gap with a concrete buyer-side check instead of
# a faked availability score.
# ---------------------------------------------------------------------------

def dim_gp_list_open(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """P4-011: NULL — Tervisekassa nimistu open/closed is a BI embed, not a feed."""
    return None, ("Perearsti nimistu avatus linnaosas (Tervisekassa "
                  "nimistute avatud/suletud per-linnaosa hinnang) on "
                  "interaktiivse raporti hinnang (EI OLE masinloetavat "
                  "nimistutabelit): Tervisekassa avaldab tegutsevate "
                  "perearstide loetelu PowerBI-raportina, linnaosa "
                  "avatud/suletud koondtabelit ega voogu pole — kontrolli "
                  "Tervisekassa perearstiabi nimistuotsingust, esita "
                  "perearsti vahetusavaldus ja küsi kohapeal; P4-011 "
                  "naaber-legid on juba liidestatud (koolikohtade leg "
                  "dims_p4_ehis-is dim_school_pressure võtmega "
                  "school_pressure, 0–6 nõudlusleg dims_p4_rel2021-is "
                  "dim_kindergarten_pressure_rel võtmega "
                  "kindergarten_pressure_rel, järjekorra-leg NULL-ina "
                  "dims_p4_haridus-is dim_kindergarten_queue_gp võtmega "
                  "kindergarten_queue_gp) — ära feigi")


P4_TKAS_DIMS = (
    ("gp_list_open", "P4-011", dim_gp_list_open),
)


def score_p4_tkas(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 Tervisekassa dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_TKAS_DIMS). The value
    is None by design — BI embed, never a faked availability score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_TKAS_DIMS}
