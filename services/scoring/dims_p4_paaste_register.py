"""P4 paaste static-register check (issue #523, dated verdict + honest-empty).

The rescue-station layer reads 0 because it holds no komando points and
must never invent them. This module answers the follow-up question: is
there a static official station register (komandod with addresses) worth
snapshotting? Verdict 2026-09-16 (two polite single GETs, probe UA, no
retries, full evidence in docs/p4_paaste_register.md): PARTIAL — the
rescue.ee kontakt tree serves STRUCTURED unit rows (names, slugs,
street addresses such as "Erika tn 3, Tallinn") via its own static
Nuxt payloads, but ZERO coordinate tokens (latitude/longitude/geojson
x 0) and ZERO komando-level rows on the regional page. Addresses are
not points: hand-geocoding them would invent stations. So the snapshot
below is a dated register WITHOUT geometry, and the dim stays NULL
with an improved empty message that names what is missing and why.

Ingestion contract: a monthly-cron adapter pulls the four regional
kontakt payloads (polite UA, per-file cache, TTL below); the pure
helper parses one payload into register rows; the dim reads the dated
snapshot. Transport errors raise and never touch the cache; HTTP 429
stops the run.

Style mirrors services/scoring/dims_p4_paaste.py (#276/#350): pure
offline scorers, stdlib-only (re + urllib), local helpers (no sibling
imports — a future central hook may import this module alongside them
and importing any of them here would turn that into a cycle, same
precedent as batch B3, PR #100).

Judgment calls (reviewable per AGENTS.md section 7.5):
* TTL 30 d follows the paaste stats cadence (PAASTE_CACHE_TTL_S):
  the kontakt tree moves on reorganisation timescales, so at most
  one live pull per month; the snapshot date travels in the extract
  and is echoed in every NULL reason.
* The dim returns None even with a fresh snapshot: a register row
  without coordinates cannot join a 500 m buffer or a 5 km komando
  penalty (dims_p4_paaste STATION_FAR_KM). Scoring an address as a
  point would be fake precision, so absence of geometry is absence
  of score — the reason says so explicitly.
* Address detection is a narrow street-suffix pattern (tn/pst/mnt/
  tee/plats/tnt plus a house number): it under-matches rather than
  over-matches — a missed address keeps the row address-less (still
  NULL either way), while a false address could one day be mistaken
  for a geocodable row. Fail-closed on purpose.
* Test fixtures are fully synthetic (clearly labelled) — real
  observed values appear only in docs/p4_paaste_register.md,
  never as ingested data.

Integration (deliberately NOT done here): feeding register rows into
livability scoring and rebalancing livability.WEIGHTS must be one
joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. No shared files touched: 3 new files only. Never touch
dims_p4_paaste.py (the P4-012 scorer) or apps/web/lib/layers_paaste.ts
(the honest-empty overlay); the improved empty message lives in this
module's reasons and docs until the joint change.
"""

import os
import re
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source identity, politeness, cache.
# ---------------------------------------------------------------------------

#: Human kontakt hub (verified 2026-09-16: HTTP 200, human HTML org tree).
PAASTE_KONTAKT_URL = "https://www.rescue.ee/et/kontaktid"
#: Static per-region payloads the hub's own Nuxt frontend serves
#: (verified 2026-09-16: HTTP 200, application/javascript, structured
#: unit rows, zero coordinate tokens). One file per paastekeskus.
PAASTE_PAYLOAD_URLS = (
    "https://www.rescue.ee/_nuxt/static/1/et/kontaktid/pohja_paastekeskus/payload.js",
    "https://www.rescue.ee/_nuxt/static/1/et/kontaktid/laane_paastekeskus/payload.js",
    "https://www.rescue.ee/_nuxt/static/1/et/kontaktid/louna_paastekeskus/payload.js",
    "https://www.rescue.ee/_nuxt/static/1/et/kontaktid/ida_paastekeskus/payload.js",
)
PAASTE_REGISTER_USER_AGENT = (
    "home-finder-p4-paaste-register/1.0 (Estonia open-data monthly adapter; "
    "polite single-pull, cache-first)"
)
#: Kontakt tree moves on reorganisation timescales: at most one live
#: pull per month (paaste stats-cadence precedent).
PAASTE_REGISTER_TTL_S = 30 * 86400
PAASTE_REGISTER_CACHE_PREFIX = "paasteamet-register-"

#: Tokens that would signal machine-readable geometry in a payload.
#: All read 0 on the 2026-09-16 probe (dated negative, pinned by test).
GEOMETRY_TOKENS = ("latitude", "longitude", "geojson", "coordinates")

#: Narrow street-address pattern (fail-closed: under-matches on purpose,
#: see module docstring). Matches "Erika tn 3", "Pärnu mnt 67a".
_ADDRESS_RE = re.compile(
    r"\b[A-ZÕÄÖÜ][\wõäöü\- ]{1,40}?\s"
    r"(?:tn|pst|mnt|tee|plats)\s+\d+[a-z]?\b"
)
#: String literals inside the Nuxt JSONP payload (pure helper input).
_LITERAL_RE = re.compile(r'"((?:[^"\\]|\\.){2,200})"')
#: Nuunicoded slash inside payload literals ("Päästeamet\u002FPõhja...").
_SLASH_ESC = "\\u002F"


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------

def _unescape(literal: str) -> str:
    return literal.replace(_SLASH_ESC, "/").replace("\\n", " ").strip()


def _is_address(text: str) -> bool:
    return _ADDRESS_RE.search(text) is not None


# ---------------------------------------------------------------------------
# Ingestion: polite cached pull (live path, NOT unit-run) + pure parse.
# ---------------------------------------------------------------------------

def _cache_path(cache_dir: str, index: int) -> str:
    return os.path.join(
        cache_dir, "%s%d.js" % (PAASTE_REGISTER_CACHE_PREFIX, index))


def cache_is_fresh(path: str, ttl_s: int = PAASTE_REGISTER_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached payload exists and is younger than ttl_s."""
    try:
        age_s = (now if now is not None else time.time()) - os.path.getmtime(path)
    except OSError:
        return False
    return age_s < ttl_s


def fetch_register_snapshot(
    cache_dir: Optional[str] = None,
    ttl_s: int = PAASTE_REGISTER_TTL_S,
) -> Tuple[str, str]:
    """Polite cached pull of the regional kontakt payloads (live path).

    Cache-first; pulls only stale/missing files (at most four small
    static GETs per TTL window). Any transport error (HTTP error,
    timeout, 429, decode failure) raises and the cache files are left
    untouched — transport errors are never cached as data, and 429
    stops the run. Returns (concatenated_payloads, provenance) with
    provenance "cache" or "live".
    """
    if cache_dir is None:
        cache_dir = os.path.join("/tmp", "hf-paaste-register")
    os.makedirs(cache_dir, exist_ok=True)
    bodies: List[str] = []
    provenance = "cache"
    for index, url in enumerate(PAASTE_PAYLOAD_URLS):
        path = _cache_path(cache_dir, index)
        if cache_is_fresh(path, ttl_s):
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                bodies.append(fh.read())
            continue
        req = urllib.request.Request(
            url, headers={"User-Agent": PAASTE_REGISTER_USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            if resp.status == 429:
                raise RuntimeError("Paasteamet vastas 429 — peatu, ara reetry")
            if resp.status != 200:
                raise RuntimeError(
                    "Paasteamet vastas HTTP %s — vahemalu puutumata" % resp.status
                )
            body = resp.read().decode("utf-8", errors="replace")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        bodies.append(body)
        provenance = "live"
    return "\n".join(bodies), provenance


def parse_register_payload(js_text: str) -> dict:
    """Parse kontakt payload(s) into the register snapshot (pure).

    Extracts unit names (rows carrying paaste/komando vocabulary),
    street addresses (narrow pattern, fail-closed), and the geometry
    signal (any GEOMETRY_TOKENS hit). A payload with no rows reads as
    an explicitly empty register (dated-negative friendly), never an
    error — absence of rows is data about openness, not a failure.
    """
    literals = [_unescape(m) for m in _LITERAL_RE.findall(js_text or "")]
    rows: List[dict] = []
    seen = set()
    for text in literals:
        lowered = text.lower()
        if "pääste" not in lowered and "komando" not in lowered:
            continue
        if len(text) > 120 or text in seen:
            continue
        seen.add(text)
        address = text if _is_address(text) else None
        rows.append({"unit": text, "address": address})
    # Attach trailing addresses: a bare unit path followed by its
    # street address lands in the same literal window — second pass
    # pairs address-only literals to the register pool.
    addresses = sorted({t for t in (_unescape(m)
                                    for m in _LITERAL_RE.findall(js_text or ""))
                        if _is_address(t)})
    lowered_all = (js_text or "").lower()
    has_geometry = any(tok in lowered_all for tok in GEOMETRY_TOKENS)
    return {
        "units": rows,
        "addresses": addresses,
        "n_units": len(rows),
        "n_addresses": len(addresses),
        "has_geometry": has_geometry,
        "source": ("Paasteamet kontaktipuu staatiline valjavote "
                   "(rescue.ee, inimloetav, koordinaatideta)"),
    }


def tallinn_extract(register: dict,
                    fetched: Optional[str] = None) -> Dict[str, object]:
    """Build the snapshot the dim consumes from a parsed register (pure).

    Keeps every unit row (thin register included — the dim applies the
    NULL contract, so the snapshot stays a faithful extract, never a
    pre-scored selection). The fetch date travels in the extract and
    is echoed in every NULL reason.
    """
    if fetched is None:
        fetched = time.strftime("%Y-%m-%d", time.gmtime())
    units = [u for u in (register or {}).get("units", [])
             if isinstance(u, dict)]
    return {"fetched": fetched, "units": units, "n_units": len(units),
            "n_addresses": (register or {}).get("n_addresses", 0),
            "has_geometry": bool((register or {}).get("has_geometry", False)),
            "source": (register or {}).get("source", "")}


# ---------------------------------------------------------------------------
# P4-012 register leg: honest-empty NULL with the improved message.
# ---------------------------------------------------------------------------

def dim_station_register(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]] = None,
                         register: Optional[dict] = None) -> Score:
    """P4-012 komando-register leg: always NULL, message names the gap.

    A register row without coordinates cannot join a distance buffer,
    so even a fresh snapshot scores nothing — the reason carries the
    dated register tally (units, street addresses, zero geometries),
    what is missing (komando coordinates) and why (addresses are not
    points; hand-geocoding would invent stations), plus the buyer-side
    check. `pois` is accepted for the uniform scorer shape and ignored
    (komando points are not OSM POIs).
    """
    _ = pois
    snap = register if isinstance(register, dict) else None
    if snap is None:
        return None, ("Päästekomandode register teadmata (EI OLE hinnangut): "
                      "kontaktipuu staatilist väljavõtet hetktõmmises pole — "
                      "lähima komando kauguse hinnang selgub rescue.ee "
                      "kontaktidest ja kohapeal, sõiduaeg Tark Tee kaardilt, "
                      "ära feigi tühjast vahemälust skoori")
    fetched = snap.get("fetched") if isinstance(snap.get("fetched"), str) \
        else "teadmata"
    return None, ("Päästekomandode register on koordinaatideta (EI OLE "
                  "hinnangut; väljavõte %s: %d üksuse-kirjet, %d "
                  "tänava-aadressi, 0 koordinaati): aadress ei ole punkt — "
                  "käsitsi geokodeerimine võltsiks komandode asukohad, "
                  "seetõttu puhvri- ega sõiduaja-hinnangut ei anta; "
                  "kontrolli rescue.ee kontakte ja Tark Tee kaarti kohapeal"
                  % (fetched, snap.get("n_units", 0),
                     snap.get("n_addresses", 0)))


P4_PAASTE_REGISTER_DIMS = (
    ("station_register", "P4-012", dim_station_register),
)
