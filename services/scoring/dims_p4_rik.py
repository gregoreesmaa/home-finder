"""P4 RIK e-Kinnistusraamat dims (issue #252, single-param demo, no coverage issue).

Demo (#252): RIK e-Kinnistusraamat ingestion for P4-004 end-to-end in
Tallinn — polite, cached, TTL-stated pulls of the per-parcel extract
plus the notary checkpoint. Single param: P4-004 Kinnistusregistri
süva (keelumärge/hüpoteek summary + notary checkpoint), per-listing
dim, weak-good capped.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #252): e-Kinnistusraamat extracts are PAID per-section — there is
no open bulk and no anonymous per-parcel feed to poll. Polite
evidence, 4 served requests total (single GETs with a labelled
one-off user-agent, headers + visible-text keyword scope read only,
no scraping, no auth attempts, no form driving, no service
enumeration), raw bodies cached at /tmp/hf-rik-probe/ (TTL: one-off
check, kept for the PR record, never committed):
* https://www.rik.ee/et/kinnistusraamat (guessed deep URL) ->
  HTTP 404 "Lehekülge ei leitud" (documented negative guess, not a
  real path — same precedent as the EMTA #256 guessed-URL 404s).
* https://www.rik.ee/ -> HTTP 301 to /et (transport note, not data).
* https://www.rik.ee/et (RIK storefront, "Avaleht |
  Registrite ja Infosüsteemide Keskus") -> HTTP 200, 36293 bytes.
  Advertises the e-Kinnistusraamat portal tree in nav only:
  "E-kinnistusraamatu portaal", "Päringud", "Teenuste hinnad",
  "Lepinguinfo", "XML teenus", "Korteriühistu väljavõte",
  "Kinnistuportaal" — i.e. queries live behind the portal's
  contract/pricing wall, not as linked open data.
* https://www.rik.ee/et/e-kinnistusraamat/e-kinnistusraamatu-portaal/teenuste-hinnad
  -> HTTP 200, 32893 bytes (~2.8k visible chars). The price table,
  verbatim: "Teenuste hinnad: Teenus / Hind — I jao kanne 2 €,
  II jao kanne 2 €, III ja IV jao kanne kokku 2 €, Terve
  registriosa 6 €. *Hindadele ei lisandu käibemaksu. *Ostetud
  andmetega saab 24 tunni jooksul korduvalt tutvuda, tehes
  päringut". Bulk-shaped access ("XML teenus") sits under
  "Lepinguinfo" — a contract, not an anonymous endpoint.
So the single dim returns None for EVERY input including missing
origin: a keelumärge/hüpoteek summary painted without a paid
extract (or without the buyer's own notary check) would be fake
precision (OTA PR #131 precedent). Reasons say "hinnang"
(estimate) and "EI OLE" and point at the concrete buyer-side check
(tasuline e-Kinnistusraamat väljavõte + notari kontroll,
notar.ee) — never a faked per-listing score.

SIBLING OVERLAP (read first, not edited): the other P4-004 slices
stay scored where they live and are named here, never re-scored —
the KKIS public-layer slice (dims_p4_maa_kataster
dim_kinnistus_syva), the Ametlikud Teadaanded notice slice
(dims_p4_ata dim_kinnistus_checkpoint), the EMTA maksuvõla slice
(dims_p4_emta dim_kinnistus_debt) and the kohtutäituri-register
slice (dims_p4_taitur dim_kinnistus_checkpoint). This module owns
ONLY the RIK paid-extract leg (registriosa I–IV jaod per parcel),
which has no open feed — hence NULL.

Style mirrors services/scoring/dims_p4_rahmin.py (#315/#377): the
scorer is pure and offline-tested — (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for paid register extracts, so there is nothing for
the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: #252 states the remaining
  0 params using this source are covered by a follow-up that is
  only created after this demo — with a dated-negative demo there
  is no ingestion to extend, so there is nothing to split out.
  One dim, one module, three new files, no shared-file edits.
* No ingestion to cache and no TTL to state beyond this one-off
  check (rahmin #315 precedent): re-probe yearly, or sooner if
  rik.ee/avaandmed or Teabevärav gains an open kinnistusraamat
  dataset. A newly opened bulk flips the verdict without
  re-probing deeper than the hinnad + portal pages.
* The openness check stopped at storefront/price-list level on
  purpose — no portal login attempts, no query-form driving, no
  XML-teenus contract probing, no per-parcel pulls (each costs
  2–6 € and needs a contract/identity). Chasing the paid flow
  with real queries is exactly the spend + enumeration this repo
  refuses (AGENTS.md section 5).
* Honest future shape (stated, not scored): per-listing dim,
  weak-good capped like the scored cousins (never 100 — a paid
  extract still needs the notary's reading; never 0 on this leg
  alone). Today every reason says EI OLE and names the
  väljavõte + notari kontroll.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-004: documented no-map RIK paid-extract NULL (OTA PR #131
# precedent). Registriosa I–IV jaod per parcel (keelumärge/hüpoteek
# summary) plus the notary checkpoint are a per-listing, per-deal
# paid flow (2 € per jagu, 6 € full registriosa, lepingu-based XML
# bulk) with no open feed; the scorer reports the gap with the
# concrete buyer-side check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_rik_extract(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """P4-004: NULL — RIK e-Kinnistusraamat väljavõte on tasuline voog."""
    return None, ("Kinnistusregistri süva RIK e-Kinnistusraamatust "
                  "(registriosa I–IV jaod: keelumärge/hüpoteek, "
                  "per-listing, nõrk-hea laega) on tehingu-hinnang "
                  "(EI OLE avatud liidestatud väljavõtet): RIK "
                  "hinnakiri küsib I jao kande 2 €, II jao kande 2 €, "
                  "III ja IV jao kande kokku 2 € ja terve registriosa "
                  "6 € ning XML-mahuvoog eeldab lepingut — osta "
                  "tasuline väljavõte (kinnistusraamat.rik.ee) ja küsi "
                  "notari kontrolli (notar.ee) enne pakkumist ning "
                  "vaata avaliku kihi legi dims_p4_maa_kataster-ist "
                  "(dim_kinnistus_syva), teadaande-legi dims_p4_ata-st "
                  "(dim_kinnistus_checkpoint), maksuvõla-legi "
                  "dims_p4_emta-st (dim_kinnistus_debt) ja täituri-legi "
                  "dims_p4_taitur-ist (dim_kinnistus_checkpoint), "
                  "ära feigi")


P4_RIK_DIMS = (
    ("rik_extract", "P4-004", dim_rik_extract),
)


def score_p4_rik(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 RIK dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_RIK_DIMS). The value
    is None by design — paid register extracts, never a faked
    per-listing score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_RIK_DIMS}
