"""TEHIK medre Step-2 ADS join adapter (issue #660).

Joins the Step-1 register rows to coordinates via the Maa-amet ADS
gazetteer (inaadress.maaamet.ee, keyless open-data endpoint) and builds
the snapshot sidecar `medre/medre-points.json` the existing loader /
kernel / route already serve (no shared-file changes needed):

- reception rows (Harju `<koht>`) join on ADS `<adr_id>`: the gazetteer
  text hit is accepted ONLY when its `adr_id` equals the row id
  (exact-id join, EHR #136 family);
- clinic rows (Uldarstiabi `<tegevuskoht>` plain-text `<aadress>`) join
  on exact text: accepted ONLY on `kaugus == 0` + `kvaliteet ==
  "tapne_taisaadress"` (documented criterion).

Unjoined rows stay COUNTED (tallies + linkage report), never invented
(paaste #493 precedent). Points on the wire carry lat/lon/slice only —
GP names, EHR/ADS codes never leave the sidecar (dims precedent).
Licence CC BY-NC-SA 3.0 — attribution + share-alike + non-commercial
scope ride in the layer legends and docs/p4_medre.md.

Stdlib only; network lives ONLY in ads_search/main (fetch with a
stated TTL + file cache). Tests cover the pure join_ads, never the
network. Sidecar output is snapshot-only, never committed (AGENTS.md 5).
"""

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                               "services", "scoring"))

#: Vintage stamped on the extract (same bulks as Step 1, re-verified).
MEDRE_VINTAGE = "2026-09-16"

#: Licence line carried by the sidecar (share-alike scope, #660).
MEDRE_LICENCE = ("CC BY-NC-SA 3.0 (TEHIK medre / Tervisekassa register; "
                 "Maa-amet ADS viitepunktid)")

#: Keyless ADS gazetteer (verified 2026-09-19: single probe GET, exact
#: text hit returns adr_id + viitepunkt_b/viitepunkt_l in WGS84).
ADS_GAZETTEER = "https://inaadress.maaamet.ee/inaadress/gazetteer"

#: Identifying user agent for the polite pull (paced single GETs).
MEDRE_ADS_UA = (
    "home-finder-660-medre-ads/1.0 "
    "(polite monthly join, paced single GETs; "
    "GitHub gregoreesmaa/home-finder issue 660)"
)

#: Seconds between ADS GETs (polite pacing on top of the TTL).
ADS_PACE_S = 1.0

#: ADS answers are stable addresses: at most one refresh per 30 d.
ADS_TTL_S = 30 * 24 * 3600

#: Default ADS response cache dir (raw JSON lives here; /tmp only).
DEFAULT_ADS_CACHE_DIR = os.path.join("/tmp", "hf-660-medre-ads")

#: Step-1 bulk cache dir (raw medre bulks live here; /tmp only).
MEDRE_BULK_CACHE_DIR = os.path.join("/tmp", "hf-609-medre")

#: Estonia plausibility box for accepted viitepunkt coords (WGS84).
EE_LAT = (57.5, 59.7)
EE_LON = (21.5, 28.2)


class AdsStop(Exception):
    """HTTP 429 from ADS: stop signal, abort the run (never retry-dare)."""


def normalize_address(text: str) -> str:
    """Fold an address for exact-match keys (whitespace + case)."""
    return " ".join((text or "").split()).casefold()


def ads_key_reception(adr_id: str) -> str:
    """Join key for a reception row: the ADS address id."""
    return "id:%s" % (adr_id or "").strip()


def ads_key_clinic(address: str) -> str:
    """Join key for a clinic row: the normalized plain-text address."""
    return "t:%s" % normalize_address(address)


def fixture_rows_378_537() -> dict:
    """Synthetic Step-1-shaped bundle: 378 reception + 537 clinic rows.

    Hermetic fixture only (synthetic Tallinn/Harju addresses, never
    network): all but 2 reception + 2 clinic rows carry known ADS keys,
    so the join proves both the joined path and the counted-unjoined
    path. Coordinates are plausible Tallinn points (test asserts range).
    """
    ads: Dict[str, Tuple[float, float]] = {}
    reception: List[dict] = []
    for i in range(378):
        adr_id = str(100000 + i)
        addr = ("Harju maakond, Tallinn, Kesklinna linnaosa, "
                "Vastuvotu tn %d" % (i + 1))
        reception.append({"adr_id": adr_id,
                          "adr_kood": "78400000000000000000000000000000",
                          "address": addr})
        if i < 376:
            ads[ads_key_reception(adr_id)] = (
                59.40 + (i % 100) * 0.001, 24.70 + (i % 100) * 0.001)
    clinic: List[dict] = []
    for i in range(537):
        addr = ("Harju maakond, Tallinn, Kliiniku tn %d" % (i + 1))
        clinic.append({"address": addr})
        if i < 535:
            ads[ads_key_clinic(addr)] = (
                59.41 + (i % 100) * 0.001, 24.71 + (i % 100) * 0.001)
    return {"reception": reception, "clinic": clinic, "ads": ads}


def join_ads(bundle: dict, out_dir: str) -> dict:
    """Join register rows to the ADS index; write the sidecar; report.

    bundle: {"reception": [{adr_id, adr_kood, address}], "clinic":
    [{address}], "ads": {join-key: (lat, lon)}}. Unknown keys stay
    unjoined (counted, never invented). Writes
    out_dir/medre/medre-points.json in the shape loadMedrePoints reads
    (points: [{lat, lon, slice}] only). Returns {"counts",
    "unjoined", "points", "linkage_rate"}.
    """
    ads = bundle.get("ads", {})
    points: List[dict] = []
    unjoined = {"reception": 0, "clinic": 0}
    for row in bundle.get("reception", []):
        hit = ads.get(ads_key_reception(row.get("adr_id", "")))
        if hit is None:
            unjoined["reception"] += 1
            continue
        lat, lon = hit
        points.append({"lat": lat, "lon": lon, "slice": "gp"})
    for row in bundle.get("clinic", []):
        hit = ads.get(ads_key_clinic(row.get("address", "")))
        if hit is None:
            unjoined["clinic"] += 1
            continue
        lat, lon = hit
        points.append({"lat": lat, "lon": lon, "slice": "clinic"})
    n_rec = len(bundle.get("reception", []))
    n_cli = len(bundle.get("clinic", []))
    total = n_rec + n_cli
    rate = len(points) / total if total else 0.0
    doc = {
        "vintage": MEDRE_VINTAGE,
        "licence": MEDRE_LICENCE,
        "linkage_rate": rate,
        "linkage_note": (
            "%d/%d addresses ADS-joined "
            "(reception by adr_id, clinic by exact text; "
            "%d unjoined, counted never placed)" % (
                len(points), total,
                unjoined["reception"] + unjoined["clinic"])),
        "counts": {"gp": sum(1 for p in points if p["slice"] == "gp"),
                   "clinic": sum(1 for p in points
                                 if p["slice"] == "clinic"),
                   "total": len(points)},
        "points": points,
    }
    medre_dir = os.path.join(out_dir, "medre")
    os.makedirs(medre_dir, exist_ok=True)
    with open(os.path.join(medre_dir, "medre-points.json"), "w",
              encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    return {"counts": {"reception": n_rec, "clinic": n_cli},
            "unjoined": unjoined,
            "points": points,
            "linkage_rate": rate}


# ---------------------------------------------------------------------------
# Live ADS resolution (network ONLY here + main).
# ---------------------------------------------------------------------------

def ads_search(address: str, cache_dir: str,
               memo: dict) -> Optional[dict]:
    """One polite gazetteer text search (TTL file cache + memo).

    Returns the parsed JSON or None (transport errors are never data).
    HTTP 429 raises AdsStop (stop signal — the run aborts unwritten).
    """
    if address in memo:
        return memo[address]
    if not (address or "").strip():
        # No address to resolve: never send an empty query (unjoined).
        memo[address] = None
        return None
    os.makedirs(cache_dir, exist_ok=True)
    key = hashlib.sha1(address.encode("utf-8")).hexdigest()
    dest = os.path.join(cache_dir, key + ".json")
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ADS_TTL_S):
            with open(dest, encoding="utf-8") as f:
                doc = json.load(f)
            memo[address] = doc
            return doc
    except (OSError, ValueError):
        pass
    url = ADS_GAZETTEER + "?" + urllib.parse.urlencode(
        {"address": address})
    req = urllib.request.Request(url, headers={"User-Agent": MEDRE_ADS_UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                memo[address] = None
                return None
            body = resp.read()
    except urllib.error.HTTPError as e:
        # urlopen RAISES on HTTP errors (never returns a 429 response,
        # so status-sniffing above cannot see one): a 429 is the stop
        # signal (abort the run unwritten); any other HTTP error marks
        # just this row unresolvable (counted-unjoined downstream).
        if e.code == 429:
            raise AdsStop("ADS answered 429 (stop, not retry)")
        memo[address] = None
        return None
    except Exception:
        memo[address] = None
        return None
    try:
        doc = json.loads(body.decode("utf-8"))
    except ValueError:
        memo[address] = None
        return None
    try:
        with open(dest, "w", encoding="utf-8") as f:
            f.write(body.decode("utf-8"))
    except OSError:
        pass
    memo[address] = doc
    return doc


def _coords_of(candidate: dict) -> Optional[Tuple[float, float]]:
    """WGS84 viitepunkt of a gazetteer candidate, plausibility-checked."""
    try:
        lat = float(candidate.get("viitepunkt_b", ""))
        lon = float(candidate.get("viitepunkt_l", ""))
    except (TypeError, ValueError):
        return None
    if not (EE_LAT[0] <= lat <= EE_LAT[1]
            and EE_LON[0] <= lon <= EE_LON[1]):
        return None
    return (lat, lon)


def pick_reception(doc: Optional[dict], adr_id: str
                   ) -> Optional[Tuple[float, float]]:
    """Accept the exact-adr_id hit with kaugus 0, else None (unjoined)."""
    if not doc or not isinstance(doc.get("addresses"), list):
        return None
    for cand in doc["addresses"]:
        if not isinstance(cand, dict):
            continue
        if str(cand.get("kaugus", "")) != "0":
            continue
        if str(cand.get("adr_id", "")) != str(adr_id or "").strip():
            continue
        hit = _coords_of(cand)
        if hit is not None:
            return hit
    return None


def pick_clinic(doc: Optional[dict]) -> Optional[Tuple[float, float]]:
    """Accept the exact full-address hit (tapne_taisaadress, kaugus 0)."""
    if not doc or not isinstance(doc.get("addresses"), list):
        return None
    for cand in doc["addresses"]:
        if not isinstance(cand, dict):
            continue
        if str(cand.get("kaugus", "")) != "0":
            continue
        if cand.get("kvaliteet") != "tapne_taisaadress":
            continue
        hit = _coords_of(cand)
        if hit is not None:
            return hit
    return None


def resolve_live(reception: List[dict], clinic: List[dict],
                 cache_dir: str) -> Dict[str, Tuple[float, float]]:
    """Resolve all rows via ADS (paced, cached); returns the ads index.

    Transport failures mark that row unresolvable (caller counts it
    unjoined); HTTP 429 raises AdsStop (whole run aborts unwritten).
    """
    ads: Dict[str, Tuple[float, float]] = {}
    memo: dict = {}
    total = len(reception) + len(clinic)
    done = 0

    def step() -> None:
        nonlocal done
        done += 1
        if done % 50 == 0:
            print("medre-ads: %d/%d resolved (%d joined)"
                  % (done, total, len(ads)))

    for row in reception:
        addr = row.get("address", "")
        hit = pick_reception(ads_search(addr, cache_dir, memo),
                             row.get("adr_id", ""))
        if hit is not None:
            ads[ads_key_reception(row.get("adr_id", ""))] = hit
        step()
        time.sleep(ADS_PACE_S)
    for row in clinic:
        addr = row.get("address", "")
        if addr in memo:
            # Shared building: no request, no pace sleep either.
            hit = pick_clinic(memo[addr])
        else:
            hit = pick_clinic(ads_search(addr, cache_dir, memo))
            time.sleep(ADS_PACE_S)
        if hit is not None:
            ads[ads_key_clinic(addr)] = hit
        step()
    return ads


def main(cache_dir: str = DEFAULT_ADS_CACHE_DIR,
         medre_cache_dir: str = MEDRE_BULK_CACHE_DIR,
         out_dir: Optional[str] = None) -> int:
    """Pull Step-1 bulks (TTL-guarded), ADS-join all rows, build sidecar."""
    import xml.etree.ElementTree as ET  # noqa: E402 (live path only)
    from batch_medre import (COMPANIES_MIN_BYTES, COMPANIES_URL,  # noqa
                             NIMISTUD_MIN_BYTES, NIMISTUD_URL,
                             fetch_cached)
    from dims_p4_medre import (parse_companies_xml,  # noqa
                               parse_nimistud_xml)
    if out_dir is None:
        print("medre-ads: refusing to write without --out-dir "
              "(sidecars are snapshot-only, never committed)")
        return 1
    nim_path = fetch_cached(NIMISTUD_URL, medre_cache_dir, "nimistud.xml",
                            NIMISTUD_MIN_BYTES)
    comp_path = fetch_cached(COMPANIES_URL, medre_cache_dir,
                             "companies.xml", COMPANIES_MIN_BYTES)
    if nim_path is None or comp_path is None:
        print("medre-ads: harvest incomplete (transport refused or thin "
              "body); no sidecar written")
        return 1
    with open(nim_path, encoding="utf-8") as f:
        rec_rows, _ = parse_nimistud_xml(f.read())
    with open(comp_path, encoding="utf-8") as f:
        cli_rows, comp_stats = parse_companies_xml(f.read())
    # Reception leg: Harju rows only (verdict rule — same 378 the Step-1
    # tallies pin); clinic leg: every Uldarstiabi tegevuskoht (537 —
    # the loader filters by viewport, wider points never render wrong).
    reception = [r for r in rec_rows
                 if (r["address"].startswith("Harju maakond")
                     or ", Tallinn" in r["address"])]
    clinic = cli_rows
    print("medre-ads: %d Harju reception + %d clinic rows to resolve"
          % (len(reception), len(clinic)))
    try:
        ads = resolve_live(reception, clinic, cache_dir)
    except AdsStop as e:
        print("medre-ads: %s; no sidecar written" % e)
        return 1
    out = join_ads({"reception": reception, "clinic": clinic,
                    "ads": ads}, out_dir)
    n_gp = sum(1 for p in out["points"] if p["slice"] == "gp")
    n_cli = sum(1 for p in out["points"] if p["slice"] == "clinic")
    print("medre-ads extract: %d points (gp %d, clinic %d), linkage %.4f; "
          "unjoined reception %d, clinic %d" % (
              len(out["points"]), n_gp, n_cli,
              out["linkage_rate"], out["unjoined"]["reception"],
              out["unjoined"]["clinic"]))
    print("register companies stats: %s" % (comp_stats,))
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", default=DEFAULT_ADS_CACHE_DIR)
    ap.add_argument("--medre-cache-dir", default=MEDRE_BULK_CACHE_DIR)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    raise SystemExit(main(cache_dir=args.cache_dir,
                          medre_cache_dir=args.medre_cache_dir,
                          out_dir=args.out_dir))
