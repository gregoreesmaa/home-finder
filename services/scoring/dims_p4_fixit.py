"""P4 fix-it channels dims (issues #301 demo + #370 coverage).

Demo (#301): Tallinna fix-it channels ingestion (P4-026) — polite,
cached, TTL-stated pulls of the annateada report-pin API, wired
end-to-end in Tallinn. Coverage (#370): P4-062 wired to the same
demoed ingestion (no new plumbing — the waste-discipline flag reads
the same pins, see judgment calls).

OPENNESS VERDICT, first round (checked 2026-09-13, dated negative):
Tallinn published no pollable machine-readable feed — /et/abiliin a
404, intake the 14410/661 9860 helpline + Mupo e-post, annateada.ee a
human report map, Tark Tee a JS shell, Teabevara no abiliin dataset.
Raw bodies cached at /tmp/hf-fixit-probe/ (TTL: one-off check, kept
for the PR record, never committed).

DIG, second round (2026-09-16, AGENTS.md section 7.7 "Open JS
shells, don't file them", per the #301 reopen note): the
annateada.ee bundle was read statically and its pins API verified
with ONE polite read probe. Polite evidence, 3 requests total (page
GET + notify.js bundle GET + a single Tallinn-bbox ask POST, paced,
labelled one-off user-agent, 25 s timeout, no retries; HTTP 429
never hit), raw bodies cached at /tmp/hf-dig/annateada/ (TTL:
one-off check, kept for the PR record, never committed):
* https://annateada.ee/ -> HTTP 200 (~24 KB, Apache, ~4.1k visible
  chars). Server-rendered intake page, NOT a shell: scripts live
  under /notify/js/ (jquery, bootstrap, notify.js, map helper).
* /notify/js/notify.js (28 KB) names the whole wire protocol:
  ``var send_url="/cgi-bin/send"`` (write path) and ``var
  ask_url="/cgi-bin/ask"`` (read path). askData() POSTs JSON
  {"lat0","lng0","lat1","lng1","instid":"i4","version":"web5",
  "uuid":"u4","code":"c4"} for the whole-Estonia bbox on every page
  load; handleAskedData() renders one map pin per returned message
  with fields lat/lng/msg/dtime/region/category/stat/comm/photo.
  sendData() is Google-reCAPTCHA-gated (grecaptcha.execute with the
  server-issued captcha_public key) and needs contact data — the
  write path is form-driving behind a captcha and is NEVER probed
  or automated here (AGENTS.md section 5).
* ONE ask probe (Tallinn bbox lat 59.30-59.55 / lng 24.45-25.15,
  same static instid/version/uuid/code the bundle sends — a smaller
  read than one normal page view) -> HTTP 200 (~130 KB JSON):
  {"messages": 294 pins, "instid", "adminabi", "tagid",
  "heatava", "abi", "annateada", "captcha_public"}. Schema per pin:
  id (server int, string), lat/lng (WGS84 strings, full
  precision), msg (free-text report, DROPPED at parse — human
  content), dtime (ISO), ts (epoch string), stat ('0'/'1'),
  region (MUNICIPALITY grain: Tallinn/Saue vald/Viimsi vald/...),
  category (server taxonomy), comm (handler comment, DROPPED),
  photo (report-photo URL, DROPPED — personal data). Observed
  Tallinn slice: 170/294 pins region=Tallinn, stat 107x '1' vs
  187x '0' bbox-wide, dtime 2026-08-27..2026-09-15 (rolling ~19-day
  window — the abi text confirms "kaardil naidatakse viimase 19
  paeva teateid"), server taxonomy (Teed ja tanavad, Heakord,
  Ohtlik objekt, Haljastus, Valesti parkimine, Muu, Valgustus,
  Surnud loom/lind; uncategorised stay None/"").
* stat semantics are DOCUMENTED, not guessed: the ask-returned abi
  help text states green pins = the authority acknowledged / is
  handling / resolved the report, red pins = currently unhandled
  ("kaesitlemata"); a week-red pin retriggers the authority
  automatically. So stat=='1' (green) = handled, stat=='0' (red) =
  unhandled, and handled/total over the rolling window is an honest
  responsiveness RATE — parameters4.md P4-026 "hex responsiveness
  rate" shape.

Honest-shape consequences (reviewable per AGENTS.md section 7.5):
* The rate join is a 500 m WINDOW rate, not per-linnaosa stats: the
  region field carries municipality grain only (every Tallinn pin
  says region=Tallinn), so per-linnaosa aggregation is NOT honestly
  possible from this feed alone. The window geometry (500 m,
  n >= 5) deliberately matches the dims_p4_trans fixithex_p4
  consumer (FIXIT_WINDOW_M / FIXIT_MIN_N / FIXIT_BANDS) so the
  weight-rebalance follow-up can unify both legs. The true
  linnaosa-polygon join stays a named follow-up: the #304 dig
  inventoried keyless Linnaosad_asumid polygons at
  https://gis.tallinn.ee/arcgis/rest/services/Linnaosad_asumid/FeatureServer
  (layers 0=Asumid, 1=Linnaosad) — one cached polygon pull plus a
  local point-in-polygon would graduate this to per-linnaosa
  without touching the scorers' shapes.
* P4-062 rides the same pins (coverage needs no new plumbing): the
  Heakord category is the waste-discipline proxy leg (counts-only
  operational flag, never addresses); the ice-fall channel leg has
  NO taxonomy entry (no ice/jää category observed), so it stays
  NULL inside the reason and points at dims_p4_paaste.
* Sibling legs stay scored where they live, named never re-scored
  (same split-slice precedent as P4-020: ATA notices in
  dims_p4_ata, bureau scores NULL in dims_p4_creditinfo): the
  Keskkonna- ja Kommunaalamet heakorra-teated + removal-lag leg
  (dims_p4_komun dim_fixit_responsiveness) and rotikaebused hex leg
  (dims_p4_komun dim_rat_icefall_hex, #290/#363); the OSM
  fixme/edit-freshness cross-check (dims_p4_osm dim_fixit) and
  waste-disposal coverage cross-check (dims_p4_osm dim_rats,
  #354); the Paasteamet ice-warning slice (dims_p4_paaste, #276,
  scores only inside a caller-supplied hex-watch flag); the KÜ
  hoolduskulu/prügiveo-kulu echos (dims_p4_arireg
  dim_maintenance_echo / dim_waste_echo). Each reason names its
  scored cousins so the buyer knows which half is already joined.
* Stays as-is (not part of this dig, per the reopen note): Tark
  Tee DATEX key gate (needs a registered key — separate decision),
  munitsipaalpolitsei phone/e-post intake (human channel, never
  scraped), the send/write path (captcha-gated form driving).

Style mirrors services/scoring/dims_p4_trans.py (#324 end-to-end
precedent: fetch_cached + pure offline readers) and
services/scoring/dims_p4_arireg.py (TTL-stated snapshot pull,
transport errors never cached as data): every scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives ONLY in
fetch_annateada_snapshot; this module adds no Overpass fragment
and no tag mapping: pin positions arrive via the ask join, not
via snapshot tags, so there is nothing honest for the live path
to fetch.

Helpers are local copies (not imported from livability, trans, or
sibling batches): a future central hook may import this module
alongside them, and importing any of them here would turn that
into a cycle (same precedent as batch B3, PR #100, and sibling
#152).

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_annateada_snapshot(cache_dir, ttl_s): polite pull, one POST
  of the Tallinn bbox with an identifying UA and a 30 s timeout;
  cache hit within TTL makes NO request; single attempt, no
  retries (HTTP 429 is a stop signal, AGENTS.md 7.4). The body is
  stored only on HTTP 200 with a JSON content type that parses
  and carries a messages list, else None is returned and nothing
  is cached (transport errors are never data). Scorers never call
  this; tests cover the cache-hit and error paths with a stubbed
  opener, never the network.
* parse_annateada_snapshot(path): pure offline reader -> pin
  records {lat, lng, handled, category, dtime, region}. Human
  content (msg/comm/photo/contact) is DROPPED at parse time
  (personal-data minimisation — counts and categories only).
* build_annateada_pins(records, region="Tallinn"): pure offline
  builder -> POI dicts of kind "annateada_pin_p4" (the join the
  scorers consume; the live snapshot-to-POI wiring stays a future
  joint change with the central hook, same as every batch).

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

import json
import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Keyless read endpoint from the annateada.ee bundle (notify.js
#: ask_url; verified 2026-09-16 with one Tallinn-bbox POST -> HTTP
#: 200 JSON, see module docstring). The write endpoint
#: (/cgi-bin/send, reCAPTCHA-gated) is never touched.
ANNATEADA_ASK_URL = "https://annateada.ee/cgi-bin/ask"

#: Tallinn pull bbox (lat0/lng0/lat1/lat1): Tallinn + close
#: neighbours; parse/builder keep region == "Tallinn" pins for the
#: Tallinn-scoped dims. One POST covers the whole bbox (the bundle
#: itself POSTs the whole country per page view — this is less).
ANNATEADA_TALLINN_BBOX = {
    "lat0": "59.30", "lng0": "24.45",
    "lat1": "59.55", "lng1": "25.15",
}

#: Static client constants the bundle sends with every ask call.
ANNATEADA_ASK_META = {
    "instid": "i4", "version": "web5", "uuid": "u4", "code": "c4",
}

#: The map shows the last ~19 days of reports (abi help text), so a
#: daily pull keeps the window fresh. Stated TTL.
ANNATEADA_TTL_S = 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "annateada-ask-snapshot.json"

#: Identifying user agent for the polite pull (one POST/day max).
ANNATEADA_UA = "home-finder annateada ingest (max 1 POST/day, read-only ask)"

#: Server-side report taxonomy observed 2026-09-16 (ask probe;
#: uncategorised pins arrive as None/""). Exact match only.
ANNATEADA_CATEGORIES = (
    "Teed ja tänavad", "Heakord", "Ohtlik objekt", "Haljastus",
    "Valesti parkimine", "Muu", "Valgustus", "Surnud loom/lind",
)

#: Waste-discipline proxy category for the P4-062 coverage flag.
WASTE_CATEGORY = "Heakord"

#: POI kind emitted by build_annateada_pins (the scorers' join).
ANNATEADA_PIN_KIND = "annateada_pin_p4"

#: P4-026 window join (geometry mirrors the dims_p4_trans
#: fixithex_p4 consumer so the rebalance can unify both legs).
FIXIT_WINDOW_M = 500.0
#: P4-026 rate -> score (high = responsive); needs n >= 5 reports
#: (FIXIT_MIN_N precedent in dims_p4_trans + MIN_N = 5 precedent
#: in dims_p4_own_asum).
FIXIT_MIN_N = 5
FIXIT_BANDS = [(0.5, 40), (0.8, 60), (float("inf"), 80)]

#: P4-062 waste-flag join: counts-only operational flag, never
#: addresses. First calibration (reviewable): 5-9 Heakord pins per
#: 500 m window = 55, 10+ = 35; thinner windows stay NULL.
WASTE_WINDOW_M = 500.0
WASTE_MIN_N = 5
WASTE_BANDS = [(9, 55), (float("inf"), 35)]


def fetch_annateada_snapshot(cache_dir: str,
                             ttl_s: int = ANNATEADA_TTL_S,
                             ask_url: str = ANNATEADA_ASK_URL,
                             ) -> Optional[str]:
    """Polite annateada ask pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made.
    Otherwise one POST of the Tallinn bbox with ANNATEADA_UA and a
    30 s timeout; the body is stored only on HTTP 200 with a JSON
    content type that parses and carries a messages list, else None
    is returned and nothing is cached (transport errors are never
    data). No retries — HTTP 429/errors are a stop signal. The
    captcha-gated send endpoint is never touched. Scorers never
    call this; tests cover the cache-hit and error paths with a
    stubbed opener, never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, CACHE_FILENAME)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    try:
        payload = dict(ANNATEADA_TALLINN_BBOX)
        payload.update(ANNATEADA_ASK_META)
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            ask_url, data=body,
            headers={"User-Agent": ANNATEADA_UA,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            ctype = resp.headers.get("Content-Type", "")
            if status != 200 or "json" not in ctype:
                return None
            raw = resp.read()
        try:
            doc = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(doc, dict) or not isinstance(
                doc.get("messages"), list):
            return None
        with open(dest, "wb") as fh:
            fh.write(raw)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached snapshot (pure; fixtures match schema).
# ---------------------------------------------------------------------------

def _to_float(raw) -> Optional[float]:
    """Finite float: numeric strings pass, bool/garbage -> None."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        v = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def parse_annateada_snapshot(path: str) -> List[dict]:
    """Parse a cached ask snapshot into minimal pin records. Pure.

    Keeps {lat, lng, handled, category, dtime, ts, region} only —
    human content (msg/comm/photo/contact) is dropped at parse time.
    ts is the report epoch (int when parseable, else None) — carried
    for map-side expiry (issue #623; the scorer itself never reads
    it, so scoring behavior is unchanged).
    handled = True iff stat is the green "teadmiseks võetud /
    lahendatud" state ('1', per the ask-returned abi text); every
    other stat (incl. red '0' = käsitlemata) is unhandled. Pins
    without parseable lat/lng are skipped. Missing file / bad JSON
    / missing messages list -> [] (never an exception).
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return []
    if not isinstance(doc, dict):
        return []
    messages = doc.get("messages")
    if not isinstance(messages, list):
        return []
    records = []
    for entry in messages:
        if not isinstance(entry, dict):
            continue
        lat = _to_float(entry.get("lat"))
        lng = _to_float(entry.get("lng"))
        if lat is None or lng is None:
            continue
        stat = entry.get("stat")
        handled = stat == 1 or stat == "1" or stat is True
        category = entry.get("category")
        if not isinstance(category, str) or not category:
            category = None
        elif category not in ANNATEADA_CATEGORIES:
            category = None
        dtime = entry.get("dtime")
        if not isinstance(dtime, str) or not dtime:
            dtime = None
        region = entry.get("region")
        if not isinstance(region, str) or not region:
            region = None
        ts = _to_int(entry.get("ts"))
        records.append({"lat": lat, "lng": lng, "handled": handled,
                        "category": category, "dtime": dtime, "ts": ts,
                        "region": region})
    return records


def _to_int(raw) -> Optional[int]:
    """Epoch int: ints and numeric strings pass, bool/garbage -> None."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
        try:
            return int(raw.strip())
        except ValueError:
            return None
    return None


def build_annateada_pins(records: List[dict],
                         region: str = "Tallinn") -> List[dict]:
    """Pin records -> scorer POIs of kind annateada_pin_p4. Pure.

    Keeps region-filtered pins only (default Tallinn — the pull
    bbox covers neighbours, the dims are Tallinn-scoped). handled
    is stored as int 0/1 (POI fields stay JSON-plain).
    """
    pois = []
    for rec in records:
        if not isinstance(rec, dict) or rec.get("region") != region:
            continue
        lat = _to_float(rec.get("lat"))
        lng = _to_float(rec.get("lng"))
        if lat is None or lng is None:
            continue
        pois.append({"kind": ANNATEADA_PIN_KIND, "lat": lat, "lon": lng,
                     "handled": 1 if rec.get("handled") else 0,
                     "category": rec.get("category"),
                     "dtime": rec.get("dtime"),
                     "ts": rec.get("ts") if isinstance(
                         rec.get("ts"), int) else None})
    return pois


# ---------------------------------------------------------------------------
# Local join helpers (copies — no livability/trans import, see docstring).
# ---------------------------------------------------------------------------

def _haversine_m(origin: Tuple[float, float], lat: float,
                 lon: float) -> float:
    """Great-circle metres between origin (lat, lon) and a point."""
    lat1, lon1 = math.radians(origin[0]), math.radians(origin[1])
    lat2, lon2 = math.radians(lat), math.radians(lon)
    a = (math.sin((lat2 - lat1) / 2.0) ** 2
         + math.cos(lat1) * math.cos(lat2)
         * math.sin((lon2 - lon1) / 2.0) ** 2)
    return 2.0 * 6371000.0 * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def _in_window(origin: Tuple[float, float], kind: str,
               pois: List[dict], window_m: float) -> List[Tuple[float, dict]]:
    """All well-formed POIs of kind within window_m, with distances."""
    hits = []
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") != kind:
            continue
        try:
            lat = float(p["lat"])
            lon = float(p["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(p.get("lat"), bool) or isinstance(p.get("lon"), bool):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        d = _haversine_m(origin, lat, lon)
        if d <= window_m:
            hits.append((d, p))
    return hits


def _band(value: Optional[float],
          bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def summarize_fixit_window(origin: Tuple[float, float],
                           pois: List[dict],
                           window_m: float = FIXIT_WINDOW_M,
                           min_n: int = FIXIT_MIN_N,
                           ) -> Optional[Tuple[int, float]]:
    """(n, handled-rate) of annateada pins near origin, else None. Pure.

    Thin windows (n < min_n) stay None — never a rate off one or two
    pins (FIXIT_MIN_N precedent). handled/total only; pins are
    counts, never addresses.
    """
    hits = _in_window(origin, ANNATEADA_PIN_KIND, pois, window_m)
    n = len(hits)
    if n < min_n:
        return None
    handled = sum(1 for _, p in hits if p.get("handled") == 1)
    return n, handled / n if n else 0.0


# ---------------------------------------------------------------------------
# P4-026: municipal fix-it responsiveness (demo param, graduated join).
# ---------------------------------------------------------------------------

def dim_fixit_channel_responsiveness(origin: Optional[Tuple[float, float]],
                                    pois: Optional[List[dict]]) -> Score:
    """P4-026: annateada window fix-rate (high = responsive).

    Hex responsiveness rate over the rolling ~19-day ask window:
    handled/total pins within 500 m, scored when the window holds
    at least 5 reports; thinner windows and missing snapshots stay
    NULL. Only this slice — the komun heakorra leg, the OSM fixme
    cross-check and the arireg cost echo stay scored where they
    live (named, never re-scored).
    """
    if not origin or pois is None:
        return None, ("KOV-i parandamiskiirus abiliini/e-teenuste-kanalites "
                      "(valgustus, augud, lumi, grafiti) on hooldaja-hinnang "
                      "(EI OLE parandatud/eemaldatud-viibe tabelit heksi "
                      "kaupa): abiliin (14410 / 661 9860), Mupo e-post ja "
                      "annateada.ee teavituskaart on inimkanalid — küsi "
                      "linnaosast eemaldamisviivet, hinda trepikoja hooldust "
                      "KÜ aruandest ja vaata heakorra-teadete slice'i "
                      "dims_p4_komun-ist (dim_fixit_responsiveness), OSM "
                      "fixme-ristkontrolli dims_p4_osm-ist (dim_fixit) ning "
                      "KÜ hoolduskulu-kaja dims_p4_arireg-ist "
                      "(dim_maintenance_echo), ära feigi")
    summary = summarize_fixit_window(origin, pois)
    if summary is None:
        return None, ("Teate-kiiruse hinnang: 500 m aknas pole piisavalt "
                      "annateada-raporteid (n<5, EI OLE liidestatud "
                      "hetktõmmes — parandamiskiirus mõõtmatu): abiliin "
                      "(14410 / 661 9860), Mupo e-post ja annateada.ee "
                      "teavituskaart on inimkanalid — küsi linnaosast "
                      "eemaldamisviivet, hinda trepikoja hooldust KÜ "
                      "aruandest ja vaata heakorra-teadete slice'i "
                      "dims_p4_komun-ist (dim_fixit_responsiveness), OSM "
                      "fixme-ristkontrolli dims_p4_osm-ist (dim_fixit) ning "
                      "KÜ hoolduskulu-kaja dims_p4_arireg-ist "
                      "(dim_maintenance_echo), ära feigi")
    n, rate = summary
    rate = min(max(rate, 0.0), 1.0)
    s = _band(rate, FIXIT_BANDS)
    assert s is not None
    return s, ("Teate-kiiruse hinnang: 500 m aknas %d annateada-raportit "
               "(19-päeva libisev aken), teadmiseks-võetud/lahendatud "
               "määr %.0f%% -> skoor %d (parandamiskiirus, mitte lubadus), "
               "ära feigi" % (n, 100 * rate, s))


# ---------------------------------------------------------------------------
# P4-062: rat complaints + ice-fall channel flags (coverage param).
# ---------------------------------------------------------------------------

def dim_rat_icefall_channel_flags(origin: Optional[Tuple[float, float]],
                                 pois: Optional[List[dict]]) -> Score:
    """P4-062: Heakord waste-flag off the same pins (high = cleaner).

    Counts-only operational flag, never addresses: Heakord-category
    pins within 500 m, flagged when the window holds at least 5;
    thinner windows stay NULL. The ice-fall channel leg has no ask
    taxonomy entry and stays NULL inside the reason (Paasteamet
    slice lives in dims_p4_paaste). Only this slice — the komun
    rotikaebused leg, the OSM waste cross-check and the arireg
    waste echo stay scored where they live.
    """
    if not origin or pois is None:
        return None, ("Heksi roti- ja jää-kukkumis-lipud abiliini-kanalite "
                      "kaudu (prügidistsipliin + katuse-hooldamatus, kunagi "
                      "mitte aadressid) on hooletusse-jäetud kvartali hinnang "
                      "(EI OLE heksi-põhist kaebuste-koondit): abiliin (14410 "
                      "/ 661 9860), Mupo e-post ja annateada.ee "
                      "teavituskaart on inimkanalid, P4-026 parandusviibe-jalg "
                      "on samuti liidestamata — hinda prügimajade seisu "
                      "kohapealsel vaatlusel, küsi KÜ-lt prüviveo-kulusid ning "
                      "vaata Päästeameti jää-hoiatuste slice'i dims_p4_paaste-st, "
                      "rotikaebuste-slice'i dims_p4_komun-ist "
                      "(dim_rat_icefall_hex), OSM jäätmepunktide-ristkontrolli "
                      "dims_p4_osm-ist (dim_rats) ja KÜ prügi-hoolduskulu-kaja "
                      "dims_p4_arireg-ist (dim_waste_echo), ära feigi")
    hits = _in_window(origin, ANNATEADA_PIN_KIND, pois, WASTE_WINDOW_M)
    waste = [p for _, p in hits if p.get("category") == WASTE_CATEGORY]
    n = len(waste)
    if n < WASTE_MIN_N:
        return None, ("Heksi heakorra-lipud (prügidistsipliin, kunagi mitte "
                      "aadressid) on hooletusse-jäetud kvartali hinnang "
                      "(EI OLE 500 m aknas piisavalt Heakord-raporteid "
                      "liidestatud hetktõmmes): P4-026 parandusviibe-jalg on "
                      "samuti mõõtmatu, jää-kukkumise kanalilipp taksonoomiast "
                      "puudub — hinda prügimajade seisu kohapealsel vaatlusel, "
                      "küsi KÜ-lt prüviveo-kulusid ning vaata Päästeameti "
                      "jää-hoiatuste slice'i dims_p4_paaste-st, "
                      "rotikaebuste-slice'i dims_p4_komun-ist "
                      "(dim_rat_icefall_hex), OSM jäätmepunktide-ristkontrolli "
                      "dims_p4_osm-ist (dim_rats) ja KÜ prügi-hoolduskulu-kaja "
                      "dims_p4_arireg-ist (dim_waste_echo), ära feigi")
    unhandled = sum(1 for p in waste if p.get("handled") != 1)
    s = _band(float(n), WASTE_BANDS)
    assert s is not None
    return s, ("Heksi heakorra-lipud: 500 m aknas %d Heakord-raportit "
               "(teadmiseks võtmata %d, 19-päeva libisev aken) -> skoor %d "
               "(prügidistsipliini-lipp, kunagi mitte aadressid; P4-026 join; "
               "jää-kanalilipp taksonoomiast EI OLE — vaata dims_p4_paaste "
               "slice'i, kohapealne vaatlus + KÜ prüviveo-kulud jäävad "
               "ostja kontrolliks), ära feigi" % (n, unhandled, s))


P4_FIXIT_DIMS = (
    ("fixit_channel_responsiveness", "P4-026", dim_fixit_channel_responsiveness),
    ("rat_icefall_channel_flags", "P4-062", dim_rat_icefall_channel_flags),
)


def score_p4_fixit(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both P4 fix-it channel dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_FIXIT_DIMS). Values are
    None wherever the ask window is thin or missing — unpublished
    fix-it channels are never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_FIXIT_DIMS}
