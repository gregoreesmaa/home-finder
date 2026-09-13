"""P4 rentcompl dims (issue #294 demo, single-param): short-rental complaints leg.

Params (this module only — sibling P4-003 legs untouched, see the split):
* P4-003 rent reality + Airbnb density, Tallinna Linnavalitsus
  lühiajalise üüri kaebuste leg (demo, batch 1 — parameters4.md P4-003
  source (5): complaints "where published"). Single-param demo: the
  remaining P4-003 sources use no follow-up coverage issue (per the
  #294 body, remaining 0 params).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#294 acceptance): Tallinna lühiajalise üüri kaebused are NOT published
as an open dataset. Polite evidence, ~12 tiny requests total (custom
UA `home-finder P4-003 rentcompl openness-check (issue #294 ...)`,
>= 3 s pacing between same-host hits, headers + search-page weight
only, no scrape, no auth, no form driving), raw bodies cached at
/tmp/hf-p4-rentcompl/ (TTL: one-off check, kept for the PR record,
never committed):
* Web search (no target load): no published complaints dataset. The
  MKM study "Lühiajalise üüri turg Eestis" (mkm.ee, 2026) uses
  Airbnb/VRBO listing open data + Inside Airbnb/Airbtics-style
  aggregators — listing density, not city complaints. EU context is
  regulation prose (2024 short-term-rental data-sharing law, 2026-09
  restriction-tool proposal), not a Tallinn feed.
* avaandmed.eesti.ee/api/3/action/package_search (x3) -> HTTP 301
  (162 B nginx): the old CKAN host now redirects to andmed.eesti.ee.
* andmed.eesti.ee/api/3/action/package_search (x3, followed) ->
  HTTP 404 JSON `Cannot GET /3/action/...`; /api/3/action/status_show
  -> HTTP 404. The new "Teabevärav" portal exposes no CKAN API —
  probing its internals would be app scraping, so the probe stops.
* GET andmed.eesti.ee/ -> HTTP 200 (Teabevärav SPA shell, transport
  note only, not data).
* GET tallinn.ee/et/search?q=lühiajaline üür kaebused -> HTTP 301 to
  /et/otsing; followed -> HTTP 200 city search page. Result scope:
  only generic hits (Botaanikaaia room hire "lühiajaline üürile
  andmine", the general "Kaebused, ettepanekud, tänuavaldused"
  contact page, kindergarten room hire) — no published complaints
  table, no CSV/XLSX/andmestik feed.
So the live path below is honest plumbing with NO live data:
fetch_rentcompl_snapshot performs NO request while RENTCOMPL_BULK_URL
is None, the scorer then returns None with an Estonian EI OLE reason,
and the scored shape is proven on fixtures only. Reopening checklist
lives in docs/p4_rentcompl.md.

HONESTY (AGENTS.md section 7.2): the scored dim says "hinnang"
(estimate) and prints its components (hex id, complaint count);
every NULL reason says "EI OLE" and names the missing input plus the
buyer-side check. Transport errors are never cached as data
(fetch_rentcompl_snapshot stores a body only on HTTP 200 with JSON
content, else returns None). A measured zero from the snapshot (0
Tallinn complaints in a covered hex while the snapshot holds Tallinn
complaints elsewhere) scores — a real calm signal — while a missing
join (no snapshot, hex not covered, no hex_id) stays NULL: absence
of data is unknown, never calm. Hex joins are exact-ID matches over
opaque official hex ids, never gradients, never interpolation, never
nearest-neighbour smoothing.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_rentcompl_snapshot(cache_dir): polite pull, max 1 download /
  30 d per cache dir (RENTCOMPL_TTL_S; parameters4.md P4-003 cadence:
  monthly/quarterly — complaints accumulate monthly, so monthly).
  Cache hit within TTL performs NO request. While no open bulk
  endpoint exists (RENTCOMPL_BULK_URL is None) it performs no request
  at all and returns the fresh-cache path or None. Single GET with an
  identifying UA once a bulk URL is known, no retries (HTTP 429 is a
  stop signal, 7.4).
* parse_rentcompl_snapshot / hex_nuisance_index: pure offline readers
  over the cached JSON snapshot (schema documented below). Network
  lives ONLY in fetch_rentcompl_snapshot; the scorer and tests never
  touch it.
* One snapshot, two keys: "hexes" (covered-hex roster, proves a zero
  is measured) + "complaints" (the single P4-003 complaints leg;
  single-param demo — no coverage tables; issue #294 states no
  follow-up coverage issue for this source).

Snapshot schema (what a future adapter would store; fixtures match it):
  {"hexes": ["H9-...", ...covered hex ids...],
   "complaints": [{"complaint_id": str, "hex_id": str, "kov": str,
                   "period": "YYYY-MM", "kind": str}]}
Malformed rows are skipped, never faked; non-Tallinn rows are skipped
(Tallinn filter — this demo joins Tallinn hexes only,
parameters4.md P4-003 "Tallinn"); a missing/unparseable file parses
to None (unknown), never to an empty snapshot. Covered hexes with no
complaint rows seed to 0 (measured calm); hexes with neither roster
cover nor Tallinn rows stay NULL (uncovered is unknown, never calm —
while a counted Tallinn row is itself measurement and self-covers).

Style mirrors services/scoring/dims_p4_plank.py (#251, the single-param
sibling): pure scorer (listing, snapshot) -> (Optional[int 0..100],
Estonian reason), local helpers (no livability import — importing it
here would turn the future central hook into a cycle, same precedent
as PRs #100/#106/#115). Unlike PLANK the join is an exact hex-ID
match (rel2021 precedent), not a buffer: complaints aggregate per
hex, and a neighbouring hex's count never leaks into the listing's
hex (pinned by test).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Hex-exact join (no buffer): the scored shape is per-hex nuisance,
  parameters4.md P4-003 "hex nuisance hinnang". Listing joins on its
  own hex_id only; nearby-hex counts never leak (rel2021 no-gradient
  precedent). Listings without a hex_id stay NULL — the module never
  geocodes an address into a hex (that join is the central hook's).
* ALL complaint kinds count (müra/prügi/muu): nuisance is nuisance
  for the "nuisance?" Buy Q; kind is kept on the row for the future
  adapter, not filtered here — pinned by test.
* Periods are informational, never filtered: every well-formed row
  counts regardless of "period"; freshness is the TTL/re-pull
  problem, not a scorer filter (same call as the stat sibling's
  latest-period discipline, inverted honestly: with no live table
  there is no latest period to pin).
* Tallinn filter matches kov case-insensitively against
  {"tallinn", "tallinna linn"} (municipal naming varies across
  register exports). Rows with a missing/unparseable kov are skipped:
  an unknown municipality is never assumed to be Tallinn.
* NUISANCE_BANDS are a first-cut judgment with no live calibration
  (0 -> 85, 1 -> 65, 2-4 -> 45, >= 5 -> 25 — high = calm,
  buyer-favourable on "nuisance?"); they MUST be recalibrated from a
  real snapshot on reopen (docs/p4_rentcompl.md checklist). The 85
  cap (never 100) marks the leg partial by construction: complaints
  are one nuisance signal, not a calm guarantee.
* Sibling-leg split (no double-scoring): this module scores ONLY the
  complaints leg with the _rentcompl-suffixed dim key. Yield context
  stays in dims_p4_stat (rent_reality_stat, Stat rent-table leg) and
  dims_p4_own_store (rent_reality, NULL), the rental-share/vacancy
  grid leg in dims_p4_rel2021 (rent_reality_rel), KV-medians in the
  adapter store, Airbnb density in the Inside-Airbnb-style check.
  Each names the others EI OLE where the param needs them.

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

#: Published Tallinna short-rental complaints bulk: NONE found 2026-09-13
#: (dated negative, see module docstring). Stays None until the reopening
#: checklist in docs/p4_rentcompl.md names a verified bulk URL; while
#: None, fetch performs no requests.
RENTCOMPL_BULK_URL: Optional[str] = None

#: Max one download per 30 d per cache dir (parameters4.md P4-003 TTL:
#: monthly/quarterly — complaints accumulate monthly, so monthly).
#: Stated TTL.
RENTCOMPL_TTL_S = 30 * 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "rentcompl-snapshot.json"

#: Identifying user agent for the polite pull (no scrape, single GET).
RENTCOMPL_UA = "home-finder P4-003 rentcompl openness-check (max 1 req/30d, no scrape)"

#: Tallinn kov spellings accepted by the Tallinn filter (lowercased).
TALLINN_KOVS = frozenset({"tallinn", "tallinna linn"})


def fetch_rentcompl_snapshot(cache_dir: str,
                             ttl_s: int = RENTCOMPL_TTL_S,
                             bulk_url: Optional[str] = RENTCOMPL_BULK_URL,
                             ) -> Optional[str]:
    """Polite complaints-snapshot pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise,
    with no known bulk endpoint (bulk_url None) it returns None WITHOUT
    any request — the dated negative stays an explicit code path, not a
    hidden assumption. With a bulk URL: one GET with RENTCOMPL_UA and a
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
        req = urllib.request.Request(bulk_url, headers={"User-Agent": RENTCOMPL_UA})
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

def parse_rentcompl_snapshot(path: str) -> Optional[dict]:
    """Read a cached complaints snapshot file. Offline, stdlib.

    Returns {"hexes": [...], "complaints": [...]} with malformed rows
    kept for the index builder to skip (never faked), or None when the
    file is missing/unparseable (unknown, never an empty snapshot —
    the scorer must not read "no file" as "no complaints").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    hexes = raw.get("hexes") if isinstance(raw.get("hexes"), list) else []
    complaints = (raw.get("complaints")
                  if isinstance(raw.get("complaints"), list) else [])
    return {
        "hexes": [h for h in hexes if isinstance(h, str) and h.strip()],
        "complaints": [r for r in complaints if isinstance(r, dict)],
    }


def _is_tallinn(row: dict) -> bool:
    """True when the row's kov is a recognised Tallinn spelling."""
    kov = row.get("kov")
    if not isinstance(kov, str):
        return False
    return kov.strip().lower() in TALLINN_KOVS


def hex_nuisance_index(snapshot: Optional[dict]) -> Optional[Dict[str, int]]:
    """Parsed snapshot (or None) -> per-hex Tallinn complaint counts. Pure.

    Covered hexes seed to 0 (measured calm); each well-formed Tallinn
    complaint row increments its hex — a counted complaint is itself
    measurement, so rows self-cover hexes outside the roster (the
    roster's job is only to prove a zero is measured). Returns None
    when there is no snapshot to index (unknown); an empty dict means
    a parsed snapshot with no Tallinn coverage at all. Non-Tallinn
    rows, hex-less rows and empty hex ids stay out.
    """
    if not isinstance(snapshot, dict):
        return None
    counts: Dict[str, int] = {}
    hexes = snapshot.get("hexes")
    if isinstance(hexes, list):
        for h in hexes:
            if isinstance(h, str) and h.strip() and h not in counts:
                counts[h] = 0
    complaints = snapshot.get("complaints")
    if not isinstance(complaints, list):
        return counts
    for row in complaints:
        if not isinstance(row, dict) or not _is_tallinn(row):
            continue
        hx = row.get("hex_id")
        if not isinstance(hx, str) or not hx.strip():
            continue
        counts[hx] = counts.get(hx, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# P4-003: short-rental complaint nuisance per hex (demo).
# ---------------------------------------------------------------------------

#: Complaint count in the listing's hex -> nuisance score (high = calm).
#: First-cut bands, MUST be recalibrated from a real snapshot on reopen.
#: Capped at 85: complaints are one nuisance signal, not a calm guarantee.
NUISANCE_BANDS = [(0, 85), (1, 65), (4, 45), (float("inf"), 25)]


def _band(value: int, bands: List[Tuple[float, int]]) -> int:
    """First score whose threshold covers the value."""
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def dim_nuisance_rentcompl_hex(listing: Optional[dict],
                               snapshot: Optional[dict]) -> Score:
    """P4-003: hex nuisance hinnang from Tallinn complaint counts.

    Exact hex-ID join: the listing's own hex_id only — neighbouring
    hexes never leak in. A covered hex with 0 complaints scores 85
    (measured calm); a hex with neither roster cover nor Tallinn rows,
    a missing hex_id, or no snapshot stays NULL with an Estonian EI OLE
    reason (a counted Tallinn row self-covers — it is measurement).
    Yield, Airbnb density,
    KV-medians and the REL2021 rental-share legs are sibling jobs and
    are named EI OLE, never faked.
    """
    if not isinstance(listing, dict):
        listing = {}
    hex_id = listing.get("hex_id")
    if not isinstance(hex_id, str) or not hex_id.strip():
        return None, ("Kaebuste info puudub (EI OLE heksi-tunnust: "
                      "kuulutusel pole heksi-id, millega Tallinna "
                      "lühiajalise üüri kaebuste hetktõmmist siduda — "
                      "küsi KÜ-lt/maaklerilt lühiajalise üüri kaebuste "
                      "kohta, ära feigi")
    counts = hex_nuisance_index(snapshot)
    if counts is None:
        return None, ("Kaebuste info puudub (EI OLE Tallinna lühiajalise "
                      "üüri kaebuste hetktõmmist: avaldatud andmestikku "
                      "pole — küsi KÜ-lt/maaklerilt lühiajalise üüri "
                      "kaebuste kohta, kontrolli kohapeal, ära feigi)")
    if hex_id not in counts:
        return None, ("Kaebuste info heksile '%s' puudub (EI OLE kaetust: "
                      "heks pole kaebuste hetktõmmise katvuses — katmata "
                      "heks ei ole rahulik otsus, küsi KÜ-lt/maaklerilt, "
                      "ära feigi)" % hex_id)
    n = counts[hex_id]
    s = _band(n, NUISANCE_BANDS)
    if n == 0:
        return s, ("Lühiajalise üüri kaebuste hinnang: heksis '%s' 0 "
                   "Tallinna kaebust (mõõdetud rahulik, hetktõmmises "
                   "Tallinna kaebusi mujal) → skoor %d (KV-mediaanide + "
                   "Airbnb-tiheduse + REL2021 üüri-osakaalu jalga EI OLE)"
                   % (hex_id, s))
    word = "üksik kaebus" if n == 1 else "%d kaebust" % n
    return s, ("Lühiajalise üüri kaebuste hinnang: heksis '%s' %s "
               "→ skoor %d (KV-mediaanide + Airbnb-tiheduse + REL2021 "
               "üüri-osakaalu jalga EI OLE)" % (hex_id, word, s))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_RENTCOMPL_DIMS = (
    ("nuisance_rentcompl_hex", "P4-003", dim_nuisance_rentcompl_hex),
)


def score_p4_rentcompl(listing: Optional[dict],
                       snapshot: Optional[dict]
                       ) -> Dict[str, Optional[int]]:
    """All P4 rentcompl dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_RENTCOMPL_DIMS)."""
    return {key: fn(listing, snapshot)[0] for key, _, fn in P4_RENTCOMPL_DIMS}
