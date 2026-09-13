"""P4 Rahandusministeerium dims (issues #315 demo + #377 coverage).

Demo (#315): Rahandusministeerium ingestion for P4-019 end-to-end in
Tallinn — polite, cached, TTL-stated pulls of the KOV finantsandmed
plus the automaks-revenue calibration. Coverage (#377): P4-037 wired
to the same demoed ingestion (no new plumbing expected unless a param
needs it; none did, see judgment calls).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #315): the ministry publishes no pollable machine-readable feed
for either slice below. Polite evidence, 4 served requests total
(four single GETs with a labelled one-off user-agent, headers +
visible-text keyword scope read only, no scraping, no auth, no form
driving, no service enumeration), raw bodies cached at
/tmp/hf-rahmin-probe/ (TTL: one-off check, kept for the PR record,
never committed):
* https://www.rahandusministeerium.ee/ -> timeout from here
  (transport note, not data — fin.ee is the working host, below).
* https://www.fin.ee/ (ministry storefront, "Avaleht |
  Rahandusministeerium") -> HTTP 200, 195440 bytes (~10.4k visible
  chars). No KOV/omavalitsus section links anywhere in the 320
  links; sweep 0 for csv / xlsx / andmestik / masinloetav.
* https://www.fin.ee/ministeerium-uudised-ja-kontakt/uuringud-ja-analuusid/statistika
  -> HTTP 200, 179939 bytes (~7.9k visible chars). No KOV finance
  section (0 hits for kohalik/omavalitsus/KOV/võlakoormus); the two
  avaandmed hits are site-nav chrome plus a pointer at EMTA open
  data and Statistikaamet (sibling territory, dims_p4_emta /
  dims_p4_stat — not re-polled here). No csv / xlsx / andmestik /
  masinloetav anywhere.
* https://www.fin.ee/riigi-rahandus-ja-maksud/maksu-ja-tollipoliitika/maksud
  -> HTTP 200, 237385 bytes (~36.5k visible chars). Automaks
  content is policy prose (M1/N1 categories, baasosa 50 eurot, CO2
  component, e-MTA payment) — no revenue table, 0 hits for
  maksulaekumine/laekumine-as-revenue; the KOV-budget pointer
  ("Andmed kohalike omavalitsuste eelarve kohta on leitavad
  järgnevalt leheküljelt") carries NO hyperlink — a dead reference
  in human prose. Sweep 0 for csv / xlsx / andmestik /
  masinloetav.
* National-portal dataset search re-uses the #301 precedent
  (andmed.eesti.ee/dataset is a JS shell with no server-rendered
  results) — not re-hammered for this probe.
So both dims return None for EVERY input including missing origin:
a per-KOV fiscal table or revenue calibration painted from a
one-off hand-read of human policy pages would be fake precision
(OTA PR #131 precedent). Reasons say "hinnang" (estimate) and
"EI OLE" and point at the concrete buyer-side check (Tallinna
eelarve + eelarvestrateegia, EMTA automaksu kalkulaator,
TLT/Peatus.ee alternatiivid, KÜ/eelarve päring) — never a faked
area score.

SIBLING OVERLAP (read first, not edited): dims_p4_emta.py owns the
EMTA slices of the SAME two params (P4-019 maamaks rate/trend via
dim_fiscal_health, P4-037 automaks/CO2 exposure via
dim_policy_exposure) — this module owns ONLY the
Rahandusministeerium legs (KOV finantsandmed, automaksu laekumise
kalibreering) and never re-scores them. dims_group16*.py (overturn
#242 G16 tax tables) is untouched.

Style mirrors services/scoring/dims_p4_fixit.py (#301/#370): every
scorer is pure and offline-tested — (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for ministry finance tables or per-KOV revenue
figures, so there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#377) states it "extends the demoed ingestion" — with the
  demo verdict dated-negative, there is no ingestion to extend, so
  the coverage slice lands in the same verdict module rather than
  a second file importing a pipeline that does not exist (same
  precedent as fix-it #301+#370, Terviseamet #289+#362, Elron
  #284+#358, TLT #277+#351).
* Pairing rationale (each param names this source in its
  parameters4.md source list): P4-019 source 2 is the
  Rahandusministeerium KOV finantsandmed leg (võlakoormus,
  investeeringud, maamaksu-trend Tallinn) — the demo slice.
  P4-037 source 6 is the Rahandusministeerium automaksu laekumine
  Tallinn leg (policy calibration) — the coverage slice.
* Sibling legs stay scored where they live, named never re-scored
  (same split-slice precedent as P4-020: ATA notices in
  dims_p4_ata, bureau scores NULL in dims_p4_creditinfo): the
  Statamet KOV-finantsnäitajate leg (dims_p4_stat
  dim_kov_fiscal_stat), the EMTA maamaksu-määra/trendi leg
  (dims_p4_emta dim_fiscal_health), the arengukava
  investeeringute-tabeli leg (dims_p4_cityplans
  dim_investeering_cityplans) and the overturn-#242 G16
  tax-table legs (dims_group16*.py, untouched); the EMTA
  automaksu/CO2 leg (dims_p4_emta dim_policy_exposure), the
  tasulise-parkimise/autovaba-ala tsooni-kulu leg (dims_p4_park
  dim_zone_cost), the liikluspiirangute leg (dims_p4_trans
  dim_policy_restrictions), the kavandatud-tsooni leg
  (dims_p4_cityplans dim_poliitika_kava_cityplans) and the
  pendelrände-alternatiivi legs (dims_p4_peatus
  dim_policy_exposure, dims_p4_tlt dim_tlt_commute_offset). Each
  reason names its scored cousins so the buyer knows which half
  is already joined.
* P4-019 (per-KOV fiscal TABLE, annual) vs P4-037 (per-KOV
  revenue CALIBRATION feeding the per-listing exposure band):
  different honest shapes, both NULL — no double-scoring by
  construction.
* The openness check stopped at storefront/page level on purpose
  — no site-search crawling, no deep-URL guessing, no Teabevärav
  re-probe, no DOC/PDF parsing. The unlinked "järgnevalt
  leheküljelt" reference is recorded as found, not chased:
  chasing it through search crawls is exactly the enumeration
  this repo refuses (AGENTS.md section 5).

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-019/P4-037: documented no-map Rahandusministeerium NULLs (OTA PR
# #131 precedent). KOV finantsandmed (võlakoormus, investeeringud,
# maamaksu trend) and automaksu laekumine Tallinn (policy
# calibration) are human policy publications with no public
# machine-readable feed; each scorer reports the gap with a
# concrete buyer-side check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_fiscal_rahmin(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """P4-019: NULL — Rahandusministeerium KOV-finantstabel puudub."""
    return None, ("KOV finantstervis Rahandusministeeriumi andmetest "
                  "(võlakoormus, investeeringud, maamaksu trend, "
                  "per-KOV tabel, aastane) on eelarve-hinnang "
                  "(EI OLE liidestatud finantstabelit): ministeerium "
                  "avaldab maksupoliitikat inimloetava proosana, KOV "
                  "eelarve-viide on linkimata lause — hinda Tallinna "
                  "eelarvest ja eelarvestrateegiast (tallinn.ee), küsi "
                  "võlakoormust ja investeeringuid ning vaata Statameti "
                  "KOV-legi dims_p4_stat-ist (dim_kov_fiscal_stat), EMTA "
                  "maamaksu-legi dims_p4_emta-st (dim_fiscal_health), "
                  "arengukava investeeringu-legi dims_p4_cityplans-ist "
                  "(dim_investeering_cityplans) ja overturn-#242 "
                  "maksutabeleid dims_group16*.py-st, ära feigi")


def dim_automaks_revenue(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-037: NULL — automaksu laekumise kalibreering puudub."""
    return None, ("Automaksu laekumise kalibreering Rahandusministeeriumist "
                  "(poliitika-kalibratsioon per-KOV, toidab kuulutuse "
                  "mõjutusriba) on poliitika-hinnang (EI OLE liidestatud "
                  "laekumistabelit): ministeeriumi automaksu-leht on "
                  "määrade-proosa (baasosa, CO2-komponent), mitte "
                  "Tallinna laekumine — arvuta oma sõiduki mõjutus EMTA "
                  "kalkulaatoris (avalik.emta.ee), hinda pendelrände "
                  "alternatiivi (TLT/Peatus.ee) ning vaata EMTA CO2-legi "
                  "dims_p4_emta-st (dim_policy_exposure), tsooni-kulu-legi "
                  "dims_p4_park-ist (dim_zone_cost), piirangu-legi "
                  "dims_p4_trans-ist (dim_policy_restrictions), "
                  "kavandatud-tsooni-legi dims_p4_cityplans-ist "
                  "(dim_poliitika_kava_cityplans) ja alternatiivi-lege "
                  "dims_p4_peatus-ist (dim_policy_exposure) ning "
                  "dims_p4_tlt-st (dim_tlt_commute_offset), ära feigi")


P4_RAHMIN_DIMS = (
    ("fiscal_rahmin", "P4-019", dim_fiscal_rahmin),
    ("automaks_revenue", "P4-037", dim_automaks_revenue),
)


def score_p4_rahmin(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both P4 Rahandusministeerium dims for one listing (entry point
    for the weight-rebalance follow-up; keys match P4_RAHMIN_DIMS).
    Every value is None by design — unpublished ministry tables,
    never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_RAHMIN_DIMS}
