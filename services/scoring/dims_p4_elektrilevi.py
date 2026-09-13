"""P4 Elektrilevi per-address/hex dimensions (issues #264 demo + #344 coverage).

Params (this module only — demo + its coverage follow-up share one source):
* P4-009 Power/internet reliability at address: outage history (SAIDI per
  feeder) + backup-feed info (batch 1, demo in #264)
* P4-008 Heating tariff zone, Elektrilevi slice: võrgutasud/hinnakiri
  (batch 1, coverage in #344)
* P4-036 Roof income, Elektrilevi slice: liitumiskaart export feasibility
  (batch 3, coverage in #344)
* P4-046 Dread removal, Elektrilevi slice: backup-feed info
  (batch 4, coverage in #344)
* P4-051 Zero-consumption stairwells: aggregated zero-consumption meters
  per hex/KOV, never addresses (batch 5, coverage in #344)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#264): Elektrilevi publishes no pollable bulk feed for any of the five
slices above. Polite evidence, ~10 tiny requests total (HEADs + single
GETs with a labelled one-off user-agent, headers + visible-text keyword
scope read only, no scraping, no auth), raw bodies cached at
/tmp/elektrilevi-open/ (TTL: one-off check, kept for the PR record,
never committed):
* https://www.elektrilevi.ee/ -> 302 to /et/avaleht (Cloudflare +
  Liferay CMS storefront).
* Canonical landing (168 KB): visible text mentions katkestused (3x)
  and hinnakiri (2x) as service pages, but avaandmed / open data /
  arendaja / developer / X-tee / X-Road / andmestik / masinloetav all
  score 0 — no open-data page, no developer portal, no X-tee service
  advertised.
* Outage history lives in the interactive rikkekaart app
  (https://rikkekaart.elektrilevi.ee/ -> HTTP 200 text/html app shell;
  linked from /et/katkestused/katkestuste-kaart): a live fault map,
  not a SAIDI-per-feeder history feed. No bulk endpoint advertised.
* Connection/capacity lives behind the account-gated self-service
  (https://minu.elektrilevi.ee/ liitumised; "minu-andmed" needs
  re-authentication) plus the vabadvoimsused map app: interactive or
  gated, never a pollable join.
* National portal: https://andmed.eesti.ee/ (successor of
  avaandmed.eesti.ee, 301) serves a JS "Teabevärav" shell with no
  server-rendered results, and its /api/3/action/package_search
  answers 404 — no trivially pollable Elektrilevi dataset exists.
* Zero-consumption aggregates and backup-feed info are published
  nowhere (the former is privacy-sensitive by construction —
  parameters4.md P4-051 mandates hex/KOV only, never addresses).
Pulling any of this anyway would mean driving session-gated flows
or scraping map-app internals — exactly the scraping this repo
refuses (AGENTS.md section 5). So all five dims return None for
EVERY input including missing origin: a feeder band painted from a
one-off hand-check would be fake precision (OTA PR #131 precedent).
Reasons say "hinnang" (estimate) and "EI OLE" and point at the
concrete buyer-side check (rikkekaart live map, TTJA netikaart,
Konkurentsiamet piirhinnad, Elering mikrotootja tingimused, KÜ
aruanne + direct KÜ enquiry, kohapealne vaatlus) — never a faked
area score.

Style mirrors services/scoring/livability.py and sibling batch
dims_group20a.py (#212): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, no Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for a DSO's unpublished per-feeder history,
so there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#344) states it extends the demo ingestion (#264): with the
  demo verdict dated-negative, there is no ingestion to extend, so
  the four coverage slices land in the same verdict module rather
  than a second file importing a pipeline that does not exist (same
  precedent as comapps #302+#371 and creditinfo #259+#340).
* P4-009 stays NULL even though its broadband half has openly
  checkable cousins (TTJA netikaart address check, Ookla open tiles):
  those are per-address live lookups / a different source's tiles,
  not the Elektrilevi feeder history this verdict covers, and wiring
  them belongs to their own demos — scoring the cousin here would
  claim the full param on a partial signal (same split-slice
  precedent as P4-020: ATA notices scored in dims_p4_ata, bureau
  scores NULL in dims_p4_creditinfo).
* P4-008 stays NULL even though the hinnakiri price lists are human-
  readable: the per-address join needs the tariff ZONE map (which
  feeder/price area serves this address), and that map is
  interactive-only. Parsing a PDF price table without the zone join
  cannot score an address — stated, not hidden.
* P4-051 names the privacy shape explicitly (hex/KOV only, never
  addresses): even a future open aggregate must stay a hex flag.
  The reason points at the KÜ remondifondi check because a dead
  stairwell shows up in uncollected funds first.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-009/P4-008/P4-036/P4-046/P4-051: documented no-map DSO-feed NULLs
# (OTA PR #131 precedent). Elektrilevi's outage history, tariff zones,
# connection map, backup-feed info and zero-consumption aggregates are
# interactive-app or account-gated with no public bulk feed; each scorer
# reports the gap with a concrete buyer-side check instead of a faked
# number.
# ---------------------------------------------------------------------------

def dim_power_reliability(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-009: NULL — feeder outage history is unpublished (no map)."""
    return None, ("Elektrikatkestuste ajalugu on Elektrilevi fiidri "
                  "hinnang (EI OLE avaandmeid): SAIDI-ajalugu fiidri "
                  "kohta avalikus voogus pole, rikkekaart näitab vaid "
                  "jooksvat kaarti — kontrolli aadressi jooksvaid "
                  "katkestusi rikkekaardilt ja interneti TTJA netikaardilt, "
                  "ära feigi ala skoori")


def dim_tariff_zone(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """P4-008: NULL — Elektrilevi tariff-zone join needs the map (no feed)."""
    return None, ("Elektrilevi võrgutasu tsoon on aadressi liitumise "
                  "hinnang (EI OLE masinloetavat tsooniandmestikku): "
                  "hinnakiri on inimloetav hinnatabel, aga tsooni "
                  "kaardiliidestus avalikus voogus puudub — võrdle "
                  "Konkurentsiameti piirhindu ja Utilitas/Adven "
                  "tariife ning küsi KÜ-lt tegelik kütte €/m² "
                  "majandusaasta aruandest, ära feigi")


def dim_roof_export(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """P4-036: NULL — roof export feasibility is a gated map (no feed)."""
    return None, ("Katuse tagasitoitmise võimalus on liitumiskaardi "
                  "hinnang (EI OLE avaandmeid): ekspordivõimekus elab "
                  "interaktiivsel/väravaga kaardil, avalikku voogu pole "
                  "— kontrolli Eleringi mikrotootja tingimusi ja hoone "
                  "katuse andmeid EHR-ist, ära feigi katusetulu skoori")


def dim_backup_feed(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """P4-046: NULL — backup-feed info is unpublished (no map)."""
    return None, ("Varutoite info on avaldamata võrguandmete hinnang "
                  "(EI OLE avaandmeid): Elektrilevi/Eleringi varutoite "
                  "infot aadressi kohta avalikus voogus pole — hinda "
                  "dubleerimist kohapeal (kamin/ahi + kaugküte, kaev + "
                  "linnavesi, teine väljasõidutee) ja küsi KÜ-lt, ära feigi")


def dim_zero_consumption(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-051: NULL — zero-consumption aggregates unpublished (hex-only)."""
    return None, ("Nulltarbimisega trepikodade koond on avaldamata "
                  "koondandmete hinnang (EI OLE avaandmeid, heks "
                  "tasandilgi): tühjade investorikorterite koond "
                  "hex/KOV tasandil (mitte kunagi aadressid) pole "
                  "avaldatud — küsi KÜ-lt kogumata remondifondi ja "
                  "kontrolli vakantsi REL2021 ruudustikust, ära feigi")


P4_ELEKTRILEVI_DIMS = (
    ("power_reliability", "P4-009", dim_power_reliability),
    ("tariff_zone", "P4-008", dim_tariff_zone),
    ("roof_export", "P4-036", dim_roof_export),
    ("backup_feed", "P4-046", dim_backup_feed),
    ("zero_consumption", "P4-051", dim_zero_consumption),
)


def score_p4_elektrilevi(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five P4 Elektrilevi dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_ELEKTRILEVI_DIMS). Every
    value is None by design — unpublished DSO feed, never a faked
    area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_ELEKTRILEVI_DIMS}
