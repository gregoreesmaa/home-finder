"""TEHIK medre primary-care harvest + build (issue #609, Step 1).

Polite single-fetch harvest of the medre GP-lists bulk (nimistud XML,
DAILY feed) and the providers bulk (companies XML), and an offline
build of the register extract the medre_gp/medre_clinic map overlays
serve. Stdlib only; network lives ONLY in fetch_cached/main.

Feed verdict (2026-09-16, see services/scoring/dims_p4_medre.py and
docs/p4_medre.md; aggregates only, raw bodies never committed): 782
<nimistu> rows (371 Harju GP reception addresses with <adr_id> ADS
refs, ZERO with coordinates) + 1572 <asutus> rows (832 Harju/Tallinn,
Üldarstiabi tegevuskohad with plain-text addresses, ZERO with
coordinates). NEITHER bulk ships coordinates — linkage_rate is 0 until
the Step-2 ADS adr_id->AKS join adapter exists (no join owned
anywhere in the repo today).

Step-1 honesty (AGENTS.md 7.2, paaste #493 precedent): the sidecar
carries the register tallies + linkage report with points [] — caller-
joined points do not exist yet, and hand-geocoding addresses would
invent clinics. The map layers serve honestly-empty (EI OLE legend)
with the loader/route/kernel plumbing ready for Step-2 points. The
open/closed leg stays NULL (no bulk column exists — dims precedent).
Transport errors are never cached as data (fetch_cached stores only
HTTP 200 bodies over a minimum size). GP names never leave the
sidecar wire (tallies only, no per-doctor rows). Licence CC BY-NC-SA
3.0 — attribution + share-alike + non-commercial scope ride in the
layer legends and docs/p4_medre.md.
"""

import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                               "services", "scoring"))
from dims_p4_medre import parse_companies_xml, parse_nimistud_xml

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: GP-lists bulk (verified 2026-09-16: HTTP 200, ~3.6 MB XML, DAILY).
NIMISTUD_URL = ("https://medre.tehik.ee/api-common/public/"
                "general-practitioner-lists/open-data")

#: Providers bulk (verified 2026-09-16: HTTP 200, ~14.5 MB XML, DAILY).
COMPANIES_URL = ("https://medre.tehik.ee/api-common/public/companies/open-data")

#: DAILY feed, monthly harvest at most (dims_p4_medre TTL 30 d).
MEDRE_TTL_S = 30 * 24 * 3600

#: Identifying user agent for the polite pull (paced single GETs, no scrape).
MEDRE_UA = (
    "home-finder-609-medre/1.0 "
    "(polite monthly harvest, paced single GETs; "
    "GitHub gregoreesmaa/home-finder issue 609)"
)

#: Seconds between harvest GETs (polite pacing on top of the TTL).
MEDRE_PACE_S = 5

#: Minimum plausible bodies: nimistud ~3.6 MB, companies ~14.5 MB —
#: anything smaller is an error page, never data.
NIMISTUD_MIN_BYTES = 2_000_000
COMPANIES_MIN_BYTES = 8_000_000

#: Vintage stamped on the extract (harvest date, re-verified per pull).
MEDRE_VINTAGE = "2026-09-16"

#: Default cache dir (raw bulks live here; /tmp only, AGENTS.md 5).
DEFAULT_CACHE_DIR = os.path.join("/tmp", "hf-609-medre")


def fetch_cached(url: str, cache_dir: str, filename: str,
                 min_bytes: int,
                 ttl_s: int = MEDRE_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise
    one GET with MEDRE_UA and a 60 s timeout; the body is stored only on
    HTTP 200 with at least min_bytes bytes, else None is returned and
    nothing is cached (transport errors are never data). No retries —
    HTTP 429/errors are a stop signal. Scorers never call this; tests
    cover the pure build, never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, filename)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": MEDRE_UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status != 200:
                return None
            body = resp.read()
    except Exception:
        return None
    if len(body) < min_bytes:
        return None
    try:
        with open(dest, "wb") as f:
            f.write(body)
    except OSError:
        return None
    return dest


# ---------------------------------------------------------------------------
# Pure offline build (hermetic, pinned by test_batch_medre.py).
# ---------------------------------------------------------------------------

def build_sidecar(nimistud_root: ET.Element, companies_root: ET.Element,
                  out_dir: str) -> dict:
    """Build medre/medre-points.json from parsed bulks; returns the doc.

    Step 1: register tallies + linkage report travel; points stays []
    (no ADS join owned — caller-joined set is empty, paaste precedent).
    Step 2 (ADS adapter) fills points and bumps linkage_rate; the loader
    and kernel already serve whatever the sidecar carries.
    """
    import json
    _, nim_stats = parse_nimistud_xml(ET.tostring(nimistud_root,
                                                  encoding="unicode"))
    _, comp_stats = parse_companies_xml(ET.tostring(companies_root,
                                                   encoding="unicode"))
    register = {
        "nimistu": nim_stats["nimistu"],
        "kohad": nim_stats["kohad"],
        "harju_kohad": nim_stats["harju_kohad"],
        "asutus": comp_stats["asutus"],
        "harju_asutus": comp_stats["harju_asutus"],
        "uldarstiabi_kohad": comp_stats["uldarstiabi_kohad"],
        "other_licences": comp_stats["other_licences"],
    }
    doc = {
        "vintage": MEDRE_VINTAGE,
        "licence": "CC BY-NC-SA 3.0 (TEHIK medre / Tervisekassa register)",
        "linkage_rate": 0,
        "linkage_note": ("0/X addresses joined — no ADS adr_id->AKS join "
                         "adapter owned (Step 2); caller-joined set empty"),
        "register": register,
        "counts": {"gp": 0, "clinic": 0, "total": 0},
        "points": [],
    }
    medre_dir = os.path.join(out_dir, "medre")
    os.makedirs(medre_dir, exist_ok=True)
    with open(os.path.join(medre_dir, "medre-points.json"), "w",
              encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    return doc


def main(cache_dir: str = DEFAULT_CACHE_DIR,
         out_dir: Optional[str] = None) -> int:
    """Harvest both bulks (polite, TTL-guarded) and build the extract."""
    nim_path = fetch_cached(NIMISTUD_URL, cache_dir, "nimistud.xml",
                            NIMISTUD_MIN_BYTES)
    time.sleep(MEDRE_PACE_S)
    comp_path = fetch_cached(COMPANIES_URL, cache_dir, "companies.xml",
                             COMPANIES_MIN_BYTES)
    if nim_path is None or comp_path is None:
        print("medre harvest incomplete (transport refused or thin body); "
              "no sidecar written")
        return 1
    doc = build_sidecar(ET.parse(nim_path).getroot(),
                        ET.parse(comp_path).getroot(),
                        out_dir or os.path.join(cache_dir, "snapshot"))
    print("medre extract: %d points %s (vintage %s, linkage %s)" % (
        doc["counts"]["total"], doc["counts"], doc["vintage"],
        doc["linkage_rate"]))
    print("register: %s" % (doc["register"],))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
