"""P4 taitur demo + coverage dims (issues #255 and #336).

Demo (#255): Kohtutäiturite register ingestion (P4-020) — polite,
cached, TTL-stated pulls of the enforcement-proceedings slice plus an
honest-shape per-entity dim. Coverage (#336): P4-004 Kinnistus süva +
notary checkpoint, taitur slice, wired to the same demoed ingestion
(no new plumbing — #336 states it extends the demoed ingestion).

Params (this agent only — sibling batches own disjoint sets):
* P4-020 Enforcement: bankruptcy/bailiff on property (demo, per-entity)
* P4-004 Kinnistus süva + notary checkpoint, taitur slice (per-listing)

HONESTY (AGENTS.md section 7.2): per-entity dims, weak-good capped;
NULL stays NULL with an Estonian reason. The register is CLOSED for
the per-property/per-developer active-proceedings purpose (dated
negative below), so every dim returns None when its join slice is
missing — never a guess, never a "clean" 100 from absence. Scored
reasons always trace to a joined case record (stage/status/subject);
NULL reasons always say EI OLE and name the missing input.

Openness verdict (2026-09-13, two HEAD probes only, custom UA,
no scraping, no auth attempts):
* https://kpkoda.ee/ -> HTTP 200 (Apache, WordPress site) — the
  Chamber's public site carries the bailiff contact directory (pages,
  not a data feed); no anonymous per-property proceedings endpoint.
* https://www.ametlikudteadaanded.ee/ -> HTTP 405 on HEAD
  (Cloudflare-fronted RIK JS app) — notices are searchable in the
  browser UI, no anonymous bulk/search endpoint probed (polite stop).
Dated negative keeps the verdict: no anonymous per-entity
active-täitemenetlus feed verified 2026-09-13. fetch_taitur_csv below
targets the documented snapshot layout with a daily TTL and the dims
score ONLY joined case slices. See docs/p4_taitur.md. Personal data
is never fetched or stored: the snapshot carries case stage/status
per subject key only (no debtor names, no personal codes).

Style mirrors services/scoring/dims_p4_ehr.py (issues #249/#333):
pure (cases, listing) -> (Optional[int 0..100], Estonian reason),
absolute bands, hermetic fixture tests. Network lives only in
fetch_taitur_csv (single polite GET, file cache, TTL); tests never
call it.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and group20a #212).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR because #336 defines coverage as
  extending the demoed ingestion — P4-004's source list names the
  kohtutäiturite register (active täitemenetlus, Tallinn properties)
  as source (4), i.e. the same feed P4-020 demos. Splitting would
  ship an ingestion with one consumer, then re-touch every
  signature (same rationale as the EHR #249/#333 pair).
* Bands are 15/40/70, never 0 and never 100: a frozen deal is never
  scored zero on the register slice alone (kinnistusraamat + notar
  decide), and a clean slice is weak-good capped at 70 — coverage is
  partial by construction (closed register), so absence of a joined
  case is not proof of a clean title.
* None (subject not in the join index) vs [] (indexed, no cases):
  None is unknown (EI OLE, check e-Kinnistusraamat/notar); [] is a
  joined empty slice and scores the weak-good 70 with the cap named.
* subject_kind is kinnistu-first: an active arest/keelumärge/oksjon
  on the property freezes THIS deal (15); an active developer-side
  case (pankrot/arendaja) clouds it (40). Resolved-only history
  scores like empty (70) — past cases do not discount the price.
* Daily TTL (86400 s): enforcement actions and auction notices
  appear daily; polls converge over runs per AGENTS.md section 7.4.

Integration (deliberately NOT done here): feeding these dims with
the listing's joined case slice inside livability scoring and
rebalancing livability.WEIGHTS must be one joint change across all
parameter batches — existing tests pin set(WEIGHTS) exactly, so
per-batch WEIGHTS edits would break every sibling.
"""

import csv
import io
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated taitur snapshot pulls.
# ---------------------------------------------------------------------------

#: Daily pull per module docstring (enforcement actions appear daily).
TAITUR_TTL_S = 86400

#: Where the public slices live (verified 2026-09-13 — see module
#: docstring; directory pages / JS UI, no anonymous case feed).
TAITUR_CHAMBER_URL = "https://kpkoda.ee/"
TAITUR_ATA_URL = "https://www.ametlikudteadaanded.ee/"

USER_AGENT = ("home-finder taitur ingest (polite daily pull, single GET, "
              "file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str, name: str) -> str:
    """Cache file for one named taitur snapshot (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)
    return os.path.join(cache_dir, "taitur-%s.csv" % safe)


def cache_is_fresh(path: str, ttl_s: int = TAITUR_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_s seconds."""
    try:
        age_s = ((now if now is not None else time.time())
                 - os.path.getmtime(path))
    except OSError:
        return False
    return age_s < ttl_s


def fetch_taitur_csv(name: str, url: str, cache_dir: str = "/tmp/hf-cache",
                     ttl_s: int = TAITUR_TTL_S) -> str:
    """Fetch one taitur snapshot politely (single GET, cached, TTL-stated).

    Returns cached text when fresh; otherwise one GET with a polite
    User-Agent and a 30 s timeout. Transport errors RAISE (never cached
    as data, AGENTS.md section 7.2); HTTP errors raise too — an error
    body is never written to the cache. Treat HTTP 429 as a stop
    signal: it propagates, the stale cache is left untouched.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, name)
    if cache_is_fresh(path, ttl_s):
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
# Parsing: taitur snapshot layout (semicolon-separated, BOM-tolerant).
# Column names follow the documented snapshot; unknown columns are
# ignored, empty cells and absent columns read as None (never guessed).
# No personal data: debtor names / personal codes are NOT columns —
# a snapshot carrying them is rejected row by row (row skipped).
# ---------------------------------------------------------------------------

#: Canonical record keys produced by parse_taitur_cases (all Optional
#: except the join key subject_key, which is always a non-empty str).
TAITUR_FIELDS = (
    "subject_key", "subject_kind", "address", "kov", "stage",
    "status", "bailiff_office", "updated",
)

_SUBJECT_KINDS = ("kinnistu", "arendaja")
_STAGES = ("arest", "keelumärge", "oksjon", "pankrot", "muu")
_STATUSES = ("aktiivne", "lõpetatud")

#: Columns that must never appear in a polite snapshot (personal data —
#: AGENTS.md section 5). Any row carrying a non-empty one is skipped.
_FORBIDDEN_COLUMNS = ("võlgnik", "isikukood", "nimi")


def _clean(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _norm(value: Optional[object]) -> str:
    return "" if value is None else str(value).strip().lower()


def parse_taitur_cases(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse one taitur snapshot into canonical per-case records.

    Semicolon-separated, BOM-tolerant; empty cells and absent columns
    become None. Rows without a subject_key are skipped (no join key —
    keeping them would fake join coverage). Rows carrying personal-data
    columns (debtor name / personal code) are skipped. Unknown
    subject_kind/stage/status tokens read as None (never guessed).
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    field_names = [(_clean(h) or "") for h in (reader.fieldnames or [])]
    lowered = [h.lower() for h in field_names]
    has_forbidden = any(col in lowered for col in _FORBIDDEN_COLUMNS)
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        if has_forbidden and any(
                _clean(row.get(h)) for h in (reader.fieldnames or [])
                if (_clean(h) or "").lower() in _FORBIDDEN_COLUMNS):
            continue
        key = _clean(row.get("subject_key"))
        if not key:
            continue
        rec = {"subject_key": key}  # type: Dict[str, Optional[object]]
        kind = _norm(row.get("subject_kind"))
        rec["subject_kind"] = kind if kind in _SUBJECT_KINDS else None
        stage = _norm(row.get("stage"))
        rec["stage"] = stage if stage in _STAGES else None
        status = _norm(row.get("status"))
        rec["status"] = status if status in _STATUSES else None
        for field in ("address", "kov", "bailiff_office", "updated"):
            rec[field] = _clean(row.get(field))
        records.append(rec)
    return records


def index_by_subject(
        records: List[Dict[str, Optional[object]]]
) -> Dict[str, List[Dict[str, Optional[object]]]]:
    """Per-subject join index (all rows per key, snapshot order kept)."""
    index = {}  # type: Dict[str, List[Dict[str, Optional[object]]]]
    for rec in records:
        key = rec.get("subject_key")
        if key:
            index.setdefault(str(key), []).append(rec)
    return index


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _lst(listing: Optional[dict]) -> dict:
    return listing if isinstance(listing, dict) else {}


def _missing_taitur() -> Score:
    return None, ("Täitemenetluse kirjeid selle objekti/arendaja kohta "
                  "hetktõmmises pole — Kohtutäiturite registri "
                  "aktiivmenetluste andmeteta skoori EI OLE (hinnangut ei "
                  "anta): kontrolli e-Kinnistusraamatust ja notarilt")


def _active(cases: List[dict]) -> List[dict]:
    return [c for c in cases if isinstance(c, dict)
            and c.get("status") == "aktiivne"]


def _describe(case: dict) -> str:
    stage = case.get("stage") or "teadmata staadium"
    kind = case.get("subject_kind") or "teadmata subjekt"
    return "%s/%s" % (stage, kind)


# ---------------------------------------------------------------------------
# P4-020 (demo): enforcement — pankrot/täitemenetlus on property/developer.
# Per-entity dim, weak-good capped at 70.
# ---------------------------------------------------------------------------

#: Stages that freeze THIS deal (property-side active proceedings).
_FREEZE_STAGES = ("arest", "keelumärge", "oksjon")


def dim_enforcement(cases: Optional[list],
                    listing: Optional[dict] = None) -> Score:
    """P4-020: active proceedings freeze/cloud the deal (15/40/70/NULL)."""
    _ = _lst(listing)  # listing side unused — per-entity register join
    if cases is None:
        return _missing_taitur()
    if not isinstance(cases, list):
        return _missing_taitur()
    active = _active(cases)
    prop_freeze = [c for c in active
                   if c.get("subject_kind") == "kinnistu"
                   and c.get("stage") in _FREEZE_STAGES]
    if prop_freeze:
        return (15, "Aktiivne %s (registriandmed, mitte hinnang) — "
                    "külmutatud tehing: notar ei tõesta enne vabastamist"
                % _describe(prop_freeze[0]))
    if active:
        return (40, "Aktiivne %s arendaja/omaniku poolel (registriandmed, "
                    "mitte hinnang) — tehing pilves, aga kinnistu ise "
                    "vaba" % _describe(active[0]))
    return (70, "Liidetud registrilõigus aktiivseid menetlusi pole "
                "(nõrk hea-signaal, ülempiir 70, mitte hinnang) — "
                "kate on osaline, kinnistusraamatu kontroll eraldi")


# ---------------------------------------------------------------------------
# P4-004 (coverage): kinnistus süva + notary checkpoint, taitur slice.
# Per-listing dim, weak-good capped at 70. The RIK e-Kinnistusraamat
# paid flow itself (keelumärge/hüpoteek summary) is NOT joined — this
# dim scores only the taitur active-proceedings slice and says so.
# ---------------------------------------------------------------------------

def dim_kinnistus_checkpoint(cases: Optional[list],
                             listing: Optional[dict] = None) -> Score:
    """P4-004: taitur slice of the closing-feasibility check (20/50/70)."""
    _ = _lst(listing)  # listing side unused — per-entity register join
    if cases is None or not isinstance(cases, list):
        return None, ("Kinnistusraamatu süva (keelumärge/hüpoteek) päringut "
                      "pole — RIK e-Kinnistusraamat on tasuline voog ja "
                      "taitur-lõiku pole liidetud (EI OLE hinnangut): "
                      "võta väljavõte ja notari kontroll enne pakkumist")
    active = _active(cases)
    prop_freeze = [c for c in active
                   if c.get("subject_kind") == "kinnistu"
                   and c.get("stage") in _FREEZE_STAGES]
    if prop_freeze:
        return (20, "Aktiivne %s (registriandmed, mitte hinnang) — "
                    "notari kontroll: tehing ei sulgu enne vabastamist"
                % _describe(prop_freeze[0]))
    if active:
        return (50, "Aktiivne %s arendaja/omaniku poolel (registriandmed, "
                    "mitte hinnang) — notar küsib täiendavalt, sulgumine "
                    "võimalik" % _describe(active[0]))
    return (70, "Taitur-lõigus takistusi pole (nõrk hea-signaal, ülempiir "
                "70, mitte hinnang) — keelumärge/hüpoteek vajab ikka "
                "kinnistusraamatu väljavõtet")


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_TAITUR_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_TAITUR_DIMS = (
    ("enforcement", "P4-020", dim_enforcement),
    ("kinnistus_checkpoint", "P4-004", dim_kinnistus_checkpoint),
)


def score_p4_taitur(cases: Optional[list],
                    listing: Optional[dict] = None
                    ) -> Dict[str, Optional[int]]:
    """Both P4 taitur dims for one listing (entry point for the future
    enrich/score hook; keys match P4_TAITUR_DIMS). Missing slices stay
    None by design — per-subject join, never a faked area score."""
    return {key: fn(cases, listing)[0] for key, _, fn in P4_TAITUR_DIMS}
