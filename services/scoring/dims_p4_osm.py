"""P4 OpenStreetMap (Tallinn extracts) demo + coverage dims (issues #280, #354).

Demo (#280) params: P4-029 Street-imagery block observer.
Coverage (#354) params: P4-012, P4-013, P4-018, P4-026, P4-027, P4-031,
P4-032, P4-035, P4-039, P4-040, P4-042, P4-044, P4-045, P4-047, P4-048,
P4-049, P4-061, P4-062.

Openness (#280 AC1, verified 2026-09-13): OpenStreetMap data is open
under the ODbL ("You are free to copy, distribute, transmit and adapt
our data, as long as you credit OpenStreetMap and its contributors",
openstreetmap.org/copyright). Positive verdict — no dated negative.

Politeness + cache + TTL (#280 AC2): network lives ONLY in
livability.fetch_pois / livability.resolve (this module adds no network
calls): three Overpass mirrors with per-mirror timeout, a 1.2 s polite
gap after calls (Overpass usage policy), and a 30-day POI cache
(livability.OVERPASS_TTL_S). The fragment below reuses the same
{lat}/{lon} placeholders and TTL.

HONESTY (AGENTS.md section 7.2): twelve params are coarse OSM-derived
PROXIES (reasons say "hinnang", name what is missing, and never claim
measurement); seven stay NULL with an Estonian reason (NULL stays NULL,
"EI OLE" marker). Machine-checkable invariant kept by the tests:
"EI OLE" appears ONLY in documented no-map NULL reasons, never in
proxy reasons. Proxy scores are capped (never 100 on presence alone)
and absences read as coverage gaps, never as area verdicts.

Tag verification (2026-09-13, author-measured with osmium tags-filter
against ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, Harjumaa-wide
— Tallinn subsets are smaller; NOT at runtime):
* highway=crossing 12348; traffic_calming 4860 -> P4-012 viable.
* amenity=parking 78071 -> P4-013 viable (on-street vs lot split kept).
* lit=yes 145725; sidewalk key 16846; highway=footway 166990;
  surface=asphalt 303336 -> P4-029/P4-035/P4-040 viable.
* entrance 4973; wheelchair 22305 -> P4-049 viable.
* shop=bakery 70; tourism=gallery 81; tourism=museum 601;
  amenity=cafe 705; amenity=library 175; leisure=sauna 143;
  amenity=atm 224; shop=supermarket 1199; shop=convenience 1099;
  amenity=pharmacy 294 -> P4-027/P4-032/P4-042/P4-044/P4-045/P4-061
  viable but sparse (caps + coverage caveats in reasons).
* winter_service 0 county-wide -> P4-018 NULL (a band over zero
  objects would be a faked gradient).
* leisure=noise 0 GLOBALLY (taginfo API, data_until 2026-09-13) ->
  P4-047 NULL; the parameters4.md "honest proxy" tag does not exist.
* fixme 5781 -> carried in the fragment (demo ingestion family per
  #280) but consumed by NO scorer: a fixme count is a maintenance
  backlog, not a response rate (P4-026) nor civic virtue (P4-039);
  scoring it either way would invert its meaning.

Style mirrors services/scoring/livability.py and sibling batch
dims_group03b.py (#152): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason).

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Shared-kind reuse (no duplicate mappings): where a tag already flows
as a live kind owned by another batch, P4 scorers consume THAT kind
and kinds_from_tags returns None for the tag (asserted by tests):
* highway=crossing / traffic_signals -> "cornerfurn" (dims_group18restb)
* traffic_calming=* -> "calming" (dims_group18)
* amenity=parking on-street subtypes -> "street_parking" (dims_group18;
  the on-street set is mirrored locally as _ONSTREET_PARKING)
* lit=* ways/areas -> "lit_street" (dims_group18) / "lit_area"
  (dims_group18b)
* shop=supermarket|convenience -> "supermarket"|"convenience"
  (livability); amenity=pharmacy -> "pharmacy" (livability).
New kinds minted here (collision-checked 2026-09-13, no live owner):
walkway, sidewalk, paved, lot_parking, grocery, bakery, culture,
thirdplace, money, entrance, stepfree, fixme.
Hook-ordering note: P4 "walkway" rows must be evaluated before
dims_group18c's STREET_HIGHWAY catch-all (same priority-chain pattern
as dims_group18.kinds_from_tags), otherwise footway ways arrive as
"street" (which includes motorways and must NOT feed arrival dims).
Failure direction is fail-safe: P4-029/P4-040 fall back to the
coverage-gap reason, never to an inflated score.

Evening hours: the live parse_overpass keeps {kind, lat, lon} only, so
opening_hours reaches these scorers ONLY if the central hook carries it
as an optional "hours" passthrough on POI dicts. Scorers read
p.get("hours") opportunistically: known-late hours enrich the reason,
unknown hours are stated as unknown (never as closed). Fixture POIs in
the tests carry "hours" to pin both paths.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR because the coverage issue body states
  it "extends the demoed ingestion" — separate PRs would re-verify the
  same fragment twice.
* P4-018 NULL despite a plausible tag: zero winter_service objects
  county-wide means any band would score a constant fallback — a
  faked gradient, not a proxy.
* P4-031 NULL despite OSM shelter tags: mapped shelters are bus stops,
  not balcony frost-pocket evidence; borrowing them would fake it.
* P4-039/P4-026 NULL despite 5781 fixme objects: fixme density points
  the WRONG way for civic virtue and is not a response rate.
* P4-044/P4-045 score culture/third-place density as TASTE-match
  (caps 75/85), never as worth judgement or gentrification proof —
  the REL2021 grids stay the missing source in the reason.
* P4-040/P4-032 deliberately exclude PPA/Paasteamet-adjacent signals
  (arrival feel is not a safety claim; usage is not safety) — the
  reasons state the exclusion so the reviewer sees it.
* Absent-POI fallbacks sit at 35-55 (weak/neutral), never 0: unmapped
  is not absent. Presence bands cap at 72-85: mapped is not measured.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with P4_OSM_OVERPASS_FRAGMENT,
livability._POI_KIND with P4_OSM_POI_KIND (routing value-split keys
through kinds_from_tags, carrying opening_hours as "hours"), and
rebalancing livability.WEIGHTS must be one joint change across all
parameter batches — existing tests pin set(WEIGHTS) exactly, so
per-batch WEIGHTS edits would break every sibling. The fragment is
self-sufficient for every consumed kind (it duplicates the G18/G18b /
livability lines its scorers read; union dedupes shared elements and
the hook author trims overlaps).
"""

import math
import re
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------

def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _nearest_m(origin: Tuple[float, float], pois: List[dict], kinds: set) -> Optional[float]:
    best: Optional[float] = None
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            d = _haversine_m(origin, p["lat"], p["lon"])
            if best is None or d < best:
                best = d
    return best


def _count_within_m(origin: Tuple[float, float], pois: List[dict],
                    kinds: set, radius_m: float) -> int:
    n = 0
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            if _haversine_m(origin, p["lat"], p["lon"]) <= radius_m:
                n += 1
    return n


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


_HHMM_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")


def _open_late(hours: object) -> Optional[bool]:
    """Coarse evening-hours heuristic over an OSM opening_hours string.

    True if any closing time is 20:00 or later (or past midnight);
    False if hours are known and every window closes earlier;
    None when hours are missing/unparseable (unknown, never closed).
    """
    if not isinstance(hours, str):
        return None
    matches = _HHMM_RANGE.findall(hours)
    if "24/7" in hours or "24h" in hours:
        return True
    if not matches:
        return None
    for oh, _om, ch, _cm in matches:
        try:
            o, c = int(oh), int(ch)
        except ValueError:
            continue
        if c <= o:  # overnight window, e.g. 18:00-02:00
            return True
        if c >= 20:
            return True
    return False


def _any_late(origin: Tuple[float, float], pois: List[dict],
              kinds: set, radius_m: float) -> Optional[bool]:
    """True if any in-window POI is known open late; False if hours are
    known and none is; None when no in-window POI carries hours."""
    seen_hours = False
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            if _haversine_m(origin, p["lat"], p["lon"]) <= radius_m:
                late = _open_late(p.get("hours"))
                if late is True:
                    return True
                if late is False:
                    seen_hours = True
    return False if seen_hours else None


#: amenity=parking subtypes that read as on-street bays (mirrors
#: dims_group18.ONSTREET_PARKING; local copy per the no-import rule).
#: On-street bays stay G18's "street_parking" kind; everything else
#: mapped here becomes "lot_parking".
_ONSTREET_PARKING = frozenset({"street_side", "lane", "on_kerb", "layby"})


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# Self-sufficient for every consumed kind (shared lines intentionally
# duplicate G18/G18b/livability lines; the (...) union dedupes shared
# elements and the hook author trims overlaps on integration).
# Radii are judgment calls: arrival/sidewalk/entrance hyper-local
# (500 m, arrival scored at 200 m), parking 800 m, third places 1 km,
# grocery/money/shops 1.5 km (fringe last-shop watch needs the reach).
# Both node[...] and way[...] lines where the feature maps either way
# (nwr/ parity, PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
P4_OSM_OVERPASS_FRAGMENT = """
  node["highway"="crossing"](around:500,{lat},{lon});
  way["highway"~"footway|pedestrian"](around:500,{lat},{lon});
  way["sidewalk"~"both|left|right|yes"](around:500,{lat},{lon});
  way["surface"~"asphalt|paved|paving_stones|concrete"](around:500,{lat},{lon});
  node["traffic_calming"](around:500,{lat},{lon});
  way["traffic_calming"](around:500,{lat},{lon});
  node["amenity"="parking"](around:800,{lat},{lon});
  way["amenity"="parking"](around:800,{lat},{lon});
  node["lit"~"yes|24/7|automatic|limited"](around:500,{lat},{lon});
  way["lit"~"yes|24/7|automatic|limited"](around:500,{lat},{lon});
  node["amenity"~"cafe|bar|pub|restaurant|library"](around:1000,{lat},{lon});
  way["amenity"~"cafe|bar|pub|restaurant|library"](around:1000,{lat},{lon});
  node["amenity"~"atm|bank"](around:1500,{lat},{lon});
  way["amenity"~"atm|bank"](around:1500,{lat},{lon});
  node["shop"~"supermarket|convenience|greengrocer|general|bakery"](around:1500,{lat},{lon});
  way["shop"~"supermarket|convenience|greengrocer|general|bakery"](around:1500,{lat},{lon});
  node["tourism"~"gallery|museum|arts_centre"](around:1000,{lat},{lon});
  way["tourism"~"gallery|museum|arts_centre"](around:1000,{lat},{lon});
  node["craft"~"bakery|confectionery"](around:1000,{lat},{lon});
  node["leisure"="sauna"](around:1000,{lat},{lon});
  node["entrance"](around:500,{lat},{lon});
  node["wheelchair"~"yes|limited|designated"](around:500,{lat},{lon});
  node["fixme"](around:500,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND — P4-NEW
#: kinds only. Shared tags (crossing, traffic_calming, lit, supermarket,
#: convenience, pharmacy) intentionally have NO row here: their kinds are
#: owned by sibling batches (see module docstring) and kinds_from_tags
#: returns None for them. fixme and amenity=parking are wildcard/subtype
#: splits the static table cannot express, so the hook must route those
#: keys through kinds_from_tags.
P4_OSM_POI_KIND = [
    ("highway", {"footway": "walkway", "pedestrian": "walkway"}),
    ("footway", {"sidewalk": "walkway", "crossing": "walkway"}),
    ("sidewalk", {"both": "sidewalk", "left": "sidewalk",
                  "right": "sidewalk", "yes": "sidewalk"}),
    ("surface", {"asphalt": "paved", "paved": "paved",
                 "paving_stones": "paved", "concrete": "paved"}),
    ("amenity", {"cafe": "thirdplace", "bar": "thirdplace",
                 "pub": "thirdplace", "restaurant": "thirdplace",
                 "library": "thirdplace", "atm": "money", "bank": "money"}),
    ("shop", {"greengrocer": "grocery", "general": "grocery",
              "bakery": "bakery"}),
    ("craft", {"bakery": "bakery", "confectionery": "bakery"}),
    ("tourism", {"gallery": "culture", "museum": "culture",
                 "arts_centre": "culture"}),
    ("leisure", {"sauna": "thirdplace"}),
    ("entrance", {"main": "entrance", "yes": "entrance", "home": "entrance",
                  "shop": "entrance", "service": "entrance",
                  "secondary": "entrance", "staircase": "entrance"}),
    ("wheelchair", {"yes": "stepfree", "limited": "stepfree",
                    "designated": "stepfree"}),
]


def _first(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.split(";")[0].strip()


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First P4-NEW kind matching the OSM tags, else None. Pure.

    Shared tags return None BY DESIGN (their kinds are owned elsewhere:
    highway=crossing -> "cornerfurn" dims_group18restb,
    traffic_calming=* -> "calming" dims_group18, lit=* -> "lit_street"/
    "lit_area" dims_group18/dims_group18b, shop=supermarket|convenience
    -> livability, amenity=pharmacy -> livability, on-street
    amenity=parking -> "street_parking" dims_group18). The off-street
    remainder of amenity=parking becomes "lot_parking" here.
    """
    if not isinstance(tags, dict):
        return None
    if tags.get("amenity") == "parking":
        sub = _first(tags.get("parking"))
        if sub in _ONSTREET_PARKING:
            return None  # G18 street_parking owns on-street bays
        return "lot_parking"
    hw = _first(tags.get("highway"))
    if hw in ("footway", "pedestrian"):
        return "walkway"
    fw = _first(tags.get("footway"))
    if fw in ("sidewalk", "crossing"):
        return "walkway"
    sw = _first(tags.get("sidewalk"))
    if sw in ("both", "left", "right", "yes"):
        return "sidewalk"
    sf = _first(tags.get("surface"))
    if sf in ("asphalt", "paved", "paving_stones", "concrete"):
        return "paved"
    am = _first(tags.get("amenity"))
    if am in ("cafe", "bar", "pub", "restaurant", "library"):
        return "thirdplace"
    if am in ("atm", "bank"):
        return "money"
    sh = _first(tags.get("shop"))
    if sh in ("greengrocer", "general"):
        return "grocery"
    if sh == "bakery":
        return "bakery"
    cr = _first(tags.get("craft"))
    if cr in ("bakery", "confectionery"):
        return "bakery"
    to = _first(tags.get("tourism"))
    if to in ("gallery", "museum", "arts_centre"):
        return "culture"
    if _first(tags.get("leisure")) == "sauna":
        return "thirdplace"
    en = _first(tags.get("entrance"))
    if en in ("main", "yes", "home", "shop", "service", "secondary",
              "staircase"):
        return "entrance"
    wc = _first(tags.get("wheelchair"))
    if wc in ("yes", "limited", "designated"):
        return "stepfree"
    if isinstance(tags.get("fixme"), str) and tags["fixme"].strip():
        return "fixme"
    return None


# ---------------------------------------------------------------------------
# P4-029: street-imagery block observer (demo; mapped walkability proxy).
# ---------------------------------------------------------------------------

#: Block-observer search radius in metres (hyper-local tier).
BLOCK_RADIUS_M = 500.0

#: Kinds reading as eye-level walkability evidence (mapped, not measured).
BLOCK_KINDS = frozenset({"walkway", "sidewalk", "paved",
                         "lit_street", "lit_area"})


def dim_block_observer(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-029: nearest mapped footway/sidewalk/surface/lit evidence."""
    if not origin or pois is None:
        return None, "Tänavapildi info puudub"
    m = _nearest_m(origin, pois, BLOCK_KINDS)
    if m is None or m > BLOCK_RADIUS_M:
        return 50, ("Kaardistatud kõnniteed/katet/valgustit 500 m raadiuses "
                    "pole (katvus lünklik — fassaadi-hinnangut ei ole; "
                    "Mapillary/KartaView kaadreid snapshots pole, foto "
                    "kuupäevata)")
    s = _band(m, [(100, 85), (250, 78), (500, 68)])
    return s, ("Lähim kaardistatud kõnnitee/kate/valgusti %s "
               "(silmakõrguse-hinnang, mitte fassaadi-tõde; Mapillary "
               "kaader ja foto kuupäev puuduvad)" % _fmt_m(m))


# ---------------------------------------------------------------------------
# P4-012: accident blackspots + rescue drive-time (mapped furniture proxy).
# ---------------------------------------------------------------------------

#: Blackspot-furniture search radius in metres (hyper-local tier).
BLACKSPOT_RADIUS_M = 500.0

#: Shared kinds: mapped corner furniture + calming (owned by G18 batches).
BLACKSPOT_KINDS = frozenset({"cornerfurn", "calming"})


def dim_blackspots(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """P4-012: nearest mapped crossing / traffic-calming furniture."""
    if not origin or pois is None:
        return None, "Ohutusinfo puudub"
    m = _nearest_m(origin, pois, BLACKSPOT_KINDS)
    if m is None or m > BLACKSPOT_RADIUS_M:
        return 50, ("Kaardistatud ülekäigurit/rahustit 500 m raadiuses pole "
                    "(inventuur lünklik — ohutus-hinnangut ei ole; "
                    "Transpordiameti õnnetuspunkte snapshots pole)")
    s = _band(m, [(150, 80), (300, 72), (500, 62)])
    return s, ("Lähim märgistatud ülekäigur/rahusti %s (ohutus-hinnang, "
               "mitte õnnetusstatistika; Päästeameti sõiduaegu snapshots "
               "pole)" % _fmt_m(m))


# ---------------------------------------------------------------------------
# P4-013: parking regime + courtyard ratio (mapped parking proxy).
# ---------------------------------------------------------------------------

#: Parking search radius in metres (daily-walk tier).
PARKING_RADIUS_M = 800.0

#: On-street bays (G18) + off-street lots (this module).
PARKING_KINDS = frozenset({"street_parking", "lot_parking"})


def dim_parking(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """P4-013: nearest mapped parking bay or lot."""
    if not origin or pois is None:
        return None, "Parkimisinfo puudub"
    m = _nearest_m(origin, pois, PARKING_KINDS)
    if m is None or m > PARKING_RADIUS_M:
        return 50, ("Kaardistatud parklat 800 m raadiuses pole "
                    "(tsooni-hinnangut ei ole; tasulise parkimise "
                    "määrustikku ja katastri hoovisuhet snapshots pole)")
    s = _band(m, [(200, 80), (400, 72), (800, 62)])
    return s, ("Lähim kaardistatud parkla %s (asukoha-hinnang, mitte "
               "elanikuloa/hoovikoha garantii)" % _fmt_m(m))


# ---------------------------------------------------------------------------
# P4-018: snow/road maintenance class (no honest signal — always None).
# ---------------------------------------------------------------------------

def dim_winter_maintenance(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-018: NULL — winter_service is unmapped county-wide (do not fake)."""
    return None, ("Talihoolduse klassi hinnangut pole (EI OLE hinnangut): "
                  "winter_service märgistust Harjumaa 2026-09-11 väljavõttes "
                  "pole (0 objekti) — vajab Transpordiameti teeregistri ja "
                  "Tallinna talihoolduse tasemete liitumist, ära feigi")


# ---------------------------------------------------------------------------
# P4-026: municipal fix-it responsiveness (no honest signal — always None).
# ---------------------------------------------------------------------------

def dim_fixit(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """P4-026: NULL — a fixme count is not a response rate (do not fake)."""
    return None, ("KOV parandamiskiiruse registrit (abilliin/e-teenused) "
                  "snapshots pole (EI OLE hinnangut): OSM fixme-loend "
                  "(5781 Harjumaal 2026-09-11) ei ole reageerimiskiirus — "
                  "küsi heakorra statistikat, ära feigi")


# ---------------------------------------------------------------------------
# P4-027: grocery slots + ride-price probes (mapped grocery proxy).
# ---------------------------------------------------------------------------

#: Grocery search radius in metres (daily-walk tier).
GROCERY_RADIUS_M = 1000.0

#: Shared supermarket/convenience (livability) + greengrocer/general.
GROCERY_KINDS = frozenset({"supermarket", "convenience", "grocery"})


def dim_grocery(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """P4-027: nearest mapped grocery + known-late evening anchor."""
    if not origin or pois is None:
        return None, "Toidupoe info puudub"
    m = _nearest_m(origin, pois, GROCERY_KINDS)
    if m is None or m > GROCERY_RADIUS_M:
        return 40, ("Kaardistatud toidupoodi 1 km raadiuses pole "
                    "(poe-hinnang; Barbora/Selver tarneaknaid ja Wolt/Bolt "
                    "katvust snapshots pole)")
    s = _band(m, [(300, 85), (600, 76), (1000, 66)])
    late = _any_late(origin, pois, GROCERY_KINDS, GROCERY_RADIUS_M)
    if late is True:
        return s, ("Lähim toidupood %s; vähemalt üks õhtune (kuni ≥20) "
                   "ankur 1 km raadiuses teada (kättesaadavuse-hinnang, "
                   "mitte tarneakna garantii)" % _fmt_m(m))
    if late is False:
        return s, ("Lähim toidupood %s (kättesaadavuse-hinnang; teadaolevad "
                   "lahtiolekuajad sulgevad enne 20 — õhtune katvus "
                   "kontrolli, mitte tarneakna garantii)" % _fmt_m(m))
    return s, ("Lähim toidupood %s (kättesaadavuse-hinnang; lahtiolekuajad "
               "hetktõmmises puuduvad — õhtune katvus vajab opening_hours "
               "liitumist, mitte tarneakna garantii)" % _fmt_m(m))


# ---------------------------------------------------------------------------
# P4-031: backyard weather + DIY air (no honest signal — always None).
# ---------------------------------------------------------------------------

def dim_backyard_weather(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-031: NULL — bus-stop shelters are not balcony facts (do not fake)."""
    return None, ("Õue mikrokliima andureid (sensor.community) ega rõdu "
                  "varju/avatus-mõõtmisi snapshots pole (EI OLE hinnangut): "
                  "peatuste varjualused ei ole rõdu fakt — baas on Harku "
                  "jaam, ära feigi")


# ---------------------------------------------------------------------------
# P4-032: activity heat as usage proxy (mapped evening-density proxy).
# ---------------------------------------------------------------------------

#: Activity-count radius in metres (evening-street tier).
ACTIVITY_RADIUS_M = 400.0

#: Kinds reading as evening footfall anchors (usage, never safety).
ACTIVITY_KINDS = frozenset({"thirdplace", "grocery", "supermarket",
                            "convenience", "bakery", "culture"})


def dim_activity(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """P4-032: evening-use anchor density (usage-hinnang, NOT safety)."""
    if not origin or pois is None:
        return None, "Kasutusinfo puudub"
    n = _count_within_m(origin, pois, ACTIVITY_KINDS, ACTIVITY_RADIUS_M)
    if n == 0:
        return 40, ("Õhtuse kasutusega kohti 400 m raadiuses pole (hõre "
                    "kasutus-hinnang, mitte ohu-hinne — PPA/Päästeamet "
                    "teadlikult kasutamata)")
    s = _band(n, [(0, 40), (2, 60), (5, 75)])
    late = _any_late(origin, pois, ACTIVITY_KINDS, ACTIVITY_RADIUS_M)
    tail = ("; õhtune ankur (kuni ≥20) teada"
            if late is True else
            " (lahtiolekuajad hetktõmmises puuduvad — õhtune filter "
            "rakendub opening_hours liitumisel)"
            if late is None else "")
    return s, ("Õhtuse kasutusega kohti 400 m raadiuses: %d "
               "(kasutus-hinnang, mitte turvalisus — PPA/Päästeamet "
               "teadlikult kasutamata%s)" % (n, tail))


# ---------------------------------------------------------------------------
# P4-035: December darkness (mapped lit proxy).
# ---------------------------------------------------------------------------

#: Darkness-proxy search radius in metres (night-walk tier).
DARKNESS_RADIUS_M = 500.0

#: Shared lit kinds (owned by G18 batches).
DARKNESS_KINDS = frozenset({"lit_street", "lit_area"})


def dim_darkness(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """P4-035: nearest mapped lit street/area (December-darkness hinnang)."""
    if not origin or pois is None:
        return None, "Pimedusinfo puudub"
    m = _nearest_m(origin, pois, DARKNESS_KINDS)
    if m is None or m > DARKNESS_RADIUS_M:
        return 45, ("lit-märgistust 500 m raadiuses pole (katvus lünklik — "
                    "detsembri-hinnang; Tallinna tänavavalgustuse kaarti ja "
                    "VIIRS-i snapshots pole)")
    s = _band(m, [(100, 80), (250, 72), (500, 62)])
    return s, ("Lähim lit-märgistusega objekt %s (detsembri-pimeduse "
               "hinnang, mitte lampide loendus)" % _fmt_m(m))


# ---------------------------------------------------------------------------
# P4-039: civic capital (no honest signal — always None).
# ---------------------------------------------------------------------------

def dim_civic(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """P4-039: NULL — fixme density points the wrong way (do not fake)."""
    return None, ("Valimisjaoskonna osalust ega OSM muutmislugu snapshots "
                  "pole (EI OLE hinnangut): fixme-tihedus on hooldusvõlg, "
                  "mitte kodanikuaktiivsus — selle vooruseks skoorimine "
                  "pööriks tähenduse pea peale; maitse-eelistus selgub "
                  "ostjaprofiilist, ära feigi")


# ---------------------------------------------------------------------------
# P4-040: last-200 m arrival sequence (mapped approach proxy).
# ---------------------------------------------------------------------------

#: Arrival-sequence radius in metres (the param's own 200 m).
ARRIVAL_RADIUS_M = 200.0


def dim_arrival(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """P4-040: mapped footway/surface/lit evidence on the last 200 m."""
    if not origin or pois is None:
        return None, "Saabumisinfo puudub"
    m = _nearest_m(origin, pois, BLOCK_KINDS)
    if m is None or m > ARRIVAL_RADIUS_M:
        return 50, ("Kaardistatud kõnniteed/katet/valgustit 200 m raadiuses "
                    "pole (katvus lünklik — saabumis-hinnangut ei ole; "
                    "Mapillary saabumiskaader kuupäevaga puudub)")
    s = _band(m, [(50, 85), (100, 76), (200, 66)])
    return s, ("Lähim kaardistatud kõnnitee/kate/valgusti %s "
               "(saabumis-hinnang, tipu-lõpu raamistik; Päästeamet/PPA "
               "teadlikult kasutamata — saabumistunne ei ole turvaväide)"
               % _fmt_m(m))


# ---------------------------------------------------------------------------
# P4-042: smell/dawn-chorus map (mapped bakery-anchor proxy, coarse only).
# ---------------------------------------------------------------------------

#: Smell-anchor search radius in metres (coarse-cell tier, never doorway).
SMELL_RADIUS_M = 800.0


def dim_smell(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """P4-042: nearest mapped bakery/confectionery anchor (coarse hinnang)."""
    if not origin or pois is None:
        return None, "Lõhnainfo puudub"
    m = _nearest_m(origin, pois, {"bakery"})
    if m is None or m > SMELL_RADIUS_M:
        return 55, ("Kaardistatud pagari/kondiitri-ankrut 800 m raadiuses "
                    "pole (jäme lõhna-hinnang ühepoolne — suitsu/prügi-"
                    "kaebuste registrit snapshots pole)")
    s = _band(m, [(300, 72), (800, 64)])
    return s, ("Lähim magusa-ankur (pagari/kondiiter) %s (jäme lõhna-"
               "hinnang, mitte ukse-täpsus)" % _fmt_m(m))


# ---------------------------------------------------------------------------
# P4-044: herd of picky people (mapped culture taste-match, capped).
# ---------------------------------------------------------------------------

#: Taste-match search radius in metres (1 km grid tier).
HERD_RADIUS_M = 1000.0


def dim_herd(origin: Optional[Tuple[float, float]],
             pois: Optional[List[dict]]) -> Score:
    """P4-044: gallery/museum taste-match (taste, never worth judgement)."""
    if not origin or pois is None:
        return None, "Kultuuriinfo puudub"
    m = _nearest_m(origin, pois, {"culture"})
    if m is None or m > HERD_RADIUS_M:
        return 55, ("Kaardistatud galeriid/muuseumi 1 km raadiuses pole "
                    "(maitse-hinnang, mitte väärtushinnang; REL2021 ametite "
                    "ruudustikku snapshots pole)")
    s = _band(m, [(400, 75), (1000, 65)])
    return s, ("Lähim galerii/muuseum/kunstikeskus %s (maitse-hinnang, "
               "mitte väärtushinnang — REL2021 ametite ruudustikku "
               "snapshots pole; tihedus ei ole gentrifikatsiooni "
               "tõestus)" % _fmt_m(m))


# ---------------------------------------------------------------------------
# P4-045: third places + keeper effect (mapped evening-place proxy).
# ---------------------------------------------------------------------------

#: Third-place search radius in metres (evening-stroll tier).
THIRDPLACE_RADIUS_M = 800.0


def dim_thirdplace(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """P4-045: nearest mapped sauna/pub/library/cafe + evening anchor."""
    if not origin or pois is None:
        return None, "Kolmanda koha info puudub"
    m = _nearest_m(origin, pois, {"thirdplace"})
    if m is None or m > THIRDPLACE_RADIUS_M:
        return 45, ("Kaardistatud sauna/pub/raamatukogu 800 m raadiuses "
                    "pole (kuuluvus-hinnang; õhtused lahtiolekuajad "
                    "snapshots puuduvad)")
    s = _band(m, [(300, 85), (500, 76), (800, 66)])
    late = _any_late(origin, pois, {"thirdplace"}, THIRDPLACE_RADIUS_M)
    if late is True:
        return s, ("Lähim kolmas koht %s; õhtune (kuni ≥20) ankur teada "
                   "(kuuluvus-hinnang, mitte püsikliendi garantii)"
                   % _fmt_m(m))
    return s, ("Lähim kolmas koht %s (kuuluvus-hinnang; lahtiolekuajad "
               "hetktõmmises puuduvad — õhtune filter vajab opening_hours "
               "liitumist, mitte püsikliendi garantii)" % _fmt_m(m))


# ---------------------------------------------------------------------------
# P4-047: small horrors calendar (no honest signal — always None).
# ---------------------------------------------------------------------------

def dim_horrors(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """P4-047: NULL — the proxy tag does not exist; calendars need dates."""
    return None, ("Väikeste õuduste kalender eeldab mürakaebuste ja "
                  "talihoolduse veograafiku kuupäevi, mida hetktõmmises "
                  "pole (EI OLE hinnangut): leisure=noise märgistust "
                  "globaalselt ei eksisteeri (taginfo 0, 2026-09-13) — küsi "
                  "KÜ logi ja linna mürakalendrit, ära feigi")


# ---------------------------------------------------------------------------
# P4-048: small delights + allotment queues (no honest signal — always None).
# ---------------------------------------------------------------------------

def dim_delights(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """P4-048: NULL — queues and registers are not in the snapshot."""
    return None, ("Väikeste rõõmude tabel eeldab pingiregistrit, linnaaia "
                  "järjekordi ja EHR orientatsiooni, mida snapshots pole "
                  "(EI OLE hinnangut): hommikupäike ja järjekorrad selguvad "
                  "KOV tabelitest ja vaatluselt, ära feigi")


# ---------------------------------------------------------------------------
# P4-049: taxi/guest test (mapped entrance proxy, weak-good capped).
# ---------------------------------------------------------------------------

#: Entrance search radius in metres (doorstep tier).
TAXI_RADIUS_M = 300.0


def dim_taxi(origin: Optional[Tuple[float, float]],
             pois: Optional[List[dict]]) -> Score:
    """P4-049: mapped entrance nearby (findability weak-good sign)."""
    if not origin or pois is None:
        return None, "Leitavusinfo puudub"
    m = _nearest_m(origin, pois, {"entrance"})
    if m is None or m > TAXI_RADIUS_M:
        return 55, ("Kaardistatud sissepääsu 300 m raadiuses pole (katvus "
                    "lünklik — leitavuse-hinnangut ei ole; külalisparkimise "
                    "reegleid snapshots pole)")
    s = _band(m, [(100, 80), (300, 72)])
    extra = ""
    a = _nearest_m(origin, pois, {"stepfree"})
    if a is not None and a <= TAXI_RADIUS_M:
        extra = "; ratastoolimärgistus %s (kasutatavuse lisamärk)" % _fmt_m(a)
    return s, ("Sissepääs kaardistatud %s (leitavuse nõrk hea-märk — ei "
               "ole külalisparkimise garantii%s)" % (_fmt_m(m), extra))


# ---------------------------------------------------------------------------
# P4-061: last-shop/pharmacy/ATM + bus-cut tracker (mapped fringe proxy).
# ---------------------------------------------------------------------------

#: Last-shop search radius in metres (fringe-settlement tier).
LASTSHOP_RADIUS_M = 1500.0

#: Shared supermarket/convenience/pharmacy (livability) + grocery + money.
LASTSHOP_KINDS = frozenset({"grocery", "supermarket", "convenience",
                            "pharmacy", "money"})


def dim_lastshop(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """P4-061: nearest mapped shop/pharmacy/money (fringe vitality)."""
    if not origin or pois is None:
        return None, "Teenusteinfo puudub"
    m = _nearest_m(origin, pois, LASTSHOP_KINDS)
    if m is None or m > LASTSHOP_RADIUS_M:
        return 35, ("Viimase-poe hoiatus: kaardistatud poodi/apteeki/"
                    "sularaha 1,5 km raadiuses pole (ääreala elujõu-"
                    "hinnang; sulgemiskalendrit ja GTFS diffi snapshots "
                    "pole)")
    s = _band(m, [(500, 85), (1000, 76), (1500, 66)])
    return s, ("Lähim pood/apteek/sularaha %s (ääreala elujõu-hinnang, "
               "mitte likviidsusgarantii)" % _fmt_m(m))


# ---------------------------------------------------------------------------
# P4-062: rat complaints + ice-fall warnings (no honest signal — always None).
# ---------------------------------------------------------------------------

def dim_rats(origin: Optional[Tuple[float, float]],
             pois: Optional[List[dict]]) -> Score:
    """P4-062: NULL — bin mapping is not a complaint rate (do not fake)."""
    return None, ("Näriliste/jääpurika kaebuste heksitabelit "
                  "(Keskkonnaamet/Päästeamet) snapshots pole (EI OLE "
                  "hinnangut): prügikastide kaardistus ei ole kaebuste "
                  "määr — heksilipud vajavad KOV tabelit, ära feigi")


P4_OSM_DIMS = (
    ("block_observer", "P4-029", dim_block_observer),
    ("blackspots", "P4-012", dim_blackspots),
    ("parking", "P4-013", dim_parking),
    ("winter", "P4-018", dim_winter_maintenance),
    ("fixit", "P4-026", dim_fixit),
    ("grocery", "P4-027", dim_grocery),
    ("backyard_weather", "P4-031", dim_backyard_weather),
    ("activity", "P4-032", dim_activity),
    ("darkness", "P4-035", dim_darkness),
    ("civic", "P4-039", dim_civic),
    ("arrival", "P4-040", dim_arrival),
    ("smell", "P4-042", dim_smell),
    ("herd", "P4-044", dim_herd),
    ("thirdplace", "P4-045", dim_thirdplace),
    ("horrors", "P4-047", dim_horrors),
    ("delights", "P4-048", dim_delights),
    ("taxi", "P4-049", dim_taxi),
    ("lastshop", "P4-061", dim_lastshop),
    ("rats", "P4-062", dim_rats),
)


def score_p4_osm(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All nineteen P4 OSM dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_OSM_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_OSM_DIMS}
