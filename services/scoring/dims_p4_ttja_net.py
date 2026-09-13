"""P4 TTJA netikaart per-address dim (issue #266 demo, single-param).

Params (this module only — the TTJA SLICE of the param; sibling
slices are owned elsewhere and untouched):
* P4-009 Power/internet reliability at address: the TTJA "sideamet
  broadband address check (netikaart, Tallinn addresses)" slice
  (source (3), batch 1, demo in #266). Disjoint from
  dims_p4_elektrilevi.dim_power_reliability, which owns the
  Elektrilevi feeder-SAIDI slice (NULL: unpublished DSO feed), from
  dims_p4_elering.dim_system_adequacy, which owns the Elering
  national-series slice (NULL: national != address), and from the
  Telia/Elisa/Tele2, Ookla and OpenCellID broadband slices (their
  own demos, not this source).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #266): TTJA publishes no pollable per-address broadband feed.
Polite evidence, ~8 tiny requests total (single GETs with a
labelled one-off user-agent, headers + visible-text keyword scope
read only, no scraping, no auth), raw bodies cached at
/tmp/hf-ttja/ (TTL: one-off check, kept for the PR record, never
committed):
* https://ttja.ee/ -> HTTP 200, 177990 bytes, title "Eraklient |
  Tarbijakaitse ja Tehnilise Järelevalve Amet" — agency portal
  reachable; visible-text sweep: netikaart 1x (nav link only),
  while avaandmed / open data / arendaja / developer / X-tee /
  X-Road / andmestik / masinloetav all score 0 — no open-data
  page, no developer portal, no X-tee service advertised.
* https://ttja.ee/eraklient/side-ja-meediateenused/sideteenused-numeratsioon/netikaart
  ("Sideteenuste kaart") -> HTTP 200, 157815 bytes — info page
  that points the live map at the Maa-amet X-GIS app below.
* https://xgis.maaamet.ee/xgis2/page/app/netikaart -> HTTP 200,
  1243 bytes, title "X-GIS 2.0 [netikaart]" — a pure Dogis JS app
  shell (mapFrame + Dogis.Map with app "netikaart"), no
  server-rendered data and no WMS/WFS/API advertised on the
  shell. The broadband coverage lives inside this interactive
  map app, never in a pollable per-address join.
* https://ttja.ee/ariklient/side-ja-meediateenused/sideteenused/kiire-internet
  ("Lairiba") -> HTTP 200, 175500 bytes — "Netikaart" appears
  only as a nav item; the only "api" hits are a chatbot config
  URL and the substring inside "kapitalimahukad" — no machine
  data feed.
* Guessed legacy hosts https://netikaart.ttja.ee/ and
  https://saadavus.ttja.ee/ -> DNS failure (curl exit 6, could
  not resolve) — retired, nothing to poll there.
* National portal https://andmed.eesti.ee/dataset?q=netikaart ->
  HTTP 200 JS "Teabevärav" shell with no server-rendered
  netikaart/TTJA results — no trivially pollable dataset.
Driving the X-GIS app internals for per-address coverage would
mean scraping map-app endpoints — exactly the scraping this repo
refuses (AGENTS.md section 5). So the dim returns None for EVERY
input including missing origin: an address band painted from a
one-off hand-check would be fake precision (OTA PR #131
precedent). The reason says "hinnang" (estimate) and "EI OLE"
and points at the concrete buyer-side check (manual TTJA
sideteenuste-kaart lookup + operator levikaardid + Ookla) —
never a faked area score.

Style mirrors services/scoring/dims_p4_elektrilevi.py (#264, the
closest sibling: same param family, same NULL-with-markers shape)
and dims_group20a.py (#212): the scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois;
this module adds no network calls, no Overpass fragment, and no
tag mapping: there is no honest snapshot tag to query for an
operator-reported per-address coverage lookup, so there is
nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param module with no ingestion function: unlike the
  Elering sibling (#265, machine-open national series to parse),
  there is no open TTJA layer to fetch, parse, or cache — the
  only artefact of the demo is this dated-negative verdict plus
  its doc note. Fetching nothing is the polite choice, stated
  not hidden.
* P4-009 stays NULL even though the buyer CAN check an address
  by hand on the X-GIS map: a manual interactive lookup is not a
  pollable join, and hand-copying one address into a scorer
  would bless a single observation as area data. The reason
  tells the buyer exactly where to click instead.
* No scored "coarse raster hinnang" off neighbouring addresses:
  parameters4.md allows one, but a raster needs >= 2 cells with
  real variation from an open layer — hand-sampled opaque tiles
  would be relabelling, not a raster (same rejected-steelman
  precedent as Elering #265).

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-009 (TTJA slice): documented no-feed broadband-address NULL
# (OTA PR #131 precedent). The per-address broadband check lives in
# the interactive X-GIS netikaart app with no public per-address
# feed; the scorer reports the gap with the concrete buyer-side
# check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_broadband_address(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-009: NULL — TTJA broadband address check is map-only (no feed)."""
    return None, ("Internetiühenduse kiirus aadressil on TTJA netikaardi "
                  "hinnang (EI OLE masinloetavat aadressivoogu): katvus "
                  "elab interaktiivses X-GIS kaardirakenduses, avalik "
                  "päringuliides puudub — kontrolli aadress käsitsi TTJA "
                  "sideteenuste kaardilt ja operaatori levikaardilt "
                  "(Telia/Elisa/Tele2) ning ära feigi ala skoori")


P4_TTJA_NET_DIMS = (
    ("broadband_address", "P4-009", dim_broadband_address),
)


def score_p4_ttja_net(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 TTJA netikaart dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_TTJA_NET_DIMS). The
    value is None by design — interactive map only, never a faked
    per-address score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_TTJA_NET_DIMS}
