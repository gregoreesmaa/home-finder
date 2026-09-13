"""P4 Elering system-data dims (issues #265 demo + #345 coverage).

Params (this module only — the Elering SLICE of each param; sibling
slices are owned elsewhere and untouched):
* P4-009 Power/internet reliability at address: the Elering
  "elektrisüsteemi avaandmed" slice (source (2), batch 1, demo in
  #265). Disjoint from dims_p4_elektrilevi.dim_power_reliability,
  which owns the Elektrilevi feeder-SAIDI slice (NULL: unpublished
  DSO feed), and from the TTJA/Ookla/OpenCellID broadband slices
  (their own demos, not this source).
* P4-036 Roof income: the Elering "päikese feed-in rules +
  mikrotootja tingimused" slice (source (1), batch 3, coverage in
  #345). Disjoint from dims_p4_ehr.dim_roof_income, which SCORES
  the EHR roof-type upside (floor 50), and from
  dims_p4_elektrilevi.dim_roof_export, which owns the Elektrilevi
  liitumiskaart slice (NULL: gated map).
* P4-046 Dread removal: the Elering half of the "Elektrilevi/Elering
  backup-feed info (where published)" slice (source (5), batch 4,
  coverage in #345). Disjoint from dims_p4_ehr heat/fireplace
  redundancy (SCORED), dims_p4_tvesi well+city-water redundancy
  (SCORED), and dims_p4_elektrilevi.dim_backup_feed, which owns the
  Elektrilevi half (NULL: unpublished).

OPENNESS VERDICT (checked 2026-09-13, four polite GETs total with a
labelled one-off user-agent, raw bodies cached at /tmp/hf-elering/,
TTL: one-off check kept for the PR record, never committed):
* https://elering.ee/ -> HTTP 200, 253401 bytes, title "Avaleht |
  Elering" — company/TSO portal reachable; connection terms live on
  human pages (110/330 kV liitumine), no open-data/dev portal
  advertised on the landing.
* https://dashboard.elering.ee/ -> HTTP 200, 4486 bytes, "Elering
  Live" JS app shell — no key on the landing.
* https://dashboard.elering.ee/api/system/with-plan -> HTTP 200,
  34003 bytes, {"success":true,"data":{"real":[64 pts],"plan":[68
  pts]}} covering 2026-09-12T21:00Z..2026-09-13T12:45Z at 15-min
  steps. MACHINE-OPEN, no key, no auth. Fields per point:
  timestamp, production, consumption, losses (null), frequency,
  system_balance, ac_balance, production_renewable,
  solar_energy_production (null across the whole window — the field
  exists but carries no value here, so it parses to None, never 0).
* https://elering.ee/en/article/renewable-energy-subsidy-applications-become-significantly-easier
  -> HTTP 200, 135739 bytes human HTML (subsidy-via-data-hub
  explainer); the only application/json on the page is the Drupal
  settings blob — NO machine feed-in-rules feed.
Verdict: MIXED. The machine-open layer is national-aggregate by TSO
design (the payload has no geographic key at all — no feeder, no
address, no building). The rules layer is human-pages-only. The
meter layer (per-address consumption/production) lives behind
e-Elering/Estfeed consent by Elering's published model (customers
choose whom to share with), so no anonymous per-address pull is
possible — politeness stops here. Dated probes keep this verdict.

HONESTY (AGENTS.md section 7.2): a national surplus/deficit series
says nothing about whether YOUR street goes dark — outages are
distribution-level (Elektrilevi feeders), and rooftop export needs
per-building facts (EHR roof, Elektrilevi connection). Numbers enter
sorts while reasons do not, so scoring an address number off the
national series would be fake precision (OTA PR #131 precedent).
Every dim therefore returns None for EVERY input: the Elering slice
carries no per-address/per-building signal. NULL stays NULL with an
Estonian reason saying "hinnang" and "EI OLE", echoing the ingested
national snapshot when present (traceable context, never a score),
and pointing at the concrete buyer-side check — never a faked area
score. Upside dims (P4-036) return None as "no evidenced upside",
not as a negative.

Style mirrors services/scoring/dims_p4_elektrilevi.py (#264, the
closest sibling: same param family, same NULL-with-markers shape)
and dims_p4_ilm.py (#308, ingestion product travels explicitly):
scorers are pure and offline-tested —
(origin, pois, elering=None) -> (Optional[int 0..100], Estonian
reason); the optional third argument IS the demoed ingestion product
(the summarize_elering_system snapshot), so every param is wired to
the demoed ingestion with fixture proof. Network lives only in
fetch_elering_system (single polite GET, file cache, TTL); tests
never call it.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because #345 states it
  "extends the demoed ingestion" with "no new plumbing expected" —
  all three params read disjoint slices of the SAME national
  snapshot (system adequacy / solar context / published-backup
  absence), so splitting would ship a one-consumer ingestion then
  re-touch every signature (same precedent as elektrilevi #264+#344
  and creditinfo #259+#340).
* Rejected steelman: a scored P4-009 "system adequacy" band off
  avg system_balance, and a scored P4-036 upside gated on the EE
  price zone. Rejected because national != address by TSO design,
  and a single Tallinn "raster cell" relabelled from the national
  value would be relabelling, not a raster (parameters4.md allows a
  "coarse raster hinnang", but a raster needs >= 2 cells with real
  variation — Elering has none). The buyer sorts the number, not
  the reason.
* ELERING_TTL_DAYS = 30 comes from parameters4.md P4-009 ("TTL:
  monthly"): a home-finder adequacy snapshot moves slowly, and a
  monthly re-pull keeps the polite budget at ~12 GETs/year.
* solar None (not 0.0) when every solar field is null: the API
  carries the key with null values (observed), so zero would bless
  missing telemetry as "no sun". Same for losses.
* Points without a timestamp are skipped (no time key — keeping them
  would fake window coverage, same join-key precedent as kudocs
  parse_kudocs skipping ku_code-less rows); success:false envelopes
  and non-JSON bodies parse to [] (an error envelope is never data).
* fetch transport/HTTP errors RAISE and are never cached as data;
  HTTP 429 propagates as a stop signal (AGENTS.md sections 7.2,
  7.4).

Integration (deliberately NOT done here): feeding these dims with
the ingested snapshot inside livability scoring and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling.
"""

import json
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated national system-series pulls.
# ---------------------------------------------------------------------------

#: Machine-open system series (verified 2026-09-13: HTTP 200, no key).
ELERING_SYSTEM_URL = "https://dashboard.elering.ee/api/system/with-plan"

#: Monthly re-pull per parameters4.md P4-009 ("TTL: monthly").
ELERING_TTL_DAYS = 30

USER_AGENT = ("home-finder elering ingest (polite monthly pull, single GET, "
              "file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str) -> str:
    """Single national-series cache file (flat dir, no subdirs)."""
    return os.path.join(cache_dir, "elering-system.json")


def cache_is_fresh(path: str, ttl_days: int = ELERING_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_elering_system(cache_dir: str = "/tmp/hf-elering",
                         ttl_days: int = ELERING_TTL_DAYS) -> str:
    """Fetch the Elering national system series politely (cached, TTL).

    Cache-first single GET with a polite User-Agent and a 30 s
    timeout. Transport errors RAISE (never cached as data, AGENTS.md
    section 7.2); HTTP errors raise too — an error body is never
    written to the cache. Treat HTTP 429 as a stop signal: it
    propagates, the stale cache is left untouched.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir)
    if cache_is_fresh(path, ttl_days):
        with open(path, encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(ELERING_SYSTEM_URL,
                                 headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = resp.read()
    text = body.decode("utf-8")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------------------
# Parsing: national series layout (dashboard with-plan envelope).
# One point per 15-min step: system slice (P4-009) + solar context
# (P4-036) + published-backup absence note (P4-046 reads the envelope
# shape, not the values). Missing keys read as None (never guessed).
# ---------------------------------------------------------------------------

#: Canonical point keys produced by parse_elering_system (all Optional
#: except timestamp, which is the join key — points without one are
#: skipped).
ELERING_POINT_FIELDS = (
    "timestamp",
    "production_mw",
    "consumption_mw",
    "system_balance_mw",
    "frequency_hz",
    "renewable_mw",
    "solar_mw",
)

#: Raw API field -> canonical key (losses/ac_balance carry no param
#: signal and are dropped, never scored).
_RAW_TO_CANONICAL = (
    ("production", "production_mw"),
    ("consumption", "consumption_mw"),
    ("system_balance", "system_balance_mw"),
    ("frequency", "frequency_hz"),
    ("production_renewable", "renewable_mw"),
    ("solar_energy_production", "solar_mw"),
)


def _to_float(raw: object) -> Optional[float]:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_int(raw: object) -> Optional[int]:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def parse_elering_system(payload: str) -> List[Dict[str, Optional[float]]]:
    """Parse one with-plan envelope into canonical national points.

    success:false envelopes, non-JSON bodies, and missing/non-list
    "real" series all yield [] — an error envelope is never data.
    """
    try:
        envelope = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    if not isinstance(envelope, dict) or not envelope.get("success"):
        return []
    data = envelope.get("data")
    series = data.get("real") if isinstance(data, dict) else None
    if not isinstance(series, list):
        return []
    points = []  # type: List[Dict[str, Optional[float]]]
    for row in series:
        if not isinstance(row, dict):
            continue
        ts = _to_int(row.get("timestamp"))
        if ts is None:
            continue
        point = {"timestamp": ts}  # type: Dict[str, Optional[float]]
        for raw_key, canon_key in _RAW_TO_CANONICAL:
            point[canon_key] = _to_float(row.get(raw_key))
        points.append(point)
    return points


#: Canonical snapshot keys produced by summarize_elering_system.
ELERING_SNAPSHOT_FIELDS = (
    "points",
    "start_ts",
    "end_ts",
    "avg_balance_mw",
    "deficit_share",
    "avg_solar_mw",
    "freq_ok_share",
)


def summarize_elering_system(
        points: List[Dict[str, Optional[float]]]
) -> Optional[Dict[str, Optional[float]]]:
    """Aggregate parsed points into the snapshot the dims consume.

    None when no usable points exist. Averages run over non-None
    measures only; avg_solar_mw stays None (never 0.0) when the
    series carries no solar values.
    """
    if not points:
        return None
    balances = [p["system_balance_mw"] for p in points
                if p.get("system_balance_mw") is not None]
    solars = [p["solar_mw"] for p in points
              if p.get("solar_mw") is not None]
    freqs = [p["frequency_hz"] for p in points
             if p.get("frequency_hz") is not None]
    return {
        "points": len(points),
        "start_ts": points[0].get("timestamp"),
        "end_ts": points[-1].get("timestamp"),
        "avg_balance_mw": (sum(balances) / len(balances)
                           if balances else None),
        "deficit_share": (sum(1 for b in balances if b < 0) / len(balances)
                          if balances else None),
        "avg_solar_mw": (sum(solars) / len(solars) if solars else None),
        "freq_ok_share": (sum(1 for f in freqs if 49.9 <= f <= 50.1)
                          / len(freqs) if freqs else None),
    }


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _fmt_mw(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return ("%.1f" % value).replace(".", ",")
    return str(value)


def _snapshot_echo(elering: Optional[dict]) -> str:
    """Traceable national context for NULL reasons (never a score)."""
    if not isinstance(elering, dict):
        return ""
    n = elering.get("points")
    bal = elering.get("avg_balance_mw")
    if not isinstance(n, int) or not isinstance(bal, (int, float)) \
            or isinstance(bal, bool):
        return ""
    echo = ("Elering Live riigi seeria: %d punkti, keskmine bilanss %s MW"
            % (n, _fmt_mw(float(bal))))
    solar = elering.get("avg_solar_mw")
    if isinstance(solar, (int, float)) and not isinstance(solar, bool):
        echo += ", päikese keskmine %s MW" % _fmt_mw(float(solar))
    else:
        echo += "; päikese mõõtmisi seerias pole"
    return echo + " — "


def _snap(elering: Optional[dict]) -> Optional[dict]:
    return elering if isinstance(elering, dict) else None


# ---------------------------------------------------------------------------
# P4-009 (demo): system adequacy — per-address dim on the Elering slice.
# ---------------------------------------------------------------------------

def dim_system_adequacy(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]],
                        elering: Optional[dict] = None) -> Score:
    """P4-009: NULL — the national series carries no feeder signal."""
    snap = _snap(elering)
    if snap is None:
        return None, ("Elering süsteemi hetktõmmis puudub ja fiidri-/"
                      "aadressiandmeid Elering masinloetavalt ei avalda "
                      "(EI OLE hinnangut): valguse/toa pimeduse riski "
                      "hindamiseks kontrolli jooksvaid katkestusi "
                      "rikkekaardilt ja interneti TTJA netikaardilt, "
                      "ära feigi riigi numbrist aadressi skoori")
    return None, ("%ssee on Eesti SÜSTEEMI hinnang, aadressi fiidri "
                  "skoori EI OLE (fiidri SAIDI-ajalugu Elering ei avalda, "
                  "see on Elektrilevi kiht): kontrolli jooksvaid "
                  "katkestusi rikkekaardilt ja interneti TTJA "
                  "netikaardilt, ära feigi riigi numbrist aadressi skoori"
                  % _snapshot_echo(snap))


# ---------------------------------------------------------------------------
# P4-036 (coverage): roof income via the Elering rules slice — per-building
# upside dim (None = no evidenced upside, never a negative).
# ---------------------------------------------------------------------------

def dim_feed_in_rules(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]],
                      elering: Optional[dict] = None) -> Score:
    """P4-036: NULL — rules are human-only, series is national."""
    snap = _snap(elering)
    ctx = _snapshot_echo(snap) if snap is not None else ""
    return None, ("%sEleringi katusetulu-reeglid (feed-in/toetusreeglid, "
                  "mikrotootja tingimused) on inimloetavad lehed ilma "
                  "masinvoota ja riigi päikeseseeria ei kanna hoone "
                  "ekspordivõimekust — tõestamata tulu EI OLE hinnangut "
                  "(upside jääb tühjaks, mitte negatiivseks): katuse "
                  "sobivus EHR-ist, liitumisvõimekus Elektrilevi "
                  "liitumiskaardilt, ära feigi reeglitest katusetulu"
                  % ctx)


# ---------------------------------------------------------------------------
# P4-046 (coverage): dread removal via the Elering backup-feed half —
# per-listing redundancy dim.
# ---------------------------------------------------------------------------

def dim_grid_backup(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]],
                    elering: Optional[dict] = None) -> Score:
    """P4-046: NULL — no per-address backup feed published (either half)."""
    snap = _snap(elering)
    ctx = _snapshot_echo(snap) if snap is not None else ""
    return None, ("%sEleringi avaldatud kihis varutoite infot aadressi "
                  "kohta pole (EI OLE skoori — allikaloetelu tingimus "
                  "'kus avaldatud' täitmata, ka Elektrilevi pool on "
                  "avaldamata hinnang): hinda dubleerimist kohapeal "
                  "(kamin/ahi + kaugküte EHR-ist, kaev + linnavesi, teine "
                  "väljasõidutee) ja küsi KÜ-lt, ära feigi"
                  % ctx)


ELERING_DIMS = (
    ("system_adequacy", "P4-009", dim_system_adequacy),
    ("feed_in_rules", "P4-036", dim_feed_in_rules),
    ("grid_backup", "P4-046", dim_grid_backup),
)


def score_p4_elering(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]],
                     elering: Optional[dict] = None
                     ) -> Dict[str, Optional[int]]:
    """All three P4 Elering dims for one listing (entry point for the
    weight-rebalance follow-up; keys match ELERING_DIMS). Every value
    is None by design — the national series carries no per-address /
    per-building signal, never a faked score."""
    return {key: fn(origin, pois, elering)[0] for key, _, fn in ELERING_DIMS}
