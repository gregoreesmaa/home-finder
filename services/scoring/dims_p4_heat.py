"""P4 heat demo + coverage dims (issues #261 and #342).

Demo (#261): heat-tariff ingestion (P4-008) — polite, cached,
TTL-stated pulls of the per-address tariff-zone snapshot plus an
honest-shape per-address dim. Coverage (#342): P4-036 roof income,
wired to the same demoed ingestion via its source (6) — Utilitas
kaugkütte tagastustemperatuuri boonused (no new plumbing — #342
states it extends the demoed ingestion).

Params (this agent only — sibling batches own disjoint sets):
* P4-008 Heating tariff zone + water/sewer tariff (demo, per-address)
* P4-036 Roof income, return-temp bonus slice (per-building upside)

HONESTY (AGENTS.md section 7.2): per-address table joins, capped
bands; NULL stays NULL with an Estonian reason. The operator feeds
are CLOSED for the per-address machine-feed purpose (dated negative
below), so every dim returns None when its joined zone record is
missing — never a guess, never a "cheap heat" 100 from absence.
Scored reasons always trace to a joined zone record (operator /
tariff / bonus); NULL reasons always say EI OLE and name the
missing input.

Openness verdict (2026-09-13, 8 polite requests total, custom UA,
short timeout, paced >=4 s, cached /tmp/hf-p4-heat/, no scraping,
no auth attempts, redirects not spidered):
* https://utilitas.ee/ -> HTTP 200 (103 154 B, "Avaleht - Utilitas",
  WordPress; www 301s to apex) — kaugküte marketing pages, ZERO
  hinnakiri/tariif/võrk/kaart hrefs on the front page: no anonymous
  per-address tariff feed verified.
* https://www.konkurentsiamet.ee/ -> HTTP 200 (120 078 B) — links to
  /elekter-gaas-soojus-ja-vesi/soojus/kooskolastatud-hinnad, which
  itself is HTTP 200 (114 278 B, "Kooskõlastatud hinnad |
  Konkurentsiamet"): a decision hub (accordion docs + HAI e-teenus),
  no anonymous per-address bulk endpoint. OPEN as the re-pull
  TRIGGER (decisions), CLOSED as a machine feed.
* https://www.tallinnavesi.ee/ -> HTTP 200 (363 912 B, apex 301s to
  www): tariff published as the /teenused/hinnakiri price-list page,
  not a per-address machine feed — CLOSED for the join purpose.
* https://adven.com/ -> HTTP 200 (corporate WordPress marketing, no
  local katlamaja tariff feed) — CLOSED for the join purpose.
* Tallinna Küte: no verified domain, not probed (polite stop).
* https://www.elektrilevi.ee/ -> HTTP 302 with empty body, not
  followed (polite stop) — cross-check leg unverified.
Dated negative keeps the verdict: no anonymous per-address
heat-tariff machine feed verified 2026-09-13. fetch_heat_csv below
targets the documented snapshot layout with a tariff-change-driven
TTL and the dims score ONLY joined zone records. See docs/p4_heat.md.

Style mirrors services/scoring/dims_p4_taitur.py (issues #255/#336):
pure (zone, listing) -> (Optional[int 0..100], Estonian reason),
absolute bands, hermetic fixture tests. Network lives only in
fetch_heat_csv (single polite GET, file cache, TTL); tests never
call it. Unlike the taitur per-subject LIST join, P4-008 is a
per-address SINGLE-record join (parameters4.md: "per-address table
join"), so there is no None-vs-[] distinction here — instead a
joined-but-empty record (no operator, no tariff) reads as NULL.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and group20a #212).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR because #342 defines coverage as
  extending the demoed ingestion — P4-036's source list names the
  Utilitas return-temp bonus as source (6), i.e. the same operator
  feed P4-008 demos. Splitting would ship an ingestion with one
  consumer, then re-touch every signature (same rationale as the
  taitur #255/#336 pair).
* Bands are 45/60 (P4-008) and 65 (P4-036 upside), never 0 and never
  100: the tariff table alone never prices a January bill (building
  consumption dominates — KÜ aruanne decides), and roof upside from
  the bonus slice alone never proves yield (solar/mast/ad legs need
  LiDAR/EHR joins). Absence of a joined record is not proof of
  cheap heat or of zero roof income.
* P4-008 scores bill PREDICTABILITY, not cheapness: a kehtiv tariff
  in a known operator zone (60) beats operator-known/tariff-pending
  (45) because the buyer can budget January, not because the heat
  is cheap. Ranking zones by €/MWh would be fake precision without
  consumption data.
* 30-day TTL (2592000 s): tariffs move on Konkurentsiamet decisions
  (a few times a year at most), so a monthly re-pull converges per
  AGENTS.md section 7.4 while decisions trigger an out-of-band
  re-pull. Stated, not hidden.
* Comma-decimal tariffs ("123,45") parse to float; unparseable
  tariffs read as None (never guessed, never zero — zero would fake
  free heat).

Integration (deliberately NOT done here): feeding these dims with
the address's joined zone record inside livability scoring and
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
# Ingestion: polite, cached, TTL-stated heat snapshot pulls.
# ---------------------------------------------------------------------------

#: Monthly pull per module docstring (tariffs move on KA decisions;
#: decisions additionally trigger an out-of-band re-pull).
HEAT_TTL_S = 30 * 86400

#: Where the public slices live (verified 2026-09-13 — see module
#: docstring; marketing homepages / decision hub / price-list page,
#: no anonymous per-address feed).
UTILITAS_URL = "https://utilitas.ee/"
KA_HEAT_PRICES_URL = ("https://www.konkurentsiamet.ee/"
                      "elekter-gaas-soojus-ja-vesi/soojus/"
                      "kooskolastatud-hinnad")
TALLINNA_VESI_URL = "https://www.tallinnavesi.ee/"
ADVEN_URL = "https://adven.com/"

USER_AGENT = ("home-finder heat ingest (polite monthly pull, single GET, "
              "file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str, name: str) -> str:
    """Cache file for one named heat snapshot (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)
    return os.path.join(cache_dir, "heat-%s.csv" % safe)


def cache_is_fresh(path: str, ttl_s: int = HEAT_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_s seconds."""
    try:
        age_s = ((now if now is not None else time.time())
                 - os.path.getmtime(path))
    except OSError:
        return False
    return age_s < ttl_s


def fetch_heat_csv(name: str, url: str, cache_dir: str = "/tmp/hf-cache",
                   ttl_s: int = HEAT_TTL_S) -> str:
    """Fetch one heat snapshot politely (single GET, cached, TTL-stated).

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
# Parsing: heat tariff-zone snapshot layout (semicolon-separated,
# BOM-tolerant). Column names follow the documented snapshot; unknown
# columns are ignored, empty cells and absent columns read as None
# (never guessed). No personal data in this layout by construction
# (zone-level tariffs, no subject rows).
# ---------------------------------------------------------------------------

#: Canonical record keys produced by parse_heat_zones (all Optional
#: except the join key zone_key, which is always a non-empty str).
HEAT_FIELDS = (
    "zone_key", "operator", "tariff_zone", "tariff_eur_mwh",
    "tariff_status", "water_zone", "return_bonus", "updated",
)

_OPERATORS = ("utilitas", "adven", "tallinna_kyte", "katlamaja")
_TARIFF_STATUSES = ("kehtiv", "kooskõlastamisel")
_BONUS_YES = ("jah", "yes", "kehtib")
_BONUS_NO = ("ei", "no", "pole")


def _clean(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _norm(value: Optional[object]) -> str:
    return "" if value is None else str(value).strip().lower()


def _parse_tariff(value: Optional[object]) -> Optional[float]:
    """Parse a €/MWh cell (comma or dot decimals); unparseable -> None."""
    s = _clean(value)
    if s is None:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _parse_bonus(value: Optional[object]) -> Optional[bool]:
    """Parse the return-temp bonus cell; unknown tokens -> None."""
    token = _norm(value)
    if not token:
        return None
    if token in _BONUS_YES:
        return True
    if token in _BONUS_NO:
        return False
    return None


def parse_heat_zones(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse one heat tariff-zone snapshot into canonical zone records.

    Semicolon-separated, BOM-tolerant; empty cells and absent columns
    become None. Rows without a zone_key are skipped (no join key —
    keeping them would fake join coverage). Unknown operator/status
    tokens read as None (never guessed); unparseable tariffs read as
    None (never zero — zero would fake free heat).
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        key = _clean(row.get("zone_key"))
        if not key:
            continue
        rec = {"zone_key": key}  # type: Dict[str, Optional[object]]
        operator = _norm(row.get("operator"))
        rec["operator"] = operator if operator in _OPERATORS else None
        rec["tariff_zone"] = _clean(row.get("tariff_zone"))
        rec["tariff_eur_mwh"] = _parse_tariff(row.get("tariff_eur_mwh"))
        status = _norm(row.get("tariff_status"))
        rec["tariff_status"] = status if status in _TARIFF_STATUSES else None
        rec["water_zone"] = _clean(row.get("water_zone"))
        rec["return_bonus"] = _parse_bonus(row.get("return_bonus"))
        rec["updated"] = _clean(row.get("updated"))
        records.append(rec)
    return records


def index_by_zone(
        records: List[Dict[str, Optional[object]]]
) -> Dict[str, Dict[str, Optional[object]]]:
    """Per-address join index (one zone record per key; first row wins)."""
    index = {}  # type: Dict[str, Dict[str, Optional[object]]]
    for rec in records:
        key = rec.get("zone_key")
        if key and str(key) not in index:
            index[str(key)] = rec
    return index


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _lst(listing: Optional[dict]) -> dict:
    return listing if isinstance(listing, dict) else {}


def _missing_heat() -> Score:
    return None, ("Selle aadressi kaugkütte tariifitsooni hetktõmmises pole "
                  "— operaator ja piirhind on teadmata (EI OLE hinnangut): "
                  "küsi KÜ-lt jaanuariarve näidis ja kontrolli "
                  "Konkurentsiameti kooskõlastatud hindu")


def _describe(zone: dict) -> str:
    operator = zone.get("operator") or "teadmata operaator"
    tariff = zone.get("tariff_eur_mwh")
    if isinstance(tariff, (int, float)):
        return "%s, %.2f €/MWh" % (operator, tariff)
    return "%s, tariif määramata" % operator


# ---------------------------------------------------------------------------
# P4-008 (demo): heating tariff zone + operator + water/sewer tariff.
# Per-address dim scoring bill PREDICTABILITY (45/60/NULL) — never
# cheapness: the table alone never prices a January bill.
# ---------------------------------------------------------------------------

def dim_heating_tariff(zone: Optional[dict],
                       listing: Optional[dict] = None) -> Score:
    """P4-008: known tariff zone makes January budgetable (60/45/NULL)."""
    _ = _lst(listing)  # listing side unused — per-address zone join
    if not isinstance(zone, dict):
        return _missing_heat()
    if zone.get("operator") is None and zone.get("tariff_eur_mwh") is None:
        return None, ("Liidetud tariifikirje on tühi (operaatorit ega "
                      "piirhinda pole) — selle aadressi küttearvet EI OLE "
                      "hinnangut: küsi KÜ-lt jaanuariarve näidis")
    if (zone.get("tariff_eur_mwh") is not None
            and zone.get("tariff_status") == "kehtiv"):
        return (60, "Teada tariifitsoon (%s, registriandmed, mitte hinnang) "
                    "— jaanuariarve on prognoositav (ülempiir 60: tegelik "
                    "kulu sõltub hoone tarbimisest, vaata KÜ aruannet)"
                % _describe(zone))
    return (45, "Operaator teada (%s, registriandmed, mitte hinnang), "
                "aga piirhind on kooskõlastamisel või määramata — "
                "nõrk ennustatavuse signaal (ülempiir 45), jaanuariarve "
                "selgub KÜ-lt" % _describe(zone))


# ---------------------------------------------------------------------------
# P4-036 (coverage): roof income, return-temp bonus slice. Per-building
# upside dim, capped at 65. The solar/mast/gable-ad legs (LiDAR roof
# facets, EHR katuse tüüp, Elektrilevi export, reklaamiluba) are NOT
# joined — this dim scores only the heat-ingestion bonus slice and
# says so.
# ---------------------------------------------------------------------------

def dim_roof_bonus(zone: Optional[dict],
                   listing: Optional[dict] = None) -> Score:
    """P4-036: Utilitas return-temp bonus as a yield kicker (65/NULL)."""
    _ = _lst(listing)  # listing side unused — per-address zone join
    if isinstance(zone, dict) and zone.get("return_bonus") is True:
        return (65, "Kaugkütte tagastustemperatuuri boonus on võimalik "
                    "(registriandmed, mitte hinnang) — tulu-kicker "
                    "(ülempiir 65): päikese/masti/reklaami jalad on "
                    "liitmata, boonuse tingimused uuri Utilitaselt")
    return None, ("Katuse tulu (päike/mast/reklaam) eeldaks LiDAR katuse- "
                  "tahkude, EHR katuse tüübi ja liitumismahu liitmist, "
                  "mida hetktõmmises pole, ja soojuslõigus boonust pole "
                  "(EI OLE tulu-hinnangut): küsi KÜ-lt katuse plaani")


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_HEAT_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_HEAT_DIMS = (
    ("heating_tariff", "P4-008", dim_heating_tariff),
    ("roof_bonus", "P4-036", dim_roof_bonus),
)


def score_p4_heat(zone: Optional[dict],
                  listing: Optional[dict] = None
                  ) -> Dict[str, Optional[int]]:
    """Both P4 heat dims for one address (entry point for the future
    enrich/score hook; keys match P4_HEAT_DIMS). Missing slices stay
    None by design — per-address join, never a faked area score."""
    return {key: fn(zone, listing)[0] for key, _, fn in P4_HEAT_DIMS}
