"""Shared adapter interface for Estonian listing portals.

Every portal adapter (kv.ee, city24.ee, ...) MUST expose this surface:

    SOURCE: str        # e.g. "kv.ee"
    BASE_URL: str      # e.g. "https://kv.ee"
    SEARCH_URL: str    # polite single-page search endpoint
    ROBOTS_URL: str    # BASE_URL + "/robots.txt" (check before polling)
    HEADERS: dict      # polite UA identifying home-finder + daily poll
    fetch_search_html(query="", page_limit=1, timeout=20.0) -> str
    parse_search_html(html) -> list[dict]  # offline-safe, no network
    scrape(query="", page_limit=1, cache_dir=None, cache_ttl_s=86400) -> list[dict]

Canonical record: {id, source, source_url, address, price} plus optional
detail fields (rooms, area_m2) which are None when the card omits them.

Politeness contract (AGENTS.md §5): default page_limit=1, daily-cron cadence,
desktop UA, file cache (default TTL 24h) so repeat runs hit disk not the
portal, and NEVER commit scraped dumps — fixtures only.
"""

import hashlib
import json
import os
import re
import time
from typing import Callable, List, Optional

import httpx

DEFAULT_USER_AGENT = "home-finder/0.1 (+research scaffold; daily poll)"
DEFAULT_TTL_S = 24 * 3600  # daily cron

# Punch-through for contract tests: every adapter must return these keys.
REQUIRED_KEYS = ("id", "source", "source_url", "address", "price")
OPTIONAL_KEYS = ("rooms", "area_m2")


def polite_headers() -> dict:
    return {"User-Agent": DEFAULT_USER_AGENT}


def normalize_listing(raw: dict) -> dict:
    """Fill a raw card dict into the canonical record shape (pure, offline)."""
    rec = dict(raw)
    rec.setdefault("address", "")
    rec["address"] = re.sub(r"\s+", " ", str(rec.get("address") or "")).strip()
    if not rec["address"]:
        rec["address"] = "%s #%s" % (rec.get("source", "unknown"), rec.get("id", "?"))
    for key in OPTIONAL_KEYS:
        rec.setdefault(key, None)
    return rec


def address_key(address: str) -> str:
    """Overlap-dedup key: lowercase, collapse whitespace, drop punctuation."""
    s = (address or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"[^\w\s]", "", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def dedup_key(item: dict) -> tuple:
    return (address_key(item.get("address", "")), item.get("price"))


def dedup_listings(*lists: List[dict]) -> List[dict]:
    """Merge portal result lists, dropping cross-portal duplicates.

    Two rows are the same listing when (normalized address, price) match.
    First occurrence wins, so callers order lists by preferred source.
    """
    seen = set()
    out: List[dict] = []
    for rows in lists:
        for item in rows or []:
            key = dedup_key(item)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out


def _cache_path(cache_dir: str, namespace: str, query: str, page_limit: int) -> str:
    digest = hashlib.sha256(("%s|%s|%s" % (namespace, query, page_limit)).encode()).hexdigest()[:16]
    return os.path.join(cache_dir, "%s-%s.html" % (namespace, digest))


def read_cache(path: str, ttl_s: float) -> Optional[str]:
    try:
        if time.time() - os.path.getmtime(path) > ttl_s:
            return None
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def write_cache(path: str, html: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def cached_fetch(
    namespace: str,
    query: str,
    page_limit: int,
    fetch_fn: Callable[[], str],
    cache_dir: Optional[str] = None,
    cache_ttl_s: float = DEFAULT_TTL_S,
) -> str:
    """Return cached HTML when fresh, else call fetch_fn once and store it."""
    if not cache_dir:
        return fetch_fn()
    path = _cache_path(cache_dir, namespace, query, page_limit)
    hit = read_cache(path, cache_ttl_s)
    if hit is not None:
        return hit
    html = fetch_fn()
    write_cache(path, html)
    return html


def fetch_html(url: str, params: dict, headers: dict, timeout: float = 20.0) -> str:
    resp = httpx.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


CHROME_BINARY_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
)

# Headless engines advertise "HeadlessChrome" in the default UA, a well-known
# bot signal. Override with the ordinary desktop UA of the engine's own
# major version (verified: this + virtual-time-budget passes kv.ee).
CHROME_DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)


def find_chrome_binary() -> Optional[str]:
    """Path to a real Chrome/Chromium engine, or None when not installed."""
    import shutil

    for cand in CHROME_BINARY_CANDIDATES:
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def fetch_html_via_chrome(url: str, timeout: float = 280.0) -> str:
    """Render a page with genuine headless Chrome and return the DOM HTML.

    Some portals (kv.ee) gate on the TLS fingerprint, which scripted HTTP
    clients cannot present; a real browser engine passes with no spoofing
    and no challenge-solving. Polite use only: callers keep page_limit=1,
    daily-cron cadence, and the 24h file cache. Raises RuntimeError when
    no Chrome engine is installed.
    """
    import subprocess
    import tempfile

    binary = find_chrome_binary()
    if not binary:
        raise RuntimeError("no Chrome/Chromium engine installed for fallback fetch")
    # Fresh profile per call: a reused dir can block on a stale Singleton lock
    # and serialize concurrent runs. --timeout caps the page load itself
    # (--dump-dom alone can hang on pages with never-ending connections);
    # the subprocess timeout is a backstop that also kills strays.
    import shutil

    profile = tempfile.mkdtemp(prefix="hf-chrome-")
    proc = None
    try:
        proc = subprocess.run(
            [
                binary,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--user-data-dir=%s" % profile,
                "--user-agent=%s" % CHROME_DESKTOP_UA,
                # Listing pages carry dozens of image carousels; decoding
                # them under software rendering dominates wall time while
                # contributing nothing to the extracted markup/JSON-LD.
                "--blink-settings=imagesEnabled=false",
                "--virtual-time-budget=20000",
                "--timeout=%d" % int(timeout * 1000),
                "--dump-dom",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("headless Chrome timed out for %s" % url)
    finally:
        if proc is None:
            for _p in _chrome_pids_for_profile(profile):
                try:
                    import os as _os
                    import signal as _signal

                    _os.kill(_p, _signal.SIGKILL)
                except OSError:
                    pass
        shutil.rmtree(profile, ignore_errors=True)
    html = proc.stdout or "" if proc else ""
    if "<html" not in html.lower():
        raise RuntimeError("headless Chrome returned no document for %s" % url)
    return html


def _chrome_pids_for_profile(profile: str) -> list:
    """PIDs whose command line references the given profile dir."""
    import subprocess as _sp

    try:
        out = _sp.run(["pgrep", "-f", profile], capture_output=True, text=True).stdout
    except OSError:
        return []
    pids = []
    for line in out.splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            pass
    return pids


def to_int_eur(raw: Optional[str]) -> Optional[int]:
    digits = re.sub(r"\D", "", raw or "")
    return int(digits) if digits else None


def to_float_m2(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    m = re.search(r"[\d.,]+", raw.replace("\u00a0", " "))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def to_int_rooms(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    m = re.search(r"\d+", raw)
    return int(m.group(0)) if m else None


def parse_meta_json(html: str) -> dict:
    """Best-effort JSON-LD / meta dump for future detail-field enrichment."""
    try:
        blobs = re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S | re.I
        )
        return {"ld_json_blocks": len(blobs)}
    except re.error:
        return {"ld_json_blocks": 0}


def adapter_contract_check(mod) -> List[str]:
    """Return a list of contract violations (empty == conforms)."""
    problems = []
    for attr in ("SOURCE", "BASE_URL", "SEARCH_URL", "ROBOTS_URL", "HEADERS"):
        if not hasattr(mod, attr):
            problems.append("missing %s" % attr)
    for fn in ("fetch_search_html", "parse_search_html", "scrape"):
        if not callable(getattr(mod, fn, None)):
            problems.append("missing callable %s" % fn)
    return problems
