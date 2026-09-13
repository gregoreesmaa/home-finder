"""P4 Tallinna parkimine dims (issues #279 demo + #353 coverage).

Params (this module only — demo + its coverage follow-up share one source):
* P4-013 Parking regime: tasulise parkimise tsoon (demo, batch 1)
* P4-037 Policy exposure: car-tax / car-free exposure, zone-cost slice
  (batch 3, coverage in #353)
* P4-049 Taxi/guest test: Saturday 19:00 guest-parking slice (batch 4,
  coverage in #353)

OPENNESS VERDICT (checked 2026-09-13, 8 polite requests total, labelled
one-off user-agent, raw bodies cached at /tmp/park-open/ — TTL: one-off
check, kept for the PR record, never committed):
* https://www.tallinn.ee/et/liikuvus/parkimine (HTTP 200, ~101 KB, one
  GET; redirects to /et/liikuvus/parkimine#Parkimine): OPEN. Carries the
  live 4-zone regime as human-readable text — kesklinn 0,025 EUR/min
  (E-R 7-19, L 8-15, P tasuta; perioodipilet 150 EUR), südalinn
  0,08 EUR/min (24/7; 250 EUR), vanalinn 0,10 EUR/min (24/7, eraldi
  Linnavalitsuse määrus; 300 EUR), Pirita 0,01 EUR/min (15.05-15.09,
  10-22). Zone lookup is interactive only (gis.tallinn.ee veebikaart,
  Google My Map, kaardiotsing) — NO pollable polygon feed.
* https://www.riigiteataja.ee/akt/431122022063 (HTTP 200, one GET):
  OPEN — the määrus text (consolidated wording uses T-numbered zones,
  e.g. T5/T6 street lists) is the legal basis behind the hub page.
* https://www.parkimine.ee/parkimisinfo/ (HTTP 200, ~133 KB, one GET;
  wp-json page record fetched, content field EMPTY): DATED NEGATIVE for
  the city-zone/permit join. 193x "tsoon" but every hit is a commercial
  operator-lot code (tsoon YT60/F1/P29, "osta parkimisluba") — 0x
  "tasuline", 0x "elaniku", 0x "külalis", 0x "määrus". A lot directory,
  not the city regime.
* https://parkimine.tallinn.ee/ (HTTP 200, ~165 KB, one GET): DATED
  NEGATIVE for polling. 46 visible characters ("Tallinna linna
  parkimise iseteenindusportaal") — a JS login shell. Driving its
  session flows would be scraping (AGENTS.md section 5, refused).
* tallinn.ee HEAD probes return 403 from Cloudflare while the same URL
  GETs 200 — HEAD status there proves nothing; the GET is the verdict.
So: zone FACTS are openly fetchable (hub page + RT act — the ingestion
below), zone POLYGONS are not (interactive viewers only). The scorers
therefore join per-parcel on an EXPLICIT zone key, never by distance:
unknown zone stays NULL with an Estonian EI OLE reason.

HONESTY (AGENTS.md section 7.2): every scored dim says "hinnang"
(estimate) and prints its components (fee, paid hours, period pass);
every NULL reason says "EI OLE" and names the missing input plus the
concrete check (Maainfo päring, Transpordiameti veebikaardi
kaardiotsing, iseteenindusportaal). Transport errors in fetch_park are
NEVER cached as data and HTTP 429 is a stop signal, not a retry dare
(AGENTS.md 7.2/7.4). A verified free zone (tsoon None = tasuta ala)
scores — a real no-burden signal — while a missing join (no "tsoon"
key, "teadmata", unknown label) stays NULL: absence of data is
unknown, never good.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_park(url, cache_dir, name, ttl_days): polite pull, one file per
  source, re-pull only after TTL_PARK_DAYS (zones/fees change by
  regulation: annual re-check — same 365 d as the kataster
  parking_zones TTL, parameters4.md "on regulation change + annual").
  Cache hit within TTL performs NO request. Single GET with an
  identifying UA, 25 s timeout, no retries. Returns the cache path or
  None (never raises into scorers; scorers never call it).
* default_snapshot(fetched): the REVIEWED zone-facts table (zone name,
  fee/min, paid hours, period pass, Saturday-19:00 guest fact, source
  URLs + fetched date). Regulation text changes rarely and is legally
  significant, so refresh = human reviews a fresh polite fetch and
  updates this table in a PR — never an HTML scrape (brittle parsing
  would be fake robustness).
* zone_facts(snapshot, tsoon): pure lookup; unknown labels -> None.
* Windows: none — this is a per-parcel regime join, not a radius.

Style mirrors services/scoring/dims_group20a.py (#212, the brief's
pattern file) for scorer purity — pure functions, offline-tested, no
network in tests — but NOT its (origin, pois) signature: a distance
gradient from a zone centroid would be fake precision, so the shape
follows parameters4.md P4-013 ("per-parcel join") and its live
precedent dim_parkimine_hoov (dims_p4_maa_kataster.py, parcel-keyed).
Helpers are local copies (not imported from kataster or siblings): a
future central hook may import this module alongside them, and
importing any of them here would turn that into a cycle (same
precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the #353 body
  states it "extends the demoed ingestion" with "no new plumbing
  expected": all three dims ride the same zone-facts snapshot (same
  precedent as peatus #314+#376, TLT #277+#351, elektrilevi, comapps).
* Slice boundary vs siblings (no double-scoring): dims_p4_osm owns the
  MAPPED-parking/entrance proxies (dim_parking, dim_taxi — both reasons
  explicitly disclaim the zone/permit legs: "tsooni-hinnangut ei ole",
  "külalisparkimise reegleid snapshots pole"); dims_p4_maa_kataster
  owns the A/B/C zone x COURTYARD join (dim_parkimine_hoov); peatus/TLT
  own the transit/arrival slices of P4-037/P4-049. This module owns
  ONLY the live-regime legs: fee/hours burden (P4-013), zone-cost
  exposure (P4-037), Saturday-19:00 guest cost (P4-049). Dim keys stay
  distinct (parking_regime, zone_cost, guest_parking) so the central
  hook can weight slices independently (trans #408 precedent):
  policy_exposure is already shared by the emta + peatus slices and
  taxi_guest by two more — this module extends neither sharing.
* Zone naming follows the LIVE hub page (kesklinn/südalinn/vanalinn/
  pirita, verified 2026-09-13), NOT the kataster module's A/B/C nor
  the RT-consolidated T-numbering — the two older schemes disagree
  with the live source and with each other. Flagged, not fixed here:
  shared-file edits are out of scope (NEW FILES ONLY), so a follow-up
  must reconcile dim_parkimine_hoov's A/B/C input domain with the live
  4-zone regime.
* Bands are first-cut burden judgments anchored on VERIFIED fees/hours
  (0,10 > 0,08 > 0,025 > 0,01 > 0 EUR/min; 24/7 vs daytime-only vs
  seasonal vs free); they MUST be re-anchored centrally if tariffs
  move (docs/p4_park.md refresh checklist). Scores fall as the daily-
  parking burden rises (Buy Q: where do I park daily).
* Pirita guest score (65) encodes the seasonal caveat openly: Sat
  19:00 falls inside the 10-22 paid window in season (token fee) and
  outside it off season (free) — the reason states both, the score
  splits the difference instead of hiding the season.
* No Overpass fragment, no tag mapping: zone polygons are not
  authoritative OSM data (OSM parking polygons already feed the
  dims_p4_osm slice), so there is nothing for the live path to fetch.

Integration (deliberately NOT done here): the listing pipeline must
fill parking["tsoon"] from the määrus lookup (Transpordiameti
veebikaardi kaardiotsing) per parcel — exactly like the kataster
parking dict today. Rebalancing livability.WEIGHTS stays one joint
change across all batches (existing tests pin set(WEIGHTS)). No
shared files touched: 3 new files only.
"""

import datetime as _dt
import os
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: sources, politeness, cache.
# ---------------------------------------------------------------------------

#: Live city parking hub (zone regime facts; probed 2026-09-13, HTTP 200).
PARK_HUB_URL = "https://www.tallinn.ee/et/liikuvus/parkimine"

#: Legal basis: Tallinna avalik tasuline parkimisala ja parkimistasu
#: (Riigi Teataja; probed 2026-09-13, HTTP 200).
RT_AKT_URL = "https://www.riigiteataja.ee/akt/431122022063"

#: City self-service portal (JS login shell — dated negative for polling,
#: named so the NULL reasons can point at the human check honestly).
PORTAL_URL = "https://parkimine.tallinn.ee/"

#: Commercial operator-lot directory (dated negative for the zone join).
OPERATOR_DIR_URL = "https://www.parkimine.ee/parkimisinfo/"

#: Zones/fees change by regulation: annual re-check (parameters4.md P4-013
#: "on regulation change + annual"; same 365 d as kataster parking_zones).
TTL_PARK_DAYS = 365

CACHE_SUBDIR = "hf-p4-park"

USER_AGENT = (
    "home-finder-research/0.1 (polite parkimine harvest; "
    "GitHub gregoreesmaa/home-finder issue 279)"
)

#: Reviewed zone facts as published on the hub page 2026-09-13
#: (fee EUR/min, paid-hours text, period-pass EUR, Saturday-19:00 guest
#: fact). Refresh = human reviews a fresh polite fetch, updates this
#: table in a PR — never scraped.
ZONE_FACTS: Dict[str, Dict[str, Optional[str]]] = {
    "kesklinn": {"tasu_min": "0,025 EUR/min", "aeg": "E-R 7-19, L 8-15, P tasuta",
                 "perioodipilet": "150 EUR", "laup_kell_19": "tasuta"},
    "südalinn": {"tasu_min": "0,08 EUR/min", "aeg": "24/7",
                 "perioodipilet": "250 EUR", "laup_kell_19": "tasuline"},
    "vanalinn": {"tasu_min": "0,10 EUR/min", "aeg": "24/7, eraldi määrus",
                 "perioodipilet": "300 EUR", "laup_kell_19": "tasuline"},
    "pirita": {"tasu_min": "0,01 EUR/min", "aeg": "15.05-15.09, 10-22",
               "perioodipilet": None, "laup_kell_19": "hooajaline"},
}

#: Canonical zone labels (lowercase); None = verified tasuta ala.
ZONES = ("kesklinn", "südalinn", "vanalinn", "pirita")

SNAPSHOT_FETCHED = "2026-09-13"


def cache_path(cache_dir: str, name: str) -> str:
    """Cache file location for a named fetch (flat files, no dumps committed)."""
    return os.path.join(cache_dir, CACHE_SUBDIR, name)


def is_fresh(path: str, ttl_days: int,
             now: Optional[_dt.datetime] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        mtime = _dt.datetime.fromtimestamp(
            os.path.getmtime(path), tz=_dt.timezone.utc)
    except OSError:
        return False
    at = now or _dt.datetime.now(tz=_dt.timezone.utc)
    return (at - mtime) <= _dt.timedelta(days=ttl_days)


def fetch_park(url: str, cache_dir: str, name: str,
               ttl_days: int = TTL_PARK_DAYS,
               timeout_s: int = 25) -> Optional[str]:
    """Polite single-GET with file cache. Returns the cache path or None.

    Fresh cache wins (no request). Transport errors, non-200 status and
    HTTP 429 yield None and are NEVER written as data (429 is a stop
    signal, no retry). Scorers never call this; tests cover the
    cache-hit and error paths with a stubbed opener, never the network.
    """
    import urllib.request

    dest = cache_path(cache_dir, name)
    if is_fresh(dest, ttl_days):
        return dest
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = getattr(resp, "status", 200)
            if status == 429 or status != 200:
                return None
            body = resp.read()
    except Exception:
        return None
    if not body:
        return None
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as fh:
        fh.write(body)
    os.replace(tmp, dest)
    return dest


def default_snapshot(fetched: str = SNAPSHOT_FETCHED) -> dict:
    """Reviewed zone-facts snapshot (offline; refresh per module docstring)."""
    return {"fetched": fetched,
            "sources": [PARK_HUB_URL, RT_AKT_URL],
            "zones": {k: dict(v) for k, v in ZONE_FACTS.items()}}


# ---------------------------------------------------------------------------
# Pure helpers (per-parcel join core — hermetically tested).
# ---------------------------------------------------------------------------

def parcel_id(parcel: Optional[dict]) -> Optional[str]:
    """Katastritunnus when the parcel join is honest, else None."""
    if not isinstance(parcel, dict):
        return None
    kid = parcel.get("katastritunnus")
    if kid is None:
        return None
    key = " ".join(str(kid).strip().split())
    return key or None


def normalise_zone(raw: Optional[str]) -> Optional[str]:
    """Lowercase + trim a zone label; None stays None (verified tasuta ala).

    Unknown labels are returned as-is so the scorers can NULL them with
    a "paranda tsooniotsing" reason instead of silently mapping them.
    """
    if raw is None:
        return None
    key = " ".join(str(raw).strip().lower().split())
    return key or "teadmata"


def zone_facts(snapshot: Optional[dict],
               tsoon: Optional[str]) -> Optional[dict]:
    """Reviewed facts for a normalised zone label, else None.

    None (tasuta ala) yields the free-area fact; unknown labels yield
    None (scorer stays NULL). Pure.
    """
    if tsoon is None:
        return {"tasu_min": "0 EUR/min", "aeg": "piiranguta",
                "perioodipilet": None, "laup_kell_19": "tasuta"}
    if not isinstance(snapshot, dict):
        return None
    zones = snapshot.get("zones")
    if not isinstance(zones, dict):
        return None
    facts = zones.get(tsoon)
    return dict(facts) if isinstance(facts, dict) else None


def _parking_zone(parking: Optional[dict]) -> Tuple[Optional[str], bool]:
    """(normalised zone, usable): the explicit per-parcel join key.

    Usable = the caller ran the määrus lookup and recorded it (None =
    verified tasuta ala). Missing key / "teadmata" / blank = no join.
    """
    if not isinstance(parking, dict) or "tsoon" not in parking:
        return None, False
    zone = normalise_zone(parking.get("tsoon"))
    if zone == "teadmata":
        return None, False
    return zone, True


# ---------------------------------------------------------------------------
# First-cut burden bands, anchored on the verified 2026-09-13 fee ladder
# (0,10 > 0,08 > 0,025 > 0,01 > 0 EUR/min). Scores fall as the daily-
# parking burden rises. Central rebalance owns the weights.
# ---------------------------------------------------------------------------

#: P4-013 daily-parking burden: fee + paid-hours leg only.
REGIME_BAND = {"vanalinn": 35, "südalinn": 45, "kesklinn": 60,
               "pirita": 75, None: 80}

#: P4-037 zone-cost exposure slice (automaks bands + transit offset live
#: in the EMTA/peatus/TLT slices — named missing, never assumed).
EXPOSURE_BAND = {"vanalinn": 30, "südalinn": 40, "kesklinn": 55,
                 "pirita": 70, None: 80}

#: P4-049 Saturday-19:00 guest-cost slice (guest-permit scheme not in the
#: snapshot — named missing; the paid/free Sat-evening FACT scores).
GUEST_BAND = {"vanalinn": 35, "südalinn": 45, "pirita": 65,
              "kesklinn": 75, None: 80}


# ---------------------------------------------------------------------------
# P4-013: parking regime, fee/hours leg (demo param).
# ---------------------------------------------------------------------------

def dim_parking_regime(parcel: Optional[dict],
                       parking: Optional[dict]) -> Score:
    """P4-013: daily-parking burden from the live zone regime.

    Parcel-keyed per-parcel join: the caller supplies parking["tsoon"]
    from the määrus lookup (Transpordiameti veebikaardi kaardiotsing).
    Courtyard ratio lives in the kataster slice, mapped bays in the OSM
    slice — this leg scores ONLY fee + paid hours + period pass.
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): parkimise "
                      "režiim on katastriüksuse join — tee Maainfo päring, "
                      "ära feigi")
    zone, usable = _parking_zone(parking)
    if not usable:
        return None, ("Parkimistsooni katastriüksuse %s kohta EI OLE "
                      "(hinnang puudub): režiim vajab Tallinna parkimise "
                      "määruse tsooniotsingut — kontrolli Transpordiameti "
                      "veebikaardi kaardiotsingust, ära feigi" % kid)
    facts = zone_facts(default_snapshot(), zone)
    if facts is None:
        return None, ("Parkimistsoon '%s' on tundmatu väärtus — režiimi- "
                      "hinnangut EI OLE: paranda tsooniotsing" % zone)
    s = REGIME_BAND[zone]
    if zone is None:
        return s, ("Parkimisrežiim (hinnang): tasuta ala — igapäevane "
                   "parkimine ilma tasuta (hoovikoha ja elanikuloa pool "
                   "katastri/OSM-osas, mitte siin) → skoor %d" % s)
    return s, ("Parkimisrežiim (hinnang): tsoon %s, %s, %s, perioodipilet "
               "%s → skoor %d"
               % (zone, facts["tasu_min"], facts["aeg"],
                  facts["perioodipilet"] or "puudub", s))


# ---------------------------------------------------------------------------
# P4-037: policy exposure, zone-cost slice (coverage param).
# ---------------------------------------------------------------------------

def dim_zone_cost(parcel: Optional[dict],
                        parking: Optional[dict]) -> Score:
    """P4-037: zone-cost exposure band (high = low decree-driven cost).

    Only THIS source's half: what the paid zone costs a car-dependent
    buyer. Automaks bands (EMTA kalkulaator), ummikumaksu/autovaba-ala
    otsused and the transit offset (peatus/TLT slices) are not in this
    snapshot — the reason names them instead of assuming them.
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): "
                      "kuluriski saab siduda ainult katastriüksusega — "
                      "tee Maainfo päring, ära feigi")
    zone, usable = _parking_zone(parking)
    if not usable:
        return None, ("Parkimistsooni katastriüksuse %s kohta EI OLE "
                      "(hinnang puudub): kulurisk vajab tsooniotsingut — "
                      "kontrolli Transpordiameti veebikaardi "
                      "kaardiotsingust, ära feigi" % kid)
    facts = zone_facts(default_snapshot(), zone)
    if facts is None:
        return None, ("Parkimistsoon '%s' on tundmatu väärtus — kuluriski "
                      "hinnangut EI OLE: paranda tsooniotsing" % zone)
    s = EXPOSURE_BAND[zone]
    if zone is None:
        return s, ("Kuluriski (hinnang, ainult tsooni-kulu pool): tasuta "
                   "ala — automaksu kalkulaator (EMTA) ja ühistranspordi "
                   "alternatiiv (peatus/TLT-osa) eraldi → skoor %d" % s)
    return s, ("Kuluriski (hinnang, ainult tsooni-kulu pool): tsoon %s, "
               "%s, %s — automaks (EMTA), ummikumaksu/autovaba-ala "
               "otsused ja transiidialternatiiv snapshots pole → "
               "skoor %d" % (zone, facts["tasu_min"], facts["aeg"], s))


# ---------------------------------------------------------------------------
# P4-049: Saturday-19:00 guest parking (coverage param).
# ---------------------------------------------------------------------------

def dim_guest_parking(parcel: Optional[dict],
                      parking: Optional[dict]) -> Score:
    """P4-049: Saturday-19:00 guest-cost slice (high = guest parks free).

    Only THIS source's half: what a Saturday-evening guest pays in the
    parcel's zone. Findability/entrance (OSM slice), Saturday transit
    (peatus slice) and guest-arrival time (TLT slice) are not scored
    here; a guest-permit scheme is not in the snapshot (named, not
    assumed).
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): "
                      "külalisparkimise saab siduda ainult "
                      "katastriüksusega — tee Maainfo päring, ära feigi")
    zone, usable = _parking_zone(parking)
    if not usable:
        return None, ("Parkimistsooni katastriüksuse %s kohta EI OLE "
                      "(hinnang puudub): külalisreegel vajab "
                      "tsooniotsingut — kontrolli Transpordiameti "
                      "veebikaardi kaardiotsingust, ära feigi" % kid)
    facts = zone_facts(default_snapshot(), zone)
    if facts is None:
        return None, ("Parkimistsoon '%s' on tundmatu väärtus — "
                      "külalisparkimise hinnangut EI OLE: paranda "
                      "tsooniotsing" % zone)
    s = GUEST_BAND[zone]
    if zone is None:
        return s, ("Külalisparkimine laupäeval kell 19 (hinnang): tasuta "
                   "ala — külaline pargib tasuta (sissepääsu leitavus "
                   "OSM-osas, mitte siin) → skoor %d" % s)
    if zone == "kesklinn":
        return s, ("Külalisparkimine laupäeval kell 19 (hinnang): tsoon "
                   "kesklinn, laupäeviti tasuline vaid 8-15 — kell 19 "
                   "külaline pargib tasuta (päevareeglid erinevad) → "
                   "skoor %d" % s)
    if zone == "pirita":
        return s, ("Külalisparkimine laupäeval kell 19 (hinnang, "
                   "hooajaline): tsoon pirita, hooajal 15.05-15.09 "
                   "10-22 tasuline sümboolse 0,01 EUR/min, väljaspool "
                   "hooaega tasuta — külalisloa skeemi snapshots pole "
                   "→ skoor %d" % s)
    return s, ("Külalisparkimine laupäeval kell 19 (hinnang): tsoon %s, "
               "%s, %s — külaline maksab ka laupäeva õhtul, külalisloa "
               "skeemi snapshots pole → skoor %d"
               % (zone, facts["tasu_min"], facts["aeg"], s))


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
P4_PARK_DIMS = (
    ("parking_regime", "P4-013", dim_parking_regime),
    ("zone_cost", "P4-037", dim_zone_cost),
    ("guest_parking", "P4-049", dim_guest_parking),
)


def score_p4_park(parcel: Optional[dict],
                  parking: Optional[dict] = None) -> Dict[str, Optional[int]]:
    """P4 park dims for one parcel (entry point for the follow-up)."""
    return {key: fn(parcel, parking)[0] for key, _, fn in P4_PARK_DIMS}
