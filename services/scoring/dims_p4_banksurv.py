"""P4 bank-collateral-survey dim (issue #323 demo only): banksurv verdict.

Demo (#323): the Bank collateral survey aggregates source via P4-038
Bargaining margin (offer-vs-close gap) end-to-end in Tallinn - the
bank-survey leg (area-type offer-vs-valuation gap from the banks' own
collateral-survey aggregates). Single-param demo: P4-038 is the only
param naming this source, so there is no coverage follow-up issue
(the #323 body states the remaining 0 params need only a follow-up
created after this demo, and with a dated-negative demo there is no
ingestion to extend); P4-038's sibling legs are already scored where
they live (see SIBLING OVERLAP).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #323: bank collateral-survey aggregates are proprietary
underwriting data with no pollable bulk feed, so the dim stays
NULL). Polite evidence, 1 polite check (2 served requests: the root
redirect plus its target, labelled one-off user-agent `home-finder
banksurv openness-check #323 (one-off, single GETs, no retry; contact
via GitHub home-finder)`, `--max-time 25`, headers + visible-text/link
scope read only, no scraping, no auth, no loan/valuation-calculator
driving, no service enumeration), raw bodies cached at
/tmp/hf-banksurv-probe/ (one-off PR record, never committed):
* GET https://www.swedbank.ee/ -> HTTP 302 (0 bytes) to /private
  (locale-split gate; transport note, not data).
* GET https://www.swedbank.ee/private (redirect target) -> HTTP 200
  (444765 bytes, ~4.3k visible chars, 75 links, title "Avaleht -
  Swedbank"). Sweep 0 for avaandmed / open data / andmestik /
  masinloetav / api / csv / geojson / wfs / download / allalaadimine /
  arendaja / developer in visible text, and 0 machine-looking hrefs
  (no api/download/csv/json/geojson/wfs/andmestik/opendata/developer/
  arendaja/allalaadi in any link target). Visible text 0 for
  küsitlus-adjacent survey/koond/aggregaat/kinnisvaraturg/ülevaade
  feed words - the only "tagatis" hits (2x) are study-loan marketing
  prose ("kinnisvara tagatiseta" õppelaen), not a survey aggregate.
  The only transaction surfaces are per-customer loan flows and the
  commentary blog (blog.swedbank.ee) - individual calculators and
  human analysis, never a bulk aggregate feed.

So the dim returns None for EVERY input including missing origin:
collateral surveys are the banks' internal lending-decision input,
and painting a per-listing opening-bid score from a one-off hand-read
of a marketing storefront - or by driving a valuation calculator with
fake borrower profiles - would be fake precision (OTA PR #131
precedent) and, for the calculator path, exactly the form-driving
this repo refuses (AGENTS.md section 5). The reason says "hinnang"
(estimate) and "EI OLE" and points at the concrete buyer-side checks
(maakleri piirkonnatüübi gap-statistika, Maa-ameti publikatsioon,
P4-002 võrdlustehingud, scored cousins below) - never a faked gap score.

Pulls / cache / TTL (acceptance criterion 2): NO pulls beyond the
one-off check above (nothing pollable exists, so there is nothing to
cache and no live TTL). If a bank ever publishes a pollable aggregate
feed, the honest cadence is quarterly at most (area-type aggregates
move on publication timescales, matching the Stat KK11 quarterly and
Maa-amet publication legs) - single GET, file cache, re-pull only -
see the reopening checklist in docs/p4_banksurv.md.

SIBLING OVERLAP (read first, not edited): three P4-038 legs are
already scored where they live - this module owns ONLY the
bank-survey leg and never re-scores them:
* Land Board publication gap-table slice - dims_p4_maa_tehingud
  dim_bargaining_margin (key bargaining_margin, area-type table
  join; NULL in production while the table is unpublished).
* Stat quarterly-index calibration slice - dims_p4_stat
  dim_bargaining_margin_stat (key bargaining_margin_stat, QoQ heat
  calibration; the gap table itself stays the tehingud leg's job).
* Own-store per-listing drop slice - dims_p4_own_store
  dim_bargaining_margin (key bargaining_margin, NULL by design:
  the listing's own price cut already belongs to P4-001, scoring it
  twice would double-count the same cut in the steal sort).
The KV.ee/city24 asking-vs-microcomp residuals, the own-adapter
price-drop distribution, and the notariaat volume heat legs have no
dims module of their own (adapter-store / unpublished inputs) and
are named where the param needs them, never faked here.

Style mirrors services/scoring/dims_p4_insurers.py (#286, the
closest proprietary-source precedent: single NULL dim, dated
negative, no network code): the scorer is pure and offline-tested -
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, no Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for a bank's internal collateral table, so
there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In
practice this verdict module needs no helpers at all - the single
dim reports its missing bank leg directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: P4-038 is the only param
  naming this source (parameters4.md P4-038 source (5) "Tallinn bank
  collateral survey aggregates (verify openness)"), so one module,
  one test file, one verdict note - no second file importing a
  pipeline that does not exist.
* Per-source slice, not the full param: the dim owns ONLY the
  bank-survey leg. The scored cousins above keep their owners,
  untouched; the reason names each cousin so the NULL stays
  actionable.
* The check stopped at storefront level on purpose: one bank's
  storefront (Swedbank, the redirect-resolved market-leader page)
  carries the verdict for the source family - collateral surveys
  are proprietary everywhere by construction, and SEB/Luminor loan
  flows are the same per-customer calculators, not bulk feeds.
  Chasing SEB/Luminor shells or driving valuation calculators would
  add bytes, not information, and calculator-driving is
  form-driving (AGENTS.md section 5).
* No fetch_* helper: with a dated-negative verdict there is no
  pollable feed to wrap, and a fetcher around storefront pages
  would be brittle scraping dressed as ingestion (komun #290
  precedent - verdict modules carry no network code, pinned by
  test_module_adds_no_network_calls).
* (origin, pois) signature instead of a join signature: with the
  dated-negative verdict there is no ingestion and hence no join
  input - the dim reports the survey-table gap for any listing, the
  same shape as the insurers/opmaps dated-negative NULLs.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-038: documented no-map bank-survey-leg NULL (OTA PR #131
# precedent). Swedbank/SEB/Luminor collateral surveys are internal
# lending-decision inputs with no public bulk feed (2026-09-13
# dated-negative verdict above); the scorer reports the gap with
# concrete buyer-side checks instead of a faked number.
# ---------------------------------------------------------------------------

def dim_bargaining_margin_banksurv(origin: Optional[Tuple[float, float]],
                                   pois: Optional[List[dict]]) -> Score:
    """P4-038: NULL - bank collateral survey aggregates are proprietary."""
    return None, ("Pangatagatis-küsitluse koond on avamispakkumuse-hinnang (EI OLE "
                  "masinloetavat koondtabelit): Swedbank/SEB/Luminori "
                  "tagatis-hindamised on sisemine laenuotsuse sisend, "
                  "hulgi-allalaadimist ega API-d pole (kontrollitud 2026-09-13, "
                  "Swedbanki esindusleht on andmevoota pood koos individuaalsete "
                  "laenuvoogude ja kommentaariblogiga) - küsi maaklerilt "
                  "piirkonnatüübi pakkumis-vs-tehingu lõhe statistikat "
                  "(Maa-ameti publikatsioon) ning võrdle küsitavat P4-002 "
                  "võrdlustehingutega; numbrilised P4-038-legid on juba "
                  "liidestatud (Maa-ameti gap-tabel dims_p4_maa_tehingud-is "
                  "dim_bargaining_margin, kvartaliindeksi kalibratsioon "
                  "dims_p4_stat-is dim_bargaining_margin_stat, kuulutuse "
                  "hinnalangus juba P4-001 skoor dims_p4_own_store-is) - "
                  "ära feigi")


P4_BANKSURV_DIMS = (
    ("bargaining_margin_banksurv", "P4-038", dim_bargaining_margin_banksurv),
)


def score_p4_banksurv(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 banksurv dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_BANKSURV_DIMS). The value
    is None by design - proprietary survey table with no pollable feed,
    never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_BANKSURV_DIMS}
