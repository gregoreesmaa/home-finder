"""Quarterly MARU harvest: T13 apartment price stats per Harju KOV.

Source: Maa-amet hinnastatistika query env (htraru/FilterUI.aspx), which
has NO bulk export. The quarterly KOV table is pulled through the same
postback sequence a human drives in the browser. Per-issue #514 policy
note: the repo's overturn verdict defined this table as a caller-supplied
maintainer export ("never scraped"); the maintainer (repo owner) EXPLICITLY
authorized this automated pull on 2026-09-16 as the supplier of record.
The politeness rules below are load-bearing, not decorative:

- Minimal query set: 4 requests per quarter (land, type-flip, submit-1,
  submit-2). Six quarters per run = ~24 requests total.
- >=5 s pacing between requests, single session, descriptive UA.
- HTTP 429 aborts the whole run immediately (stop signal, never a dare).
- Raw report HTML is NEVER committed (fixtures in tests are synthetic).

Flow mechanics (reverse-engineered 2026-09-16; the app is ASP.NET
WebForms and crashes on any deviation -- see docs/p4_maru.md):
  land -> flip DDTrykis=G (Price statistics) ->
  submit-1 (T13 + chkAsukoht + chkValiKoik + quarter dates) reveals the
  region radios (RBLPiirkond_0 checked) ->
  submit-2 (browser-mirrored state) returns the per-KOV report.
Golden rule: every POST carries EXACTLY the controls rendered in the
current page state (controls() mirrors a browser). Stale/foreign fields
(DDLoikeProtsent on landing, RBLTehingud under Price statistics,
RBLPiirkond before it renders) crash the submit with "Tootlemata viga".

Scope note: RBLTehingud (All transactions vs Purchase-Sale) is ABSENT
from the Price-statistics tree, so scope stays All transactions (the
screenshot default). Documented here, not silently chosen.

Quarterly cron shape (TTL 90 days, alongside the Ookla re-pull):
  python3 scripts/build/harvest_maru_quarterly.py /tmp/maru-Q.json \
      2026-Q3 [... more quarters]
  python3 -c assemble tables doc (synthetic False, period, note) \
  python3 scripts/build/batch_maru_choropleth.py --tables ... \
      --kov-extract ... --outdir $HF_SNAPSHOT/osm
  restart web (masters are cached per process) + verify /api routes.

Usage: harvest_maru_quarterly.py OUT.json Q1 [Q2 ...]  (labels 2025-Q1..)
"""

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar

BASE = "https://www.maaamet.ee/kinnisvara/htraru/"
ACTION = "https://www.maaamet.ee/kinnisvara/htraru/FilterUI.aspx"
UA = ("home-finder-maru-harvest/1.0 (quarterly KOV pull, paced; "
      "github gregoreesmaa/home-finder)")
GAP = 5.0
QSTART = {"Q1": "01", "Q2": "04", "Q3": "07", "Q4": "10"}
QEND = {"Q1": "03", "Q2": "06", "Q3": "09", "Q4": "12"}
MIN_KOV_ROWS = 10  # Harju has 16 KOVs; fewer means an empty/validation page


def new_session():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def fetch(op, url, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with op.open(req, timeout=90) as r:
        if r.status == 429:
            raise SystemExit("HTTP 429: stop signal, aborting harvest")
        return r.status, r.read().decode("utf-8", "replace")


def hidden(html_, name):
    m = re.search(r'name="%s"[^>]*value="([^"]*)"' % name, html_)
    return m.group(1) if m else ""


def controls(html_):
    """Mirror a browser: every named control in the CURRENT tree with its
    current value. Checked radios/checkboxes only; multi-selects only when
    options are selected; drop-downs default to the first item."""
    f = {}
    for m in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*>', html_):
        t, name = m.group(0), m.group(1)
        ty = (re.search(r'type="([^"]*)"', t) or [None, "text"])[1]
        if ty in ("radio", "checkbox"):
            if "checked" in t:
                v = re.search(r'value="([^"]*)"', t)
                f[name] = v.group(1) if v else "on"
        elif ty == "submit":
            continue
        else:
            v = re.search(r'value="([^"]*)"', t)
            f[name] = v.group(1) if v else ""
    for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>',
                         html_, re.S):
        tag, name, inner = m.group(0), m.group(1), m.group(2)
        sel = re.findall(r'<option[^>]*value="([^"]*)"[^>]*selected[^>]*>',
                         inner)
        if sel:
            f[name] = sel if len(sel) > 1 else sel[0]
        elif "multiple" not in tag:
            first = re.search(r'<option[^>]*value="([^"]*)"', inner)
            if first:
                f[name] = first.group(1)
    return f


def post(html_, extra):
    f = controls(html_)
    f.update(extra)
    pairs = []
    for k, v in f.items():
        if isinstance(v, list):
            pairs.extend([(k, x) for x in v])
        else:
            pairs.append((k, v))
    return urllib.parse.urlencode(pairs).encode()


def num(s):
    """Estonian number ('4 038,05', '***' masked) -> float/None."""
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_report(rep):
    """KOKKU rows of the first table -> [{kov, deals, median_eur_m2}].
    '***' (min-5 masking) and blanks become None, never 0."""
    t = re.findall(r"<table.*?</table>", rep, re.S)[0]
    rows = re.findall(r"<tr.*?>(.*?)</tr>", t, re.S)

    def cells(r):
        return [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
    head = cells(rows[1])
    i_deals = head.index("Arv")
    i_med = head.index("Mediaan")
    out, cur = [], ""
    for r in rows[2:]:
        c = cells(r)
        if not c:
            continue
        if c[0]:
            cur = c[0]
        if "KOKKU" in c:
            deals = num(c[i_deals]) if c[i_deals] not in ("", "***") else None
            med = num(c[i_med]) if c[i_med] not in ("", "***") else None
            out.append({"kov": cur, "deals": deals, "median_eur_m2": med})
    return out


def quarter_report(quarter, gap=GAP):
    """One quarter label like 2026-Q2. Returns row list (raises on crash)."""
    year, q = quarter.split("-")
    op = new_session()
    _, landing = fetch(op, BASE)
    time.sleep(gap)
    _, s1 = fetch(op, ACTION, post(landing, {
        "__EVENTTARGET": "DDTrykis", "__EVENTARGUMENT": "", "DDTrykis": "G"}))
    assert "Töötlemata" not in s1, "type-flip crashed"
    extra1 = {
        "__EVENTTARGET": "", "__EVENTARGUMENT": "",
        "DDTrykis": "G", "LBTrykis": "T13",
        "chkAsukoht": "on", "chkValiKoik": "on",
        "RBLAeg": "0",
        "txtAlgus": "%s.%s" % (QSTART[q], year),
        "txtLopp": "%s.%s" % (QEND[q], year),
        "btnTryki": "Koosta aruanne",
    }
    time.sleep(gap)
    _, s2 = fetch(op, ACTION, post(s1, extra1))
    assert "Töötlemata" not in s2, "submit-1 crashed"
    extra2 = dict(extra1)
    extra2.pop("chkAsukoht", None)
    extra2.pop("chkValiKoik", None)
    time.sleep(gap)
    _, s3 = fetch(op, ACTION, post(s2, extra2))
    assert "Töötlemata" not in s3, "submit-2 crashed"
    rows = parse_report(s3)
    assert len(rows) >= MIN_KOV_ROWS, "empty report (%d rows)" % len(rows)
    for r in rows:
        r["quarter"] = quarter
    return rows


if __name__ == "__main__":
    outpath, quarters = sys.argv[1], sys.argv[2:]
    all_rows = []
    for quarter in quarters:
        rows = None
        for attempt in range(1, 4):
            try:
                rows = quarter_report(quarter)
                break
            except AssertionError as e:
                print(quarter, "attempt", attempt, "failed:", e, flush=True)
                time.sleep(10)
        if rows is None:
            raise SystemExit("quarter failed 3x, aborting: " + quarter)
        n_med = sum(1 for r in rows if r["median_eur_m2"] is not None)
        print(quarter, "kovs:", len(rows), "with-median:", n_med, flush=True)
        all_rows.extend(rows)
    json.dump(all_rows, open(outpath, "w"), ensure_ascii=False, indent=1)
    print("wrote", outpath, len(all_rows), "rows")
