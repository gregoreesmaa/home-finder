"""EMTA KOV transfer choropleth table builder (issue #539).

Stdlib only. Offline, snapshot-only (NO network): the maintainer places
the two annual EMTA CSVs (tulumaks + maamaks, `;`-delimited, BOM,
Estonian thousands spaces -- layout verified 2026-09-16 on the 2026
files, see services/scoring/dims_p4_emta_kov.py) and this script emits
the per-KOV join table the scorer dims consume.

SCOPE (exact joins): every KOV holds its own row's band inputs -- never
a kernel, never smoothing across KOV borders, never interpolation,
never forward-fill. A KOV whose row (or required year PAIR) is absent
stays unmapped (EI OLE), exactly like the scorer-side NULLs. Tallinn is
one KOV row (#521 inside-Tallinn flatness: stated, not fixed here).

METRICS (population-free by design -- totals alone would rank Tallinn
worst and Loksa best; per-capita needs the rahvastik join this issue
does not own):
* maamaks_share_2025 = maamaks_kokku_2025 /
  (maamaks_kokku_2025 + tulumaks_kokku_2025) * 100 (band input).
* maamaks_ytd_trend_pct = (Jan-Aug 2026 maamaks - Jan-Aug 2025 maamaks)
  / Jan-Aug 2025 * 100 (computed for context, NOT scored: the 2025
  land-revaluation reform makes one jump reform noise -- Rae +83.9%,
  Raasiku +38.4%, Joelahtme +36.6% measured 2026-09-16).

JOIN (EHAK-code or normalised name, never faked): keys are emitted both
ways ("code:<EHAK>", "name:<normalised>") mirroring
dims_p4_emta_kov.kov_lookup_key -- local copy, no cross-tree import.

Rebuild (once the maintainer places the CSVs):
  python3 scripts/build/batch_emta_choropleth.py \\
    --tulumaks /path/to/tulumaks_2026.csv \\
    --maamaks /path/to/maamaks_2026.csv \\
    --out /tmp/hf-emta-kov.json
"""

import argparse
import csv
import json


def parse_eur(text):
    """Estonian-format euros ('1 242', BOM/nbsp spaces) -> float/None."""
    if text is None:
        return None
    cleaned = (text.replace("\ufeff", "").replace("\xa0", "")
                   .replace(" ", "").strip())
    if not cleaned:
        return None
    try:
        return float(cleaned.replace(",", "."))
    except ValueError:
        return None


def normalise_kov(name):
    """Lowercase + whitespace collapse (MARU precedent, no fuzz)."""
    return " ".join(name.lower().split())


#: Column layout of the 2026 files (0-based): 0 Kood, 1 name,
#: then Jan26/Jan25 .. Dec26/Dec25 pairs (idx 2..25), Kokku26=26,
#: Kokku25=27. Verified 2026-09-16; older yearly files share the shape
#: (months x (year, year-1) + Kokku) with shifted year labels.
KOKKU_THIS = 26
KOKKU_PREV = 27
YTD_THIS = list(range(2, 18, 2))   # Jan..Aug of `this` year
YTD_PREV = list(range(3, 18, 2))   # Jan..Aug of `prev` year


def parse_kov_csv(path):
    """Parse one EMTA KOV CSV -> (prev_year, {code: (name, row)}).

    prev_year is the `Kokku` comparison-year label (e.g. "2025" in the
    2026 file); numeric-code rows only, header/title rows skipped.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    prev_year = "prev"
    for row in rows:
        if row and row[0].strip() == "Kood" and len(row) > KOKKU_PREV:
            prev_year = row[KOKKU_PREV].strip() or "prev"
            break
    table = {}
    for row in rows:
        if not row or not row[0].strip().isdigit():
            continue
        table[row[0].strip()] = (row[1].strip(), row)
    return prev_year, table


def build_kov_table(tulumaks_path, maamaks_path):
    """Join the two CSVs -> {lookup_key: metrics} (+ '_meta')."""
    _, tulumaks = parse_kov_csv(tulumaks_path)
    prev_year, maamaks = parse_kov_csv(maamaks_path)
    share_key = "maamaks_share_" + prev_year
    table = {}
    for code in sorted(set(tulumaks) & set(maamaks)):
        tname, trow = tulumaks[code]
        mname, mrow = maamaks[code]
        name = tname or mname
        mm_prev = parse_eur(mrow[KOKKU_PREV]) if len(mrow) > KOKKU_PREV else None
        tm_prev = parse_eur(trow[KOKKU_PREV]) if len(trow) > KOKKU_PREV else None
        metrics = {}
        if mm_prev is not None and tm_prev is not None \
                and (mm_prev + tm_prev) > 0:
            metrics[share_key] = mm_prev / (mm_prev + tm_prev) * 100.0
        ytd_this = sum(v for i in YTD_THIS
                       if len(mrow) > i
                       for v in [parse_eur(mrow[i])] if v is not None)
        ytd_prev = sum(v for i in YTD_PREV
                       if len(mrow) > i
                       for v in [parse_eur(mrow[i])] if v is not None)
        if ytd_prev:
            metrics["maamaks_ytd_trend_pct"] = (
                (ytd_this - ytd_prev) / ytd_prev * 100.0)
        for key in ("code:" + code, "name:" + normalise_kov(name)):
            table[key] = dict(metrics)
            table[key]["kov_code"] = code
            table[key]["kov_name"] = name
    table["_meta"] = {
        "source": ("EMTA avaandmed, kohalikele omavalitsustele ule "
                   "kantud tulumaks ja maamaks"),
        "note": ("maamaks_share_<year> is the scorer band input; "
                 "maamaks_ytd_trend_pct is context only (reform-year "
                 "noise, never scored)."),
    }
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the EMTA KOV transfer join table.")
    parser.add_argument("--tulumaks", required=True)
    parser.add_argument("--maamaks", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    table = build_kov_table(args.tulumaks, args.maamaks)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=2)
    n = len([k for k in table if not k.startswith("_")]) // 2
    print("kovs=%d out=%s" % (n, args.out))


if __name__ == "__main__":
    main()
