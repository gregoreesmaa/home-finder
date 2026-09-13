"""P4 EHIS / HaridusSilm demo + coverage dims (issues #271 and #347).

Demo (#271): EHIS / HaridusSilm ingestion (P4-011) — polite, cached,
TTL-stated pulls of the per-linnaosa school-capacity snapshot table
plus the honest-shape P4-011 dim. Coverage (#347): the remaining
param consuming this source, P4-044, wired to its art/music-school
density slice of the SAME table (no new plumbing).

Params (this agent only — sibling sources own disjoint legs):
* P4-011 Lasteaia queue + perearst open/closed, EHIS slice: Tallinn
  school capacity (schools, pupil places, pupils) + teeninduspiirkond
  note per linnaosa (demo, per-linnaosa table)
* P4-044 Herd of picky people, EHIS slice: Tallinn art/music-school
  (huvikool) density per linnaosa, leading-indicator cross-check
  (coverage, grid taste-match, never worth judgement)

HONESTY (AGENTS.md section 7.2): no anonymous per-linnaosa capacity
bulk URL is verified (see verdict below), so every dim returns None
when its snapshot row/slice is missing — never a guess. Scored
reasons always say "HaridusSilm/EHIS" (traceable to a joined row);
the P4-044 taste-match always says "maitsesobivus" and never reads
as a worth judgement. NULL stays NULL with an Estonian reason.

Openness verdict (2026-09-13, polite probes, cache /tmp/hf-ehis):
* https://www.haridussilm.ee/ -> 301 -> https://haridussilm.ee
  (HTTP 200, 41186 bytes) — "Haridusandmete portaal" JS SPA shell:
  title only, no server-rendered data, no bulk href.
* https://ehis.ee/ -> https://www.ehis.ee/ (HTTP 200, 7815 bytes) —
  register front page: public view ("avalik vaade ... ilma
  kasutajatunnuseta") at https://enda.ehis.ee/avalik/ plus an
  "Avaandmed" entry, and open EENet file-store extracts
  (koolide_kontaktid.xls, oppekavad.xlsx via gituja.eenet.ee).
* https://enda.ehis.ee/avalik/ (HTTP 200, 436 bytes) — "Loading..."
  JS shell only; no anonymous bulk endpoint probed (polite stop).
* https://haridusportaal.edu.ee/kool/kaart (HTTP 200, 66834 bytes) —
  "Koolide kaart" JS SPA shell; school map needs JS, no bulk href.
* HEAD gituja koolide_kontaktid.xls -> HTTP 200
  (application/octet-stream) — register extracts ARE anonymously
  fetchable, but they carry contacts/curricula, NOT per-linnaosa
  capacity. Dated negative keeps the verdict on the capacity bulk.
Verdict: OPEN-partial (register lookups + file-store extracts open;
per-linnaosa capacity table has no verified anonymous bulk), so
fetch_ehis_table below takes an explicit snapshot-pipeline URL with
a quarterly TTL and the dims score ONLY joined rows. See
docs/p4_ehis.md for the full note.

Style mirrors services/scoring/dims_p4_ehr.py (issues #249/#333):
pure (row, listing) -> (Optional[int 0..100], Estonian reason),
absolute bands, hermetic fixture tests. Network lives only in
fetch_ehis_table (single polite GET, file cache, TTL); tests never
call it.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  issue body (#347) states it "extends the demoed ingestion" with
  "no new plumbing expected": P4-044 source (3) is the art/music
  slice of the same per-linnaosa table P4-011 demos, so splitting
  would ship a table with one consumer then re-touch every
  signature (EHR #249/#333, tvesi #263/#343 precedent).
* P4-011 scores ONLY the EHIS school-capacity leg (utilization
  bands, never 0/100): the lasteaia-queue leg belongs to the
  Tallinna Haridusamet demo (#270) and the perearst leg to
  Tervisekassa — both are named as not-joined in every reason, so a
  capacity 75 never reads as "family services fine" (same
  split-slice precedent as P4-020: ATA notices in dims_p4_ata,
  bureau scores NULL in dims_p4_creditinfo).
* Utilization bands are 75/60/45/30: a school at 80% full is calm
  but never "solved" (100), and an over-full school is weak-bad
  (30), never zero — capacity alone never zeroes a neighbourhood.
* P4-044 is capped at 70 and floors at 50 (never 0/100): art-school
  count is a taste-match cross-check for ONE buyer taste, and zero
  art schools in a linnaosa is neutral, not bad. Sibling legs
  (REL2021 occupation grid primary, OSM culture, arireg employers,
  tehingud front) are named as not-joined.
* Queue length, when the snapshot row carries it, is ECHOED inside
  the P4-011 reason as a Haridusamet number — never scored here,
  so fixture tests prove the column wiring without claiming the
  queue leg.

Integration (deliberately NOT done here): feeding these dims with
the listing's linnaosa row inside livability scoring and
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
# Ingestion: polite, cached, TTL-stated EHIS/HaridusSilm pulls.
# ---------------------------------------------------------------------------

#: Quarterly bulk per parameters4.md P4-011 ("TTL: quarterly/annual").
EHIS_TTL_DAYS = 90

#: Verified-open endpoints (2026-09-13 probes, see module docstring).
#: The per-linnaosa capacity table itself has NO verified anonymous
#: bulk URL, so fetch_ehis_table takes an explicit snapshot-pipeline
#: URL — none is defaulted here (no invented feed).
EHIS_PUBLIC_URL = "https://enda.ehis.ee/avalik/"
HARIDUSSILM_URL = "https://haridussilm.ee/"
KOOLIKAART_URL = "https://haridusportaal.edu.ee/kool/kaart"
EHIS_FILESTORE_BASE = "https://gituja.eenet.ee/ehis/ehis1/failihoidla/-/raw/main/"

USER_AGENT = ("home-finder EHIS ingest (polite quarterly bulk, single GET, "
              "file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str, name: str) -> str:
    """Cache file for one named EHIS table (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)
    return os.path.join(cache_dir, "ehis-%s.csv" % safe)


def cache_is_fresh(path: str, ttl_days: int = EHIS_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_ehis_table(name: str, url: str, cache_dir: str = "/tmp/hf-cache",
                     ttl_days: int = EHIS_TTL_DAYS) -> str:
    """Fetch one EHIS/HaridusSilm table politely (single GET, cached, TTL).

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
# Parsing: per-linnaosa snapshot-table layout (semicolon, BOM-tolerant).
# Column names follow the documented snapshot layout; unknown columns
# are ignored, missing/empty cells read as None (never guessed).
# ---------------------------------------------------------------------------

#: Canonical record keys produced by parse_linnaosa_table.
EHIS_FIELDS = (
    "linnaosa", "schools", "pupil_places", "pupils", "queue_len",
    "art_music_schools", "catchment_note",
)

_INT_FIELDS = ("schools", "pupil_places", "pupils", "queue_len",
               "art_music_schools")


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


def parse_linnaosa_table(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse one per-linnaosa snapshot table into canonical records.

    Semicolon-separated, BOM-tolerant; empty cells and absent columns
    become None. Rows without a linnaosa are skipped (no join key —
    keeping them would fake join coverage).
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        district = (row.get("linnaosa") or "").strip()
        if not district:
            continue
        rec = {"linnaosa": district}  # type: Dict[str, Optional[object]]
        for field in EHIS_FIELDS:
            if field == "linnaosa":
                continue
            raw = row.get(field)
            if field in _INT_FIELDS:
                rec[field] = _to_int(raw)
            else:
                s = None if raw is None else str(raw).strip()
                rec[field] = s if s else None
        records.append(rec)
    return records


def _norm_linnaosa(value: Optional[object]) -> str:
    return "" if value is None else str(value).strip().casefold()


def index_by_linnaosa(
        records: List[Dict[str, Optional[object]]]
) -> Dict[str, Dict[str, Optional[object]]]:
    """Per-linnaosa join index (first row wins on duplicates)."""
    index = {}  # type: Dict[str, Dict[str, Optional[object]]]
    for rec in records:
        key = _norm_linnaosa(rec.get("linnaosa"))
        if key and key not in index:
            index[key] = rec
    return index


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _row(linnaosa_row: Optional[dict]) -> Optional[dict]:
    return linnaosa_row if isinstance(linnaosa_row, dict) else None


def _missing_row() -> Score:
    return None, ("HaridusSilm/EHIS linnaosa-rida puudub — koolikohtade "
                  "andmeteta skoori EI OLE (hinnangut ei anta): kontrolli "
                  "koolivõrku Haridusportaali koolikaardilt, lasteaia "
                  "järjekorda Haridusametist ja perearsti Tervisekassast")


def _norm(value: Optional[object]) -> str:
    return "" if value is None else str(value).strip().lower()


# ---------------------------------------------------------------------------
# P4-011 (demo): school-capacity pressure per linnaosa — EHIS slice only.
# ---------------------------------------------------------------------------

def dim_school_pressure(linnaosa_row: Optional[dict],
                        listing: Optional[dict] = None) -> Score:
    """P4-011: utilization (pupils/places) bands 75/60/45/30; NULL w/o row.

    Scores ONLY the HaridusSilm/EHIS capacity leg. The lasteaia-queue
    leg (Tallinna Haridusamet, #270) and the perearst leg
    (Tervisekassa) are named as not-joined in every reason.
    """
    rec = _row(linnaosa_row)
    if rec is None:
        return _missing_row()
    places = rec.get("pupil_places")
    pupils = rec.get("pupils")
    if not isinstance(places, int) or not isinstance(pupils, int):
        return None, ("HaridusSilm/EHIS koolikohtade arv linnaosas puudub "
                      "(EI OLE hinnangut): lasteaia järjekorda Haridusametist "
                      "ja perearsti Tervisekassast kontrolli eraldi")
    if places <= 0:
        return None, ("HaridusSilm/EHIS õppekohtade arv pole kasutatav "
                      "(EI OLE hinnangut): kontrolli koolikaardilt")
    util = pupils / places
    if util < 0.85:
        band = (75, "Koolides ruumi (HaridusSilm/EHIS registriandmed, mitte "
                    "hinnang): täituvus %.0f%%" % (util * 100))
    elif util < 0.95:
        band = (60, "Koolid peaaegu täis (HaridusSilm/EHIS registriandmed, "
                    "mitte hinnang): täituvus %.0f%%" % (util * 100))
    elif util <= 1.05:
        band = (45, "Koolid täis (HaridusSilm/EHIS registriandmed, mitte "
                    "hinnang): täituvus %.0f%% — teeninduspiirkond määrab"
                    % (util * 100))
    else:
        band = (30, "Koolid ületäitunud (HaridusSilm/EHIS registriandmed, "
                    "mitte hinnang): täituvus %.0f%% (nõrk signaal)"
                    % (util * 100))
    score, reason = band
    queue = rec.get("queue_len")
    if isinstance(queue, int):
        reason += ("; lasteaia järjekord linnaosas %d (Haridusameti number, "
                   "mitte EHIS — eraldi kontroll)" % queue)
    catchment = rec.get("catchment_note")
    if catchment:
        reason += " Teeninduspiirkond: %s." % str(catchment).strip()
    reason += " Lasteaia-järjekorra (Haridusamet) ja perearsti (Tervisekassa) jalga ei hinnata."
    return score, reason


# ---------------------------------------------------------------------------
# P4-044 (coverage): art/music-school density per linnaosa — taste-match.
# ---------------------------------------------------------------------------

def dim_artschool_density(linnaosa_row: Optional[dict],
                          listing: Optional[dict] = None) -> Score:
    """P4-044: huvikoolide count 50/60/70 taste-match (capped, capped low).

    Leading-indicator cross-check for ONE buyer taste; zero art/music
    schools is neutral (50), never bad. Never worth judgement.
    """
    rec = _row(linnaosa_row)
    if rec is None:
        return None, ("HaridusSilm/EHIS linnaosa-rida puudub — huvikoolide "
                      "tiheduse maitsesobivust EI OLE (hinnangut ei anta): "
                      "loomingulise kvartali eelistust kaalu ostjaprofiilis, "
                      "REL2021 hõive-ruudustikku ja OSM kultuuritihedust "
                      "kontrolli eraldi")
    count = rec.get("art_music_schools")
    if not isinstance(count, int):
        return None, ("HaridusSilm/EHIS kunsti-/muusikakoolide arv linnaosas "
                      "puudub (EI OLE hinnangut): maitsesobivus selgub "
                      "ostjaprofiilist, mitte oletusest")
    tail = (" Maitsesobivus, mitte väärtushinnang (hinnang): "
            "REL2021 hõive-segu, OSM kultuuritihedus, ariregistri "
            "loomeettevõtted ja tehingute gentrifikatsiooni-rinne jäävad "
            "eraldi allikateks.")
    if count <= 0:
        return (50, "Kunsti-/muusikakoole linnaosas registri järgi pole "
                    "(HaridusSilm/EHIS registriandmed, neutraalne "
                    "maitsesobivus, mitte hinnang halvuse kohta)." + tail)
    if count <= 2:
        return (60, "Kunsti-/muusikakoole %d (HaridusSilm/EHIS "
                    "registriandmed): loome-pisiku maitsesobivus, mitte "
                    "hinnang." % count + tail)
    return (70, "Kunsti-/muusikakoole %d (HaridusSilm/EHIS registriandmed): "
                "tihe loome-pisiku maitsesobivus, ülempiir 70, mitte "
                "hinnang." % count + tail)


P4_EHIS_DIMS = (
    ("school_pressure", "P4-011", dim_school_pressure),
    ("artschool_density", "P4-044", dim_artschool_density),
)


def score_p4_ehis(linnaosa_row: Optional[dict],
                  listing: Optional[dict] = None) -> Dict[str, Optional[int]]:
    """Both P4 EHIS dims for one linnaosa row (entry point for the
    weight-rebalance follow-up; keys match P4_EHIS_DIMS)."""
    return {key: fn(linnaosa_row, listing)[0] for key, _, fn in P4_EHIS_DIMS}
