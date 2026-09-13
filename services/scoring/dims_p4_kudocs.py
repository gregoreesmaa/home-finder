"""P4 kudocs demo + coverage dims (issues #258 and #339).

Demo (#258): KÜ dokumendid / otsused / logid ingestion (P4-007 slice)
— polite, cached, TTL-stated pulls of the per-KÜ document bundle plus
honest-shape per-listing join dims. Coverage (#339): the remaining
1 param off this source (P4-047 KÜ kaebuste-logid slice), wired to the
same demoed ingestion.

Params (this agent only — sibling batches own disjoint slices):
* P4-007 KÜ loan + remondifond + kütte EUR/m2 (demo, per-listing dim
  from the KÜ-document slice: haldus/remondifondi otsused).
  Disjoint from dims_p4_own_store.dim_ku_loan, which owns the
  listing-text NLP slice ("remondifond" mention noted, never scored),
  and from the e-Äriregister XBRL bulk (source (1), not this source).
* P4-047 small horrors calendar (coverage, KÜ kaebuste-logid slice:
  per-listing dim from the 12-month complaint count).
  Disjoint from dims_p4_osm.dim_horrors, which owns the OSM
  leisure=noise slice (tag does not exist -> always NULL there).

HONESTY (AGENTS.md section 7.2): KÜ general-meeting decisions and
complaint logs are per-association private by construction — each KÜ
keeps its own gated management portal, and no anonymous public bulk
exists (dated negative below). Every dim returns None when its KÜ
slice is missing — never a guess. Scored reasons always say "KÜ
dokumendid"/"kaebuste logi" (traceable to a joined bundle record);
NULL reasons say EI OLE and name the buyer-side check (küsi KÜ-lt /
müüjalt protokolli). NULL stays NULL with an Estonian reason.

Openness verdict (2026-09-13, dated probes, cache /tmp/hf-kudocs):
* https://ariregister.rik.ee/ -> 200 -> /est, 80541 bytes, title
  "Juriidilise isiku otsing | e-Äriregister" — the company-search
  portal is reachable, but KÜ üldkoosoleku protokollid/otsused are
  NOT filed with the register (only annual reports are); decisions
  live in each KÜ's own gated portal.
* https://andmed.eesti.ee/api/3/action/package_search?q=korteriyhistu
  -> HTTP 404 "Cannot GET" — national portal has no CKAN API
  (same finding as the EHR #249 probe); no KÜ-docs dataset.
* https://avaandmed.rik.ee/ -> HTTP 200 with Content-Length: 0 —
  empty shell, no usable bulk listing.
Dated negative keeps the verdict: KÜ dokumendid/otsused/logid are
PRIVATE-per-association (gated). Probing any single KÜ's management
portal without a mandate would target a private association, so
politeness stops here: one GET per public endpoint, no per-KÜ pulls.
fetch_kudocs_csv below therefore takes a caller-supplied URL (the
KÜ's published bundle link, or the seller/buyer handoff file staged
at a URL) with a quarterly TTL; the dims score ONLY joined records.
See docs/p4_kudocs.md for the full note.

Style mirrors services/scoring/dims_p4_ehr.py (issue #249): pure
(kudocs, listing) -> (Optional[int 0..100], Estonian reason),
absolute bands, hermetic fixture tests. Network lives only in
fetch_kudocs_csv (single polite GET, file cache, TTL); tests never
call it.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and group20a #212).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR because #339 states it "extends the
  demoed ingestion" with "no new plumbing expected" — splitting
  would ship a one-consumer ingestion, then re-touch every
  signature for the second consumer.
* Pairing rationale: both params consume the SAME per-KÜ bundle
  (otsused + kaebuste logi keyed by ku_code). P4-007 reads the
  finance slice (laen, remondifond, küte — source (2) of its source
  list); P4-047 reads the complaint slice (source (6) of its source
  list). One ingestion, two disjoint slices, no overlap with the
  OSM or listing-text slices owned elsewhere.
* P4-007 bands are 70/60/35, never 100 or 0: KÜ docs alone never
  prove a healthy HOA (the audited annual-report bulk is source
  (1)'s job), and an active renovation loan is normal, not
  disqualifying. No-loan + accumulating fund is weak-good (70);
  loan-free on a thin file is neutral-good (60); unknown loan with
  a known fund is weak-good with the gap stated (60); an active
  loan is weak-bad (35). Heating EUR/m2 is echoed as context, never
  scored alone — the January-bill tariff zone is P4-008's job.
* Täitmata haldusotsused (decisions_open > 0) are echoed in P4-007
  reasons: unexecuted renovation decisions are the "5-figure bill
  coming" signal this source uniquely carries beyond XBRL numbers.
* P4-047 bands are 75/60/40, never 0: a complaint count is building
  signal, not a dealbreaker verdict, and the bundle carries no
  dates — the "calendar" shape stays capped until dated logs exist.
  Individual complaints are never named (hex-only aggregation in
  map layers; the dim reads counts, not names).
* Negative complaints_12m is invalid bundle data -> NULL, not 0:
  clamping it to "quiet building" would bless a corrupt file.

Integration (deliberately NOT done here): feeding these dims with
the listing's KÜ record inside livability scoring and rebalancing
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
# Ingestion: polite, cached, TTL-stated per-KÜ bundle pulls.
# ---------------------------------------------------------------------------

#: Quarterly re-check per parameters4.md P4-007 ("annual + quarterly
#: refresh"): KÜ decisions change at general meetings, so a joined
#: bundle older than this needs a fresh seller/KÜ handoff.
KUDOCS_TTL_DAYS = 90

USER_AGENT = ("home-finder kudocs ingest (polite quarterly pull, single GET, "
              "file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str, name: str) -> str:
    """Cache file for one named KÜ bundle (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)
    return os.path.join(cache_dir, "kudocs-%s.csv" % safe)


def cache_is_fresh(path: str, ttl_days: int = KUDOCS_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_kudocs_csv(name: str, url: str, cache_dir: str = "/tmp/hf-cache",
                     ttl_days: int = KUDOCS_TTL_DAYS) -> str:
    """Fetch one per-KÜ document bundle politely (single GET, cached, TTL).

    There is no anonymous public KÜ-docs bulk (see module docstring),
    so url is caller-supplied: the KÜ's published bundle link, or a
    seller/buyer handoff file staged at a URL. Returns cached text
    when fresh; otherwise one GET with a polite User-Agent and a 30 s
    timeout. Transport errors RAISE (never cached as data, AGENTS.md
    section 7.2); HTTP errors raise too — an error body is never
    written to the cache. Treat HTTP 429 as a stop signal: it
    propagates, the stale cache is left untouched.
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
# Parsing: per-KÜ bundle layout (semicolon-separated, BOM-tolerant).
# One row per KÜ: finance slice (P4-007) + complaint slice (P4-047).
# Unknown columns are kept verbatim, missing columns read as None
# (never guessed).
# ---------------------------------------------------------------------------

#: Canonical record keys produced by parse_kudocs (all Optional).
KUDOCS_FIELDS = (
    "ku_code",
    "address",
    "has_loan",
    "loan_balance_eur",
    "loan_maturity_year",
    "remondifond_eur_m2_month",
    "heating_eur_m2_year",
    "decisions_total",
    "decisions_open",
    "complaints_12m",
    "record_date",
)

_INT_FIELDS = ("loan_balance_eur", "loan_maturity_year",
               "decisions_total", "decisions_open", "complaints_12m")

_FLOAT_FIELDS = ("remondifond_eur_m2_month", "heating_eur_m2_year")

_BOOL_FIELDS = ("has_loan",)

_TRUTHY = ("jah", "yes", "true", "1", "olemas", "kehtib")
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
        value = float(s)
    except ValueError:
        return None
    return value


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


def parse_kudocs(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse one per-KÜ bundle into canonical records.

    Semicolon-separated, BOM-tolerant; empty cells and absent columns
    become None. Rows without a ku_code are skipped (no join key —
    keeping them would fake join coverage).
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        code = (row.get("ku_code") or "").strip()
        if not code:
            continue
        rec = {"ku_code": code}  # type: Dict[str, Optional[object]]
        for field in KUDOCS_FIELDS:
            if field == "ku_code":
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


def index_by_ku_code(
        records: List[Dict[str, Optional[object]]]
) -> Dict[str, Dict[str, Optional[object]]]:
    """Per-ku_code join index (first row wins on duplicates)."""
    index = {}  # type: Dict[str, Dict[str, Optional[object]]]
    for rec in records:
        code = rec.get("ku_code")
        if code and code not in index:
            index[code] = rec
    return index


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _rec(kudocs: Optional[dict]) -> Optional[dict]:
    return kudocs if isinstance(kudocs, dict) else None


def _missing_kudocs() -> Score:
    return None, ("KÜ dokumendid puuduvad — selle ühistu otsuste/logideta "
                  "skoori EI OLE (hinnangut ei anta): küsi müüjalt/KÜ-lt "
                  "üldkoosoleku protokolli ja remondifondi väljavõtet")


def _fmt_eur_m2(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return ("%.2f" % value).replace(".", ",")
    return str(value)


def _heating_echo(rec: dict) -> str:
    heat = rec.get("heating_eur_m2_year")
    if isinstance(heat, (int, float)) and not isinstance(heat, bool):
        return ("; kütte kulu %s €/m²/a (KÜ andmed, tariifitsoon on "
                "P4-008 teema)" % _fmt_eur_m2(float(heat)))
    return ""


def _open_decisions_echo(rec: dict) -> str:
    open_n = rec.get("decisions_open")
    if isinstance(open_n, int) and not isinstance(open_n, bool) \
            and open_n > 0:
        return ("; täitmata haldusotsuseid %d (võimalik tulevane arve — "
                "kontrolli protokollist)" % open_n)
    return ""


# ---------------------------------------------------------------------------
# P4-007 (demo): KÜ loan + remondifond + heating — per-listing dim from
# the KÜ-document slice (haldus/remondifondi otsused).
# ---------------------------------------------------------------------------

def dim_ku_finance(kudocs: Optional[dict],
                   listing: Optional[dict] = None) -> Score:
    """P4-007: loan/fund bands from the joined KÜ bundle (70/60/35/NULL)."""
    rec = _rec(kudocs)
    if rec is None:
        return _missing_kudocs()
    has_loan = rec.get("has_loan")
    fund = rec.get("remondifond_eur_m2_month")
    fund_known = (isinstance(fund, (int, float))
                  and not isinstance(fund, bool))
    heat = rec.get("heating_eur_m2_year")
    heat_known = (isinstance(heat, (int, float))
                  and not isinstance(heat, bool))
    if has_loan is True:
        bal = rec.get("loan_balance_eur")
        bal_txt = (", jääk %d €" % bal
                   if isinstance(bal, int) and not isinstance(bal, bool)
                   else "")
        mat = rec.get("loan_maturity_year")
        mat_txt = (" (lõpp %d)" % mat
                   if isinstance(mat, int) and not isinstance(mat, bool)
                   else "")
        return (35, "Kehtiv KÜ laenuotsus%s%s (KÜ dokumendid, mitte "
                    "hinnang) — laenu teenindab kasvanud arve"
                    "%s%s"
                % (bal_txt, mat_txt, _heating_echo(rec),
                   _open_decisions_echo(rec)))
    if has_loan is False:
        if fund_known:
            return (70, "Laenuotsust pole + remondifond koguneb %s €/m²/kuu "
                        "(KÜ dokumendid, mitte hinnang)"
                        "%s%s"
                    % (_fmt_eur_m2(float(fund)), _heating_echo(rec),  # type: ignore[arg-type]
                       _open_decisions_echo(rec)))
        return (60, "Laenuotsust kirjas pole (KÜ dokumendid, mitte hinnang) "
                    "— fondi-infota õhuke toimik, aastaruanne kontrolli "
                    "eraldi%s%s"
                % (_heating_echo(rec), _open_decisions_echo(rec)))
    if fund_known:
        return (60, "Remondifond koguneb %s €/m²/kuu (KÜ dokumendid), aga "
                    "laenuotsus teadmata — EI OLE täishinnangut, protokolli "
                    "kontroll kohustuslik%s%s"
                % (_fmt_eur_m2(float(fund)), _heating_echo(rec),  # type: ignore[arg-type]
                   _open_decisions_echo(rec)))
    if heat_known:
        return None, ("Ainult kütte kulu teada (%s €/m²/a, KÜ dokumendid), "
                      "aga laenu- ja fondiotsus puudub — EI OLE hinnangut: "
                      "küsi müüjalt/KÜ-lt protokolli"
                      % _fmt_eur_m2(float(heat)))
    return None, ("KÜ kirje liitunud, aga laenu-/fondi-/küttekirjeid pole "
                  "(EI OLE hinnangut): dokumendipakett tühi — küsi "
                  "müüjalt/KÜ-lt täielikku protokolli")


# ---------------------------------------------------------------------------
# P4-047 (coverage): small horrors via the KÜ complaint log — per-listing
# dim from the 12-month complaint count (counts only, never names).
# ---------------------------------------------------------------------------

def dim_horrors_ku(kudocs: Optional[dict],
                   listing: Optional[dict] = None) -> Score:
    """P4-047: complaint-log bands (75/60/40/NULL, counts only)."""
    rec = _rec(kudocs)
    if rec is None:
        return None, ("KÜ kaebuste logi puudub — väikeste õuduste (kajaka-/"
                      "lehepuhuri-/lumekoristuse-mured) skoori EI OLE "
                      "(hinnangut ei anta): logi on ühistupõhine, küsi KÜ-lt")
    count = rec.get("complaints_12m")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        return None, ("KÜ kaebuste logi 12 kuu kirjeid pole (EI OLE "
                      "hinnangut): logi puudub või on vigane — küsi KÜ-lt, "
                      "ära feigi vaikset maja")
    if count == 0:
        return (75, "Kaebuste logis 12 kuu jooksul kirjeid pole (KÜ andmed, "
                    "mitte hinnang) — vaikne maja, üksikuid nimesid ei loeta")
    if count <= 3:
        return (60, "Kaebuste logis %d kirjet 12 kuu jooksul (KÜ andmed, "
                    "mitte hinnang) — üksikud mured, kalendrit (kuupäevi) "
                    "logis pole" % count)
    return (40, "Kaebuste logis %d kirjet 12 kuu jooksul (KÜ andmed, mitte "
                "hinnang) — korduvad väikesed õudused; kuupäevadeta logi "
                "kalendrit ei anna, kohapealne külastus eri kellaaegadel "
                "soovitatav" % count)


KUDOCS_DIMS = (
    ("ku_finance", "P4-007", dim_ku_finance),
    ("horrors_ku", "P4-047", dim_horrors_ku),
)


def score_kudocs(kudocs: Optional[dict],
                 listing: Optional[dict] = None) -> Dict[str, Optional[int]]:
    """Both kudocs dims for one listing (entry point for the
    weight-rebalance follow-up; keys match KUDOCS_DIMS)."""
    return {key: fn(kudocs, listing)[0] for key, _, fn in KUDOCS_DIMS}
