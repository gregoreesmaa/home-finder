"""P4 wildfire-recurrence avoidance dim (issue #529, measured history).

Source: Rescue Board (Päästeamet) forest/landscape fires
(metsa-ja maastikutulekahjud) 2014-04-01 -> present via
opendata.smit.ee (daily current-year CSV plus archive CSVs).
Licence CC_BY_NC_ND_4.0 per the national catalogue (attribute
Paasteamet; respect NC/ND; daily TTL at most).

OPENNESS (probed 2026-09-16, one polite round, UA
home-finder-idea-probe/1.0, paced >= 3 s, cached to /tmp/hf-526-529-probe,
full evidence in docs/p4_wildfire.md):
* metsa_ja_maastikutulekahjud_jooksev_aasta.csv: HTTP 200,
  191 911 B, 652 rows 2026-YTD (173 Harju, incl. 58 Tallinn,
  Saue/Harku/Jõelähtme/Maardu represented — the Nõmme-Männiku /
  Merivälja-Pirita / Harku-Rannamõisa buyer signal is present).
* TAB-separated, 25 columns incl. sundmuse_number,
  sundmuse_kuupaev_dt (ISO YYYY-MM-DD), tulekahju_liik, mis_poles
  (Maastik 515 / Mets 70 / both 66), wgs_latitude/wgs_longitude
  (WGS84 directly — zero blank coordinates in 652 rows), maakond, kov.
* Archive gap (dated, kept): the 2014-2025 archive name guessed from
  the current-year pattern 404'd (single HEAD, no hunting per polite
  rules) — the adapter resolves archive URLs via the Teabevärav
  catalogue entry, documented in docs/p4_wildfire.md §5. The dim
  below is history-shape ready (caller-supplied multi-year rows);
  recency runs off the snapshot's caller date.

HONESTY (AGENTS.md 7.2): fire-point recency kernel — a recent fire
(<=5 yrs) within 500 m scores 35 (avoidance); older or farther
incidents score 55-65; no incidents in window is NULL (absence of
ignitions is not absence of risk, never "safe"). The dim names the
nearest incident year + buyer check (kindlustus, Päästeameti
tuleohukaart) and states the statistics caveat: this dataset feeds
national statistics but is NOT the Environment Agency's official
fire statistics (do not conflate). No per-address "fire risk score"
beyond the honest kernel. Transport errors are never cached as data;
HTTP 429 stops the run.

Style mirrors services/scoring/dims_p4_shelters.py (#528, same
session): pure offline scorers, stdlib-only, local helpers (no
sibling imports — a future central hook may import this module
alongside the others).

Judgment calls (reviewable per AGENTS.md 7.5):
* RECENT_YEARS = 5 with caller-supplied as_of (the module takes NO
  wall-clock — hermetic, deterministic; undated incidents read as
  old, never fresh).
* Distance tiers: NEAR_M = 500 (parcel-relevant smoke/ember range),
  FAR_M = 2000 (honestly-labelled Euclidean kernel, no routing).
  Band matrix: near+recent 35, near+old 55, far+recent 55,
  far+old 65. The nearest incident decides (one bad summer next
  door dominates five quiet ones further out).
* mis_poles (Mets vs Maastik) does NOT split bands: both burn
  smoke into the same buyer question; the fuel label travels in
  the reason for the buyer to judge.
* Rows without finite coordinates or without a parseable year are
  skipped and counted by summarize_snapshot (never zero-filled).

Integration (deliberately NOT done here): livability hook +
WEIGHTS rebalance stay one joint change across batches (existing
tests pin set(WEIGHTS)). No shared files touched: 3 new files only.
"""

import csv
import io
import math
import os
import re
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source identity, politeness, cache.
# ---------------------------------------------------------------------------

#: Current-year incidents (verified 2026-09-16: HTTP 200, 191 911 B, 652 rows).
WILDFIRE_URL = ("https://opendata.smit.ee/paa/csv/"
                "metsa_ja_maastikutulekahjud_jooksev_aasta.csv")
WILDFIRE_USER_AGENT = (
    "home-finder-p4-wildfire/1.0 (Estonia open-data daily adapter; "
    "polite single-pull, cache-first)"
)
#: Publisher updates daily: at most one live pull per day.
WILDFIRE_CACHE_TTL_S = 1 * 86400
WILDFIRE_CACHE_NAME = "metsa_ja_maastikutulekahjud_jooksev_aasta.csv"

#: Recency window in years (caller-dated, never wall-clock).
RECENT_YEARS = 5
#: Distance tiers in metres (honestly-labelled Euclidean kernel).
NEAR_M = 500.0
FAR_M = 2000.0

#: (near, recent) -> score matrix.
WILDFIRE_BANDS = {
    (True, True): 35,    # recent fire next door: avoidance signal
    (True, False): 55,   # old fire next door: faded but noted
    (False, True): 55,   # recent fire in the wider kernel
    (False, False): 65,  # old fire in the wider kernel: weak note
}

_YEAR_RE = re.compile(r"^(\d{4})-\d{2}-\d{2}")


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------

def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points (pure)."""
    r = 6371.0
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    dla = math.radians(b[0] - a[0])
    dlo = math.radians(b[1] - a[1])
    h = (math.sin(dla / 2.0) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2.0) ** 2)
    return 2.0 * r * math.asin(min(1.0, math.sqrt(h)))


def _fnum(value: object) -> Optional[float]:
    try:
        v = float(str(value).strip().replace(" ", "").replace(",", "."))
    except (TypeError, ValueError, AttributeError):
        return None
    return v if math.isfinite(v) else None


def incident_year(value: object) -> Optional[int]:
    """Parse an ISO incident date to its year (pure, fail-closed)."""
    if not isinstance(value, str):
        return None
    m = _YEAR_RE.match(value.strip())
    if not m:
        return None
    try:
        year = int(m.group(1))
    except ValueError:
        return None
    return year if 1900 <= year <= 2100 else None


def asof_year(value: object) -> Optional[int]:
    """Parse the caller-supplied snapshot date to its year (pure)."""
    return incident_year(value)


# ---------------------------------------------------------------------------
# Ingestion: polite cached pull (live path, NOT unit-run) + pure parse.
# ---------------------------------------------------------------------------

def _cache_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, WILDFIRE_CACHE_NAME)


def cache_is_fresh(path: str, ttl_s: int = WILDFIRE_CACHE_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_s."""
    try:
        age_s = (now if now is not None else time.time()) - os.path.getmtime(path)
    except OSError:
        return False
    return age_s < ttl_s


def fetch_wildfire_snapshot(
    cache_dir: Optional[str] = None,
    ttl_s: int = WILDFIRE_CACHE_TTL_S,
) -> Tuple[dict, str]:
    """Polite cached pull of the current-year CSV (live path, NOT unit-run).

    Fresh cache wins (no request). Any transport error raises and the
    cache file is left untouched — transport errors are never cached
    as data, and 429 stops the run. Returns (snapshot, provenance)
    with provenance "cache" or "live".
    """
    if cache_dir is None:
        cache_dir = os.path.join("/tmp", "hf-wildfire-cache")
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir)
    provenance = "cache"
    if cache_is_fresh(path, ttl_s):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    else:
        req = urllib.request.Request(
            WILDFIRE_URL, headers={"User-Agent": WILDFIRE_USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            if resp.status == 429:
                raise RuntimeError("opendata.smit.ee vastas 429 — peatu, ära reetry")
            if resp.status != 200:
                raise RuntimeError(
                    "opendata.smit.ee vastas HTTP %s — vahemalu puutumata"
                    % resp.status
                )
            text = resp.read().decode("utf-8-sig", errors="replace")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        provenance = "live"
    snapshot = {
        "incidents": parse_metsa_tsv(text),
        "as_of": time.strftime("%Y-%m-%d", time.gmtime()),
        "source": "Päästeameti metsa- ja maastikutulekahjud "
                  "(opendata.smit.ee, CC BY-NC-ND 4.0)",
    }
    return snapshot, provenance


def parse_metsa_tsv(tsv_text: str) -> List[dict]:
    """Parse a metsa_ja_maastikutulekahjud CSV (TAB-separated) (pure).

    Rows without finite WGS84 coordinates or without a parseable
    incident year are skipped (counted by summarize_snapshot, never
    zero-filled — an undated fire cannot join a recency kernel).
    """
    reader = csv.DictReader(io.StringIO((tsv_text or "").lstrip("\ufeff")),
                            delimiter="\t")
    out: List[dict] = []
    for row in reader:
        lat = _fnum(row.get("wgs_latitude"))
        lon = _fnum(row.get("wgs_longitude"))
        year = incident_year(row.get("sundmuse_kuupaev_dt"))
        if lat is None or lon is None or year is None:
            continue
        out.append({
            "id": (row.get("sundmuse_number") or "").strip(),
            "year": year,
            "fuel": (row.get("mis_poles") or "").strip(),
            "maakond": (row.get("maakond") or "").strip(),
            "kov": (row.get("kov") or "").strip(),
            "lat": lat,
            "lon": lon,
        })
    return out


def summarize_snapshot(tsv_text: str) -> dict:
    """Honest counts for a CSV payload: rows / parsed / Harju / years (pure)."""
    incidents = parse_metsa_tsv(tsv_text)
    reader = csv.DictReader(io.StringIO((tsv_text or "").lstrip("\ufeff")),
                            delimiter="\t")
    total = sum(1 for _ in reader)
    years = sorted({i["year"] for i in incidents})
    return {
        "rows": total,
        "incidents": len(incidents),
        "skipped": total - len(incidents),
        "harju": sum(1 for i in incidents if "Harju" in i["maakond"]),
        "year_min": years[0] if years else None,
        "year_max": years[-1] if years else None,
    }


# ---------------------------------------------------------------------------
# Scorer: recency kernel (recent+near avoids, silence NULLs).
# ---------------------------------------------------------------------------

def dim_wildfire_recency(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]] = None,
                         fires: Optional[dict] = None) -> Score:
    """Wildfire-recurrence avoidance: history scores, silence NULLs.

    `fires` is the snapshot from fetch_wildfire_snapshot (incidents +
    caller date as_of). `pois` is accepted for the uniform scorer shape
    and ignored — fire history is not OSM POIs. No wall-clock: recency
    runs off as_of, so undated snapshots score nothing.
    """
    _ = pois
    snap = fires if isinstance(fires, dict) else None
    if not origin:
        return None, ("Tulekahjude kordumine teadmata (EI OLE hinnangut): "
                      "aadress puudub — metsa- ja maastikutulekahjude "
                      "(Nõmme-Männiku, Merivälja-Pirita, Harku-Rannamõisa) "
                      "kaugus selgub aadressi asendist, mitte tühjalt")
    now_year = asof_year((snap or {}).get("as_of"))
    incidents = [i for i in (snap or {}).get("incidents", [])
                 if isinstance(i, dict)]
    if now_year is None or not incidents:
        return None, ("Tulekahjude kordumine teadmata (EI OLE hinnangut): "
                      "metsa- ja maastikutulekahjude hetktõmmist (koos "
                      "kuupäevaga) pole — Päästeameti register "
                      "(opendata.smit.ee, CC BY-NC-ND 4.0, igapäevane) "
                      "selgub päeva väljavõttest; küsi kindlustusandjalt "
                      "suitsukahjude ajalugu ja vaata Päästeameti "
                      "tuleohukaarti")
    best = None
    best_km = None
    for i in incidents:
        if i.get("lat") is None or i.get("lon") is None:
            continue
        km = haversine_km(origin, (i["lat"], i["lon"]))
        if best_km is None or km < best_km:
            best, best_km = i, km
    if best is None or best_km is None:
        return None, ("Tulekahjude kordumine teadmata (EI OLE hinnangut): "
                      "hetktõmmise ühelgi kirjel pole koordinaate — "
                      "kontrolli Päästeameti registrit kohapeal")
    if best_km * 1000.0 > FAR_M:
        return None, ("Tulekahjude kordumine teadmata (EI OLE hinnangut): "
                      "lähim registreeritud tulekahju (%d, %s) on %.1f km "
                      "kaugusel (väljaspool 2 km hinnanguala): kustutatud "
                      "tulekahjude puudumine ei ole tuleohu puudumise "
                      "hinnang; küsi kindlustusandjalt ja vaata Päästeameti "
                      "tuleohukaarti" % (best.get("year") or 0,
                                         best.get("kov") or "teadmata",
                                         best_km))
    near = best_km * 1000.0 <= NEAR_M
    recent = (now_year - int(best.get("year") or 0)) <= RECENT_YEARS
    score = WILDFIRE_BANDS[(near, recent)]
    fuel = (" (%s)" % best["fuel"]) if best.get("fuel") else ""
    return score, ("Tulekahju %d. aastal%s %.0f m kaugusel (%s, hinnang — "
                   "kordumise vältimiskiht, mitte tuleohuprognoos): "
                   "suitsusuved ja kindlustatavus selguvad kindlustusandja "
                   "pakkumisest ja Päästeameti tuleohukaardilt; andmestik "
                   "toidab riiklikku statistikat, kuid ei ole "
                   "Keskkonnaagentuuri ametlik tulekahjustatistika"
                   % (best.get("year") or 0, fuel, best_km * 1000.0,
                      best.get("kov") or "teadmata"))


def score_p4_wildfire(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]] = None,
                      fires: Optional[dict] = None
                      ) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """Rollup: {dim_key: score|None} + non-NULL reasons (pure)."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for key, _label, fn in P4_WILDFIRE_DIMS:
        value, reason = fn(origin, pois, fires)
        dims[key] = value
        if value is not None:
            reasons.append(reason)
    return dims, reasons


P4_WILDFIRE_DIMS = (
    ("wildfire_recency", "Wildfire", dim_wildfire_recency),
)
