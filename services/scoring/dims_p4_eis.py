"""P4 EIS (ex-KredEx) demo + coverage dims (issues #260 and #341).

Demo (#260): EIS renovation-grant register + queue + loan-guarantee
ingestion (P4-010) — polite, cached, TTL-stated pulls of the EIS grant
register layout plus honest-shape per-building join dims. Coverage
(#341): the remaining 2 params that consume the demoed ingestion, each
wired to its EIS-record slice (P4-007 loan-guarantee slice, P4-060
subsidy-queue slice).

Params (this agent only — sibling batches own disjoint sets):
* P4-010 renovation-grant status + queue (demo, per-building dim)
* P4-007 KUE loan + remondifond + heating EUR/m2, EIS slice: loan
  guarantee (kaendus) per building (per-building dim)
* P4-060 stormwater fee + subsidy queue, EIS slice: subsidy queue
  position via the P4-010 join (queue dim; fee zones stay NULL)

HONESTY (AGENTS.md section 7.2): no anonymous direct-download EIS
grant-register CSV URL verified 2026-09-13 (dated negative keeps the
verdict — see module docstring verdict + docs/p4_eis.md), so every dim
returns None when its EIS slice is missing — never a guess. Scored
reasons always say "EIS" (traceable to a register record); pure-join
params stay NULL with the primary source named. NULL stays NULL with
an Estonian reason.

Openness verdict (2026-09-13, dated probes, cache /tmp/hf-eis):
* https://eis.ee/ -> HTTP 200, 294612 bytes — live EIS site.
* https://kredex.ee/ -> HTTP 200 -> https://eis.ee/avaleht-elamumajandus/
  (legacy KredEx housing domain now serves the EIS housing section —
  ex-KredEx continuity confirmed).
* https://eis.ee/rekonstrueerimise-kulude-kalkulaator-korteruhistutele/
  -> HTTP 200, 216542 bytes — guidance calculator, not a bulk
  register.
* https://etoetus.rtk.ee/ -> HTTP 200 -> /esf2web/ AngularJS SPA shell
  (3592 bytes) — state grant application portal, login-gated, no
  anonymous bulk endpoint probed (polite stop: one GET each).
* https://andmed.eesti.ee/ -> HTTP 200, 75497-byte Teabevarav SPA —
  national portal has no CKAN API (EHR #249 precedent); dataset
  search needs JS.
Dated negative keeps the verdict: no anonymous per-building EIS
grant/queue CSV verified 2026-09-13. The source stays OPEN-but-gated
(published programme pages + gated e-toetus portal), so fetch_eis_csv
below targets the documented register layout with a quarterly TTL and
the dims score ONLY joined records. See docs/p4_eis.md for the full
note.

Style mirrors services/scoring/dims_p4_ehr.py (issues #249/#333):
pure (eis, listing) -> (Optional[int 0..100], Estonian reason),
absolute bands, hermetic fixture tests. Network lives only in
fetch_eis_csv (single polite GET, file cache, TTL); tests never call
it.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and group20a #212).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR because the coverage issue (#341) body
  states it "extends the demoed ingestion" — splitting would ship an
  ingestion with one consumer, then re-touch every dim signature
  (same precedent as EHR #249/#333, PR merged).
* P4-010 bands (85/60/50/35) are copied verbatim from the EHR slice
  dim_renovation_grant in dims_p4_ehr.py so the two sources agree
  when both are joined; the EHR slice stays the mirror, this module
  is the primary EIS ingestion (pairing rationale).
* P4-007 scores ONLY the EIS kaendus slice (70/50/50): the full
  param (KU loan + remondifond + heating EUR/m2 from annual reports)
  belongs to e-Ariregister (#257 pipeline), so the reason always
  names the annual-report remainder. No guarantee is neutral (50),
  never bad — most buildings simply have none.
* P4-060 scores ONLY the EIS subsidy-queue slice (55/70): the
  stormwater fee zone table belongs to Tallinna Vesi / Tallinna UVK
  (not EIS), so the zone half stays NULL with that pointer. Queue
  position known beats status-only (55 vs 50/70 mix) because a
  numbered queue slot is the most actionable buyer fact.
* Join key is ehr_code first, eis_id fallback: EIS decisions
  reference buildings that the EHR already codes, so ehr_code keeps
  this module join-compatible with dims_p4_ehr.py; rows with
  neither key are skipped (keeping them would fake join coverage).

Integration (deliberately NOT done here): feeding these dims with
the listing's EIS record inside livability scoring and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling.
"""

import csv
import io
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated EIS register pulls.
# ---------------------------------------------------------------------------

#: Quarterly bulk per parameters4.md P4-010 ("TTL: quarterly").
EIS_TTL_DAYS = 91

#: Where the programme lives (verified 2026-09-13 — see module
#: docstring; programme pages public, per-building bulk gated).
EIS_HOUSING_URL = "https://eis.ee/avaleht-elamumajandus/"
ETOETUS_URL = "https://etoetus.rtk.ee/esf2web/"

USER_AGENT = ("home-finder EIS ingest (polite quarterly bulk, single GET, "
              "file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str, name: str) -> str:
    """Cache file for one named EIS register extract (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)
    return os.path.join(cache_dir, "eis-%s.csv" % safe)


def cache_is_fresh(path: str, ttl_days: int = EIS_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_eis_csv(name: str, url: str, cache_dir: str = "/tmp/hf-cache",
                  ttl_days: int = EIS_TTL_DAYS) -> str:
    """Fetch one EIS register extract politely (single GET, cached, TTL-stated).

    Returns cached text when fresh; otherwise one GET with a polite
    User-Agent and a 30 s timeout. Transport errors RAISE (never cached
    as data, AGENTS.md section 7.2); HTTP errors raise too — an error
    body is never written to the cache. Treat HTTP 429 as a stop
    signal: it propagates, the stale cache is left untouched.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, name)
    if cache_is_fresh(path, ttl_days):
        with io.open(path, encoding="utf-8-sig") as f:
            return f.read()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = resp.read()
    text = body.decode("utf-8-sig")
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------------------
# Parsing: EIS register layout (semicolon-separated, BOM-tolerant).
# Column names follow the documented extract; unknown columns are kept
# verbatim, missing columns read as None (never guessed).
# ---------------------------------------------------------------------------

#: Canonical record keys produced by parse_eis_grants (all Optional).
EIS_FIELDS = (
    "eis_id", "address", "kov", "ehr_code", "grant_status",
    "queue_pos", "grant_amount_eur", "decision_date",
    "guarantee_status", "guarantee_amount_eur",
    "subsidy_queue_pos",
)

_INT_FIELDS = ("queue_pos", "grant_amount_eur", "guarantee_amount_eur",
               "subsidy_queue_pos")


def _to_int(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    s = str(raw).strip().replace(" ", "")
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_eis_grants(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse one EIS register extract into canonical per-building records.

    Semicolon-separated, BOM-tolerant; empty cells and absent columns
    become None. Rows with neither ehr_code nor eis_id are skipped (no
    join key — keeping them would fake join coverage).
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        code = (row.get("ehr_code") or "").strip()
        eid = (row.get("eis_id") or "").strip()
        if not code and not eid:
            continue
        rec = {"ehr_code": code or None,
               "eis_id": eid or None}  # type: Dict[str, Optional[object]]
        for field in EIS_FIELDS:
            if field in ("ehr_code", "eis_id"):
                continue
            raw = row.get(field)
            if field in _INT_FIELDS:
                rec[field] = _to_int(raw)
            else:
                s = None if raw is None else str(raw).strip()
                rec[field] = s if s else None
        records.append(rec)
    return records


def index_by_ehr_code(
        records: List[Dict[str, Optional[object]]]
) -> Dict[str, Dict[str, Optional[object]]]:
    """Per-ehr_code join index (first row wins on duplicates)."""
    index = {}  # type: Dict[str, Dict[str, Optional[object]]]
    for rec in records:
        code = rec.get("ehr_code")
        if code and code not in index:
            index[code] = rec
    return index


def index_by_eis_id(
        records: List[Dict[str, Optional[object]]]
) -> Dict[str, Dict[str, Optional[object]]]:
    """Per-eis_id fallback index (first row wins on duplicates)."""
    index = {}  # type: Dict[str, Dict[str, Optional[object]]]
    for rec in records:
        eid = rec.get("eis_id")
        if eid and eid not in index:
            index[eid] = rec
    return index


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _rec(eis: Optional[dict]) -> Optional[dict]:
    return eis if isinstance(eis, dict) else None


def _lst(listing: Optional[dict]) -> dict:
    return listing if isinstance(listing, dict) else {}


def _missing_eis() -> Score:
    return None, ("EIS kirje puudub — renoveerimistoetuste registri andmeteta "
                  "skoori EI OLE (hinnangut ei anta): kontrolli KÜ-st ja "
                  "eis.ee elamumajanduse lehelt")


def _norm(value: Optional[object]) -> str:
    return "" if value is None else str(value).strip().lower()


# ---------------------------------------------------------------------------
# P4-010 (demo): renovation-grant status + queue — per-building dim.
# Bands mirror dims_p4_ehr.dim_renovation_grant so both sources agree.
# ---------------------------------------------------------------------------

_GRANT_BANDS = (
    (("eraldatud", "tehtud", "lõpetatud"), 85,
     "Renoveerimistoetus eraldatud/tehtud (EIS andmed, mitte hinnang)"),
    (("järjekorras", "ootel"), 60, None),
    (("taotletud", "menetluses"), 50, None),
    (("puudub", "ei", "tagasi lükatud"), 35,
     "Renoveerimistoetus puudub (EIS andmed): 5-kohaline ühistu-arve "
     "võimalik — KÜ fondi kontrolli, mitte hinnang"),
)


def dim_eis_grant_status(eis: Optional[dict],
                         listing: Optional[dict] = None) -> Score:
    """P4-010: grant status bands; queue position named when known."""
    rec = _rec(eis)
    if rec is None:
        return _missing_eis()
    status = _norm(rec.get("grant_status"))
    if not status:
        return None, ("EIS renoveerimistoetuse järjekorra andmed puuduvad "
                      "(EI OLE hinnangut): KÜ-st ja EIS-ist kontrolli")
    for keys, score, fixed in _GRANT_BANDS:
        if status in keys:
            if fixed is not None:
                return score, fixed
            pos = rec.get("queue_pos")
            tail = (" — järjekorrakoht %s" % pos
                    if isinstance(pos, int) else "")
            verb = ("järjekorras" if status in ("järjekorras", "ootel")
                    else "taotletud/menetluses")
            return (score, "Renoveerimistoetus %s%s (EIS andmed, mitte "
                           "hinnang) — raha teel, aga ooteajaga"
                    % (verb, tail))
    return None, ("Tundmatu EIS toetuse staatus (%s) — EI OLE "
                  "hinnangut, kontrolli EIS-ist"
                  % str(rec.get("grant_status")).strip())


# ---------------------------------------------------------------------------
# P4-007 (coverage): KU loan + remondifond + heating EUR/m2, EIS slice.
# The EIS record carries only the loan guarantee (kaendus); the annual-
# report fields (laen, remondifond, kutte EUR/m2) stay with
# e-Ariregister, named in every reason.
# ---------------------------------------------------------------------------

_GUARANTEE_ACTIVE = ("kehtiv", "antud", "jõus")
_GUARANTEE_PENDING = ("taotletud", "menetluses", "ootel")
_GUARANTEE_NONE = ("puudub", "ei", "lõppenud", "kehtetu",
                   "tagasi lükatud")


def dim_ku_loan_guarantee(eis: Optional[dict],
                          listing: Optional[dict] = None) -> Score:
    """P4-007 EIS slice: loan-guarantee status; annual-report fields stay NULL."""
    rec = _rec(eis)
    if rec is None:
        return _missing_eis()
    status = _norm(rec.get("guarantee_status"))
    if not status:
        return None, ("EIS kaenduse andmed puuduvad (EI OLE hinnangut): "
                      "KU laen, remondifond ja kütte EUR/m2 on "
                      "e-Ariregistri majandusaasta aruannetes — kontrolli sealt")
    if status in _GUARANTEE_ACTIVE:
        amount = rec.get("guarantee_amount_eur")
        tail = (" — kaenduse summa %s EUR" % amount
                if isinstance(amount, int) else "")
        return (70, "EIS renoveerimislaenu kaendus kehtiv%s (EIS andmed, "
                    "mitte hinnang, nõrk hea): KU laen, remondifond ja "
                    "kütte EUR/m2 vaata aruannetest"
                % tail)
    if status in _GUARANTEE_PENDING:
        return (50, "EIS kaendus taotletud/menetluses (EIS andmed, mitte "
                    "hinnang): otsus teel — KU laen, remondifond ja kütte "
                    "EUR/m2 vaata aruannetest")
    if status in _GUARANTEE_NONE:
        return (50, "EIS kaendus puudub (EIS andmed, mitte hinnang) — "
                    "tavaseis, mitte riskisignaal: KU laen, remondifond ja "
                    "kütte EUR/m2 on e-Ariregistri aruannetes")
    return None, ("Tundmatu EIS kaenduse staatus (%s) — EI OLE "
                  "hinnangut, kontrolli EIS-ist"
                  % str(rec.get("guarantee_status")).strip())


# ---------------------------------------------------------------------------
# P4-060 (coverage): stormwater fee + subsidy queue, EIS slice.
# The fee zone table belongs to Tallinna Vesi / Tallinna UVK (not EIS),
# so the zone half stays NULL with that pointer; the EIS record scores
# only the subsidy queue position (P4-010 join per parameters4.md).
# ---------------------------------------------------------------------------


def dim_stormwater_subsidy_queue(eis: Optional[dict],
                                 listing: Optional[dict] = None) -> Score:
    """P4-060 EIS slice: subsidy queue position; fee zones stay NULL."""
    rec = _rec(eis)
    if rec is None:
        return _missing_eis()
    pos = rec.get("subsidy_queue_pos")
    if isinstance(pos, int):
        return (55, "EIS toetuse järjekorrakoht %d (EIS andmed, mitte "
                    "hinnang) — raha teel, aga ooteajaga; sademevee tasu "
                    "tsoon (Tallinna Vesi hinnakiri) kontrolli eraldi"
                % pos)
    status = _norm(rec.get("grant_status"))
    if status in ("eraldatud", "tehtud", "lõpetatud"):
        return (70, "EIS toetus eraldatud (EIS andmed, mitte hinnang) — "
                    "subsiidium kindel; sademevee tasu tsoon (Tallinna "
                    "Vesi hinnakiri) kontrolli eraldi")
    if status in ("järjekorras", "ootel", "taotletud", "menetluses"):
        return (50, "EIS toetus %s (EIS andmed, mitte hinnang), "
                    "järjekorrakoht numbrita — KÜ-st täpsusta; sademevee "
                    "tasu tsoon (Tallinna Vesi hinnakiri) kontrolli eraldi"
                % ("järjekorras" if status in ("järjekorras", "ootel")
                   else "taotletud/menetluses"))
    return None, ("EIS subsiidiumi-järjekorra andmed puuduvad (EI OLE "
                  "hinnangut): sademevee tasu tsoon on Tallinna Vesi "
                  "hinnakirjas, järjekord KÜ-s ja EIS-is — kontrolli sealt")


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_EIS_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_EIS_DIMS = (
    ("eis_grant_status", "P4-010", dim_eis_grant_status),
    ("ku_loan_guarantee", "P4-007", dim_ku_loan_guarantee),
    ("stormwater_subsidy_queue", "P4-060", dim_stormwater_subsidy_queue),
)


def score_p4_eis(eis: Optional[dict],
                 listing: Optional[dict] = None
                 ) -> Dict[str, Optional[int]]:
    """All 3 P4 EIS dims for one listing (entry point for the future
    enrich/score hook; keys match P4_EIS_DIMS). Missing slices stay None
    by design — per-building join, never a faked area score."""
    return {key: fn(eis, listing)[0] for key, _, fn in P4_EIS_DIMS}
