"""P4 ppa dims (issues #278 demo + #352 coverage): PPA open-data ingestion +
two honest-shape choropleth dims off the same source family.

Demo param (this ingestion's anchor):
* P4-012 Traffic-accident blackspots + rescue drive-time -> dim_traffic_supervision
  (PPA leg only: traffic-supervision intensity per linnaosa)

Coverage param (extends the demoed ingestion, no new plumbing):
* P4-015 Insurability: flood/theft tariff zones -> dim_theft_tariff_proxy
  (PPA leg only: property-offence volume per linnaosa)

OPENNESS VERDICT (checked 2026-09-13, six polite single GETs with a probe
UA, `--max-time 20`, no retries, 2 s pacing, /tmp/hf-ppa-cache kept for
the PR record, never committed; full evidence in docs/p4_ppa.md):
* OPEN (keyless, machine-readable, CC BY-SA 3.0, weekly Thursday refresh):
  the PPA open-data guide
  ``https://www.politsei.ee/et/juhend/politseitoeoega-seotud-avaandmed``
  (HTTP 200, human HTML) names per-dataset sub-pages, and the two
  P4-relevant sub-pages link straight to CSV dumps on opendata.smit.ee:
  ``liiklusjarelevalve_{1,2,3}.csv`` (traffic-supervision offences;
  _1 = this + last year, observed 56 012 549 B) and ``vara_{1,2,3}.csv``
  (property offences; _1 observed 10 519 355 B). Both feeds verified
  keyless (HEAD 200, Last-Modified Thu 2026-09-10, Accept-Ranges) and a
  4 KB ranged peek of each shows TAB-separated quoted rows with
  ``ValdLinnNimetus``/``KohtNimetus`` geography down to Tallinna
  linnaosa (e.g. "Põhja-Tallinna linnaosa", "Lasnamäe linnaosa") plus
  L-EST 500 m grid bins (``Lest_X``/``Lest_Y``) and fresh September 2026
  dates. TSV despite the .csv suffix (stated, not assumed).
* OPEN but human-only (cited, not ingested):
  ``/et/statistika`` hub (HTTP 200) redirects the two official legs
  elsewhere by its own text - crime stats to Justiitsministeerium,
  accident stats to Transpordiamet - and
  ``/et/politseis-registreeritud-oeoepaeeva-suendmused`` carries daily
  human summaries with no machine feed. Neither is pulled by the adapter.
* DATED NEGATIVE (keeps verdict): no per-linnaosa machine feed beyond
  the two CSV families above (no JSON API, no precinct polygons); the
  linnaosa join therefore runs on file _1 (current window), never on a
  live query.

HONESTY (AGENTS.md section 7.2): the CSVs count DETECTED offences, not
danger. The P4-012 leg scores supervision intensity (weak, compressed
bands, direction-ambiguous by design - more detections can mean busier
roads or stricter enforcement) and every reason says so ("järelevalve
aktiivsus, mitte ristmiku ohu tõend"); the P4-015 leg scores theft
volume as a tariff proxy with the same bands as the paaste fire slice
(70/50/25) and an illiquidity flag on the top third. Both dims say
"hinnang"; every NULL reason says "EI OLE" and names the missing table
plus the concrete buyer-side check. Transport errors are never cached
as data (fetch raises, cache untouched); HTTP 429 is a stop signal.
Bodies without the expected header token are refused, never cached.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_ppa_snapshot(kind, cache_dir, ttl_s): polite pull of the _1 CSV
  for "traffic"/"theft" (weekly TTL - source refreshes Thursdays, so at
  most one live pull/week; 30 s timeout, single attempt, no retries).
  Network lives ONLY here; scorers and default tests never touch it.
* parse_ppa_snapshot(text, kind): pure offline reader over the cached
  payload (TAB-separated, UTF-8, header-pinned). Filters Tallinn rows
  (``ValdLinnNimetus == "Tallinn"``), normalises linnaosa names, counts
  rows per linnaosa. Empty payload reads as empty counts (never an
  error); a header without the geography columns raises ValueError so a
  silent schema change fails visibly in cron logs instead of quietly
  NULLing the city.
* The linnaosa join uses the CSV's own place names, NOT the L-EST grid
  bins: no L-EST97 -> WGS84 projection step is needed (unlike the trans
  accident points, #275/#349), and no coordinates are faked from bins.

Style mirrors services/scoring/dims_p4_paaste.py (#276/#350) and
dims_p4_trans.py (#275/#349): pure scorers
(origin, pois, coverage=None) -> (Optional[int 0..100], Estonian
reason), local helpers (no livability import - importing it here would
turn the future central hook into a cycle, same precedent as PRs
#100/#106/#115). The pois argument is accepted for central-hook shape
compatibility and ignored: PPA data is a linnaosa table, and stuffing
it into OSM POIs would abuse the POI channel (same call as paaste).
No Overpass fragment is staged: positions arrive via the CSV join, not
via snapshot tags. Coverage keys are ppa_-prefixed so the central hook
can carry the trans/paaste slices alongside without collision.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #352's body states it
  "extends the demoed ingestion ... no new plumbing expected": the theft
  dim reuses fetch/parse plus the tertile shape, reading its own CSV
  family and coverage key - no second source is pulled.
* Per-source slices, not full params (trans #408 precedent, distinct
  dim keys throughout so the central hook can weight slices
  independently): P4-012 keeps the trans casualty-buffer slice
  (dim_accident_blackspots) and the paaste komando slice; this module
  adds only the PPA supervision leg. P4-015 keeps the paaste fire
  slice; this module adds only the PPA theft leg. Flood/insurer-tariff
  legs stay EI OLE in every reason here.
* Relative tertiles, never absolute bands: with only a 4 KB schema peek
  (never a full-file calibration pull - polite automation, AGENTS.md
  7.4), absolute count thresholds would be fake precision. Each dim
  ranks the coverage table's linnaosad by (count, name) and bands the
  thirds (p*3<n -> madal, p*3<2n -> keskmine, else korge); the reason
  prints count + rank + base size so the comparison is checkable. A
  one-linnaosa table scores neutral keskmine with a "võrdlusbaas üks
  linnaosa" note (no comparison exists); unknown linnaosa reads None.
* Traffic bands are compressed (60/50/40, +/-10 around neutral): the
  direction is ambiguous, so the signal is deliberately weak. Theft
  bands (70/50/25) mirror the paaste P4-015 fire slice - same param,
  same scale, different leg.
* Only the two observed genitives are mapped (Põhja-Tallinna ->
  Põhja-Tallinn, Kesklinna -> Kesklinn); other stems pass through
  unchanged and MUST be revisited against the first full pull
  (docs/p4_ppa.md checklist) - same honesty as the trans codelist note.
* The 56 MB traffic _1 file is pulled whole by the weekly cron (the
  source offers no slice endpoint); streaming-parse is an explicit
  first-pull optimisation, not done here.

Integration (deliberately NOT done here): the weekly-cron snapshotter,
any livability hook, and rebalancing livability.WEIGHTS must be one
joint change across all parameter batches - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. No shared files touched: 3 new files only.
"""

import csv
import os
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source identity, politeness, cache.
# ---------------------------------------------------------------------------

#: Current-window CSVs (file _1 = this + last year per the dataset pages;
#: verified 2026-09-13: HEAD 200, Last-Modified Thu 2026-09-10).
PPA_TRAFFIC_CSV_URL = "https://opendata.smit.ee/ppa/csv/liiklusjarelevalve_1.csv"
PPA_THEFT_CSV_URL = "https://opendata.smit.ee/ppa/csv/vara_1.csv"
#: Human hub + open-data guide (reference only, never pulled here).
PPA_STATS_URL = "https://www.politsei.ee/et/statistika"
PPA_AVAANDMED_URL = (
    "https://www.politsei.ee/et/juhend/politseitoeoega-seotud-avaandmed"
)
PPA_DATASETS = {
    "traffic": PPA_TRAFFIC_CSV_URL,
    "theft": PPA_THEFT_CSV_URL,
}
PPA_USER_AGENT = (
    "home-finder-p4-ppa/1.0 (Estonia open-data weekly adapter; "
    "polite single-pull, cache-first)"
)
#: Source refreshes Thursdays (page text + Last-Modified header agree):
#: at most one live pull per week, cache wins inside the TTL.
PPA_CACHE_TTL_S = 7 * 86400
PPA_CACHE_NAMES = {
    "traffic": "ppa-liiklusjarelevalve_1.csv",
    "theft": "ppa-vara_1.csv",
}
#: Geography columns the parser pins (header must carry both).
PPA_PLACE_COLUMNS = ("ValdLinnNimetus", "KohtNimetus")
#: Only the two genitives observed in the 2026-09-13 peek are mapped;
#: every other stem passes through unchanged (see module docstring).
PPA_GENITIVE_FIX = {
    "Põhja-Tallinna": "Põhja-Tallinn",
    "Kesklinna": "Kesklinn",
}
PPA_LINNAOSA_SUFFIX = " linnaosa"

#: Relative-tertile score bands (see module docstring for rationale).
TRAFFIC_BANDS = {"madal": 60, "keskmine": 50, "korge": 40}
THEFT_BANDS = {"madal": 70, "keskmine": 50, "korge": 25}
KOLMANDIK_ET = {"madal": "alumine", "keskmine": "keskmine",
                "korge": "ülemine"}


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------

def _coverage(coverage: Optional[dict]) -> dict:
    return coverage if isinstance(coverage, dict) else {}


def normalize_linnaosa(raw: Optional[str]) -> str:
    """Normalise a CSV KohtNimetus value to a linnaosa key (pure).

    Strips whitespace and the " linnaosa" suffix, then applies the two
    observed genitive fixes. Unknown stems pass through unchanged -
    never guessed (matching stays exact on both sides via this helper).
    """
    if not isinstance(raw, str):
        return ""
    stem = raw.strip().strip('"').strip()
    if stem.endswith(PPA_LINNAOSA_SUFFIX):
        stem = stem[: -len(PPA_LINNAOSA_SUFFIX)].strip()
    return PPA_GENITIVE_FIX.get(stem, stem)


def _tertile_band(linnaosa: Optional[str],
                  counts: Optional[dict]) -> Optional[Tuple[str, int, int]]:
    """Rank a linnaosa inside a count table into thirds (pure).

    Sorts (count asc, name asc); returns (band, rank1, n) with
    p*3<n -> "madal", p*3<2n -> "keskmine", else "korge". A
    single-linnaosa table reads neutral "keskmine" (no comparison
    exists); missing linnaosa or an empty table reads None.
    """
    if not linnaosa or not isinstance(counts, dict) or not counts:
        return None
    ordered = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]))
    names = [name for name, _ in ordered]
    if linnaosa not in counts:
        return None
    n = len(ordered)
    rank0 = names.index(linnaosa)
    if n == 1:
        return ("keskmine", 1, 1)
    if rank0 * 3 < n:
        return ("madal", rank0 + 1, n)
    if rank0 * 3 < 2 * n:
        return ("keskmine", rank0 + 1, n)
    return ("korge", rank0 + 1, n)


# ---------------------------------------------------------------------------
# Ingestion: polite cached pull (live path, NOT unit-run) + pure parse.
# ---------------------------------------------------------------------------

def _cache_path(cache_dir: str, kind: str) -> str:
    return os.path.join(cache_dir, PPA_CACHE_NAMES[kind])


def fetch_ppa_snapshot(
    kind: str,
    cache_dir: Optional[str] = None,
    ttl_s: int = PPA_CACHE_TTL_S,
) -> Tuple[str, str]:
    """Polite cached pull of one PPA _1 CSV (live path, NOT unit-run).

    Cache wins inside the TTL; on a live pull any transport error
    (HTTP error, timeout, 429, decode failure, unexpected body shape)
    raises and the cache file is left untouched - transport errors are
    never cached as data, and 429 stops the run. Returns (text,
    provenance) with provenance "cache" or "live".
    """
    if kind not in PPA_DATASETS:
        raise ValueError(
            "tundmatu PPA andmestik %r (lubatud: %s)"
            % (kind, ", ".join(sorted(PPA_DATASETS)))
        )
    if cache_dir is None:
        cache_dir = os.path.join("/tmp", "hf-ppa-cache")
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, kind)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl_s:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(), "cache"
    req = urllib.request.Request(
        PPA_DATASETS[kind], headers={"User-Agent": PPA_USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", None) or 200
            if status == 429:
                raise RuntimeError("PPA vastas 429 - peatu, ära reetry")
            if status != 200:
                raise RuntimeError(
                    "PPA vastas HTTP %s - vahemälu puutumata" % status
                )
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RuntimeError("PPA vastas 429 - peatu, ära reetry")
        raise RuntimeError(
            "PPA vastas HTTP %s - vahemälu puutumata" % exc.code
        )
    if "KohtNimetus" not in body:
        raise RuntimeError(
            "PPA vastas ootamatu vorminguga (KohtNimetus puudub) - "
            "vahemälu puutumata"
        )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return body, "live"


def parse_ppa_snapshot(text: str, kind: str) -> dict:
    """Parse one PPA CSV payload into per-linnaosa counts (pure).

    The payloads are TAB-separated despite the .csv suffix. Only rows
    with ValdLinnNimetus == "Tallinn" and a non-empty KohtNimetus are
    counted (keyed by normalize_linnaosa); everything else lands in
    skipped_rows, never guessed. An empty payload reads as explicitly
    empty counts (dated-negative friendly), never an error; a header
    without the geography columns raises ValueError so a schema change
    fails visibly instead of quietly NULLing the city.
    """
    if kind not in PPA_DATASETS:
        raise ValueError(
            "tundmatu PPA andmestik %r (lubatud: %s)"
            % (kind, ", ".join(sorted(PPA_DATASETS)))
        )
    counts: Dict[str, int] = {}
    tallinn_rows = 0
    skipped = 0
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return {"kind": kind, "counts": counts, "tallinn_rows": 0,
                "skipped_rows": 0,
                "source": "PPA avaandmed (opendata.smit.ee), CC BY-SA 3.0"}
    reader = csv.reader(lines, delimiter="\t")
    header = [cell.strip() for cell in next(reader)]
    try:
        city_i = header.index("ValdLinnNimetus")
        place_i = header.index("KohtNimetus")
    except ValueError:
        raise ValueError(
            "PPA %s päisest puuduvad kohaveerud %s (skeem muutus?)"
            % (kind, "/".join(PPA_PLACE_COLUMNS))
        )
    for row in reader:
        if len(row) <= max(city_i, place_i):
            skipped += 1
            continue
        if row[city_i].strip() != "Tallinn":
            continue
        key = normalize_linnaosa(row[place_i])
        if not key:
            skipped += 1
            continue
        tallinn_rows += 1
        counts[key] = counts.get(key, 0) + 1
    return {"kind": kind, "counts": counts, "tallinn_rows": tallinn_rows,
            "skipped_rows": skipped,
            "source": "PPA avaandmed (opendata.smit.ee), CC BY-SA 3.0"}


# ---------------------------------------------------------------------------
# P4-012 (demo): traffic-supervision intensity per linnaosa (PPA leg).
# ---------------------------------------------------------------------------

def dim_traffic_supervision(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]],
                            coverage: Optional[dict] = None) -> Score:
    """P4-012: PPA supervision-count tertile (weak activity proxy)."""
    cov = _coverage(coverage)
    linnaosa = cov.get("linnaosa")
    counts = cov.get("ppa_traffic_counts") or {}
    ranked = _tertile_band(linnaosa, counts)
    if ranked is None:
        return None, ("Liiklusjärelevalve tase teadmata (EI OLE hinnangut): "
                      "linnaosa rikkumisloendustabelit hetktõmmises pole - "
                      "PPA avaandmete liiklusfail on töötlemata; "
                      "Transpordiameti õnnetuspunktid ja Tark Tee "
                      "intsidendid on liitmata, hinda ristmikku kohapeal")
    band, rank1, n = ranked
    base_txt = "; võrdlusbaas üks linnaosa" if n == 1 else ""
    return TRAFFIC_BANDS[band], (
        "PPA liiklusjärelevalve hinnang linnaosas %s: %d avastatud "
        "rikkumist failiaknas (%s kolmandik, %d. koht %d linnaosast%s - "
        "järelevalve aktiivsus, mitte ristmiku ohu tõend): "
        "Transpordiameti õnnetuspunktid ja Tark Tee intsidendid on "
        "liitmata" % (linnaosa, counts[linnaosa], KOLMANDIK_ET[band],
                      rank1, n, base_txt))


# ---------------------------------------------------------------------------
# P4-015 (coverage): property-offence volume per linnaosa (PPA theft leg).
# ---------------------------------------------------------------------------

def dim_theft_tariff_proxy(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]],
                           coverage: Optional[dict] = None) -> Score:
    """P4-015: PPA theft-count tertile + illiquidity flag on top third."""
    cov = _coverage(coverage)
    linnaosa = cov.get("linnaosa")
    counts = cov.get("ppa_theft_counts") or {}
    ranked = _tertile_band(linnaosa, counts)
    if ranked is None:
        return None, ("Kindlustatavus (varguse jalg) teadmata (EI OLE "
                      "hinnangut): linnaosa vargusloendustabelit "
                      "hetktõmmises pole - PPA avaandmete varafail on "
                      "töötlemata; PZU/ERGO/If tariifitsoonid ja "
                      "üleujutusjalg on liitmata, küsi pakkumist "
                      "kindlustusandjalt")
    band, rank1, n = ranked
    base_txt = "; võrdlusbaas üks linnaosa" if n == 1 else ""
    if band == "korge":
        return THEFT_BANDS[band], (
            "PPA vargusstatistika hinnang linnaosas %s: %d juhtumit "
            "failiaknas (ÜLEMINE kolmandik, %d. koht %d linnaosast%s - "
            "kindlustus-keeldumise / hinnatõusu risk, "
            "mittelikviidsuse lipp): uuri kindlustuspakkumist enne "
            "broneerimist; üleujutusjalg ja tariif on liitmata"
            % (linnaosa, counts[linnaosa], rank1, n, base_txt))
    return THEFT_BANDS[band], (
        "PPA vargusstatistika hinnang linnaosas %s: %d juhtumit "
        "failiaknas (%s kolmandik, %d. koht %d linnaosast%s - ainult "
        "varguse jalg, mitte tariif): üleujutusjalg ja "
        "kindlustustariif on liitmata, küsi pakkumist "
        "kindlustusandjalt" % (linnaosa, counts[linnaosa],
                               KOLMANDIK_ET[band], rank1, n, base_txt))


#: Registry for UI/API wiring on integration: key -> (param id, title, fn).
P4PPA_DIMS = {
    "traffic_supervision": ("P4-012", "Liiklusjärelevalve (PPA)",
                            dim_traffic_supervision),
    "theft_tariff": ("P4-015", "Kindlustatavus (varguse jalg, PPA)",
                      dim_theft_tariff_proxy),
}

#: Param-number wiring for the central weight-rebalance follow-up.
P4PPA_PARAM_IDS = {
    "traffic_supervision": 12,
    "theft_tariff": 15,
}


def score_p4_ppa(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]],
                 coverage: Optional[dict] = None
                 ) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """Both P4-ppa dims at once: ({key: score}, [reasons]).

    NULL dims contribute no reasons (no fake evidence) - same rollup
    contract as sibling score_p4_paaste.
    """
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for key, (_, _, fn) in P4PPA_DIMS.items():
        v, reason = fn(origin, pois, coverage)
        dims[key] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
