"""P4 e-Äriregister KÜ reports (new fields) demo + coverage dims (issues #257, #338).

Demo (#257): e-Äriregister KÜ majandusaasta aruanded ingestion (XBRL
bulk: laen, remondifond, kutte EUR/m2 - new fields vs #232) plus
P4-007 end-to-end in Tallinn. Coverage (#338): the remaining 13
params that consume the demoed ingestion, each wired to its KU-report
slice (no new plumbing - coverage adds field readers over the same
snapshot, said in docs/p4_arireg.md).

Params (this module only - overturn #232 owns the parameters3
e-Äriregister bulk for p361/p369 in dims_group04*.py, which this
module does NOT touch; no shared/group files are edited):
* P4-007 KÜ loan + remondifond + heating EUR/m2 (demo, 3 per-listing dims)
* P4-010 renovation-grant status, arireg leg: collected-fund echo (NULL)
* P4-020 enforcement, arireg leg: maksehäired/aruandevõlad (scored, capped)
* P4-021 developer track record, arireg leg: age/turnover (scored, capped)
* P4-026 fix-it responsiveness, arireg leg: hoolduskulu echo (NULL)
* P4-034 overheating, arireg leg: katuse/soojustuse echo (NULL)
* P4-039 civic capital, arireg leg: fondikogumise echo (NULL)
* P4-042 smell map, arireg leg: emitter-address join missing (NULL)
* P4-044 herd of picky people, arireg leg: employer-address join missing (NULL)
* P4-051 dead stairwell, arireg leg: arrears risk flag (scored, bad-side only)
* P4-052 turnover wave, arireg leg: fondidünaamika echo (NULL)
* P4-057 heat-pump hum, arireg leg: heating-capex echo (NULL)
* P4-060 stormwater/subsidy, arireg leg: sademevee-kulu echo (NULL)
* P4-062 rats/ice, arireg leg: prügi-/hoolduskulu echo (NULL)

HONESTY (AGENTS.md section 7.2): the Äriregister bulk is NOT in the
2026-09-12 snapshot, so every dim returns None when its joined KU
record (or the needed slice of it) is missing - never a guess.
Scored reasons always name the joined report row (registrikood +
arvestusaasta) and say "hinnang" with components; every NULL reason
says "EI OLE" and names the missing input. Transport errors are
never cached as data (fetch_arireg_snapshot stores a body only on
HTTP 200 with JSON content, else returns None). A measured zero
(laen 0, remondifond 0 kairitud reana) scores - a real
debt-free/empty-fund signal - while a missing join (no snapshot, no
row for the registrikood, field None) stays NULL: absence of data is
unknown, never good. Per-m2 normalisation needs area_m2; a record
without it stays NULL on the per-m2 dims (never divided by a guess).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #257 acceptance; polite evidence, 9 tiny doc/search reads total,
custom UA, no scrape - raw pages cached at /tmp/arireg-open/, TTL:
one-off check kept for the PR record, never committed):
* https://ariregister.rik.ee/ -> HTTP 303 -> /est (HTTP 200,
  "Juriidilise isiku otsing | e-Äriregister", 80 541 B): human-facing
  per-company search UI, no bulk link on the front page.
* https://www.rik.ee/et/e-ariregister/ariregistri-paringud (HTTP 200,
  37 760 B) documents the "Avaandmete teenus": an open-data download
  environment at avaandmed.ariregister.rik.ee with per-company
  endpoints including "majandusaasta aruannete loetelu päring" and
  "majandusaasta aruannete päring".
* API intro (HTTP 200, 26 968 B): "Avaandmete API ehk XML teenuste
  kasutamiseks on vajalik sõlmida RIKiga leping (v.a e-arvete
  vastuvõtjate ja autocomplete päringute kasutamiseks)" - a contract
  application via the e-ariregister portal (free-tier choice exists:
  "Ainult tasuta API teenuste kasutamiseks ... igakuist lepingutasu
  ei lisandu", review within five workdays). No anonymous bulk
  download verified.
* Report-query doc (HTTP 200, 44 503 B): query name
  arireg.majandusaastaAruanneteKirjed_v1 over the loetelu_v1 output,
  RIK-makett structure, TWO periods per report (A1 aruandeperiood +
  A2 võrdlusperiood) - the snapshot below keeps current + previous
  fund rows for the P4-052 dynamics echo.
Verdict: OPEN-but-gated (same class as the EHR #249 verdict):
contract-gated bulk, paid extracts stay NULL. ARIREG_BULK_URL stays
None until the reopening checklist in docs/p4_arireg.md names a
contracted endpoint; until then the fetcher performs no requests and
the scorers stay NULL with an Estonian EI OLE reason. Scored shapes
are proven on fixtures only (hermetic tests).

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_arireg_snapshot(cache_dir): polite pull, max 1 download /
  90 d per cache dir (ARIREG_TTL_S; parameters4.md P4-007 cadence:
  annual reports + quarterly refresh ride one quarterly ticket).
  Cache hit within TTL performs NO request. While no contracted bulk
  endpoint exists (ARIREG_BULK_URL is None) it performs no request at
  all and returns the fresh-cache path or None. Single GET with an
  identifying UA once an endpoint is contracted, no retries
  (HTTP 429 is a stop signal, 7.4).
* parse_arireg_snapshot / index_by_registry_code: pure offline
  readers over the cached JSON snapshot (schema documented below).
  Network lives ONLY in fetch_arireg_snapshot; scorers and tests
  never touch it.
* One snapshot, one table ("reports"): the company-card slice
  (founded_year, turnover, payment defaults - same e-Äriregister
  source family, used by P4-020/P4-021) rides the same snapshot as
  the XBRL rows. This is why demo + coverage pair in ONE PR - #338
  expects no new plumbing, said in docs/p4_arireg.md.

Snapshot schema (what a future adapter would store; fixtures match it):
  {"reports": [{"registry_code": str, "name": str|None,
                "tallinn": bool, "report_year": int|None,
                "area_m2": float|None,
                "loan_balance": float|None, "repair_fund_balance": float|None,
                "repair_fund_prev": float|None,
                "heating_cost_annual": float|None,
                "maintenance_cost_annual": float|None,
                "waste_cost_annual": float|None,
                "stormwater_cost_annual": float|None,
                "heating_capex_note": str|None, "roof_state": str|None,
                "payment_defaults": int|None, "report_debts": bool|None,
                "founded_year": int|None, "turnover_annual": float|None}]}
Malformed rows are skipped, never faked; a missing/unparseable file
parses to None (unknown), never to an empty snapshot. Money fields
are euros; per-m2 dims divide by area_m2 (annual euros per m2).

Style mirrors services/scoring/dims_p4_ehr.py (issues #249/#333):
pure (arireg, listing) -> (Optional[int 0..100], Estonian reason),
absolute bands, hermetic fixture tests. Network lives only in
fetch_arireg_snapshot (single polite GET, file cache, TTL); tests
never call it.

Helpers are local copies (not imported from livability, sibling
batches, dims_group04, dims_p4_ata, or dims_p4_taitur): a future
central hook may import this module alongside them, and importing
any of them here would turn that into a cycle (same precedent as
batch B3, PR #100, and group20a #212). In particular nothing is
shared with the #232 bulk client - the new-field ingestion stands
alone.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR because the coverage issue body states
  it "extends the demoed ingestion" with "no new plumbing expected":
  coverage adds field readers over the same reports table, not a
  second source (same precedent as the EHR #249+#333 and
  TPR #250+#334 PRs).
* P4-007 is three dims, not one composite: loan, repair fund, and
  heating answer three different buyer questions (debt load, fund
  adequacy, bill shock) and fail independently (a report can carry
  heating rows without a loan row). Averaging them would hide the
  binding constraint.
* P4-007 bands are first-cut judgments with no live calibration
  (loan 0->85/<=50->65/<=150->40/else 20; fund >=20->80/>=8->60/
  >=2->40/else 25; heating <=8->80/<=14->60/<=22->40/else 25);
  they MUST be recalibrated from a real snapshot on reopen
  (docs/p4_arireg.md checklist). Debt-free caps at 85, never 100:
  off-balance obligations (EIS garantii, haldusvõlad) are NOT
  joined.
* P4-010 stays NULL with a fund echo on purpose: the arireg slice
  (kogutud fond) is the BILL side of "fond vs 5-figure bill", and
  scoring the level again would double-score P4-007's fund dim.
  The grant/queue verdict needs the EIS register - the NULL reason
  echoes the collected fund figure so fixture tests prove the
  wiring without faking a score (EHR P4-030/031/050/052 precedent).
* P4-020 appears in four slices on purpose with disjoint legs:
  dims_p4_ata scores the teadaande-notice slice (cap 75),
  dims_p4_taitur the kohtutaitur slice, the #232 client the
  parameters3 probate scope, and this module ONLY the
  maksehäired/aruandevõlad slice (clean cap 70 - narrower evidence
  than a notice-window search, so a lower cap; active defaults 20,
  never 0: a record can be stale or mis-joined). Neither claims the
  full param; Creditinfo scores and kohtuotsused stay unjoined.
* P4-021 appears in three slices: dims_p4_ehr scores the
  builder-completion slice (cap 80), dims_p4_ata the
  developer-notice slice (cap 75), this module ONLY the
  age/turnover slice (cap 75 - TTJA kaebused NOT joined). A young
  firm scores 45 (thin history, not fraud): youth is weak-neutral,
  never strong-bad.
* P4-051 is bad-side-only by shape: arrears on the books flag a
  dead-stairwell risk (30, hex-lipp, never a building verdict),
  but a clean single-KÜ ledger does NOT clear the hex - so the
  clean side stays NULL instead of scoring high. Asymmetric by
  design, documented here.
* P4-042/P4-044 stay NULL naming the missing address-cluster join:
  emitter/creative-employer addresses are a different ariregister
  query than the KU-report rows, not fields of this snapshot -
  the NULL names the join so the gap is reviewable, not hidden.
* The Tallinn gate (arireg["tallinn"] is False -> NULL) keeps the
  demo scope honest: non-Tallinn joins are out of scope, not bad
  deals. A missing "tallinn" key defaults to relevant (older joins
  predate the flag; absence is not evidence either way).
* No staged Overpass fragment and no tag mapping: OSM has no honest
  tag for KÜ ledger rows, so there is nothing for the live path to
  fetch (same rationale as the group20a no-map batches).

Integration (deliberately NOT done here): feeding these dims with
the listing's joined KÜ record inside livability scoring and
rebalancing livability.WEIGHTS must be one joint change across all
parameter batches - existing tests pin set(WEIGHTS) exactly, so
per-batch WEIGHTS edits would break every sibling. No shared files
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

#: Contracted bulk endpoint: NONE while the RIK open-data API stays
#: contract-gated (verified 2026-09-13, dated negative, see module
#: docstring). Stays None until the reopening checklist in
#: docs/p4_arireg.md names a contracted endpoint; while None, fetch
#: performs no requests.
ARIREG_BULK_URL: Optional[str] = None

#: Annual-report query names observed on the RIK open-data doc page
#: (2026-09-13, offline doc read - no pull performed).
ARIREG_REPORT_LIST_QUERY = "majandusaastaAruanneteLoetelu_v1"
ARIREG_REPORT_QUERY = "arireg.majandusaastaAruanneteKirjed_v1"

#: Human search UI (verified 2026-09-13: per-company search, no bulk).
ARIREG_SEARCH_URL = "https://ariregister.rik.ee/est"

#: Max one download per 90 d per cache dir (parameters4.md P4-007:
#: annual reports + quarterly refresh ride one quarterly ticket).
#: Stated TTL.
ARIREG_TTL_S = 90 * 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "arireg-ku-snapshot.json"

#: Identifying user agent for the polite pull (no scrape, single GET).
ARIREG_UA = "home-finder arireg ingest (max 1 req/90d, no scrape)"


def fetch_arireg_snapshot(cache_dir: str,
                          ttl_s: int = ARIREG_TTL_S,
                          bulk_url: Optional[str] = ARIREG_BULK_URL,
                          ) -> Optional[str]:
    """Polite KU-report snapshot pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made.
    Otherwise, with no contracted bulk endpoint (bulk_url None) it
    returns None WITHOUT any request - the dated negative stays an
    explicit code path, not a hidden assumption. With an endpoint:
    one GET with ARIREG_UA and a 30 s timeout; the body is stored
    only on HTTP 200 with JSON content, else None is returned and
    nothing is cached (transport errors are never data). No retries
    - HTTP 429/errors are a stop signal. Scorers never call this;
    tests cover the cache-hit and no-endpoint paths with a stubbed
    opener, never the network.
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
        req = urllib.request.Request(bulk_url, headers={"User-Agent": ARIREG_UA})
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

#: Canonical record keys produced by parse_arireg_snapshot (all Optional
#: except the registry_code join key).
ARIREG_FIELDS = (
    "registry_code", "name", "tallinn", "report_year", "area_m2",
    "loan_balance", "repair_fund_balance", "repair_fund_prev",
    "heating_cost_annual", "maintenance_cost_annual",
    "waste_cost_annual", "stormwater_cost_annual",
    "heating_capex_note", "roof_state",
    "payment_defaults", "report_debts",
    "founded_year", "turnover_annual",
)

_MONEY_FIELDS = ("area_m2", "loan_balance", "repair_fund_balance",
                 "repair_fund_prev", "heating_cost_annual",
                 "maintenance_cost_annual", "waste_cost_annual",
                 "stormwater_cost_annual", "turnover_annual")

_INT_FIELDS = ("report_year", "payment_defaults", "founded_year")


def _to_money(raw) -> Optional[float]:
    """Euros: ints/floats/numeric strings only; bool/garbage -> None."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        v = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):  # NaN/inf are not money
        return None
    return v if v >= 0 else None


def _to_int(raw) -> Optional[int]:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        v = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def parse_arireg_snapshot(path: str) -> Optional[dict]:
    """Read a cached KU-report snapshot file. Offline, stdlib.

    Returns {"reports": [...]} with malformed rows skipped, or None
    when the file is missing/unparseable (unknown, never an empty
    snapshot - scorers must not read "no file" as "debt-free").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    reports = raw.get("reports")
    if not isinstance(reports, list):
        return None
    clean = []
    for row in reports:
        if not isinstance(row, dict):
            continue
        code = row.get("registry_code")
        code = str(code).strip() if code is not None else ""
        if not code:
            continue  # no join key - keeping it would fake join coverage
        rec: Dict[str, Optional[object]] = {"registry_code": code}
        for field in ARIREG_FIELDS:
            if field == "registry_code":
                continue
            raw_v = row.get(field)
            if field in _MONEY_FIELDS:
                rec[field] = _to_money(raw_v)
            elif field in _INT_FIELDS:
                rec[field] = _to_int(raw_v)
            elif field == "tallinn":
                rec[field] = None if raw_v is None else bool(raw_v)
            elif field == "report_debts":
                rec[field] = None if raw_v is None else bool(raw_v)
            else:
                s = None if raw_v is None else str(raw_v).strip()
                rec[field] = s if s else None
        clean.append(rec)
    return {"reports": clean}


def index_by_registry_code(
        records: List[Dict[str, Optional[object]]]
) -> Dict[str, Dict[str, Optional[object]]]:
    """Per-registry_code join index (first row wins on duplicates)."""
    index: Dict[str, Dict[str, Optional[object]]] = {}
    for rec in records:
        code = rec.get("registry_code")
        if code and code not in index:
            index[code] = rec
    return index


# ---------------------------------------------------------------------------
# Small input helpers (local copies - no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _rec(arireg: Optional[dict]) -> Optional[dict]:
    return arireg if isinstance(arireg, dict) else None


def _missing_ku() -> Score:
    return None, ("KÜ aruande kirje puudub — äriregistri andmeteta skoori "
                  "EI OLE (hinnangut ei anta): kontrolli registrikoodi järgi "
                  "ariregister.rik.ee-st")


def _out_of_scope() -> Score:
    return None, ("KÜ asub väljaspool Tallinna — demo ulatus EI OLE "
                  "hinnang (Tallinna filter, parameters4.md P4-007)")


def _tallinn_gate(rec: dict) -> Optional[Score]:
    """None when the record is in scope, else the out-of-scope NULL."""
    if rec.get("tallinn") is False:
        return _out_of_scope()
    return None


def _provenance(rec: dict) -> str:
    code = rec.get("registry_code") or "teadmata"
    year = rec.get("report_year")
    tail = "aruanne %s" % year if isinstance(year, int) else "aasta teadmata"
    return "KÜ %s, %s (e-Äriregister)" % (code, tail)


def _per_m2(amount: Optional[object], area: Optional[object]) -> Optional[float]:
    """Annual euros per m2; None when either side is missing/invalid."""
    if (not isinstance(amount, (int, float)) or isinstance(amount, bool)
            or not isinstance(area, (int, float)) or isinstance(area, bool)):
        return None
    if area <= 0:
        return None
    return float(amount) / float(area)


def _fmt_eur(v: float) -> str:
    return "%.2f EUR/m2" % v


# ---------------------------------------------------------------------------
# P4-007 (demo): KÜ loan + remondifond + heating EUR/m2 - per-listing dims.
# First-cut bands (MUST be recalibrated from a real snapshot on reopen).
# ---------------------------------------------------------------------------

#: Loan balance per m2 -> score (high = debt-free). Debt-free caps at
#: 85: off-balance obligations are NOT joined.
LOAN_BANDS = [(0.0, 85), (50.0, 65), (150.0, 40), (float("inf"), 20)]

#: Repair-fund balance per m2 -> score (high = well funded).
FUND_BANDS = [(2.0, 25), (8.0, 40), (20.0, 60), (float("inf"), 80)]

#: Annual heating cost per m2 -> score (high = cheap heat).
HEAT_BANDS = [(8.0, 80), (14.0, 60), (22.0, 40), (float("inf"), 25)]


def _band_asc(value: float, bands: List[Tuple[float, int]]) -> int:
    """First score whose threshold covers the value (ascending bands)."""
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def dim_ku_loan(arireg: Optional[dict],
                listing: Optional[dict] = None) -> Score:
    """P4-007: KÜ loan balance per m2 (high = debt-free, cap 85)."""
    rec = _rec(arireg)
    if rec is None:
        return _missing_ku()
    gate = _tallinn_gate(rec)
    if gate is not None:
        return gate
    per_m2 = _per_m2(rec.get("loan_balance"), rec.get("area_m2"))
    if per_m2 is None:
        return None, ("KÜ laenujääk teadmata (EI OLE hinnangut): %s — "
                      "laenu- või pinnarida aruandes puudu" % _provenance(rec))
    s = _band_asc(per_m2, LOAN_BANDS)
    return s, ("KÜ laenukoormus (hinnang): laenujääk %s — %s; "
               "bilansivälised kohustused liitmata, ülempiir 85"
               % (_fmt_eur(per_m2), _provenance(rec)))


def dim_repair_fund(arireg: Optional[dict],
                    listing: Optional[dict] = None) -> Score:
    """P4-007: remondifond balance per m2 (high = well funded)."""
    rec = _rec(arireg)
    if rec is None:
        return _missing_ku()
    gate = _tallinn_gate(rec)
    if gate is not None:
        return gate
    per_m2 = _per_m2(rec.get("repair_fund_balance"), rec.get("area_m2"))
    if per_m2 is None:
        return None, ("Remondifondi jääk teadmata (EI OLE hinnangut): %s — "
                      "fondi- või pinnarida aruandes puudu" % _provenance(rec))
    s = _band_asc(per_m2, FUND_BANDS)
    return s, ("Remondifondi seis (hinnang): fond %s — %s"
               % (_fmt_eur(per_m2), _provenance(rec)))


def dim_heating_cost(arireg: Optional[dict],
                     listing: Optional[dict] = None) -> Score:
    """P4-007: annual heating cost per m2 (high = cheap heat)."""
    rec = _rec(arireg)
    if rec is None:
        return _missing_ku()
    gate = _tallinn_gate(rec)
    if gate is not None:
        return gate
    per_m2 = _per_m2(rec.get("heating_cost_annual"), rec.get("area_m2"))
    if per_m2 is None:
        return None, ("Küttekulu teadmata (EI OLE hinnangut): %s — "
                      "kütterida või pinnarida aruandes puudu"
                      % _provenance(rec))
    s = _band_asc(per_m2, HEAT_BANDS)
    return s, ("Küttekulu (hinnang, aasta): %s — %s"
               % (_fmt_eur(per_m2), _provenance(rec)))


# ---------------------------------------------------------------------------
# Coverage (#338): the arireg leg of each remaining param. Scored where
# the KÜ row carries the answer; NULL-with-echo where the param needs a
# register this snapshot does not join (the echo proves the wiring).
# ---------------------------------------------------------------------------

def _scope_or_none(arireg: Optional[dict]) -> Tuple[Optional[dict], Optional[Score]]:
    """(record, None) when a joined in-scope record exists, else (None, NULL)."""
    rec = _rec(arireg)
    if rec is None:
        return None, _missing_ku()
    gate = _tallinn_gate(rec)
    if gate is not None:
        return None, gate
    return rec, None


def dim_grant_fund_echo(arireg: Optional[dict],
                        listing: Optional[dict] = None) -> Score:
    """P4-010: NULL - collected fund is known, the EIS queue is not.

    The arireg slice (kogutud fond) is the BILL side of "fond vs
    5-figure bill"; scoring its level would double-score P4-007's
    fund dim. The grant/queue verdict needs the EIS register, so the
    NULL echoes the collected fund figure to prove the wiring.
    """
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    per_m2 = _per_m2(rec.get("repair_fund_balance"), rec.get("area_m2"))
    echo = ("kogutud fond %s" % _fmt_eur(per_m2)
            if per_m2 is not None else "fondirida aruandes puudu")
    return None, ("Renoveerimistoetuse järjekord teadmata (EI OLE hinnangut): "
                  "%s — %s; EIS register liitmata, otsus puudub"
                  % (echo, _provenance(rec)))


def dim_enforcement_arireg(arireg: Optional[dict],
                           listing: Optional[dict] = None) -> Score:
    """P4-020: maksehäired/aruandevõlad slice (active 20, clean cap 70).

    Only the arireg leg: teadaande- (dims_p4_ata, cap 75) and
    kohtutäiturislice (dims_p4_taitur) plus Creditinfo/kohtuotsused
    stay unjoined, so a clean ledger caps at 70 - narrower evidence
    than a notice-window search.
    """
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    bad = rec.get("payment_defaults")
    debts = rec.get("report_debts")
    if (isinstance(bad, int) and bad > 0) or debts is True:
        detail = ("maksehäireid %d" % bad
                  if isinstance(bad, int) and bad > 0
                  else "aruandevõlad märgitud")
        return (20, "KÜ maksehäired (hinnang, ainult äriregistri-pool): %s — "
                    "%s; tehingu külmumise risk, Creditinfo/kohtulahend "
                    "liitmata" % (detail, _provenance(rec)))
    if (isinstance(bad, int) and bad == 0) or debts is False:
        return (70, "KÜ maksehäireid kirjas pole (nõrk hea hinnang, ainult "
                    "äriregistri-pool) — %s; teadaanded/täitur/TTJA "
                    "liitmata, ülempiir 70" % _provenance(rec))
    return None, ("KÜ maksehäirete info puudub (EI OLE hinnangut): %s — "
                  "häire- ja võlarida aruandes puudu" % _provenance(rec))


#: Developer age (years since founded_year) -> track-record score.
#: Capped at 75: TTJA kaebused and the EHR completion slice stay out.
DEVELOPER_AGE_BANDS = [(3, 45), (10, 60), (10 ** 9, 75)]

REPORT_YEAR_FALLBACK = 2026


def dim_developer_age_arireg(arireg: Optional[dict],
                             listing: Optional[dict] = None) -> Score:
    """P4-021: company age/turnover slice (cap 75, youth is neutral)."""
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    founded = rec.get("founded_year")
    if not isinstance(founded, int):
        return None, ("Arendaja vanus teadmata (EI OLE hinnangut): %s — "
                      "asutamisaasta registrikaardil puudu"
                      % _provenance(rec))
    year = rec.get("report_year")
    ref = year if isinstance(year, int) else REPORT_YEAR_FALLBACK
    age = max(0, ref - founded)
    s = _band_asc(age, DEVELOPER_AGE_BANDS)
    turnover = rec.get("turnover_annual")
    tail = (", käive %.0f EUR/a" % turnover
            if isinstance(turnover, (int, float)) and not isinstance(turnover, bool)
            else ", käive teadmata")
    return s, ("Arendaja staaž (hinnang, ainult äriregistri-pool): %d a%s — "
               "%s; TTJA kaebused ja EHR valmimissuhe liitmata, ülempiir 75"
               % (age, tail, _provenance(rec)))


def dim_maintenance_echo(arireg: Optional[dict],
                         listing: Optional[dict] = None) -> Score:
    """P4-026: NULL - hoolduskulu is known, the hex response rate is not."""
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    per_m2 = _per_m2(rec.get("maintenance_cost_annual"), rec.get("area_m2"))
    echo = ("trepikoja hoolduskulu %s/a" % _fmt_eur(per_m2)
            if per_m2 is not None else "hoolduskulurida aruandes puudu")
    return None, ("KOV fix-it kiirus teadmata (EI OLE hinnangut): %s — %s; "
                  "abiliini/e-teenuste heksakiirus liitmata"
                  % (echo, _provenance(rec)))


def dim_roof_echo(arireg: Optional[dict],
                  listing: Optional[dict] = None) -> Score:
    """P4-034: NULL - katuse/soojustuse seis is known, the sim is EHR's."""
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    roof = rec.get("roof_state")
    echo = ("katuse/soojustuse seis: %s" % roof
            if isinstance(roof, str) and roof else "katuse/soojustuse rida puudu")
    return None, ("Ülekuumenemise risk teadmata (EI OLE hinnangut): %s — %s; "
                  "korruse/orientatsiooni füüsikamudel (EHR-pool) liitmata"
                  % (echo, _provenance(rec)))


def dim_commons_echo(arireg: Optional[dict],
                     listing: Optional[dict] = None) -> Score:
    """P4-039: NULL - fondikogumine is known, turnout/OSM freshness is not."""
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    per_m2 = _per_m2(rec.get("repair_fund_balance"), rec.get("area_m2"))
    echo = ("kogutud fond %s" % _fmt_eur(per_m2)
            if per_m2 is not None else "fondirida aruandes puudu")
    return None, ("Kodanikukapital teadmata (EI OLE hinnangut): %s — %s; "
                  "valimisaktiivsus ja OSM-värskus liitmata, maitsefilter puudub"
                  % (echo, _provenance(rec)))


def dim_smell_arireg(arireg: Optional[dict],
                     listing: Optional[dict] = None) -> Score:
    """P4-042: NULL - needs the emitter-address cluster join (not a KÜ row)."""
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    return None, ("Lõhna/koorikaardi info puudub (EI OLE hinnangut): %s — "
                  "toidutootjate suitsu/lõhna aadressiklaster ei ole KÜ-aruande "
                  "rida, Keskkonnaameti kaebuste liides liitmata"
                  % _provenance(rec))


def dim_herd_arireg(arireg: Optional[dict],
                    listing: Optional[dict] = None) -> Score:
    """P4-044: NULL - needs the creative-employer address join (not a KÜ row)."""
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    return None, ("Occupation-mixi info puudub (EI OLE hinnangut): %s — "
                  "loomesektori tööandjate aadressiklaster ei ole KÜ-aruande "
                  "rida, REL2021 ruudustik liitmata" % _provenance(rec))


def dim_dead_stairwell_arireg(arireg: Optional[dict],
                              listing: Optional[dict] = None) -> Score:
    """P4-051: arrears flag a dead-stairwell risk (30); clean stays NULL.

    Bad-side-only by shape: one KÜ's arrears are a real governance
    signal, but one KÜ's clean ledger does NOT clear the hex - so the
    clean side stays NULL instead of scoring high.
    """
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    bad = rec.get("payment_defaults")
    debts = rec.get("report_debts")
    if (isinstance(bad, int) and bad > 0) or debts is True:
        detail = ("maksehäireid %d" % bad
                  if isinstance(bad, int) and bad > 0
                  else "aruandevõlad märgitud")
        return (30, "Surnud trepikoja risk (hinnang, heksilipp, mitte "
                    "hoone-otsus): %s — %s; Elektrilevi/Vee nullkulu ja "
                    "REL2021 vakants liitmata" % (detail, _provenance(rec)))
    return None, ("Trepikoja elujõu info puudub (EI OLE hinnangut): %s — "
                  "üks puhas KÜ-ledger heksi puhtaks ei pese, heksilipp "
                  "puudub" % _provenance(rec))


def dim_turnover_echo(arireg: Optional[dict],
                      listing: Optional[dict] = None) -> Score:
    """P4-052: NULL - fund dynamics (A1/A2) known, tehingud readings missing."""
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    cur = rec.get("repair_fund_balance")
    prev = rec.get("repair_fund_prev")
    if isinstance(cur, (int, float)) and isinstance(prev, (int, float)) \
            and not isinstance(cur, bool) and not isinstance(prev, bool):
        echo = "fondidünaamika %.0f -> %.0f EUR" % (prev, cur)
    else:
        echo = "fondidünaamika (A1/A2) aruandes puudu"
    return None, ("Käibe laine teadmata (EI OLE hinnangut): %s — %s; "
                  "tehingute probleem-vs-gentrifitseerumise lugemid puudu, "
                  "mõlemad lugemid lahtised" % (echo, _provenance(rec)))


def dim_heatpump_echo(arireg: Optional[dict],
                      listing: Optional[dict] = None) -> Score:
    """P4-057: NULL - heating-capex note known, hum corridor needs EHR + ears."""
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    note = rec.get("heating_capex_note")
    echo = ("kütte-investeeringute märkus: %s" % note
            if isinstance(note, str) and note else "kütte-investeeringute rida puudu")
    return None, ("Soojuspumba mürakoridor teadmata (EI OLE hinnangut): %s — "
                  "%s; EHR kütte-liigi muutus ja mürakaebused liitmata"
                  % (echo, _provenance(rec)))


def dim_stormwater_echo(arireg: Optional[dict],
                        listing: Optional[dict] = None) -> Score:
    """P4-060: NULL - sademevee kulu known, fee zone + subsidy queue missing."""
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    per_m2 = _per_m2(rec.get("stormwater_cost_annual"), rec.get("area_m2"))
    echo = ("sademevee kulu %s/a" % _fmt_eur(per_m2)
            if per_m2 is not None else "sademevee kulurida aruandes puudu")
    return None, ("Sademevee tasu + toetusjärjekord teadmata (EI OLE "
                  "hinnangut): %s — %s; Tallinna Vesi tsoonitabel ja "
                  "EIS järjekord (P4-010) liitmata" % (echo, _provenance(rec)))


def dim_waste_echo(arireg: Optional[dict],
                   listing: Optional[dict] = None) -> Score:
    """P4-062: NULL - prügi-/hoolduskulu known, hex complaint flags missing."""
    rec, err = _scope_or_none(arireg)
    if err is not None:
        return err
    assert rec is not None
    waste = _per_m2(rec.get("waste_cost_annual"), rec.get("area_m2"))
    maint = _per_m2(rec.get("maintenance_cost_annual"), rec.get("area_m2"))
    bits = []
    if waste is not None:
        bits.append("prügivedu %s/a" % _fmt_eur(waste))
    if maint is not None:
        bits.append("hooldus %s/a" % _fmt_eur(maint))
    echo = ", ".join(bits) if bits else "prügi-/hoolduskulurida aruandes puudu"
    return None, ("Näriliste/jääpurikate heksilipp teadmata (EI OLE "
                  "hinnangut): %s — %s; Keskkonnaameti/Päästeameti "
                  "heksikaebused liitmata" % (echo, _provenance(rec)))


#: Registry for the central weight-rebalance follow-up:
#: (dim key, param id, scorer). Keys carry the arireg-leg suffix
#: where a sibling module scores another leg of the same param.
P4_ARIREG_DIMS = (
    ("ku_loan_per_m2", "P4-007", dim_ku_loan),
    ("repair_fund_per_m2", "P4-007", dim_repair_fund),
    ("heating_cost_per_m2", "P4-007", dim_heating_cost),
    ("grant_fund_cover_arireg", "P4-010", dim_grant_fund_echo),
    ("enforcement_arireg", "P4-020", dim_enforcement_arireg),
    ("developer_age_arireg", "P4-021", dim_developer_age_arireg),
    ("fixit_cost_arireg", "P4-026", dim_maintenance_echo),
    ("overheat_roof_arireg", "P4-034", dim_roof_echo),
    ("civic_commons_arireg", "P4-039", dim_commons_echo),
    ("smell_arireg", "P4-042", dim_smell_arireg),
    ("herd_arireg", "P4-044", dim_herd_arireg),
    ("dead_stairwell_arireg", "P4-051", dim_dead_stairwell_arireg),
    ("turnover_fund_arireg", "P4-052", dim_turnover_echo),
    ("heatpump_capex_arireg", "P4-057", dim_heatpump_echo),
    ("stormwater_cost_arireg", "P4-060", dim_stormwater_echo),
    ("waste_cost_arireg", "P4-062", dim_waste_echo),
)


def score_p4_arireg(arireg: Optional[dict],
                    listing: Optional[dict] = None) -> Dict[str, Optional[int]]:
    """All sixteen P4 arireg dims for one joined KÜ record (entry point
    for the weight-rebalance follow-up; keys match P4_ARIREG_DIMS)."""
    return {key: fn(arireg, listing)[0] for key, _, fn in P4_ARIREG_DIMS}
