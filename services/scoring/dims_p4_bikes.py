"""P4 bikes dims (issue #309 demo, single-param): bike counters + MPD leg.

Params (this module only — sibling P4-032 legs untouched, see the split):
* P4-032 Activity heat as usage proxy, Tallinna rattaloendurid + city
  mobility MPD aggregates leg (demo, batch 3 — parameters4.md P4-032
  sources (1)+(2): aggregated evening foot/bike counters, "counts only,
  no individuals", e.g. city mobility project MPD aggregates where
  open; Tallinna rattaloendurid). Single-param demo: the #309 body
  states the remaining 0 param(s) need no follow-up coverage issue
  for this source.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#309 acceptance): Tallinn publishes NO open machine-readable bulk feed
for bike-counter counts or MPD aggregates. Polite evidence, ~10 tiny
requests total (custom UA `home-finder P4-032 bikes openness-check
(issue #309, one-off, no scrape)`, >= 3 s pacing between same-host
hits, headers + visible-text keyword scope read only, no scraping, no
auth, no form driving, no TLS bypass), raw bodies cached at
/tmp/hf-p4-bikes/ (TTL: one-off check, kept for the PR record, never
committed):
* Web search (no target load): Bicification (EIT Urban Mobility pilot:
  ~1 500 users, Tallinn/Istanbul/Braga, 4 months) built a municipality
  dashboard + heatmaps for the city, plus a "more limited, public"
  Open Data Platform per its guidebook — the project site itself is
  now unreachable (SSL certificate expired, curl (60), no bypass
  attempted) and no live pollable Tallinn aggregate endpoint surfaced.
* avaandmed.tallinn.ee/ -> HTTP 200, universal table-param API landing
  ("Use this API to make GET requests to /data/ ... datasets are
  documented at the Estonian Open Data Portal").
* avaandmed.tallinn.ee/openapi.json -> HTTP 200, confirms the
  table-param shape (no table catalogue endpoint).
* avaandmed.tallinn.ee/data/?table=rattaloendurid&per_page=1 ->
  HTTP 500 `{"detail":"404: Table not found"}` (a name guess, recorded
  as tried — proves only that no counter table lives under that name).
* andmed.eesti.ee/dataset?q=rattaloendur -> HTTP 200, ~75 KB JS
  "Teabevärav" shell with 10 visible characters and zero hits for
  rattaloendur/ratta/jalgratta/loendur/Bicification/MPD/mobility —
  no trivially pollable national-portal bike dataset (same shell as
  the #264/#277/#284 checks).
* tallinn.ee/et/search -> HTTP 301 to /et/otsing; followed
  /et/otsing?query=rattaloendur -> HTTP 200, ~129 KB, ~7.5k visible
  chars: results are AJAX-loaded, server HTML carries only nav plus
  the query echo — no counter dataset/table/CSV/API link.
* tallinn.ee/et/liikuvus/jalgratas -> HTTP 404.
* tallinn.ee/et/liikuvus/mikromobiilsus -> HTTP 200, ~63 KB: bike
  PARKING page (Bikeep rattaparklad) — 0 hits for loendur/andmestik/
  avaandmed/CSV, so no counter feed linked from the cycling pages.
So the live path below is honest plumbing with NO live data:
fetch_bikes_snapshot performs NO request while BIKES_BULK_URL is None,
the scorer then returns None with an Estonian EI OLE reason, and the
scored shape is proven on fixtures only. Reopening checklist lives in
docs/p4_bikes.md.

HONESTY (AGENTS.md section 7.2): the scored dim says "hinnang"
(estimate) and prints its components (hex id, evening count); every
NULL reason says "EI OLE" and names the missing input plus the
buyer-side check (kohapealne õhtune vaatlus). The usage-not-safety
label is explicit: PPA/Paasteamet is NOT a source, and an evening
count is a lived-in-street proxy, never a safety verdict. Transport
errors are never cached as data (fetch_bikes_snapshot stores a body
only on HTTP 200 with JSON content, else returns None). A measured
zero from the snapshot (0 evening counts in a covered hex while the
snapshot holds Tallinn counts elsewhere) scores — a real quiet
signal — while a missing join (no snapshot, hex not covered, no
hex_id) stays NULL: absence of data is unknown, never quiet. Hex
joins are exact-ID matches over opaque official hex ids, never
gradients, never interpolation, never nearest-neighbour smoothing.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_bikes_snapshot(cache_dir): polite pull, max 1 download / 24 h
  per cache dir (BIKES_TTL_S; parameters4.md P4-032 states no cadence
  — counters stream continuously, so daily per AGENTS.md section 5
  polite-cron guidance). Cache hit within TTL performs NO request.
  While no open bulk endpoint exists (BIKES_BULK_URL is None) it
  performs no request at all and returns the fresh-cache path or None.
  Single GET with an identifying UA once a bulk URL is known, no
  retries (HTTP 429 is a stop signal, 7.4).
* parse_bikes_snapshot / hex_usage_index: pure offline readers over
  the cached JSON snapshot (schema documented below). Network lives
  ONLY in fetch_bikes_snapshot; the scorer and tests never touch it.
* One snapshot, two keys: "hexes" (covered-hex roster, proves a zero
  is measured) + "counts" (the single P4-032 counters+MPD leg;
  single-param demo — no coverage tables; issue #309 states no
  follow-up coverage issue for this source).

Snapshot schema (what a future adapter would store; fixtures match it):
  {"hexes": ["H9-...", ...covered hex ids...],
   "counts": [{"counter_id": str, "hex_id": str, "period": "YYYY-MM",
               "evening_count": int >= 0, "kind": "counter"|"mpd"}]}
Rows are evening-window aggregates as published (the window is the
feed's, e.g. 17-22; the module never filters time — freshness is the
TTL/re-pull problem, not a scorer filter). Malformed rows are
skipped, never faked; a missing/unparseable file parses to None
(unknown), never to an empty snapshot. Covered hexes with no count
rows seed to 0 (measured quiet); hexes with neither roster cover nor
Tallinn rows stay NULL (uncovered is unknown, never quiet — while a
counted Tallinn row is itself measurement and self-covers).

Style mirrors services/scoring/dims_p4_rentcompl.py (#294, the
single-param sibling): pure scorer (listing, snapshot) ->
(Optional[int 0..100], Estonian reason), local helpers (no livability
import — importing it here would turn the future central hook into a
cycle, same precedent as PRs #100/#106/#115). The join is an exact
hex-ID match (rel2021 precedent), not a buffer: counts aggregate per
hex, and a neighbouring hex's count never leaks into the listing's
hex (pinned by test).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Hex-exact join (no buffer): the scored shape is per-hex usage,
  parameters4.md P4-032 "hex usage hinnang". Listing joins on its own
  hex_id only; nearby-hex counts never leak (rel2021 no-gradient
  precedent). Listings without a hex_id stay NULL — the module never
  geocodes an address into a hex (that join is the central hook's).
* Counter + MPD rows SUM per hex (both are this source's two feeds,
  kind kept on the row for the future adapter, never filtered):
  evening usage heat is additive across sensors/cells in one hex.
  Overlap double-counting (a counter and an MPD cell seeing the same
  cyclists) is unresolvable without a live feed and MUST be revisited
  from real histograms on reopen — pinned as documented, not solved.
* Periods and the feed's evening window are informational, never
  filtered (same call as the rentcompl sibling: with no live table
  there is no latest period to pin; freshness is TTL).
* USAGE_BANDS are a first-cut judgment with no live calibration
  (0 -> 30, 1-9 -> 55, 10-49 -> 75, >= 50 -> 90 — high = lively,
  buyer-favourable on "lived-in evening street?"); they MUST be
  recalibrated from a real snapshot on reopen (docs/p4_bikes.md
  checklist). The 90 cap (never 100) marks the leg partial by
  construction: counters+MPD are one usage signal, not a lived-in
  guarantee.
* Sibling-leg split (no double-scoring): this module scores ONLY the
  counters+MPD leg with the _bikes-suffixed dim key. The Elron
  evening-ridership leg stays NULL in dims_p4_elron
  (dim_elron_evening_ridership), the TLT leg NULL in dims_p4_tlt
  (dim_tlt_evening_ridership), the OSM leisure-density proxy in
  dims_p4_osm (dim_activity), the lit-street usage leg in
  dims_p4_veebi (dim_lit_street_usage). Each names the others EI OLE
  where the param needs them.

Integration (deliberately NOT done here): wiring the snapshot into a
listing pipeline plus rebalancing livability.WEIGHTS must be one joint
change across all batches — existing tests pin set(WEIGHTS) exactly,
so per-batch WEIGHTS edits would break every sibling. No shared files
touched: 3 new files only.
"""

import json
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Published Tallinna bike-counter / MPD-aggregate bulk: NONE found
#: 2026-09-13 (dated negative, see module docstring). Stays None until
#: the reopening checklist in docs/p4_bikes.md names a verified bulk
#: URL; while None, fetch performs no requests.
BIKES_BULK_URL: Optional[str] = None

#: Max one download per 24 h per cache dir (parameters4.md P4-032 states
#: no cadence — counters stream continuously, so daily per AGENTS.md
#: section 5 polite-cron guidance). Stated TTL.
BIKES_TTL_S = 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "bikes-snapshot.json"

#: Identifying user agent for the polite pull (no scrape, single GET).
BIKES_UA = "home-finder P4-032 bikes openness-check (max 1 req/24h, no scrape)"

#: Row kinds accepted by the counters+MPD leg (informational only —
#: both legs sum, never filtered; unknown kinds still count when the
#: row is otherwise well-formed).
COUNT_KINDS = frozenset({"counter", "mpd"})


def fetch_bikes_snapshot(cache_dir: str,
                         ttl_s: int = BIKES_TTL_S,
                         bulk_url: Optional[str] = BIKES_BULK_URL,
                         ) -> Optional[str]:
    """Polite usage-snapshot pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise,
    with no known bulk endpoint (bulk_url None) it returns None WITHOUT
    any request — the dated negative stays an explicit code path, not a
    hidden assumption. With a bulk URL: one GET with BIKES_UA and a
    30 s timeout; the body is stored only on HTTP 200 with JSON content,
    else None is returned and nothing is cached (transport errors are
    never data). No retries — HTTP 429/errors are a stop signal. The
    scorer never calls this; tests cover the cache-hit and no-endpoint
    paths with a stubbed opener, never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, CACHE_FILENAME)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    if bulk_url is None:
        return None
    try:
        req = urllib.request.Request(bulk_url, headers={"User-Agent": BIKES_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            ctype = resp.headers.get("Content-Type", "")
            if status != 200 or "json" not in ctype:
                return None
            body = resp.read()
        try:
            json.loads(body)
        except ValueError:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached snapshot (pure; fixtures match schema).
# ---------------------------------------------------------------------------

def parse_bikes_snapshot(path: str) -> Optional[dict]:
    """Read a cached usage snapshot file. Offline, stdlib.

    Returns {"hexes": [...], "counts": [...]} with malformed rows kept
    for the index builder to skip (never faked), or None when the file
    is missing/unparseable (unknown, never an empty snapshot — the
    scorer must not read "no file" as "no usage").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    hexes = raw.get("hexes") if isinstance(raw.get("hexes"), list) else []
    counts = (raw.get("counts")
              if isinstance(raw.get("counts"), list) else [])
    return {
        "hexes": [h for h in hexes if isinstance(h, str) and h.strip()],
        "counts": [r for r in counts if isinstance(r, dict)],
    }


def _evening_count(row: dict) -> Optional[int]:
    """Evening count of a row, or None when malformed (never faked)."""
    n = row.get("evening_count")
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        return None
    return n


def hex_usage_index(snapshot: Optional[dict]) -> Optional[Dict[str, int]]:
    """Parsed snapshot (or None) -> per-hex summed evening counts. Pure.

    Covered hexes seed to 0 (measured quiet); each well-formed count
    row adds its evening_count to its hex — a counted row is itself
    measurement, so rows self-cover hexes outside the roster (the
    roster's job is only to prove a zero is measured). Returns None
    when there is no snapshot to index (unknown); an empty dict means
    a parsed snapshot with no coverage at all. Hex-less rows and
    malformed counts stay out.
    """
    if not isinstance(snapshot, dict):
        return None
    totals: Dict[str, int] = {}
    hexes = snapshot.get("hexes")
    if isinstance(hexes, list):
        for h in hexes:
            if isinstance(h, str) and h.strip() and h not in totals:
                totals[h] = 0
    counts = snapshot.get("counts")
    if not isinstance(counts, list):
        return totals
    for row in counts:
        if not isinstance(row, dict):
            continue
        hx = row.get("hex_id")
        if not isinstance(hx, str) or not hx.strip():
            continue
        n = _evening_count(row)
        if n is None:
            continue
        totals[hx] = totals.get(hx, 0) + n
    return totals


# ---------------------------------------------------------------------------
# P4-032: bike-counter + MPD evening usage per hex (demo).
# ---------------------------------------------------------------------------

#: Summed evening count in the listing's hex -> usage score (high =
#: lively). First-cut bands, MUST be recalibrated from a real snapshot
#: on reopen. Capped at 90: counters+MPD are one usage signal, not a
#: lived-in guarantee.
USAGE_BANDS = [(0, 30), (9, 55), (49, 75), (float("inf"), 90)]


def _band(value: int, bands: List[Tuple[float, int]]) -> int:
    """First score whose threshold covers the value."""
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def dim_usage_bikes_hex(listing: Optional[dict],
                        snapshot: Optional[dict]) -> Score:
    """P4-032: hex usage hinnang from evening bike/MPD counts.

    Exact hex-ID join: the listing's own hex_id only — neighbouring
    hexes never leak in. A covered hex with 0 counts scores 30
    (measured quiet); a hex with neither roster cover nor count rows,
    a missing hex_id, or no snapshot stays NULL with an Estonian EI OLE
    reason (a counted row self-covers — it is measurement). Usage is
    usage-not-safety (PPA/Paasteamet pole allikas); Elron/TLT
    ridership, OSM leisure-density and lit-street legs are sibling
    jobs and are named EI OLE, never faked.
    """
    if not isinstance(listing, dict):
        listing = {}
    hex_id = listing.get("hex_id")
    if not isinstance(hex_id, str) or not hex_id.strip():
        return None, ("Kasutusaktiivsuse info puudub (EI OLE heksi-tunnust: "
                      "kuulutusel pole heksi-id, millega Tallinna "
                      "rattaloendurite ja MPD-agregaatide hetktõmmist siduda "
                      "— hinda õhtust elavust kohapealsel vaatlusel, "
                      "ära feigi")
    totals = hex_usage_index(snapshot)
    if totals is None:
        return None, ("Kasutusaktiivsuse info puudub (EI OLE Tallinna "
                      "rattaloendurite ja MPD-agregaatide hetktõmmist: "
                      "avaldatud andmestikku pole, kasutus-mitte-turvalisus "
                      "— PPA/Päästeamet pole allikas — hinda õhtust "
                      "elavust kohapealsel vaatlusel, ära feigi)")
    if hex_id not in totals:
        return None, ("Kasutusaktiivsuse info heksile '%s' puudub (EI OLE "
                      "kaetust: heks pole loenduste hetktõmmise katvuses — "
                      "katmata heks ei ole vaikne otsus, hinda õhtust "
                      "elavust kohapealsel vaatlusel, ära feigi)" % hex_id)
    n = totals[hex_id]
    s = _band(n, USAGE_BANDS)
    if n == 0:
        return s, ("Õhtuse kasutusaktiivsuse hinnang: heksis '%s' 0 "
                   "õhtust loendust (mõõdetud vaikne, hetktõmmises "
                   "Tallinna loendusi mujal, kasutus-mitte-turvalisus "
                   "— PPA/Päästeamet pole allikas) "
                   "→ skoor %d (Elroni/TLT õhtuse täituvuse + "
                   "OSM-õhtutiheduse + valgustatud-teede jalga EI OLE)"
                   % (hex_id, s))
    word = "üksik õhtune loendus" if n == 1 else "%d õhtust loendust" % n
    return s, ("Õhtuse kasutusaktiivsuse hinnang: heksis '%s' %s "
               "(kasutus-mitte-turvalisus — PPA/Päästeamet pole "
               "allikas) → skoor %d (Elroni/TLT "
               "õhtuse täituvuse + OSM-õhtutiheduse + valgustatud-teede "
               "jalga EI OLE)" % (hex_id, word, s))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_BIKES_DIMS = (
    ("usage_bikes_hex", "P4-032", dim_usage_bikes_hex),
)


def score_p4_bikes(listing: Optional[dict],
                   snapshot: Optional[dict]
                   ) -> Dict[str, Optional[int]]:
    """All P4 bikes dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_BIKES_DIMS)."""
    return {key: fn(listing, snapshot)[0] for key, _, fn in P4_BIKES_DIMS}
