"""P4 notar demo dims (issue #253).

Demo (#253): notar.ee closing-guidance ingestion for P4-004 end-to-end
in Tallinn — polite, cached, TTL-stated pulls of the Notarite Koda
closing-guidance slice plus an honest-shape per-listing dim. There is
no follow-up coverage issue: P4-004's remaining legs are already
scored in sibling modules (see SIBLING OVERLAP), so the "remaining 0
params" clause of #253 holds and this demo ships alone.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #253): Notarite Koda publishes closing guidance as human prose,
not pollable data. Polite evidence, 5 served requests + 1
headers-only HEAD total (labelled one-off user-agent
`home-finder openness probe #253 (one-off, single GETs; contact via
GitHub home-finder)`, 2 s pacing between GETs, headers + visible-text
keyword scope read only, no scraping, no auth, no form driving, no
service enumeration), raw bodies cached at /tmp/hf-notar-probe/
(TTL: one-off check, kept for the PR record, never committed):
* GET https://notar.ee/ -> HTTP 301 (162 bytes) to
  https://www.notar.ee/ (transport note, not data).
* GET one guessed deep guidance URL
  (/kinnisvara-ost-muuk-ja-urimine/) -> HTTP 301 (162 bytes, dead
  guess — recorded, not chased; guessing deeper URLs is exactly the
  enumeration this repo refuses, AGENTS.md section 5).
* GET https://www.notar.ee/et (redirect target) -> HTTP 200, 69607
  bytes (~3.5k visible chars, title "Notarite Koda"). 67 links; the
  `api` hits are Google-Fonts stylesheet links plus a Drupal
  date_api CSS module (chrome, not a data feed). Sweep 0 for csv /
  xlsx / andmestik / masinloetav / avaandmed.
* GET https://www.notar.ee/et/teabekeskus/kinnisvara -> HTTP 200,
  94832 bytes (~14.8k visible chars, title "Kinnisvaratehingud |
  Notarite Koda"). 70 links; sweep 0 for csv / xlsx / andmestik /
  masinloetav / avaandmed / open-data / api. The `json` hits are
  jQuery cookie chrome, the `xml` hits are xml:lang attributes —
  no export, no download, no feed.
So the dim returns None for EVERY input including missing origin:
guidance prose is not pollable data, and painting a per-listing
closing score from a one-off hand-read of the Kinnisvaratehingud
page would be fake precision (OTA PR #131 precedent). Reasons say
"hinnang" (estimate) and "EI OLE" and point at the concrete
buyer-side check (notar.ee Kinnisvaratehingud guidance + notari tasu
kalkuleerimine, RIK e-Kinnistusraamat väljavõte, notari
ajabroneerimine) — never a faked closing score.

SIBLING OVERLAP (read first, not edited): four P4-004 legs are
already scored where they live — this module owns ONLY the
notar.ee closing-guidance leg and never re-scores them:
* KKIS/kataster kitsenduste slice — dims_p4_maa_kataster
  dim_kinnistus_syva (per-parcel join).
* Kohtutäiturite-register active-proceedings slice —
  dims_p4_taitur dim_kinnistus_checkpoint (coverage #336).
* Ametlike Teadaannete keelumärge/arest slice — dims_p4_ata
  dim_kinnistus_checkpoint.
* EMTA maksuvõlg-per-entity slice — dims_p4_emta
  dim_kinnistus_debt.
Deal-cost cousins (notary fees per deal, G16) stay in
dims_group16a.py (dim_closing_costs, untouched).

Style mirrors services/scoring/dims_p4_rahmin.py (#315/#377): every
scorer is pure and offline-tested — (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for notary guidance prose, so there is nothing for the
live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo with NO coverage issue: #253 states the
  remaining 0 params using this source need the follow-up coverage
  issue "created after this demo" — but P4-004's non-guidance legs
  are already scored (taitur #336, ATA, EMTA, maa-kataster,
  all merged before this probe), so there is nothing left to cover
  and no follow-up issue is opened. The sibling legs are named,
  never re-scored (same split-slice precedent as P4-020: ATA
  notices in dims_p4_ata, bureau scores NULL in
  dims_p4_creditinfo).
* (origin, pois) signature instead of a join signature: with the
  dated-negative verdict there is no ingestion and hence no join
  input — the dim reports the guidance gap for any listing, the
  same shape as the rahmin dated-negative NULLs.
* Guidance prose can never score a listing, even machine-readable:
  a future notar.ee guidance export would version the checklist
  text, never produce a per-listing number — so the honest shape
  stays per-listing NULL by construction and the scored cousins
  above carry every number.
* The openness check stopped at storefront + guidance-page level on
  purpose — no site-search crawling, no deep-URL guessing beyond
  the one recorded dead guess, no Teabevärav re-probe, no DOC/PDF
  parsing. National-portal dataset search re-uses the #301
  precedent (andmed.eesti.ee/dataset is a JS shell with no
  server-rendered results) — not re-hammered for this probe.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-004: documented no-map notar.ee closing-guidance NULL (OTA PR #131
# precedent). The Kinnisvaratehingud guidance page is human prose with
# no public machine-readable feed; the scorer reports the gap with a
# concrete buyer-side check instead of a faked closing score.
# ---------------------------------------------------------------------------

def dim_notar_closing_guidance(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """P4-004: NULL — notar.ee closing guidance is prose, not pollable data."""
    return None, ("Notari sulgemisjuhis notar.ee-st (Kinnisvaratehingud "
                  "teabekeskus, per-listing sulgemisvalmiduse hinnang) "
                  "on juhendproosa-hinnang (EI OLE liidestatud "
                  "sulgemisandmeid): Notarite Koda avaldab sulgemise "
                  "samme inimloetavana, masinloetavat voogu pole — loe "
                  "notar.ee Kinnisvaratehingud lehte, arvuta notari tasu "
                  "kalkuleerimis-lehest, võta RIK e-Kinnistusraamatu "
                  "väljavõte ja broneeri notari aeg; numbrilised "
                  "P4-004-legid on juba liidestatud (KKIS/kitsendused "
                  "dims_p4_maa_kataster-is dim_kinnistus_syva, "
                  "taitur-lõik dims_p4_taitur-is dim_kinnistus_checkpoint, "
                  "AT-lõik dims_p4_ata-s dim_kinnistus_checkpoint, "
                  "maksuvõla-lõik dims_p4_emta-s dim_kinnistus_debt), "
                  "tehingukulud dims_group16a-s (dim_closing_costs) — "
                  "ära feigi")


P4_NOTAR_DIMS = (
    ("notar_closing_guidance", "P4-004", dim_notar_closing_guidance),
)


def score_p4_notar(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 notar.ee dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_NOTAR_DIMS). The value
    is None by design — guidance prose, never a faked closing score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_NOTAR_DIMS}
