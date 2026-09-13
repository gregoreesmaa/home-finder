"""P4 muinsus dims (issues #324 demo + #380 coverage): Muinsuskaitseamet
(new uses) verdict.

Demo (#324): Muinsuskaitseamet (new uses) via P4-005
Ehitusluba/kasutusluba existence - the heritage-protection leg
(Vanalinna / milieu-value-area query: is the building a listed
monument, in a kaitsevoond, or in a milieuvoortuslik ala, which
decides whether renovation needs Muinsuskaitseamet coordination
before the deal is bankable) end-to-end in Tallinn.
Coverage (#380): P4-041 Glimpse economics (piilukas view sliver),
Muinsuskaitseamet Vanalinna vaatekoridorid slice (protected-view
constraints), wired to the same demoed ingestion.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #324: the registry has no pollable machine endpoint for either
leg, so both dims stay NULL). Polite evidence, 5 single GETs total
(labelled one-off user-agent, >= 6 s pacing, `--max-time 25`,
headers + visible-text scope read only, no scraping, no auth;
the single spaced 520 re-probe below is a down-confirmation, not a
retry dare - HTTP 429/errors are a stop signal), raw bodies cached
at /tmp/hf-muinsus-probe/ (one-off PR record, never committed):
* https://register.muinsuskaitseamet.ee/ and
  https://register.muinsuskaitseamet.ee/api/v1/ -> DNS NXDOMAIN
  (curl exit 6 on both, nslookup confirms NXDOMAIN): the
  parameters3 Group 6 documented registry hostname is dead.
  Transport error, never data.
* https://muinsuskaitseamet.ee/ -> HTTP 200 (158500 bytes): agency
  front page; the registry link it publishes points at
  https://register.muinas.ee/ (5 mentions) - the register moved.
* https://register.muinas.ee/ -> HTTP 520 ("error code: 520",
  16 bytes), twice, 20+ s apart: origin down at check time. A
  human registry page that 520s cannot be polled, let alone joined.

So both dims return None for EVERY input including missing origin:
a protection verdict hand-read from a down registry, or a corridor
band painted from the agency front page's links, would be fake
precision (OTA PR #131 precedent). Reasons say "hinnang"
(estimate) and "EI OLE" and point at the concrete buyer-side check
(register desk, KOV milieu-area plans, vaatekohtade register,
on-site stand, sibling slices) - never a faked area score.

Style mirrors services/scoring/dims_p4_events.py (#310/#375): every
scorer is pure and offline-tested - (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for registry protection verdicts or dated corridor
polygons, so there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In
practice this verdict module needs no helpers at all - each dim
reports its missing registry leg directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#380) states it extends the demoed ingestion (#324) with
  "no new plumbing expected": with the demo verdict dated-negative,
  there is no ingestion to extend, so the P4-041 corridor slice
  lands in the same verdict module rather than a second file
  importing a pipeline that does not exist (same precedent as
  events #310+#375, komun #290+#363, TLT #277+#351, elektrilevi
  #264+#344, Elron #284+#358, RB #281+#355, kesk #291+#364, sadam
  #298+#368).
* Pairing rationale (each param names this source family in its
  parameters4.md source list, so no weak link): P4-005 source (5)
  "Muinsuskaitseamet paring for Vanalinna/miljoovaartus areas" is
  the demo leg; P4-041 source (3) "Muinsuskaitseamet Vanalinna
  vaatekoridorid (protected-view constraints)" is the
  glimpse-economics coverage leg.
* Per-source slices, not full params: P4-005 keeps the EHR permit
  leg (dims_p4_ehr dim_permit_bankable - read first, untouched:
  different record, different question, no overlap); P4-041 keeps
  the EHR floor-ratio glimpse leg (dims_p4_ehr dim_glimpse), the
  Maa-amet LiDAR/LoD2 view-fan leg, and the price-residual leg.
  Overturn #237 (parameters3 G6 muinas register, dims_group06*.py
  OSM heritage proxies - read, untouched) owns the G6 district /
  craft / friction params, a different question family from these
  two P4 bankability/view slices. Distinct dim keys throughout so
  the central hook can weight slices independently. Each reason
  names its cousins.
* The agency front page EXISTS (registry link observed) but a link
  is not a feed, and the registry itself 520s: activity is not
  openness. The reopening checklist in docs/p4_muinsus.md says
  exactly what would graduate each dim.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-005/P4-041: documented no-map muinsus-leg NULLs (OTA PR #131
# precedent). The documented registry hostname is dead (NXDOMAIN)
# and the moved register 520s (2026-09-13 dated-negative verdict
# above); each scorer reports the gap with a concrete buyer-side
# check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_permit_heritage(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-005: NULL - heritage-protection leg needs the registry (no map)."""
    return None, ("Muinsus-kaitse hinnangut pole (EI OLE masinloetavat "
                  "kultuurimälestiste registri voogu): dokumenteeritud "
                  "register.muinsuskaitseamet.ee on surnud (NXDOMAIN, "
                  "kontrollitud 2026-09-13) ja kolitud register.muinas.ee "
                  "vastab veaga HTTP 520 - kas hoone on mälestis, "
                  "kaitsevööndis või miljööväärtuslikul alal (Vanalinna), "
                  "kontrolli registri uksest / Muinsuskaitseametist ja KOV "
                  "miljööalade plaanidest enne renoveerimiseelarvet; "
                  "ehitusloa olemasolu dims_p4_ehr'is, ajaloolise kvartali "
                  "hõng dims_group06's, ära feigi")


def dim_glimpse_corridor(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-041: NULL - corridor slice needs pollable polygons (no map)."""
    return None, ("Piilukas-koridori hinnangut pole (EI OLE Vanalinna "
                  "vaatekoridoride masinloetavat kihti): register on maas "
                  "(HTTP 520, kontrollitud 2026-09-13), nii et kaitstud "
                  "vaate piirangut ei saa kaardilt liita - kas mere- või "
                  "vanalinna-piilukas jääb tuleviku-ehitusest puutumata, "
                  "kontrolli Tallinna üldplaneeringu vaatekohtade "
                  "registrist ja seisa kohapeal; korruse-suhte "
                  "piilukas-klass dims_p4_ehr'is, LiDAR/vaateanalüüs "
                  "eraldi, ära feigi")


P4_MUINSUS_DIMS = (
    ("permit_heritage", "P4-005", dim_permit_heritage),
    ("glimpse_corridor", "P4-041", dim_glimpse_corridor),
)


def score_p4_muinsus(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both P4 muinsus dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_MUINSUS_DIMS). Every value
    is None by design - dead registry hostname plus down register,
    no pollable feed, never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_MUINSUS_DIMS}
