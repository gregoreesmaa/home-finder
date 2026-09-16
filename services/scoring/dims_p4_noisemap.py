"""P4 strategic-noise-map dim (issue #526, documented no-map + band dim).

Source: Maa- ja Ruumiamet (Land and Spatial Administration) strategic
noise maps (mürakaardid) WFS — Tallinn + Tartu + main roads; road,
tram, rail, air + industrial sources; Lden/Lday/Levening/Lnight;
2017 maps (2015 data) and 2022 maps (2020-2021 data).
Viewer: xgis.maaamet.ee/xgis2/page/app/myrakaart.

OPENNESS (probed 2026-09-16, one polite round, UA
home-finder-idea-probe/1.0, paced >= 3 s, cached to /tmp/hf-526-529-probe,
full evidence in docs/p4_noisemap.md):
* GetCapabilities: HTTP 200, 69 922 B, title "Mürakaardi rakenduse
  kaardikihid". ~70 layers: 2017 myra_* (auto/mnt/rdt/lend/toostus/
  kast/sum x paev/ohtu/oo/aasta) + 2022 myra22_siser_* (national
  Ld/Ln at 2 m) + 2022 myra22_strat_* (strategic, incl. the Lden
  leg ms:myra22_strat_sum_oopaev and the Lnight leg
  ms:myra22_strat_sum_oo).
* Service self-declares Fees "Teenuse kasutamisel tasusid ei
  rakendu" and AccessConstraints NONE; CRS EPSG:3301 (+3857/4258/
  4326). DescribeFeatureType on the Lden leg: ID, YLDKLASS,
  MYRALIIK, MYRAINDEKS, MYRAKLASS (band field), AEG.
* Harjumaa hits: GetFeature resultType=hits on the Lden leg with a
  Harjumaa bbox (59.2,23.9-59.7,25.4) matched 4705 polygons.
* LICENCE: the national catalogue states NONE — the Teabevärav
  dataset page is a JS app shell (no static licence text to verify),
  and the WFS Fees/AccessConstraints lines govern service use, not
  the data licence. No open licence is confirmed.

VERDICT (the issue's own fallback clause): documented no-map. No
feature data was harvested (capabilities + schema + hits only), so
no Tallinn histogram exists to calibrate bands, and without a
confirmed licence nothing is ingested. The dim below implements the
issue's proposed Lden bands as caller-supplied provisional bands
(NULL without rows, NULL outside mapped polygons — outside stays
teadmata, never "quiet"), so only the harvest + histogram step
remains once the licence clears. Group 9 OSM proxy layers and
dims_p4_trans.noise_zone_trans stay untouched (no re-tuning here).

Style mirrors services/scoring/dims_p4_seveso.py (#527, same
session): pure offline scorers, stdlib-only, local helpers (no
sibling imports — a future central hook may import this module
alongside the others).

Judgment calls (reviewable per AGENTS.md 7.5):
* LDEN_BANDS are the issue's proposal verbatim (<=45 -> 85, <=55
  -> 65, <=65 -> 40, >65 -> 20). LNIGHT_BANDS shift 5 dB down
  (<=40 -> 85, <=50 -> 65, <=60 -> 40, >60 -> 20) — sleep
  disturbance starts lower; challenge with the histogram.
* The binding (minimum) leg wins when both Lden and Lnight rows
  are present: a quiet day does not cancel a loud night (the issue
  names Lnight "the binding one").
* parse_myaklass assumes the band domain reads like "55-59",
  "55-59 dB", ">65", "<45" (UNVERIFIED — no feature data was
  pulled; the adapter must confirm against real MYRAKLASS values
  and this assumption is pinned in docs/p4_noisemap.md §5).
  Unparseable labels read as None (never guessed).
* The capabilities fetch (TTL 180 d — maps renew every 5 years)
  exists only to date the verdict; it never feeds the scorer.

Integration (deliberately NOT done here): harvest script, raster
master, livability hook + WEIGHTS rebalance stay follow-up work
(reopening checklist in docs/p4_noisemap.md §5). No shared files
touched: 3 new files only.
"""

import os
import re
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Source identity, verdict record, politeness.
# ---------------------------------------------------------------------------

#: Strategic noise maps WFS (verified 2026-09-16: HTTP 200, 69 922 B caps).
NOISEMAP_WFS_BASE = "https://teenus.maaamet.ee/ows/myrakaart"
NOISEMAP_CAPS_URL = (NOISEMAP_WFS_BASE
                     + "?service=WFS&version=2.0.0&request=GetCapabilities")
#: Binding legs: 2022 strategic sum Lden + Lnight (hits-verified 2026-09-16).
NOISEMAP_LDEN_LAYER = "ms:myra22_strat_sum_oopaev"
NOISEMAP_LNIGHT_LAYER = "ms:myra22_strat_sum_oo"
NOISEMAP_USER_AGENT = (
    "home-finder-p4-noisemap/1.0 (Estonia open-data verdict check; "
    "polite single-pull, cache-first)"
)
#: Maps renew every 5 years (IRREG): the verdict re-check sleeps 180 d.
NOISEMAP_CACHE_TTL_S = 180 * 86400
NOISEMAP_CACHE_NAME = "myrakaart-capabilities.xml"

#: Dated probe this verdict rests on (YYYY-MM-DD).
PROBE_DATE = "2026-09-16"
#: GetCapabilities body size in bytes on the probe date.
PROBE_CAPS_BYTES = 69922
#: Lden-leg Harjumaa-bbox hits on the probe date (resultType=hits, no data).
PROBE_HARJU_HITS = 4705
#: Service self-declaration (service use, NOT a data licence — see verdict).
PROBE_FEES = "Teenuse kasutamisel tasusid ei rakendu"
PROBE_ACCESS = "NONE"
#: Licence state on the probe date: catalogue states NONE, Teabevärav
#: page is a JS shell with no static licence text, WFS lines govern
#: service use only.
PROBE_LICENCE = "kinnitamata (EI OLE avatud litsentsi)"

#: Provisional Lden bands (dB upper bound -> score; issue proposal verbatim).
LDEN_BANDS = ((45.0, 85), (55.0, 65), (65.0, 40))
LDEN_LOUD = 20
#: Provisional Lnight bands (5 dB sleep offset — reviewable judgment).
LNIGHT_BANDS = ((40.0, 85), (50.0, 65), (60.0, 40))
LNIGHT_LOUD = 20


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------

def _band_score(db_value: float,
                bands: Tuple[Tuple[float, int], ...], loud: int) -> int:
    for limit, pts in bands:
        if db_value <= limit:
            return pts
    return loud


_MYA_UPPER_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:dB)?\s*$")
_MYA_GT_RE = re.compile(r"^>\s*(\d+(?:[.,]\d+)?)")
_MYA_LT_RE = re.compile(r"^<\s*(\d+(?:[.,]\d+)?)")


def _num(text: str) -> Optional[float]:
    try:
        return float(text.replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse_myaklass(raw: Optional[str]) -> Optional[float]:
    """Parse a MYRAKLASS band label to its dB upper bound (pure, fail-closed).

    Assumed domain (UNVERIFIED — no feature data pulled, see module
    docstring): "55-59" / "55-59 dB" -> 59.0, ">65" -> 99.0 (above
    every band -> loud leg), "<45" -> 44.9 (below the first band ->
    quiet leg), "65" -> 65.0. Anything else reads as None.
    """
    if not isinstance(raw, str):
        return None
    text = " ".join(raw.strip().split()).replace("\u2013", "-").replace(
        "\u2014", "-")
    if not text:
        return None
    m = _MYA_GT_RE.match(text)
    if m:
        v = _num(m.group(1))
        return 99.0 if v is not None else None
    m = _MYA_LT_RE.match(text)
    if m:
        v = _num(m.group(1))
        return (v - 0.1) if v is not None else None
    if "-" in text:
        upper = _MYA_UPPER_RE.match(text.split("-")[-1].strip())
        return _num(upper.group(1)) if upper else None
    m = _MYA_UPPER_RE.match(text)
    return _num(m.group(1)) if m else None


_TITLE_RE = re.compile(r"<ows:Title>(.*?)</ows:Title>", re.DOTALL)
_NAME_RE = re.compile(r"<Name>(ms:[A-Za-z0-9_]+)</Name>")
_CRS_RE = re.compile(r"DefaultCRS>(urn:ogc:def:crs:EPSG::\d+)")


def parse_capabilities_layers(xml_text: str) -> dict:
    """Parse a GetCapabilities body into the verdict record (pure).

    Extracts the service title, ms:* layer names, and the default
    CRS. An unparseable body reads as explicitly empty (dated-negative
    friendly), never an error.
    """
    text = xml_text or ""
    title = _TITLE_RE.search(text)
    layers = sorted(set(_NAME_RE.findall(text)))
    crs = _CRS_RE.search(text)
    return {
        "title": title.group(1).strip() if title else "",
        "layers": layers,
        "n_layers": len(layers),
        "crs": crs.group(1) if crs else "",
        "source": "Maa- ja Ruumiamet mürakaardi WFS (teenus.maaamet.ee)",
    }


# ---------------------------------------------------------------------------
# Ingestion: polite cached capabilities pull (verdict-dating only) + dim.
# ---------------------------------------------------------------------------

def _cache_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, NOISEMAP_CACHE_NAME)


def cache_is_fresh(path: str, ttl_s: int = NOISEMAP_CACHE_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_s."""
    try:
        age_s = (now if now is not None else time.time()) - os.path.getmtime(path)
    except OSError:
        return False
    return age_s < ttl_s


def fetch_wfs_capabilities(
    cache_dir: Optional[str] = None,
    ttl_s: int = NOISEMAP_CACHE_TTL_S,
) -> Tuple[str, str]:
    """Polite cached GetCapabilities pull (live path, NOT unit-run).

    Dates the no-map verdict; never feeds the scorer. Fresh cache wins
    (no request). Any transport error raises and the cache file is left
    untouched — transport errors are never cached as data, and 429
    stops the run. Returns (xml, provenance).
    """
    if cache_dir is None:
        cache_dir = os.path.join("/tmp", "hf-noisemap-cache")
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir)
    if cache_is_fresh(path, ttl_s):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(), "cache"
    req = urllib.request.Request(
        NOISEMAP_CAPS_URL, headers={"User-Agent": NOISEMAP_USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as resp:  # noqa: S310
        if resp.status == 429:
            raise RuntimeError("Maa-amet vastas 429 — peatu, ära reetry")
        if resp.status != 200:
            raise RuntimeError(
                "Maa-amet vastas HTTP %s — vahemalu puutumata" % resp.status
            )
        body = resp.read().decode("utf-8", errors="replace")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return body, "live"


def dim_noise_lden(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]] = None,
                   noise: Optional[dict] = None) -> Score:
    """Strategic-noise Lden/Lnight band dim (provisional bands, binding leg).

    `noise` is a caller-supplied band join ({lden_db, lnight_db} in dB,
    plus fetched/source) — the future licensed harvest owns it. `pois`
    is accepted for the uniform scorer shape and ignored (noise bands
    are not OSM POIs). Without rows, or outside mapped polygons, the
    dim is NULL (teadmata, never "quiet").
    """
    _ = pois
    snap = noise if isinstance(noise, dict) else None
    if not origin:
        return None, ("Mürakaardi hinnang teadmata (EI OLE hinnangut): "
                      "aadress puudub — strateegilise mürakaardi Lden/ "
                      "Lnight vöönd (Ülemiste lennutrass, raudtee, "
                      "magistraalid) selgub aadressi asendist, mitte tühjalt")
    legs: Dict[str, float] = {}
    if snap is not None:
        for key in ("lden_db", "lnight_db"):
            v = snap.get(key)
            if isinstance(v, bool):
                continue
            try:
                f = float(v)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            import math as _math
            if _math.isfinite(f):
                legs[key] = f
    if not legs:
        return None, ("Mürakaardi hinnang teadmata (EI OLE hinnangut): "
                      "strateegilise mürakaardi (Maa- ja Ruumiamet, WFS) "
                      "litsents on kinnitamata ja Tallinna histogrammi "
                      "pole (%s) — vööndi väljavõtet hetktõmmises pole; "
                      "kontrolli xgis.maaamet.ee mürakaardi rakendust ja "
                      "9. rühma liiklusprokseid kohapeal"
                      % PROBE_LICENCE)
    scored = {}
    if "lden_db" in legs:
        scored["Lden"] = _band_score(legs["lden_db"], LDEN_BANDS, LDEN_LOUD)
    if "lnight_db" in legs:
        scored["Lnight"] = _band_score(legs["lnight_db"], LNIGHT_BANDS,
                                       LNIGHT_LOUD)
    binding = min(scored, key=lambda k: scored[k])
    score = scored[binding]
    detail = ", ".join("%s %.0f dB -> %d" % (k, legs[k.lower() + "_db"],
                                             scored[k]) for k in sorted(scored))
    return score, ("Strateegilise mürakaardi vööndi-hinnang (%s; siduv jalg "
                   "%s — vaikne päev ei kustuta lärmakat ööd): %s "
                   "(esialgsed bändid, histogramm kalibreerimata); unehäire "
                   "selgub Lnight-jalast, päevamüra Lden-jalast"
                   % (detail, binding, score))


def score_p4_noisemap(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]] = None,
                      noise: Optional[dict] = None
                      ) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """Rollup: {dim_key: score|None} + non-NULL reasons (pure)."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for key, _label, fn in P4_NOISEMAP_DIMS:
        value, reason = fn(origin, pois, noise)
        dims[key] = value
        if value is not None:
            reasons.append(reason)
    return dims, reasons


P4_NOISEMAP_DIMS = (
    ("noise_lden", "Noisemap", dim_noise_lden),
)
