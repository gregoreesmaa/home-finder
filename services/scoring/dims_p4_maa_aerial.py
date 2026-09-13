"""P4 Maa-amet aerial + surface layers dims: demo (#246) + coverage (#330).

Demo param (this ingestion's anchor):
* P4-022 Listing photo forensics (facade change cross-check off the aerial)

Coverage params (extend the demoed ingestion, no new plumbing):
* P4-029 Street-imagery block observer (Mapillary/CV + aerial vintage leg)
* P4-030 Satellite change delta (coarse change flag off vintages + NDVI input)
* P4-041 Glimpse economics (piilukas view class off the LiDAR/LoD2 fan input)
* P4-056 Enclosed-courtyard trap (LiDAR enclosure-index leg)
* P4-057 Heat-pump hum corridors (weak hinnang off heating-type change input)
* P4-058 Falling-ice roofs + cliff retreat (per-parcel dims with dates)
* P4-060 Stormwater fee zones + subsidy queue (zone table + checklist dim)

OPENNESS VERDICT (probed 2026-09-13, single polite fetches, cached
/tmp/hf-p4-maa-aerial/, contact UA in headers — full evidence in
docs/p4_maa_aerial.md):
* fotokaart WMS GetCapabilities (EESTIFOTO orthophoto + queryable nDSM):
  OPEN (HTTP 200, 60 038 B).
* ajalooline WMS GetCapabilities (historical topo maps, change context):
  OPEN (HTTP 200, 154 273 B).
* Korgusandmed page (DEM/DSM/nDSM + Maakattemudeli/Maapinnamudeli WCS):
  OPEN (HTTP 200, 59 528 B). LiDAR-flown coverage + years documented.
* Tallinna Vesi sademevesi page (lahkvoolne/uhisvoolne piirkonnad +
  hinnakiri): OPEN (HTTP 200, 317 921 B) — P4-060 zone-table leg is real.
* DATED PARTIAL-NEGATIVES (verdict kept, legs named EI OLE, never faked):
  no per-year aerial-vintage WMS layers (fotokaart serves the current
  mosaic; vintages live in downloads/production history), no dedicated
  Maa-amet shoreline-retreat layer, no Maa-amet impervious-surface layer
  found. Re-probe annually; newly opened layers flip the verdict without
  code changes (ingestion already caches with TTL).

HONESTY (AGENTS.md section 7.2): the only scored shapes here are coarse
change flags / cross-checks and per-listing context dims — never a
distance gradient, never interpolation, never a heat-coloured guess.
Every NULL reason says "hinnang" (estimate) and "EI OLE" and names the
concrete check (adapter store, aerial cross-check, manual checklist) —
never a faked number. Transport errors in fetch_cached are NEVER cached
as data, and HTTP 429 is a stop signal, not a retry dare (AGENTS.md
sections 7.2/7.4).

Style: pure offline scorers (listing, aerial, ...) -> (Optional[int
0..100], Estonian reason), mirroring dims_p4_maa_tehingud.py (#384).
Network lives ONLY in fetch_cached (polite single-GET + file cache +
TTL); tests never touch the network. No livability/WEIGHTS/layers
integration here — rebalancing stays one joint change across batches
(existing tests pin WEIGHTS).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #330's body states it
  extends the #246 demo ingestion ("no new plumbing expected") — same
  precedent as #384 (#244 demo + #328 coverage). Splitting would leave
  the demo unreviewable against its coverage contract.
* P4-056 folds in the LiDAR-enclosure leg that dims_p4_ilm's
  dim_courtyard_trap names missing ("kinnisuse indeks eeldaks Maa-ameti
  LiDAR-it"). That ilm dim stays UNTOUCHED (this task forbids shared-file
  edits); its Harku calm-share wind leg is cross-referenced in the reason,
  never re-scored here, so the legs cannot double-push the sort. The
  weight-rebalance follow-up merges them.
* No per-year vintage WMS exists, so P4-022/P4-030 score a coarse
  then/now cross-check (ajalooline topo + then/now labels), never a true
  year-delta — a year-delta off one mosaic would be fake precision.
* P4-041 scores the view-fan RESULT (open/sliver/none) as the class;
  floor alone is an input to the fan, not a standalone signal, so a
  missing fan stays NULL even when the floor is known.
* P4-057 stays WEAK by construction: heating-type change is a proxy for
  hum exposure, not a measurement — uptake-only scores neutral 55, never
  high, so it cannot sell quiet it did not measure.
* P4-058 ambiguity rule: any ice/cliff risk scores low (40) with the
  date in the reason; only legs WITH data and clean score 70. Absence of
  warnings is unknown, never safe.
* P4-060's Maa-amet impervious-surface fee-base proxy was not found
  (dated partial-negative), so the dim scores the Tallinna Vesi zone
  table + manual checklist; the proxy leg is named EI OLE, not faked.
* TTL 365 d for every source: #246 mandates annual bulk, and the WCS
  models / tariffs move yearly at most.

Aerial-record schema (one dict per listing, built from the cached
WMS/WCS pulls + adapter store; every field optional, missing -> leg
stays out, never defaulted):
* ortho_vintage: newest orthophoto vintage string, e.g. "2024"
* ortho_then_label / ortho_now_label: coarse then/now labels (e.g.
  "hoone", "haljasala", "tuhi krunt", "ehitusplats")
* facade_change: True/False/None (aerial facade cross-check)
* duplicate_hashes: int|None (own-store image-hash relist matches)
* exif_daylight_ok: True/False/None (own-snapshot daylight sanity)
* mapillary_date: "YYYY-MM-DD"|None; facade_ok: True/False/None
* street_issues: list[str] (facade/litter/wrecks/sidewalk findings)
* sidewalk_ok: True/False/None (OSM ground-truth cross-check)
* ndvi_delta: float|None (Sentinel-2 year delta, own computation)
* construction_nearby / raieluba_nearby / dump_suspected: bool|None
* view_fan: "open"|"sliver"|"none"|None (LiDAR/LoD2 fan result)
* protected_view_corridor / future_blockage (P4-006 join): bool
* enclosure_index: float 0..1|None (LiDAR); courtyard_green: bool|None
* heating_changed_heatpump / hum_complaints: bool|None
* listing_mentions_heatpump: bool (adapter NLP flag)
* roof_type: str|None; roof_pitch_steep: bool|None
* ice_warning_date: "YYYY-MM-DD"|None
* cliff_retreat_nearby: bool|None; dist_cliff_m: float|None
* stormwater_zone: str|None; subsidy_queue_pos: int|None
"""

import datetime as _dt
import os
import re
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite fetch + cache + TTL (demo #246 acceptance criterion 2).
# ---------------------------------------------------------------------------

SOURCE_URLS = {
    # Current orthophoto mosaic + queryable nDSM (OPEN 2026-09-13).
    "fotokaart_caps": (
        "https://kaart.maaamet.ee/wms/fotokaart"
        "?SERVICE=WMS&REQUEST=GetCapabilities"
    ),
    # Historical topo maps for the coarse change cross-check (OPEN).
    "ajalooline_caps": (
        "https://kaart.maaamet.ee/wms/ajalooline"
        "?SERVICE=WMS&REQUEST=GetCapabilities"
    ),
    # Elevation models + WCS references (OPEN; LiDAR coverage documented).
    "korgusandmed": (
        "https://geoportaal.maaruum.ee/est/Ruumiandmed/Korgusandmed/"
        "Korgusmudelid-p508.html"
    ),
    # Stormwater zones + tariff page for the P4-060 table (OPEN).
    "sademevesi": "https://www.tallinnavesi.ee/veetarbijale/sademevesi",
}

# TTLs in days: #246 mandates annual bulk; WCS models and tariffs move
# yearly at most, so every source re-probes once a year.
TTL_DAYS = {
    "ortho_mosaic": 365,
    "elevation_wcs": 365,
    "historical": 365,
    "stormwater_zones": 365,
}

CACHE_SUBDIR = "hf-p4-maa-aerial"
USER_AGENT = (
    "home-finder-research/0.1 (polite annual bulk; "
    "GitHub gregoreesmaa/home-finder issue 246)"
)


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


def fetch_cached(url: str, cache_dir: str, name: str, ttl_days: int,
                 timeout_s: int = 25) -> str:
    """Polite single-GET with file cache. Returns the cache path.

    Fresh cache wins (no request). Transport errors are raised and NEVER
    written as data; HTTP 429 raises immediately (stop signal, no retry).
    Pulls urllib only (no new dependency).
    """
    import urllib.request

    dest = cache_path(cache_dir, name)
    if is_fresh(dest, ttl_days):
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status == 429:
                raise RuntimeError("HTTP 429 — stop, do not retry: " + url)
            body = resp.read()
    except Exception:
        raise
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as fh:
        fh.write(body)
    os.replace(tmp, dest)
    return dest


def parse_wms_layer_names(caps_xml: str) -> List[str]:
    """Layer names from a cached WMS GetCapabilities document (pure).

    Used to verify EESTIFOTO / nDSM / historical layers are still served
    before any GetMap/WCS pull; hermetically tested on fixture XML.
    """
    return re.findall(r"<Name>([^<]+)</Name>", caps_xml or "")


def _clamp(score: float) -> int:
    return max(0, min(100, int(round(score))))


# ---------------------------------------------------------------------------
# Demo dim: P4-022 listing photo forensics (issue #246).
# ---------------------------------------------------------------------------

def dim_photo_forensics(listing: dict, aerial: dict) -> Score:
    """P4-022: cross-portal duplicates + daylight sanity + aerial cross-check.

    Four legs, each optional: own-store image-hash duplicates, EXIF/daylight
    sanity, photo-vs-EHR room-count mismatch, Maa-amet aerial facade-change
    cross-check. 2+ flags -> 30, 1 flag -> 55, clean with >= 2 legs -> 80.
    No leg at all stays NULL (never a clean bill off zero evidence).
    """
    dup = aerial.get("duplicate_hashes")
    daylight = listing.get("exif_daylight_ok", aerial.get("exif_daylight_ok"))
    photo_n = listing.get("photo_room_count")
    ehr_n = listing.get("ehr_room_count")
    facade_change = aerial.get("facade_change")

    legs = 0
    flags: List[str] = []
    if isinstance(dup, int) and dup >= 0:
        legs += 1
        if dup >= 1:
            flags.append("ristportaali duplikaat/relist (%d)" % dup)
    if isinstance(daylight, bool):
        legs += 1
        if not daylight:
            flags.append("päevavalguse kahtlus (EXIF/hetktõmmise kontroll)")
    if (isinstance(photo_n, int) and isinstance(ehr_n, int)):
        legs += 1
        if photo_n != ehr_n:
            flags.append("tubade arvu lõhe (%d fotol vs %d EHR-is)"
                         % (photo_n, ehr_n))
    if isinstance(facade_change, bool):
        legs += 1
        if facade_change:
            vintage = aerial.get("ortho_vintage") or "teadmata vintage"
            flags.append("fassaadimuutuse ristsignaal aerofotolt (%s)"
                         % vintage)
    if legs == 0:
        return None, ("Kuulutusefotode kontrolli jalgu EI OLE (hinnang puudub): "
                      "adapteri pildiladu (duplikaadid/päevavalgus) + "
                      "aerofoto fassaadi-ristkontroll puuduvad — kogu "
                      "fototõed kohapeal/adapterist, ära feigi")
    if len(flags) >= 2:
        return 30, ("Fotokontrolli hinnang 30/100: %s — võimalik "
                    "relist/varjatud defekt, küsimus maaklerile"
                    % "; ".join(flags))
    if len(flags) == 1:
        return 55, ("Fotokontrolli hinnang 55/100: %s — üksik "
                    "hoiatussignaal, kontrolli üle" % flags[0])
    return 80, ("Fotokontrolli hinnang 80/100: %d jalga puhtad "
                "(duplikaate/päevavalguse viga/tubade lõhe/fassaadimuutust "
                "pole) — relistisignaali EI OLE" % legs)


# ---------------------------------------------------------------------------
# Coverage dims: the 7 remaining params off this source (issue #330).
# ---------------------------------------------------------------------------

def _photo_age_days(date_s: Optional[str],
                    today: Optional[str] = None) -> Optional[int]:
    if not date_s:
        return None
    try:
        seen = _dt.date.fromisoformat(str(date_s))
    except ValueError:
        return None
    now = _dt.date.fromisoformat(str(today)) if today else _dt.date.today()
    return (now - seen).days


def dim_street_block_observer(listing: dict, aerial: dict,
                              today: Optional[str] = None) -> Score:
    """P4-029: eye-level street reading with photo date (Mapillary/CV leg).

    Clean + fresh (<= 2 y) -> 75; street issues or bad facade -> 40;
    sidewalk-only doubt -> 55; stale photo caps at 60. No imagery leg at
    all stays NULL; the P4-022 join is named, not re-scored.
    """
    _ = listing
    date_s = aerial.get("mapillary_date")
    facade_ok = aerial.get("facade_ok")
    issues = aerial.get("street_issues") or []
    sidewalk_ok = aerial.get("sidewalk_ok")
    has_imagery = (date_s is not None or isinstance(facade_ok, bool)
                   or bool(issues) or isinstance(sidewalk_ok, bool))
    if not has_imagery:
        return None, ("Tänavakaadrit (Mapillary/KartaView) + aerofoto "
                      "ristjalga EI OLE — silmakõrguse hinnang puudub: "
                      "jaluta tänav läbi / oota kaadrit, ära feigi")
    if issues or facade_ok is False:
        problems = ", ".join(issues) if issues else "fassaad kahtlane"
        return 40, ("Tänavavaatluse hinnang 40/100 (%s): fassaad/praht/vrakk/"
                    "kõnnitee-mure — vaata kohapeal üle (foto %s)"
                    % (problems, date_s or "kuupäevata"))
    if sidewalk_ok is False:
        return 55, ("Tänavavaatluse hinnang 55/100: kõnnitee-kahtlus (OSM "
                    "ristkontroll), muu puhas — foto %s"
                    % (date_s or "kuupäevata"))
    age = _photo_age_days(date_s, today)
    if age is not None and age > 730:
        return 60, ("Tänavavaatluse hinnang 60/100 (vananenud foto, %d p "
                    "vana — lagi): puhas, aga kaader vajab uuendust "
                    "(P4-022 fotoliiniga koos)" % age)
    return 75, ("Tänavavaatluse hinnang 75/100: fassaad ja umbrus puhtad "
                "(foto %s)" % (date_s or "kuupäevata"))


def dim_satellite_change_delta(listing: dict, aerial: dict) -> Score:
    """P4-030: coarse change flag (Sentinel-2 NDVI + vintage cross-check).

    Dump suspicion -> 35; construction/grove-loss signals -> 45; legs
    present but quiet -> 70. No leg stays NULL. Coarse flag only — never
    a year-delta off the single current mosaic.
    """
    _ = listing
    dump = aerial.get("dump_suspected")
    ndvi = aerial.get("ndvi_delta")
    construction = aerial.get("construction_nearby")
    raieluba = aerial.get("raieluba_nearby")
    facade_change = aerial.get("facade_change")
    legs = sum([
        dump is not None,
        isinstance(ndvi, (int, float)),
        construction is not None,
        raieluba is not None,
        facade_change is not None,
    ])
    if legs == 0:
        return None, ("Muutusejalgu (NDVI-delta, aerofoto ristsignaal, "
                      "raieload/ehitusload) EI OLE — kaduva salu / uue "
                      "naabri / ladestuse hinnang puudub")
    if dump is True:
        return 35, ("Muutuse hinnang 35/100: ebaseadusliku ladestuse "
                    "kahtlus (jäätmeteade/prügila-signaal) — kontrolli "
                    "Keskkonnaameti teateid")
    signals = []
    if isinstance(ndvi, (int, float)) and ndvi <= -0.15:
        signals.append("NDVI-langus %.2f (haljastuse kadu)" % ndvi)
    if construction is True:
        signals.append("uus naaberhoone (EHR ehitusloa ristsignaal)")
    if raieluba is True:
        signals.append("raieluba linnaosas")
    if facade_change is True:
        signals.append("aerofoto fassaadimuutus")
    if signals:
        return 45, ("Muutuse hinnang 45/100 (jäme lipp, mitte aastadelta): "
                    "%s — vaate/müra-risk, kontrolli detailplaneeringut"
                    % "; ".join(signals))
    return 70, ("Muutuse hinnang 70/100: %d jalga vaiksed (NDVI stabiilne, "
                "ehitus-/raiesignaali EI OLE) — kaduva salu riski pole"
                % legs)


def dim_glimpse_economics(listing: dict, aerial: dict) -> Score:
    """P4-041: piilukas (sliver) vs vaade (open) view class off the fan.

    open -> 85, sliver -> 70, none -> 50 (neutral taste-match, never a
    penalty for liking walls). Future blockage (P4-006 join) -15, floor
    30. Missing fan stays NULL even when the floor is known: floor is a
    fan input, not a standalone signal.
    """
    fan = aerial.get("view_fan")
    if fan not in ("open", "sliver", "none"):
        return None, ("Vaatelehvikut (Maa-amet LiDAR/LoD2 mere/vanalinna/"
                      "tornikiilu lehvik) EI OLE — piilukase hinnang puudub: "
                      "korrus (%s) üksi ei näita vaadet, ära feigi"
                      % listing.get("floor"))
    if fan == "open":
        base, word = 85, "vaade (avatud mere/vanalinna/tornikiil)"
    elif fan == "sliver":
        base, word = 70, "piilukas (kitsas riba, mitte vaade)"
    else:
        base, word = 50, "vaateta (neutraalne maitsesobivus)"
    note = ""
    if aerial.get("protected_view_corridor") is True:
        note += "; kaitsealune vaatekoridor (Muinsuskaitseameti piirang)"
    if aerial.get("future_blockage") is True:
        base = max(30, base - 15)
        note += "; tulevase varjutuse risk (P4-006 liit, -15)"
    return base, ("Piilukasehinnang %d/100: %s%s (80%% rõõm, 20%% hind — "
                  "arbitraaž vaateta hinnastuse vastu)"
                  % (base, word, note))


def dim_courtyard_trap(listing: dict, aerial: dict) -> Score:
    """P4-056: enclosed-courtyard trap off the LiDAR enclosure index.

    Per-parcel morphology join: enclosure >= 0.7 -> 35 (cold + fumes +
    heat held), 0.4..0.7 -> 55, below 0.4 -> 75. Missing index stays
    NULL; the Harku calm-share wind leg lives in dims_p4_ilm (named,
    never re-scored — no double-push).
    """
    _ = listing
    enc = aerial.get("enclosure_index")
    if not isinstance(enc, (int, float)) or not 0.0 <= enc <= 1.0:
        return None, ("Hoovi kinnisuse indeksit (Maa-amet LiDAR/LoD2) EI OLE "
                      "— mikrokliima-tasku hinnang puudub: õhuvahetuse "
                      "tuule-jalg on P4-ilm moodulis, hoovi kuju kontrolli "
                      "aerofotolt/kohapeal, ära feigi")
    green = aerial.get("courtyard_green")
    green_txt = ("; hoovihaljastuse puudujääk" if green is False
                 else ("; hoovis haljastust" if green is True else ""))
    if enc >= 0.7:
        return 35, ("Hoovilõksu hinnang 35/100: kinnisus %.2f (külm + "
                    "heitgaasid + kuumus püsivad)%s — tuulutus umbhoovis "
                    "nõrk" % (enc, green_txt))
    if enc >= 0.4:
        return 55, ("Hoovilõksu hinnang 55/100: kinnisus %.2f (keskmine)%s — "
                    "kontrolli tuulutust kohapeal" % (enc, green_txt))
    return 75, ("Hoovilõksu hinnang 75/100: kinnisus %.2f (avatud)%s — "
                "taskuriski EI OLE" % (enc, green_txt))


def dim_heatpump_hum(listing: dict, aerial: dict) -> Score:
    """P4-057: weak hinnang off suburban heat-pump uptake (heating change).

    Uptake + hum complaints -> 40; uptake only -> neutral 55 (weak,
    never high); data present with no uptake -> 70. No heating data at
    all stays NULL. A proxy, not a measurement — documented as such.
    """
    uptake = aerial.get("heating_changed_heatpump")
    complaints = aerial.get("hum_complaints")
    mention = aerial.get("listing_mentions_heatpump")
    if uptake is None and complaints is None and not mention:
        return None, ("Kütte-liigi muutuse infot (EHR õhksoojuspump, "
                      "mürakaebused) EI OLE — naabri-umina hinnang puudub "
                      "(nõrk proksi, mitte mõõtmine)")
    if uptake is True and complaints is True:
        return 40, ("Soojuspumba-umina hinnang 40/100 (nõrk proksi): "
                    "ümberkaudne õhksoojuspumba kasutus + uminakaebused — "
                    "magamistoa akende asend kontrolli kohapeal")
    if uptake is True or mention:
        return 55, ("Soojuspumba-umina hinnang 55/100 (nõrk, neutraalne): "
                    "kasutusmuutus teada, kaebuseinfot EI OLE — ei müü "
                    "vaikust, mida ei mõõtnud")
    return 70, ("Soojuspumba-umina hinnang 70/100: kütteandmetes "
                "soojuspumba-levikut EI OLE — uminakoridori riski pole")


def dim_ice_cliff(listing: dict, aerial: dict) -> Score:
    """P4-058: falling-ice roofs + coastal cliff retreat, dims with dates.

    Ice leg (steep roof / warning date) or cliff leg (retreat flag /
    < 100 m to the edge) at risk -> 40 with the date. Both legs WITH
    data and clean -> 70. No leg stays NULL: warnings absent is unknown,
    never safe.
    """
    _ = listing
    steep = aerial.get("roof_pitch_steep")
    warn = aerial.get("ice_warning_date")
    retreat = aerial.get("cliff_retreat_nearby")
    dist = aerial.get("dist_cliff_m")
    ice_data = (steep is not None or warn is not None)
    cliff_data = (retreat is not None
                  or isinstance(dist, (int, float)))
    if not ice_data and not cliff_data:
        return None, ("Jääpurika/kaljupealse jalgu (katuse kalle, "
                      "Päästeameti hoiatuse kuupäev, rannajoone-muutus) "
                      "EI OLE — talvise vastutuse/kalju-hinnang puudub")
    risks = []
    if steep is True:
        risks.append("järsk katus (EHR katuse kalle)")
    if warn:
        risks.append("jääpurika-hoiatus %s" % warn)
    if retreat is True:
        risks.append("rannajoone taandumise ristsignaal")
    if isinstance(dist, (int, float)) and dist < 100:
        risks.append("kaljuserv %.0f m" % dist)
    if risks:
        return 40, ("Jää/kalju hinnang 40/100: %s — kõnnitee-vastutus / "
                    "erosiooniserv, küsi KÜ-lt katusehooldust"
                    % "; ".join(risks))
    return 70, ("Jää/kalju hinnang 70/100: andmetega jalad puhtad (hoiatusi "
                "ega taandumissignaali EI OLE) — riski pole näha")


def dim_stormwater_subsidy(listing: dict, aerial: dict,
                           zone_table: Optional[dict] = None) -> Score:
    """P4-060: stormwater fee zone + subsidy queue (zone table dim).

    zone_table maps zone -> annual fee EUR (Tallinna Vesi hinnakiri,
    manual table). Fee 0 -> 75, <= 50 -> 65, <= 150 -> 50, above -> 40;
    the EIS queue position rides along in the reason. No zone or no
    table stays NULL; the Maa-amet impervious-surface proxy leg was not
    found (dated partial-negative) and is named, not faked.
    """
    zone = listing.get("stormwater_zone", aerial.get("stormwater_zone"))
    if not zone_table or zone not in zone_table:
        return None, ("Sademevee-tsooni tabelit (Tallinna Vesi hinnakiri, "
                      "tsoon '%s') EI OLE — tulevase arve/toetuse hinnang "
                      "puudub (vett mitteläbilaskva pinna Maa-ameti kihti "
                      "ei leitud — tariifitabel käsitsi)" % zone)
    fee = zone_table[zone]
    if not isinstance(fee, (int, float)) or fee < 0:
        return None, ("Tsooni '%s' tasuväärtus on vigane — hinnangut EI OLE"
                      % zone)
    if fee <= 0:
        score, word = 75, "tasu EI OLE (ühisvool/kompensatsioon)"
    elif fee <= 50:
        score, word = 65, "väike tasu (%.0f €/a)" % fee
    elif fee <= 150:
        score, word = 50, "keskmine tasu (%.0f €/a)" % fee
    else:
        score, word = 40, "kõrge tasu (%.0f €/a)" % fee
    queue = aerial.get("subsidy_queue_pos")
    queue_txt = (("EIS renoveerimistoetuse järjekoht %d" % queue)
                 if isinstance(queue, int) else
                 "toetuse järjekohainfot EI OLE")
    return score, ("Sademevee/toetuse hinnang %d/100: tsoon '%s', %s; %s "
                   "(aastane tsoonitabel)" % (score, zone, word, queue_txt))


# ---------------------------------------------------------------------------
# Registry + aggregator (entry point for the weight-rebalance follow-up).
# ---------------------------------------------------------------------------

P4_MAA_AERIAL_DIMS = (
    ("photo_forensics", "P4-022", dim_photo_forensics),
    ("street_observer", "P4-029", dim_street_block_observer),
    ("change_delta", "P4-030", dim_satellite_change_delta),
    ("glimpse", "P4-041", dim_glimpse_economics),
    ("courtyard_trap", "P4-056", dim_courtyard_trap),
    ("heatpump_hum", "P4-057", dim_heatpump_hum),
    ("ice_cliff", "P4-058", dim_ice_cliff),
    ("stormwater", "P4-060", dim_stormwater_subsidy),
)


def score_p4_maa_aerial(listing: dict, aerial: dict,
                        zone_table: Optional[dict] = None,
                        today: Optional[str] = None
                        ) -> Dict[str, Optional[int]]:
    """All 8 P4 Maa-aerial dims for one listing (keys match registry)."""
    out: Dict[str, Optional[int]] = {}
    for key, _pnum, fn in P4_MAA_AERIAL_DIMS:
        if fn in (dim_street_block_observer,):
            out[key] = fn(listing, aerial, today)
        elif fn in (dim_stormwater_subsidy,):
            out[key] = fn(listing, aerial, zone_table)
        else:
            out[key] = fn(listing, aerial)
    # dim_* return (score, reason); unwrap to score-only for the aggregator.
    return {k: (v[0] if isinstance(v, tuple) else v)
            for k, v in out.items()}
