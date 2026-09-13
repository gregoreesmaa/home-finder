"""Harvest per-KOV Statamet PX-Web aggregates for issue #485 (Layer: Statamet
per-KOV choropleths RVR/IA028/EH/RR).

Polite keyless pull (contact UA, >=3 s pacing, 25 s timeout, file cache with
TTL; HTTP 429 is a stop signal, transport errors never cached). Writes the
dated aggregate fixture scripts/build/statkov_px_tables.json (16 Harju KOVs x
a handful of annual numbers -- an aggregate table, never a scraped dump).

Table grains (verified 2026-09-13, metadata cached /tmp/hf-485-stat/):
* RVR02 (ranne): per-haldusuksus, annual to 2025. Pre-reform area codes
  (140=Anija ... H39=Lääne-Harju) -- joined by NAME, never by H-code.
  Pull: 2025, Sugu=total, Näitaja=Rändesaldo, Rände liik=sise+väli (summed).
* EH44U (kasutusload): per-haldusüksus, annual to 2025. Full EHAK-path
  codes (EE0037...) -- the EHAK digits join OSM TEHAK:code exactly.
  Pull: 2025, TOTAL rooms, PNUM (completions only -- permits have NO KOV
  grain: EH04 is national, EH045 is county. Dated negative, docstring).
* RR300 (KOV eelarve): per-haldusüksus, annual to 2025. Pull: 2025,
  indicators 1 (tulud) / 19 (kulud) / 29 (tulem) / 43 (eelarve tulem).
* RV0291U (rahvaarv): per-Elukoht, 1. jaanuar to 2026. Pull: 2025+2026
  Rahvaarv (mid-year average = rate denominator, documented).
* IA028 (eluaskeme hinnaindeks): NATIONAL grain only (Aasta/Kvartal/
  Eluaseme liik -- no area dimension). A national constant cannot colour
  KOVs (flat-colour fantasy, MARU/Euribor PR #475 precedent) -- REFUSED
  for the choropleth, dated negative. No pull.

Usage:
  python3 scripts/build/harvest_statkov_px.py --out scripts/build/statkov_px_tables.json
  python3 scripts/build/harvest_statkov_px.py --refresh   # ignore cache, re-pull
"""

import argparse
import datetime as _dt
import hashlib
import json
import os
import time
import urllib.request

BASE = "https://andmed.stat.ee/api/v1/et/stat"
UA = ("home-finder-research/0.1 (polite PX-Web aggregate harvest; "
      "GitHub gregoreesmaa/home-finder issue 485)")
TABLES = {
    "RVR02": "rahvastik/rahvastikusundmused/ranne/RVR02.px",
    "EH44U": "majandus/ehitus/ehitus-ja-kasutusload/EH44U.PX",
    "RR300": ("majandus/rahandus/valitsemissektori-rahandus/"
              "kohalike-omavalitsuste-eelarve/RR300.PX"),
    "RV0291U": ("rahvastik/rahvastikunaitajad-ja-koosseis/"
                "rahvaarv-ja-rahvastiku-koosseis/RV0291U.PX"),
}
TTL_DAYS = 365  # all four pulls are annual tables

# Harju KOV area codes per table (exact metadata values 2026-09-13) with the
# canonical join name. RVR/RR codes are PRE-REFORM (Saku 718, Saue 727,
# Lääne-Harju H39/H16) -- names are the join key, codes are pull-only.
RVR_AREAS = [
    ("140", "Anija"), ("198", "Harku"), ("245", "Jõelähtme"),
    ("296", "Keila"), ("304", "Kiili"), ("337", "Kose"),
    ("353", "Kuusalu"), ("424", "Loksa"), ("H39", "Lääne-Harju"),
    ("446", "Maardu"), ("651", "Raasiku"), ("653", "Rae"),
    ("718", "Saku"), ("727", "Saue"), ("784", "Tallinn"),
    ("890", "Viimsi"),
]
EH_AREAS = [
    ("EE00370141000001", "Anija"), ("EE00370198000001", "Harku"),
    ("EE00370245000001", "Jõelähtme"), ("EE00370296000004", "Keila"),
    ("EE00370305000001", "Kiili"), ("EE00370338000001", "Kose"),
    ("EE00370353000001", "Kuusalu"), ("EE00370424000004", "Loksa"),
    ("EE00370431000001", "Lääne-Harju"), ("EE00370446000004", "Maardu"),
    ("EE00370651000001", "Raasiku"), ("EE00370653000001", "Rae"),
    ("EE00370719000001", "Saku"), ("EE00370725000001", "Saue"),
    ("EE00370784000004", "Tallinn"), ("EE00370890000001", "Viimsi"),
]
RR_AREAS = [(c if c != "H39" else "H16", n) for c, n in RVR_AREAS]
RV_AREAS = [
    ("7", "Anija"), ("10", "Harku"), ("11", "Jõelähtme"),
    ("12", "Keila"), ("13", "Kiili"), ("14", "Kose"),
    ("15", "Kuusalu"), ("16", "Loksa"),
    ("17", "Lääne-Harju"), ("20", "Maardu"), ("21", "Raasiku"),
    ("22", "Rae"), ("23", "Saku"), ("24", "Saue"),
    ("27", "Tallinn"), ("36", "Viimsi"),
]

QUERIES = {
    "RVR02": [
        ("Aasta", ["2025"]),
        ("Haldusüksus/Asustuspiirkonna liik", [c for c, _ in RVR_AREAS]),
        ("Sugu", ["1"]),
        ("Näitaja", ["3"]),
        ("Rände liik", ["1", "2"]),
    ],
    "EH44U": [
        ("Vaatlusperiood", ["2025"]),
        ("Piirkond/haldusüksus", [c for c, _ in EH_AREAS]),
        ("Tubade arv", ["TOTAL"]),
        ("Näitaja", ["PNUM"]),
    ],
    "RR300": [
        ("Aasta", ["2025"]),
        ("Piirkond/Haldusüksus", [c for c, _ in RR_AREAS]),
        ("Näitaja", ["1", "19", "29", "43"]),
    ],
    "RV0291U": [
        ("Elukoht", [c for c, _ in RV_AREAS]),
        ("Aasta", ["2025", "2026"]),
        ("Näitaja", ["1"]),
    ],
}
AREA_DIM = {
    "RVR02": "Haldusüksus/Asustuspiirkonna liik",
    "EH44U": "Piirkond/haldusüksus",
    "RR300": "Piirkond/Haldusüksus",
    "RV0291U": "Elukoht",
}
AREA_NAMES = {
    "RVR02": dict(RVR_AREAS),
    "EH44U": dict(EH_AREAS),
    "RR300": dict(RR_AREAS),
    "RV0291U": dict(RV_AREAS),
}


def _fresh(path, ttl_days, now=None):
    try:
        mtime = _dt.datetime.fromtimestamp(
            os.path.getmtime(path), tz=_dt.timezone.utc)
    except OSError:
        return False
    at = now or _dt.datetime.now(tz=_dt.timezone.utc)
    return (at - mtime) <= _dt.timedelta(days=ttl_days)


def _post(url, payload, cache_path, ttl_days, refresh=False):
    if not refresh and _fresh(cache_path, ttl_days):
        with open(cache_path, "rb") as fh:
            return fh.read()
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        if resp.status == 429:
            raise RuntimeError("HTTP 429 -- stop, do not retry: " + url)
        raw = resp.read()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    tmp = cache_path + ".part"
    with open(tmp, "wb") as fh:
        fh.write(raw)
    os.replace(tmp, cache_path)
    return raw


def pull(table, cache_dir, refresh=False):
    """POST one data query; returns the decoded JSON-stat dataset."""
    url = BASE + "/" + TABLES[table]
    payload = {
        "query": [
            {"code": code,
             "selection": {"filter": "item", "values": values}}
            for code, values in QUERIES[table]
        ],
        "response": {"format": "json"},
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
    cache_path = os.path.join(cache_dir, "hf-485-px",
                              "%s-%s.json" % (table, digest))
    raw = _post(url, payload, cache_path, TTL_DAYS, refresh)
    return json.loads(raw.decode("utf-8"))


def _number(raw):
    if raw is None:
        return None
    try:
        return float(str(raw).replace(" ", ""))
    except ValueError:
        return None


def flatten(dataset):
    """PX row-JSON payload -> {(dimcode, valuecode, ...): number|None}.

    Payload shape: {"columns": [{code, ..., type}...],
    "data": [{"key": [...], "values": [...]}]}. The trailing content
    column (type "c") has no key entry and is skipped.
    """
    cols = [c["code"] for c in dataset["columns"] if c.get("type") != "c"]
    out = {}
    for row in dataset["data"]:
        key = tuple(zip(cols, row["key"]))
        vals = row.get("values") or []
        out[key] = _number(vals[0] if vals else None)
    return out


def get(cell, *pairs):
    return cell.get(tuple(pairs))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache-dir", default="/tmp/hf-cache")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)

    cells = {}
    for table in ("RVR02", "EH44U", "RR300", "RV0291U"):
        cells[table] = flatten(pull(table, args.cache_dir, args.refresh))
        if table != "RV0291U":
            time.sleep(3)

    kovs = {}
    for code, name in RVR_AREAS:
        a = AREA_DIM["RVR02"]
        sise = get(cells["RVR02"], ("Aasta", "2025"), (a, code),
                   ("Sugu", "1"), ("Näitaja", "3"), ("Rände liik", "1"))
        vali = get(cells["RVR02"], ("Aasta", "2025"), (a, code),
                   ("Sugu", "1"), ("Näitaja", "3"), ("Rände liik", "2"))
        saldo = None if sise is None or vali is None else sise + vali
        kovs.setdefault(name, {})["rvr_saldo_2025"] = saldo
    for code, name in EH_AREAS:
        a = AREA_DIM["EH44U"]
        kovs.setdefault(name, {})["eh_completions_2025"] = get(
            cells["EH44U"], ("Vaatlusperiood", "2025"), (a, code),
            ("Tubade arv", "TOTAL"), ("Näitaja", "PNUM"))
    for code, name in RR_AREAS:
        a = AREA_DIM["RR300"]
        row = kovs.setdefault(name, {})
        row["rr_tulud_2025"] = get(cells["RR300"], ("Aasta", "2025"),
                                   (a, code), ("Näitaja", "1"))
        row["rr_kulud_2025"] = get(cells["RR300"], ("Aasta", "2025"),
                                   (a, code), ("Näitaja", "19"))
        row["rr_tulem_2025"] = get(cells["RR300"], ("Aasta", "2025"),
                                   (a, code), ("Näitaja", "29"))
        row["rr_eelarve_tulem_2025"] = get(cells["RR300"], ("Aasta", "2025"),
                                          (a, code), ("Näitaja", "43"))
    for code, name in RV_AREAS:
        row = kovs.setdefault(name, {})
        row["pop_2025_01_01"] = get(cells["RV0291U"], ("Elukoht", code),
                                    ("Aasta", "2025"), ("Näitaja", "1"))
        row["pop_2026_01_01"] = get(cells["RV0291U"], ("Elukoht", code),
                                    ("Aasta", "2026"), ("Näitaja", "1"))

    fixture = {
        "harvested_at": _dt.date.today().isoformat(),
        "period": "2025 (RVR saldo / EH completions / RR budget; "
                  "population 01.01.2025 + 01.01.2026 mid-year average)",
        "sources": {t: BASE + "/" + TABLES[t]
                    for t in ("RVR02", "EH44U", "RR300", "RV0291U")},
        "ia028_negative": ("IA028 eluaskeme hinnaindeks is NATIONAL grain "
                           "(Aasta/Kvartal/Eluaseme liik, no area dimension) "
                           "-- refused for the choropleth 2026-09-13."),
        "kovs": kovs,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(fixture, fh, ensure_ascii=False, indent=1)
    print("wrote %s (%d KOVs)" % (args.out, len(kovs)))
    for name in sorted(kovs):
        print(" ", name, kovs[name])


if __name__ == "__main__":
    main()
