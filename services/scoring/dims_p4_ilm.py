"""P4 ilm batch: Ilmateenistus Tallinn-Harku honest-shape dims (issues #308, #374).

Params (this module only — demo + coverage paired in one PR because the
coverage body states it extends the demo ingestion):
* P4-031 backyard weather + DIY air (demo via P4-031)
* P4-034 summer overheating risk (cooling-degree trend)
* P4-035 December darkness (sun-hours baseline)
* P4-053 odour roses by wind frequency (sector + calendar)
* P4-056 enclosed-courtyard trap (ventilation proxy)

HONESTY (AGENTS.md section 7.2): Tallinn-Harku is ONE station, so this
module never emits a spatial gradient — a per-parcel 0..100 ramp off a
single anemometer would be fake precision by construction (OTA PR #131
precedent). Honest shapes are baseline (one city-wide band for every
Tallinn listing, labelled baseline), sector (16 discrete wind-rose
sectors for P4-053, never a circle buffer), and calendar (monthly
buckets: July heat for P4-034, December sun for P4-035). Where the
required input is absent — no ingested baseline, no July/December
bucket, no emitter inventory, or a param that needs per-parcel facts
(P4-031 DIY sensor density, P4-056 LiDAR enclosure) — the dim returns
None with an Estonian reason that says "hinnang" and "EI OLE" and
points at the concrete buyer-side check. NULL stays NULL.

Openness verdict (2026-09-13, two polite pulls, cached to
/tmp/hf-ilm-cache, full evidence in docs/p4_ilm.md):
* observations.php XML: OPEN, no key — HTTP 200, 125 kB, Tallinn-Harku
  WMO 26038 with winddirection/windspeed, airtemperature,
  relativehumidity, airpressure, sunshineduration, globalradiation.
* kliimanormid/ normals: OPEN as human HTML tables (Tallinn-Harku
  monthly rows incl. "Paikesepaiste kestus"), NO machine-readable
  download (no csv/xls/json/xml links) — cross-check only, never
  ingested. Normals fixtures in tests are synthetic, clearly labelled.
* Machine wind-rose feed: NOT located in the two polite pulls (dated
  negative, kept) — the rose is therefore derived from the archived
  observations' winddirection series, which the same two pulls prove
  is machine-open. No extra hunting: polite automation stops at
  sufficient (AGENTS.md section 7.4).

Ingestion contract: a daily-cron adapter archives observations.php
into a local record list (polite UA, file cache, TTL below); this
module's pure helpers parse one XML payload and aggregate record
lists into the baseline dict the dims consume. Transport errors are
never cached as data (fetch raises, cache untouched); HTTP 429 is a
stop signal, not a retry dare.

Style mirrors services/scoring/livability.py and sibling batch
dims_group08b.py (#168): scorers are pure and offline-tested. The
uniform scorer shape is (origin, pois, baseline=None) — the optional
third argument IS the new plumbing the coverage issue anticipates
("no new plumbing expected unless a param needs it"): calendar dims
need the ingested baseline the snapshot never carries, and stuffing
climate normals into OSM POIs would abuse the POI channel, so the
baseline travels explicitly. Helpers are local copies (not imported
from livability or sibling batches): a future central hook may import
this module alongside them, and importing any of them here would turn
that into a cycle (same precedent as batch B3, PR #100).

Deliberately NO Overpass fragment and NO tag mapping here (unlike
proxy batches): Ilmateenistus data is not OSM data, and the odour
emitter inventory (e-Ariregister addresses) is caller-supplied until
a future adapter job owns it — inventing a fragment would be
dishonest plumbing. The emitter POI kind "odour_emitter" is a
caller-side contract documented below, not a snapshot tag.

Judgment calls (reviewable per AGENTS.md section 7.5):
* P4-034 July bands (<16 C -> 80, <18 -> 65, <20 -> 50, <22 -> 35,
  else 20) and P4-035 December bands (<10 h -> 20, <20 -> 35,
  <35 -> 50, <50 -> 65, else 80) are coarse city-baseline bands,
  floored so baseline alone never scores the extreme: P4-034 never
  below 20 without listing facts (orientation/floor/draft are EHR
  facts, not in snapshot), P4-035 never above 80 without the lamp
  inventory. Reasons name the missing check.
* P4-053 score = round(100*(1 - freq/0.20)) clamped 0..100: a sector
  blowing 20%+ of the year saturates at 0 (downwind truth), a never
  sector scores 100. Downwind convention is meteorological
  (wind-FROM): the listing is downwind of the emitter when the wind
  comes FROM the emitter's bearing as seen from the listing, so the
  sector is sector_of_bearing(bearing(listing -> emitter)).
* Calm = windspeed < 0.5 m/s (P4-056 ventilation proxy).
* CDD uses base 18 C per observation (observation-CDD proxy for
  trend use, not an energy certificate).
* Missing July/December bucket returns None rather than the warmest/
  darkest available month — substituting months would fake a
  calendar (never a gradient applies to time too).

Integration (deliberately NOT done here): the daily-cron archiver,
any livability hook, and rebalancing livability.WEIGHTS must be one
joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling.
"""

import math
import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source identity, politeness, cache.
# ---------------------------------------------------------------------------

#: Machine-open observations feed (verified 2026-09-13: HTTP 200, no key).
ILM_OBSERVATIONS_URL = (
    "https://www.ilmateenistus.ee/ilma_andmed/xml/observations.php"
)
#: Human-table normals (verified 2026-09-13: HTTP 200, tables only, no
#: machine download) — cross-check reference, never an ingestion source.
ILM_NORMALS_URL = "https://www.ilmateenistus.ee/kliima/kliimanormid/"
ILM_STATION_NAME = "Tallinn-Harku"
ILM_STATION_WMO = "26038"
ILM_USER_AGENT = (
    "home-finder-p4-ilm/1.0 (Estonia open-data daily adapter; "
    "polite single-pull, cache-first)"
)
#: Observations refresh ~hourly server-side, but a climate baseline moves
#: slowly: at most one live pull per day, cache wins inside the TTL.
ILM_CACHE_TTL_S = 24 * 3600
ILM_CACHE_NAME = "ilmateenistus-observations.xml"

#: 16-sector meteorological rose, clockwise from north.
SECTORS_16 = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)

#: CDD base for the observation-CDD proxy (trend use only, not a certificate).
CDD_BASE_C = 18.0
#: Below this windspeed the air counts as calm (ventilation proxy).
CALM_MAX_MS = 0.5
#: A sector blowing at/above this share saturates the odour dim at 0.
ODOUR_SAT_FREQ = 0.20


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------

def sector_of_bearing(deg: float) -> str:
    """Map a compass bearing to its 16-sector wind-rose label (pure)."""
    idx = int((float(deg) + 11.25) // 22.5) % 16
    return SECTORS_16[idx]


def bearing_deg(frm: Tuple[float, float], to: Tuple[float, float]) -> float:
    """Initial bearing in degrees (0..360, 0 = north) from point to point."""
    la1, la2 = math.radians(frm[0]), math.radians(to[0])
    dlo = math.radians(to[1] - frm[1])
    x = math.sin(dlo) * math.cos(la2)
    y = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlo)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def _float(text) -> Optional[float]:
    try:
        return float(str(text).strip().replace(",", "."))
    except (TypeError, ValueError, AttributeError):
        return None


def parse_harku_observation(xml_text: str) -> Optional[dict]:
    """Parse one observations.php payload to the Harku record (pure).

    Returns None when the payload parses but carries no Tallinn-Harku
    station block (dated-negative friendly); raises ValueError on
    unparseable XML (transport garbage is never a record).
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError("Ilmateenistus XML ei parsinud: %s" % exc)
    ts_raw = _float(root.get("timestamp"))
    for st in root.iter("station"):
        if (st.findtext("name") or "").strip() != ILM_STATION_NAME:
            continue
        t = _float(st.findtext("airtemperature"))
        return {
            "station": ILM_STATION_NAME,
            "wmo": (st.findtext("wmocode") or "").strip() or None,
            "ts": int(ts_raw) if ts_raw is not None else None,
            "t": t,
            "winddir": _float(st.findtext("winddirection")),
            "windspeed": _float(st.findtext("windspeed")),
            "humidity": _float(st.findtext("relativehumidity")),
            "pressure": _float(st.findtext("airpressure")),
            "sun": _float(st.findtext("sunshineduration")),
            "radiation": _float(st.findtext("globalradiation")),
            "phenomenon": (st.findtext("phenomenon") or "").strip() or None,
            "cdd18": max(0.0, t - CDD_BASE_C) if t is not None else None,
        }
    return None


def _cache_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, ILM_CACHE_NAME)


def fetch_harku_observation(
    cache_dir: Optional[str] = None,
    ttl_s: int = ILM_CACHE_TTL_S,
) -> Tuple[dict, str]:
    """Polite cached pull of the Harku observation (live path, NOT unit-run).

    Cache wins inside the TTL; on a live pull any transport error
    (HTTP error, timeout, 429, unparseable body, missing station)
    raises and the cache file is left untouched — transport errors
    are never cached as data, and 429 stops the run. Returns
    (record, provenance) with provenance "cache" or "live".
    """
    if cache_dir is None:
        cache_dir = os.path.join("/tmp", "hf-ilm-cache")
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl_s:
        with open(path, "r", encoding="utf-8") as fh:
            record = parse_harku_observation(fh.read())
        if record is not None:
            return record, "cache"
    req = urllib.request.Request(
        ILM_OBSERVATIONS_URL, headers={"User-Agent": ILM_USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        if resp.status == 429:
            raise RuntimeError("Ilmateenistus vastas 429 — peatu, ära reetry")
        if resp.status != 200:
            raise RuntimeError(
                "Ilmateenistus vastas HTTP %s — vahemälu puutumata" % resp.status
            )
        body = resp.read().decode("utf-8", errors="replace")
    record = parse_harku_observation(body)
    if record is None:
        raise RuntimeError("Harku jaama plokki vastuses polnud — vahemälu puutumata")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return record, "live"


def aggregate_baseline(records: List[dict]) -> dict:
    """Aggregate parsed Harku records into the baseline dict dims consume.

    Pure; record lists are what the daily archiver accumulates. Monthly
    buckets carry only months present in the input — absent months stay
    absent (dims NULL them, never substitute another month). The wind
    rose counts only records with a wind direction; shares are over
    the directed records.
    """
    monthly: Dict[int, dict] = {}
    rose: Dict[str, int] = {}
    n_rose = 0
    n_calm = 0
    n_wind = 0
    first_ts: Optional[int] = None
    last_ts: Optional[int] = None
    for rec in records or []:
        ts = rec.get("ts")
        if ts is not None:
            first_ts = ts if first_ts is None else min(first_ts, ts)
            last_ts = ts if last_ts is None else max(last_ts, ts)
            month = time.gmtime(ts).tm_mon
        else:
            month = None
        bucket = None
        if month is not None:
            bucket = monthly.setdefault(
                month, {"n": 0, "t_sum": 0.0, "t_n": 0,
                        "sun_sum": 0.0, "cdd_sum": 0.0})
            bucket["n"] += 1
            if rec.get("t") is not None:
                bucket["t_sum"] += rec["t"]
                bucket["t_n"] += 1
            if rec.get("sun") is not None:
                bucket["sun_sum"] += rec["sun"]
            if rec.get("cdd18") is not None:
                bucket["cdd_sum"] += rec["cdd18"]
        wdir = rec.get("winddir")
        if wdir is not None:
            rose[sector_of_bearing(wdir)] = rose.get(sector_of_bearing(wdir), 0) + 1
            n_rose += 1
        wsp = rec.get("windspeed")
        if wsp is not None:
            n_wind += 1
            if wsp < CALM_MAX_MS:
                n_calm += 1
    months = {}
    for month, b in sorted(monthly.items()):
        months[month] = {
            "n": b["n"],
            "t_mean": (b["t_sum"] / b["t_n"]) if b["t_n"] else None,
            "sun_hours": b["sun_sum"],
            "cdd18": b["cdd_sum"],
        }
    wind_rose = {s: rose.get(s, 0) / n_rose for s in SECTORS_16} if n_rose else {}
    return {
        "station": ILM_STATION_NAME,
        "wmo": ILM_STATION_WMO,
        "n": len(records or []),
        "period": {"first": first_ts, "last": last_ts},
        "monthly": months,
        "wind_rose": wind_rose,
        "calm_share": (n_calm / n_wind) if n_wind else None,
        "source": "Keskkonnaagentuur Ilmateenistus, %s (vaatluste arhiiv)" % ILM_STATION_NAME,
    }


def _july(baseline: Optional[dict]) -> Optional[dict]:
    if not baseline:
        return None
    return (baseline.get("monthly") or {}).get(7)


def _december(baseline: Optional[dict]) -> Optional[dict]:
    if not baseline:
        return None
    return (baseline.get("monthly") or {}).get(12)


# ---------------------------------------------------------------------------
# P4-031: backyard weather + DIY air (demo param — documented NULL).
# ---------------------------------------------------------------------------

def dim_backyard_weather(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]],
                         baseline: Optional[dict] = None) -> Score:
    """P4-031: NULL — one Harku station cannot resolve backyard pockets.

    Frost pockets and wind tunnels are per-backyard facts; the honest
    per-parcel inputs (sensor.community DIY density, Tehnopol pilot,
    LiDAR cold-air drainage) are not in the snapshot. The ingested
    Harku baseline is city-wide context, never a backyard score, so
    the value stays None and the reason carries the baseline plus the
    sensor-count check the buyer must do instead.
    """
    if baseline and (baseline.get("monthly") or {}):
        means = [m["t_mean"] for m in baseline["monthly"].values()
                 if m.get("t_mean") is not None]
        ctx = ("Harku linnabaas (hinnang, %d vaatlust)" % baseline.get("n", 0)
               + ("; keskmine +%.1f °C" % (sum(means) / len(means)) if means else ""))
        return None, ("%s — hoovi mikrokliima EI OLE jaamamõõt: külmakotid ja "
                      "tuulekoridorid selguvad DIY-andurite tihedusest "
                      "(sensor.community), mitte Harku jaamast — loe andureid" % ctx)
    return None, ("Hoovi ilm teadmata (EI OLE hinnangut): Harku jaama baasjoont "
                  "pole sisse loetud ja DIY-andurite tihedust hetktõmmises pole — "
                  "kontrolli sensor.community katvust ja hoovi varju/tuult kohapeal")


# ---------------------------------------------------------------------------
# P4-034: summer overheating risk (July baseline band, capped).
# ---------------------------------------------------------------------------

#: July-mean bands: coarse city baseline, capped (never below 20 on
#: baseline alone — the S/W top-floor sim needs EHR listing facts).
OVERHEAT_BANDS = ((16.0, 80), (18.0, 65), (20.0, 50), (22.0, 35))


def dim_overheat_risk(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]],
                      baseline: Optional[dict] = None) -> Score:
    """P4-034: July-mean city baseline band (capped, never a sim)."""
    july = _july(baseline)
    if july is None or july.get("t_mean") is None:
        return None, ("Suve kuumenemine teadmata (EI OLE hinnangut): Harku juuli "
                      "baasjoont pole (vajab juulikuu vaatlusarhiivi) — S/W suund, "
                      "ülemine korrus ja läbiv tuulutus selguvad kuulutusest/EHR-ist")
    t = july["t_mean"]
    for limit, pts in OVERHEAT_BANDS:
        if t < limit:
            score = pts
            break
    else:
        score = 20
    return score, ("Tallinna juuli baasjoon (Harku, +%.1f °C, %d vaatlust, hinnang "
                   "— mitte korteri simulatsioon): kontrolli S/W suund, ülemine "
                   "korrus, läbiv tuulutus ja jahutus" % (t, july["n"]))


# ---------------------------------------------------------------------------
# P4-035: December darkness (December sun-hours baseline band, capped).
# ---------------------------------------------------------------------------

#: December-sun-total bands (hours/month): coarse city baseline, capped
#: (never above 80 on baseline alone — lamps need the inventory).
DARKNESS_BANDS = ((10.0, 20), (20.0, 35), (35.0, 50), (50.0, 65))


def dim_december_darkness(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]],
                          baseline: Optional[dict] = None) -> Score:
    """P4-035: December sun-hours city baseline band (capped)."""
    dec = _december(baseline)
    if dec is None:
        return None, ("Detsembri pimedus teadmata (EI OLE hinnangut): Harku "
                      "detsembri baasjoont pole (vajab detsembrikuu "
                      "vaatlusarhiivi) — tänavavalgustus, hoovi vari ja akende "
                      "suund selguvad kaardilt/kuulutusest")
    sun = dec["sun_hours"]
    for limit, pts in DARKNESS_BANDS:
        if sun < limit:
            score = pts
            break
    else:
        score = 80
    return score, ("Tallinna detsembri baasjoon (Harku, päikesepaiste %.1f h/kuu, "
                   "%d vaatlust, hinnang — mitte valgustuse mõõt): kontrolli "
                   "tänavavalgustus, hoovi varju ja akende suunda" % (sun, dec["n"]))


# ---------------------------------------------------------------------------
# P4-053: odour roses by wind frequency (sector dim, never a buffer).
# ---------------------------------------------------------------------------

#: Caller-supplied emitter inventory entries look like
#: {"kind": "odour_emitter", "lat": 59.45, "lon": 24.66, "name": "Paljassaare"}.
ODOUR_EMITTER_KIND = "odour_emitter"


def _nearest_emitter(origin: Tuple[float, float],
                     pois: List[dict]) -> Optional[dict]:
    best = None
    best_key = None
    for p in pois or []:
        if p.get("kind") != ODOUR_EMITTER_KIND:
            continue
        if p.get("lat") is None or p.get("lon") is None:
            continue
        key = ((p["lat"] - origin[0]) ** 2 + (p["lon"] - origin[1]) ** 2)
        if best_key is None or key < best_key:
            best, best_key = p, key
    return best


def dim_odour_rose(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]],
                   baseline: Optional[dict] = None) -> Score:
    """P4-053: downwind-sector frequency off the Harku rose (sector dim)."""
    if not origin or not pois:
        return None, ("Lõhnaroos teadmata (EI OLE hinnangut): aadress ja "
                      "heitja-inventuur puuduvad — Paljassaare/asfaldi/pruuli/"
                      "kalasuitsu suund selgub tuuleroosi sektorist, mitte ringpuhvrist")
    emitter = _nearest_emitter(origin, pois)
    if emitter is None:
        return None, ("Lõhnaroos teadmata (EI OLE hinnangut): heitjate inventuuri "
                      "(e-Äriregister: Paljassaare, asfalditehas, pruulikoda, "
                      "kalasuits) hetktõmmises pole — küsi Keskkonnaameti "
                      "lõhnakaebusi sektori kaupa")
    rose = (baseline or {}).get("wind_rose") or {}
    if not rose:
        return None, ("Lõhnaroos teadmata (EI OLE hinnangut): Harku tuuleroosi "
                      "baasjoont pole (vajab tuulesuuna vaatlusarhiivi) — "
                      "allatuule päevade arv selgub roosi sektorisagedusest")
    sector = sector_of_bearing(bearing_deg(origin, (emitter["lat"], emitter["lon"])))
    if sector not in rose:
        return None, ("Lõhnaroos teadmata (EI OLE hinnangut): roosi sektorit %s "
                      "arhiivis pole — allatuule hinnangut ei feigi" % sector)
    freq = rose[sector]
    score = max(0, min(100, int(round(100.0 * (1.0 - freq / ODOUR_SAT_FREQ)))))
    days = int(round(freq * 365))
    name = emitter.get("name") or "heitja"
    return score, ("Lõhnasektor %s: Harku roosi sagedus %.1f%% (~%d allatuule "
                   "päeva/aastas, hinnang — %s suund, mitte korstna-täpsus)" % (
                       sector, freq * 100.0, days, name))


# ---------------------------------------------------------------------------
# P4-056: enclosed-courtyard trap (documented NULL, ventilation context).
# ---------------------------------------------------------------------------

def dim_courtyard_trap(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]],
                       baseline: Optional[dict] = None) -> Score:
    """P4-056: NULL — per-parcel enclosure needs LiDAR (no map)."""
    if baseline and baseline.get("calm_share") is not None:
        return None, ("Hoovi lõks teadmata (EI OLE hinnangut): kinnisuse indeks "
                      "eeldaks Maa-ameti LiDAR-it, mida hetktõmmises pole — Harku "
                      "tuulevaikuse baas %.1f%% (hinnang, õhuvahetuse proksi), "
                      "hoovi kuju kontrolli aerofotolt/kohapeal"
                      % (baseline["calm_share"] * 100.0))
    return None, ("Hoovi lõks teadmata (EI OLE hinnangut): kinnisuse indeks eeldaks "
                  "Maa-ameti LiDAR-it ja Harku tuulevaikuse baasjoont, kumbagi "
                  "hetktõmmises pole — kontrolli hoovi kuju ja haljastust kohapeal")


#: Registry for UI/API wiring on integration: key -> (param id, title, fn).
P4ILM_DIMS = {
    "backyard_weather": ("P4-031", "Hoovi ilm + DIY-õhk (kontroll)", dim_backyard_weather),
    "overheat_risk": ("P4-034", "Suve kuumenemine (baasjoon)", dim_overheat_risk),
    "december_darkness": ("P4-035", "Detsembri pimedus (baasjoon)", dim_december_darkness),
    "odour_rose": ("P4-053", "Lõhnaroos (sektor)", dim_odour_rose),
    "courtyard_trap": ("P4-056", "Hoovi lõks (kontroll)", dim_courtyard_trap),
}

#: Param-number wiring for the central weight-rebalance follow-up.
P4ILM_PARAM_IDS = {
    "backyard_weather": 31,
    "overheat_risk": 34,
    "december_darkness": 35,
    "odour_rose": 53,
    "courtyard_trap": 56,
}


def score_p4_ilm(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]],
                 baseline: Optional[dict] = None) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All five P4-ilm dims at once: ({key: score}, [reasons]).

    NULL dims contribute no reasons (no fake evidence) — same rollup
    contract as sibling score_group08b.
    """
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for key, (_, _, fn) in P4ILM_DIMS.items():
        v, reason = fn(origin, pois, baseline)
        dims[key] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
