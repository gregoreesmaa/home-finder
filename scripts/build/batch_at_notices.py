"""Month-by-month Ametlikud Teadaanded harvester + kataster linkage miner.

Issue #628 (linkage before flags, #550): AT records carry no
coordinates, so flags need a proven parcel join first. This builder
pulls type-sliced month lists through the public URI-reuse scheme,
fetches each notice XML, mines free text for kataster tunnus
signatures, and measures the linkage_rate that gates every flag.

Politeness (AGENTS.md section 7.4, verified 2026-09-17):
* Type-sliced lists ONLY -- the wide-open month list
  (/ee/-/-/-/{year}/{month}) times out server-side, so it is never
  requested. One slice x one month per run unless --all-slices.
* 2 s pace between GETs, HTTP 429 stops the run (no retry dare),
  TTL-guarded file cache (default 1 day, enforcement window).
* NEVER commit real pulls -- sidecar goes to the snapshot dir only;
  tests use synthetic fixtures.

List pages carry full rows inline (title + Avaldamise algus/lopp +
body + provider), so one GET yields up to 1000 minable notices --
per-notice XML pulls are unnecessary for linkage. Bodies may contain
personal data (names, isikukood): the miner keeps TUNNUS signatures
ONLY and never persists notice text or person fields.

Usage:
  python3 scripts/build/batch_at_notices.py --slice zoning --year 2026 --month 8 \\
      --cache-dir /tmp/hf-at --snap ~/hf-data/2026-09-17
  python3 scripts/build/batch_at_notices.py --merge-only --cache-dir /tmp/hf-at \\
      --snap ~/hf-data/2026-09-17   # offline rebuild from cache
"""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "services", "scoring"))
from dims_p4_ata import parse_kpv  # noqa: E402

AT_BASE = "https://www.ametlikudteadaanded.ee"
UA = ("home-finder AT harvest (polite type-sliced month pulls, file "
      "cache; contact via GitHub home-finder)")
TTL_DAYS = 1
PACE_S = 2.0

#: Harvest slices. pealiik slugs are PROVISIONAL (lowercased display
#: stems per the /ee/-/advokatuur example) -- verified=False until a
#: live run proves each slug serves a list. A wrong slug fails LOUD
#: (non-200 list URL raises), never silently harvests zero notices.
SLICES = {
    "quarry": {"pealiik": "kaevandamisluba", "alaliik": "-",
               "dim": "quarry", "band": 35, "verified": False,
               "keywords": ("kaevandamis", "kaevandus", "maardla",
                            "karjäär", "kaeve")},
    "zoning": {"pealiik": "planeering", "alaliik": "-",
               "dim": "zoning", "band": 55, "verified": False,
               "keywords": ("planeering", "detailplaneering",
                            "üldplaneering")},
    "cadastre": {"pealiik": "kinnistus", "alaliik": "-",
                 "dim": "cadastre", "band": 60, "verified": False,
                 "keywords": ("kinnistus", "kataster", "katastritunnus",
                              "piirimenetlus")},
    "felling": {"pealiik": "metsateatis", "alaliik": "-",
                "dim": "felling", "band": None, "verified": False,
                "keywords": ("metsateatis", "raieluba", "raie",
                             "metsaregister")},
}

#: Estonian kataster tunnus: 78401:107:0760. Segments validated
#: loosely (municipality 2-5 digits); tighter validation belongs to
#: the kataster join, not the text miner.
TUNNUS_RE = re.compile(r"\b(\d{2,5}:\d{1,4}:\d{1,4})\b")

#: Notice rows on a URI-list page (verified 2026-09-17 on
#: /ee/-/advokatuur): title link /avalik/teadaanne?teate_number=N,
#: then announcement-date (Avaldamise algus/lopp dd.mm.yyyy), full
#: announcement-body text, and announcement-provider. Rows are mined
#: inline -- no per-notice fetch needed for linkage.
ROW_RE = re.compile(
    r'<a href="/avalik/teadaanne\?teate_number=(\d+)">([^<]*)</a>'
    r'.*?<div class="announcement-date">\s*'
    r'Avaldamise algus:\s*([0-9.]+)<br>\s*'
    r'Avaldamise l\u00f5pp:\s*([0-9.]+)'
    r'.*?<div class="announcement-body">(.*?)</div>\s*'
    r'.*?<div class="announcement-provider">(.*?)<',
    re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def slice_list_url(pealiik, alaliik="-"):
    """Type-sliced list URI (month filter runs client-side on algus).

    Date segments in the URI serve empty shells anonymously
    (verified 2026-09-17, even for a known-good pealiik), so the
    month window is applied to Avaldamise algus after the pull --
    never the wide-open unfiltered list.
    """
    url = "%s/ee/-/%s" % (AT_BASE, pealiik)
    if alaliik != "-":
        url += "/%s" % alaliik
    return url


def _in_month(algus, year, month):
    day = parse_kpv(algus)
    return day is not None and day.year == year and day.month == month


def _resolve_archived(lopp, today=None):
    from datetime import date as _date
    day = parse_kpv(lopp)
    if day is None:
        return None
    return day < (today if today is not None else _date.today())


def _get_offline(url, cache_dir):
    """Cache read for --merge-only (missing cache fails loud)."""
    path = _cache_path(cache_dir, url)
    if not os.path.exists(path):
        raise RuntimeError("offline cache miss %s (run online first)"
                           % url)
    with open(path, "rb") as f:
        return f.read()


def _rows_to_notices(rows, slice_key, year, month):
    month_rows = [r for r in rows if _in_month(r["algus"], year, month)]
    notices = []
    for row in month_rows:
        rec = row_to_record(row, slice_key)
        rec["archived"] = _resolve_archived(row["lopp"])
        notices.append(rec)
    return notices, len(rows)


def _cache_path(cache_dir, url):
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_"
                   for c in url)
    return os.path.join(cache_dir, "at-%s" % safe[-120:])


def _fresh(path, ttl_days=TTL_DAYS):
    if not os.path.exists(path):
        return False
    age_days = (time.time() - os.path.getmtime(path)) / 86400.0
    return age_days < ttl_days


def _get(url, cache_dir, pace_s=PACE_S, ttl_days=TTL_DAYS):
    """One polite GET with TTL file cache. 429 stops the run loud."""
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, url)
    if _fresh(path, ttl_days):
        with open(path, "rb") as f:
            return f.read()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.status == 429:
                raise RuntimeError("HTTP 429 -- stop, not retry (polite)")
            body = r.read()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("GET failed %s: %s" % (url, exc))
    with open(path, "wb") as f:
        f.write(body)
    time.sleep(pace_s)
    return body


def _clean(raw):
    """Visible text of an HTML fragment (tags -> space, collapsed)."""
    text = html.unescape(TAG_RE.sub(" ", raw or ""))
    return WS_RE.sub(" ", text).strip()


def parse_list_html(page_html):
    """Notice rows off a URI-list page (deduped on teate_number).

    Returns [{number, title, algus, lopp, body, provider}]; person
    names/codes in body/provider are the caller's to DROP (miner
    keeps tunnus signatures only).
    """
    text = page_html.decode("utf-8", errors="replace") if isinstance(
        page_html, (bytes, bytearray)) else page_html
    seen, out = set(), []
    for match in ROW_RE.finditer(text):
        num = match.group(1)
        if num in seen:
            continue
        seen.add(num)
        out.append({"number": num,
                    "title": _clean(match.group(2)),
                    "algus": match.group(3).strip(),
                    "lopp": match.group(4).strip(),
                    "body": _clean(match.group(5)),
                    "provider": _clean(match.group(6))})
    return out


def row_to_record(row, slice_key):
    """A list row -> linkage record (tunnus signatures only)."""
    return {"notice_id": row["number"],
            "url": "%s/avalik/teadaanne?teate_number=%s"
                   % (AT_BASE, row["number"]),
            "liik_nimi": row["title"],
            "avaldatud": row["algus"],
            "lopp": row["lopp"],
            "archived": None,  # resolved against monthday, see below
            "andmeandja": None,  # provider text may name persons: dropped
            "slice": slice_key,
            "tunnused": mine_tunnused(row["body"], row["title"])}


def mine_tunnused(*texts):
    """Kataster tunnus signatures from free-text fields (order kept)."""
    found = []
    for text in texts:
        if not isinstance(text, str):
            continue
        for match in TUNNUS_RE.finditer(text):
            tun = match.group(1)
            if tun not in found:
                found.append(tun)
    return found


def linkage_rate(notices):
    """Share of notices carrying >= 1 mined tunnus (0.0 on empty)."""
    if not notices:
        return 0.0
    linked = sum(1 for n in notices if n.get("tunnused"))
    return linked / len(notices)


def harvest_slice(slice_key, year, month, cache_dir, pace_s=PACE_S,
                  max_notices=1000, pealiik=None, alaliik=None):
    """One slice -> month-filtered linkage records (ONE polite GET)."""
    spec = SLICES[slice_key]
    pealiik = pealiik or spec["pealiik"]
    alaliik = alaliik if alaliik is not None else spec["alaliik"]
    if pealiik != spec["pealiik"]:
        print("pealiik override %s (slice default %s, unverified)"
              % (pealiik, spec["pealiik"]), flush=True)
    body = _get(slice_list_url(pealiik, alaliik), cache_dir, pace_s)
    rows = parse_list_html(body)
    if not rows and not spec["verified"]:
        print("WARNING: slug '%s' served zero rows -- pealiik slug "
              "unverified (see SLICES); run --pealiik with a verified "
              "slug" % pealiik, flush=True)
    if len(rows) >= max_notices:
        print("WARNING: slice hit the 1000-result cap -- narrow by "
              "alaliik (%s)" % slice_key, flush=True)
    return _rows_to_notices(rows, slice_key, year, month)


def harvest_slice_offline(slice_key, year, month, cache_dir,
                          max_notices=1000, pealiik=None, alaliik=None):
    """Offline rebuild of one slice-month from cache (no network)."""
    _ = max_notices
    spec = SLICES[slice_key]
    pealiik = pealiik or spec["pealiik"]
    alaliik = alaliik if alaliik is not None else spec["alaliik"]
    body = _get_offline(slice_list_url(pealiik, alaliik), cache_dir)
    return _rows_to_notices(parse_list_html(body), slice_key, year, month)


def build_sidecar(notices, listed, slice_key, year, month):
    """Snapshot doc: per-notice linkage rows + honest stats."""
    rows = [{"id": n.get("notice_id"), "url": n.get("url"),
             "liik": n.get("liik_nimi"), "avaldatud": n.get("avaldatud"),
             "archived": n.get("archived"), "tunnused": n.get("tunnused", []),
             "slice": slice_key} for n in notices]
    return {"slice": slice_key, "year": year, "month": month,
            "pealiik": SLICES[slice_key]["pealiik"],
            "slug_verified": SLICES[slice_key]["verified"],
            "notices": rows,
            "stats": {"listed": listed, "parsed": len(notices),
                      "linked": sum(1 for r in rows if r["tunnused"]),
                      "linkage_rate": linkage_rate(notices),
                      "attribution": ("Ametlikud Teadaanded "
                                      "(avaandmed, URI-otsing)")}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", default="zoning",
                    choices=sorted(SLICES),
                    help="harvest slice (type-sliced lists only)")
    ap.add_argument("--pealiik", default=None,
                    help="override the slice pealiik slug (proof runs)")
    ap.add_argument("--alaliik", default=None)
    ap.add_argument("--all-slices", action="store_true")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int, default=8)
    ap.add_argument("--cache-dir", default="/tmp/hf-at")
    ap.add_argument("--snap", default=None)
    ap.add_argument("--merge-only", action="store_true",
                    help="offline rebuild from cache (no network)")
    ap.add_argument("--pace", type=float, default=PACE_S)
    ap.add_argument("--max-notices", type=int, default=1000,
                    help="1000-result cap guard (slice further on hit)")
    args = ap.parse_args(argv)
    if not args.snap:
        ap.error("--snap is required (writes <snap>/at/at-notices.json)")
    keys = sorted(SLICES) if args.all_slices else [args.slice]
    merged = []
    for key in keys:
        if args.merge_only:
            notices, listed = harvest_slice_offline(
                key, args.year, args.month, args.cache_dir,
                args.max_notices, args.pealiik, args.alaliik)
        else:
            notices, listed = harvest_slice(
                key, args.year, args.month, args.cache_dir, args.pace,
                args.max_notices, args.pealiik, args.alaliik)
        print("%s %d-%02d: listed=%d parsed=%d linked=%d rate=%.3f"
              % (key, args.year, args.month, listed, len(notices),
                 sum(1 for n in notices if n.get("tunnused")),
                 linkage_rate(notices)), flush=True)
        if listed >= args.max_notices:
            print("WARNING: slice hit the 1000-result cap -- narrow by "
                  "alaliik or day (%s %d-%02d)" % (key, args.year,
                                                   args.month), flush=True)
        if len(keys) == 1:
            doc = build_sidecar(notices, listed, key, args.year,
                                args.month)
        else:
            merged.extend((key, n) for n in notices)
    if len(keys) > 1:
        flat = []
        for key, n in merged:
            n["slice"] = key
            flat.append(n)
        doc = {"slices": keys, "year": args.year, "month": args.month,
               "notices": flat,
               "stats": {"parsed": len(flat),
                         "linkage_rate": linkage_rate(flat)}}
    out = os.path.join(args.snap, "at", "at-notices.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    print("wrote %d notices -> %s" % (len(doc["notices"]), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
