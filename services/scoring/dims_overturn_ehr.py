"""Overturn #234 (G2 EHR bulk): per-code registry join + listing enrichment.

Scope (issue #234): parameters3.md G2 params p21/p30/p33/p35/p48/p79/p154/p495
(p196 already ships). Honest output is listing enrichment + per-code dims,
never an area gradient — building attributes are not place fields (#136
precedent, docs/nomap.md G2 verdicts, which this PR deliberately does NOT
edit; the final index PR owns nomap.md).

Pipeline state (dated probes, 2026-09-13 ~13:3x UTC, polite one-GET-each
`home-finder-verification` User-Agent — re-verified for this issue):

* https://www.eehitus.ee/infoportal -> 301 ->
  https://eehitus.digitaalehitus.ee/ (HTTP 200, ~695 kB cluster marketing
  site, no CSV endpoint).
* https://livekluster.ehr.ee/ui/ehr/v1 (HTTP 200, 3663-byte JS shell) —
  live platform UI, login-gated.
* https://koodivaramu.eesti.ee/mkm-ehr/ehr-v1 -> 302 ->
  https://koodivaramu.eesti.ee/users/sign_in — source-code/API host,
  sign-in-gated, no anonymous bulk.
* National portal moved avaandmed.eesti.ee -> andmed.eesti.ee (Teabevarav
  SPA, no CKAN /api/3/action — HTTP 404 "Cannot GET", #333 precedent).

Dated negative keeps the verdict: NO anonymous direct-download EHR bulk CSV
URL is verified, so there is no live backfill — every dim below returns None
when its EHR record slice is missing ("Flag NULL; do not fake", §5.2), and
fetch_ehr_bulk() requires the caller to supply the gated export URL (weekly
infoportal report / quarterly dump placed by the maintainer). What this
module DOES ship honestly:

1. Polite bulk ingest (fetch_ehr_bulk): single GET, file cache under
   /tmp/hf-cache, TTL EHR_TTL_DAYS = 30 (parameters3.md §5.2: "Quarterly
   bulk dump sync; on-demand cache TTL 30 days per building code").
   Transport errors RAISE and are never cached as data; HTTP 429
   propagates (stop signal, AGENTS.md §7.4).
2. Per-ehr_code join (parse_ehr_buildings + index_by_ehr_code) over the
   documented report layout (Buildings / Permits / Certificates slices).
3. Listing enrichment (enrich_listing_from_ehr): p21/p33/p35 copy EHR facts
   onto the listing record where honest — the listing's own value always
   wins, EHR only fills gaps, provenance is recorded per field.
4. Per-code dims for the rest (p30/p48/p79/p154/p495) scoring ONLY joined
   records; every reason says "EHR", estimated bands additionally say
   "hinnang".

Relationship to siblings (READ, not edited — see issue):
* dims_group02.py (#136) scores p30/p35/p48 from LISTING attributes
  (floor+lift, energy class, permit status) and deliberately has NO p21/p33
  dims (filter / taste axis, never monotonic goodness). This module does
  not duplicate that judgment: p21/p33 stay scoreless here too (enrichment
  only), and the p30/p48 dims below consume the BULK-joined EHR record,
  converging with the listing-attribute dims only at integration.
* dims_group02b.py (#137) scores p79/p154/p495 (+p196) from a small EHR
  record. The p79/p154/p495 dims below are their bulk-record twins: same
  bands, distinct "hulgilaadung" (bulk-join) reasons proving the join
  wiring. p196 is owned by group02b and is NOT repeated here.
* dims_p4_ehr.py (#249/#333) owns the parameters4 P4-xxx EHR dims — a
  separate pipeline, untouched.

Style mirrors dims_group02b.py: pure (ehr[, listing]) ->
(Optional[int 0..100], Estonian reason), absolute bands, hermetic fixture
tests. Network lives only in fetch_ehr_bulk; tests never call it with a
remote URL. Helpers are local copies (no sibling imports): a future central
hook may import this module alongside them, and importing any of them here
would turn that into a cycle (batch B3 / PR #100 precedent).

Judgment calls (reviewable per AGENTS.md §7.5):
* p21 enriches as `building_net_area_m2` (BUILDING fact), never overwriting
  the listing's own `area_m2`: the bulk "Buildings" slice carries no
  per-flat (ehitise osa) area, and scoring flat goodness off building size
  would repeat the #136 filter fallacy. The EHR area is context for the
  buyer (cross-check vs kuulutus), not a score.
* p33 enriches `build_year` + `building_age_years` but stays scoreless:
  age goodness is taste (Vanalinn charm vs new build, #136 verdict stands).
* p35 enriches `energy_class` only; scoring stays with group02 dim_energy
  once wired — one band definition, no fork.
* p30 needs the LISTING floor for walk-ups: a 5-floor lift-less building
  tells nothing about a 1st-floor flat. Lift comes from EHR (fills the
  listing gap); without either side the dim stays NULL.
* p48 with a present-but-empty permit record (0 open / 0 finalized) stays
  NULL, never "clean": old stock predates digital records, absence is not
  evidence (dims_p4_ehr P4-005 precedent).
* p154 never derives warranty from build_year: guarantee terms vary by
  contract, computing one from age would be fake precision. Explicit
  `warranty_valid` field or NULL.
* Duplicate ehr_code rows: first row wins (same as dims_p4_ehr); rows
  without ehr_code are skipped (no join key — keeping them would fake
  join coverage).

Integration (deliberately NOT done here): feeding enrich/score outputs into
livability scoring and rebalancing livability.WEIGHTS must be one joint
change across all parameter batches — existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling.
"""

import csv
import datetime
import io
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated EHR bulk pulls.
# ---------------------------------------------------------------------------

#: Quarterly bulk per parameters3.md §5.2 ("Quarterly bulk dump sync;
#: on-demand cache TTL 30 days per building code").
EHR_TTL_DAYS = 30

#: Report slices of the documented EHR open-data layout (Buildings,
#: Permits, Certificates per §5.2 Alternate 1). Names only — the gated
#: export URL is caller-supplied (no anonymous bulk URL verified).
EHR_BULK_REPORTS = ("buildings", "permits", "certificates")

#: Verified landing pages (probes 2026-09-13, see docstring): login- or
#: marketing-gated, kept as provenance constants — NOT fetch targets.
EHR_UI_URL = "https://livekluster.ehr.ee/ui/ehr/v1"
EHR_INFO_URL = "https://eehitus.digitaalehitus.ee/"
EHR_API_URL = "https://koodivaramu.eesti.ee/mkm-ehr/ehr-v1"

USER_AGENT = ("home-finder EHR bulk ingest (polite quarterly bulk, single "
              "GET, file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str, name: str) -> str:
    """Cache file for one named EHR bulk report (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)
    return os.path.join(cache_dir, "ehr-bulk-%s.csv" % safe)


def cache_is_fresh(path: str, ttl_days: int = EHR_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_ehr_bulk(name: str, url: Optional[str], cache_dir: str = "/tmp/hf-cache",
                   ttl_days: int = EHR_TTL_DAYS) -> str:
    """Fetch one EHR bulk report politely (single GET, cached, TTL-stated).

    Returns cached text when fresh; otherwise one GET with a polite
    User-Agent and a 30 s timeout. `url` is the gated export URL placed by
    the maintainer — no anonymous bulk URL is verified (dated negative,
    see docstring), so an empty url raises ValueError instead of guessing
    an endpoint. Transport errors RAISE (never cached as data, AGENTS.md
    §7.2); HTTP errors raise too — an error body is never written to the
    cache. Treat HTTP 429 as a stop signal: it propagates, the stale cache
    is left untouched.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, name)
    if cache_is_fresh(path, ttl_days):
        with io.open(path, encoding="utf-8-sig") as f:
            return f.read()
    if not url:
        raise ValueError(
            "EHR bulk URL puudub: anonüümset hulgilaadimise URL-i pole "
            "kinnitatud (dated negative 2026-09-13) — anna ette "
            "värava ekspordi URL või kasuta vahemälu")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = resp.read()
    text = body.decode("utf-8-sig")
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------------------
# Parsing: EHR bulk-report layout (semicolon-separated, BOM-tolerant).
# Column names follow the documented export; unknown columns are ignored,
# missing columns read as None (never guessed).
# ---------------------------------------------------------------------------

#: Canonical record keys produced by parse_ehr_buildings (all Optional).
EHR_FIELDS = (
    "ehr_code", "address", "kov", "net_area_m2", "floors_total",
    "has_lift", "elevator_count", "build_year", "energy_class",
    "permits_open", "permits_finalized", "unpermitted_works",
    "warranty_valid", "builder",
)

_INT_FIELDS = ("floors_total", "elevator_count", "build_year",
               "permits_open", "permits_finalized")

_FLOAT_FIELDS = ("net_area_m2",)

_BOOL_FIELDS = ("has_lift", "unpermitted_works", "warranty_valid")

_TRUTHY = ("jah", "yes", "true", "1", "olemas")
_FALSY = ("ei", "no", "false", "0", "puudub")


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


def _to_float(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip().replace(" ", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_bool(raw: Optional[str]) -> Optional[bool]:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    if s in _TRUTHY:
        return True
    if s in _FALSY:
        return False
    return None


def parse_ehr_buildings(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse one EHR bulk report into canonical per-building records.

    Semicolon-separated, BOM-tolerant; empty cells and absent columns
    become None. Rows without an ehr_code are skipped (no join key —
    keeping them would fake join coverage).
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        code = (row.get("ehr_code") or "").strip()
        if not code:
            continue
        rec = {"ehr_code": code}  # type: Dict[str, Optional[object]]
        for field in EHR_FIELDS:
            if field == "ehr_code":
                continue
            raw = row.get(field)
            if field in _INT_FIELDS:
                rec[field] = _to_int(raw)
            elif field in _FLOAT_FIELDS:
                rec[field] = _to_float(raw)
            elif field in _BOOL_FIELDS:
                rec[field] = _to_bool(raw)
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


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _rec(ehr: Optional[dict]) -> Optional[dict]:
    return ehr if isinstance(ehr, dict) else None


def _lst(listing: Optional[dict]) -> dict:
    return listing if isinstance(listing, dict) else {}


def _missing_ehr() -> Score:
    return None, ("EHR kirje puudub — ehitisregistri hulgilaadungita skoori "
                  "EI OLE (hinnangut ei anta): kontrolli ehr_code järgi "
                  "livekluster.ehr.ee-st")


def _norm(value: Optional[object]) -> str:
    return "" if value is None else str(value).strip().lower()


# ---------------------------------------------------------------------------
# Listing enrichment (p21/p33/p35): EHR facts fill listing gaps.
# The listing's own value always wins; provenance is recorded per field.
# ---------------------------------------------------------------------------

#: Enriched field -> owning G2 param id.
ENRICH_PARAM_IDS = {
    "building_net_area_m2": 21,
    "build_year": 33,
    "building_age_years": 33,
    "energy_class": 35,
}


def enrich_listing_from_ehr(
        listing: Optional[dict], ehr: Optional[dict],
        ref_year: Optional[int] = None) -> Tuple[dict, Dict[str, str]]:
    """Enrich one listing record from its joined EHR building record.

    Returns (enriched_listing, provenance): enriched_listing is a COPY of
    the listing with gaps filled (never mutates the input); provenance
    maps each filled field to its EHR source note. Listing values always
    win — EHR only fills missing/blank fields. No EHR record (or no EHR
    fact) leaves the listing untouched: enrichment adds facts, never
    guesses.
    """
    out = dict(_lst(listing))
    prov = {}  # type: Dict[str, str]
    rec = _rec(ehr)
    if rec is None:
        return out, prov
    code = rec.get("ehr_code")

    def _fill(field: str, value: Optional[object], note: str) -> None:
        if value is None:
            return
        cur = out.get(field)
        if cur is not None and str(cur).strip() != "":
            return
        out[field] = value
        prov[field] = note

    # p21: BUILDING net area as buyer context — never the flat's area_m2.
    area = rec.get("net_area_m2")
    if isinstance(area, (int, float)) and area > 0:
        _fill("building_net_area_m2", float(area),
              "EHR hulgilaadung, ehr_code %s (hoone, mitte korteri pind)"
              % code)
    # p33: build year + derived age (taste axis — fact, never a score).
    year = rec.get("build_year")
    if isinstance(year, int) and year > 0:
        _fill("build_year", year,
              "EHR hulgilaadung, ehr_code %s" % code)
        if ref_year is None:
            ref_year = datetime.date.today().year
        if ref_year >= year:
            _fill("building_age_years", ref_year - year,
                  "EHR ehitusaastast arvutatud (hinnanguta vanus, maitse-telg)")
    # p35: energy class — scoring stays with group02 dim_energy.
    energy = rec.get("energy_class")
    if isinstance(energy, str) and energy.strip():
        _fill("energy_class", energy.strip().upper(),
              "EHR hulgilaadung, ehr_code %s" % code)
    return out, prov


# ---------------------------------------------------------------------------
# p30: accessibility (stories) — EHR lift fills the listing gap, walk-up
# bands mirror dims_group02 (same judgment, one place to converge).
# ---------------------------------------------------------------------------

#: Walk-up floor (2+) without a lift -> score (judgment call, mirrors
#: dims_group02.WALKUP_FLOOR_SCORE — converge at integration).
WALKUP_FLOOR_SCORE = {2: 80, 3: 60, 4: 40}


def dim_accessibility_p30(ehr: Optional[dict],
                          listing: Optional[dict] = None) -> Score:
    """p30: step-free access — EHR lift status + listing floor."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    lst = _lst(listing)
    lift = rec.get("has_lift")
    if lift is None:
        count = rec.get("elevator_count")
        if isinstance(count, int):
            lift = count >= 1
    lst_lift = lst.get("has_lift")
    eff_lift = lst_lift if isinstance(lst_lift, bool) else lift
    if eff_lift is True:
        return (100, "Lift olemas (EHR hulgilaadung, ehr_code %s) — "
                     "ligipääs tagatud" % rec.get("ehr_code"))
    floor = lst.get("floor")
    if floor is None:
        return None, ("Korruse info puudub (EI OLE hinnangut): EHR kirjes "
                      "lifti pole ja kuulutuse korrus teadmata — kontrolli "
                      "kuulutusest")
    try:
        f = int(floor)
    except (TypeError, ValueError):
        return None, ("Korruse info puudub (EI OLE hinnangut): EHR kirjes "
                      "lifti pole ja kuulutuse korrus teadmata — kontrolli "
                      "kuulutusest")
    if f < 1:
        return None, ("Korruse info puudub (EI OLE hinnangut): tundmatu "
                      "korruse-number, lifti EHR kirjes pole")
    if f == 1:
        return (100, "1. korrus — trepivaba ligipääs (kuulutuse andmed; "
                     "EHR kirjes lifti pole)")
    if eff_lift is None:
        # Floor known above ground, lift unknown on both sides: assuming a
        # lift would fake step-free access (dims_group02 precedent).
        return None, ("Lifti info puudub (EI OLE hinnangut): ei kuulutuses "
                      "ega EHR kirjes — kontrolli kohapeal")
    if f in WALKUP_FLOOR_SCORE:
        return (WALKUP_FLOOR_SCORE[f],
                "%d. korrus ilma liftita (EHR hulgilaadung + kuulutuse "
                "korrus): ligipääs piiratud (hinnang)" % f)
    return (25, "%d. korrus ilma liftita (EHR hulgilaadung + kuulutuse "
                "korrus): ligipääs piiratud (hinnang)" % f)


# ---------------------------------------------------------------------------
# p48: permit history — status derived from bulk permit counts.
# ---------------------------------------------------------------------------

def dim_permit_status_p48(ehr: Optional[dict],
                          listing: Optional[dict] = None) -> Score:
    """p48: permit status from the joined bulk record (clean/flagged)."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    if rec.get("unpermitted_works") is True:
        return (0, "Loata ehitis/ümberehitus kirjas (EHR hulgilaadung, "
                   "ehr_code %s)" % rec.get("ehr_code"))
    open_n = rec.get("permits_open")
    done = rec.get("permits_finalized")
    if isinstance(open_n, int) and open_n > 0:
        return (20, "EHR hulgilaadung: %d avatud luba (ehr_code %s) — "
                    "loaloos märge, kontrolli ehitisregistrist"
                % (open_n, rec.get("ehr_code")))
    if isinstance(open_n, int) and isinstance(done, int):
        if done >= 1:
            return (100, "Load korras (EHR hulgilaadung: %d lõpetatud luba, "
                         "avatud lube pole, ehr_code %s)"
                    % (done, rec.get("ehr_code")))
        # Present-but-empty record: old stock predates digital records —
        # absence is not evidence, never "clean".
        return None, ("Loaajaloo info puudub (EI OLE hinnangut): EHR kirjes "
                      "lube pole — vanem hoone võib digiajastust varasem "
                      "olla, kontrolli livekluster.ehr.ee-st")
    return None, ("Loaajaloo info puudub (EI OLE hinnangut): EHR kirjes "
                  "loa-arve pole — kontrolli livekluster.ehr.ee-st")


# ---------------------------------------------------------------------------
# p79: building permit history (finalized-permit count = transparency).
# Bulk-record twin of dims_group02b.dim_permit_history: same bands,
# distinct hulgilaadung reasons proving the join wiring.
# ---------------------------------------------------------------------------

def dim_permit_history_p79(ehr: Optional[dict],
                           listing: Optional[dict] = None) -> Score:
    """p79: transparency of the building's bulk-joined permit history."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    done = rec.get("permits_finalized")
    if not isinstance(done, int):
        return None, ("Ehitusloa ajaloo info puudub (EI OLE hinnangut): EHR "
                      "hulgilaadungis lõpetatud lubade arvu pole")
    if done >= 2:
        return (85, "EHR hulgilaadung: lõpetatud ehituslubasid vähemalt 2 "
                    "(läbipaistev ehituslugu)")
    if done == 1:
        return 70, "EHR hulgilaadung: 1 lõpetatud ehitusluba"
    return (45, "EHR hulgilaadung: lõpetatud ehituslubasid pole kirjas "
                "(nõrk ehituslugu, mitte rikkumine)")


# ---------------------------------------------------------------------------
# p154: builder warranties — explicit field only, never derived from age.
# ---------------------------------------------------------------------------

def dim_warranty_p154(ehr: Optional[dict],
                      listing: Optional[dict] = None) -> Score:
    """p154: whether a builder warranty currently covers the flat."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    valid = rec.get("warranty_valid")
    if valid is None:
        return None, ("Ehitaja garantii info puudub (EI OLE hinnangut): EHR "
                      "hulgilaadungis garantiivälja pole — vanusest ei "
                      "tuletata, kontrolli KÜ dokumentidest")
    if valid is True:
        return 90, "EHR hulgilaadung: ehitusgarantii kehtib"
    if valid is False:
        return 50, "EHR hulgilaadung: ehitusgarantii on lõppenud"
    return None, ("Ehitaja garantii info puudub (EI OLE hinnangut): "
                  "tundmatu garantiiväärtus EHR kirjes")


# ---------------------------------------------------------------------------
# p495: unpermitted sunroom addition (violation on record = red).
# ---------------------------------------------------------------------------

def dim_sunroom_p495(ehr: Optional[dict],
                     listing: Optional[dict] = None) -> Score:
    """p495: unpermitted works (sunroom/glazing or similar) on record."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    works = rec.get("unpermitted_works")
    if works is None:
        return None, ("Loata ehitiste info puudub (EI OLE hinnangut): EHR "
                      "hulgilaadungis vastavat välja pole")
    if works is True:
        return (20, "EHR hulgilaadung: kirjas loata ehitis "
                    "(päikesevarjund/klaasveranda vms)")
    if works is False:
        return 85, "EHR hulgilaadung: loata ehitisi pole kirjas"
    return None, ("Loata ehitiste info puudub (EI OLE hinnangut): "
                  "tundmatu väärtus EHR kirjes")


#: Registry for UI/API wiring on integration: field -> (param id, fn).
#: p21/p33/p35 enrich (no score — filter/taste/deferred-band verdicts
#: stand); p30/p48/p79/p154/p495 score per-code facts.
OVERTURN_DIMS = (
    ("accessibility_p30", 30, dim_accessibility_p30),
    ("permit_status_p48", 48, dim_permit_status_p48),
    ("permit_history_p79", 79, dim_permit_history_p79),
    ("warranty_p154", 154, dim_warranty_p154),
    ("sunroom_p495", 495, dim_sunroom_p495),
)

#: Enrichment fields (p21/p33/p35) for the integration follow-up.
OVERTURN_ENRICH_FIELDS = (
    ("building_net_area_m2", 21),
    ("build_year", 33),
    ("building_age_years", 33),
    ("energy_class", 35),
)


def score_overturn_ehr(ehr: Optional[dict], listing: Optional[dict] = None
                       ) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All five overturn score dims at once: ({field: score}, [reasons]).

    ehr is one listing's bulk-joined EHR record (or None while the
    pipeline has no EHR data — every dim then stays None, never faked).
    """
    dims = {}  # type: Dict[str, Optional[int]]
    reasons = []  # type: List[str]
    for field, _param, fn in OVERTURN_DIMS:
        v, reason = fn(ehr, listing)
        dims[field] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
