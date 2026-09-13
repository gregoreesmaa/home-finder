"""P4 Tallinna Vesi demo + coverage dims (issues #263 and #343).

Demo (#263): Tallinna Vesi ingestion (P4-017) — polite, cached,
TTL-stated pulls of the tariff + zone-table slices plus an honest-shape
per-parcel zone join end-to-end in Tallinn. Coverage (#343): P4-008,
P4-046, P4-051, P4-060 wired to the same demoed ingestion (no new
plumbing — #343 states none is expected unless a param needs it; none
did, see judgment calls).

Params (this agent only — sibling batches own disjoint sets):
* P4-017 Drinking-water quality + sewer reality (demo, per-parcel
  zone-table join)
* P4-008 Heating tariff zone + water/sewer tariff (per-address tariff
  join — water/sewer leg only, kaugküte leg named missing)
* P4-046 Dread removal, well+city water slice (per-listing redundancy)
* P4-051 Zero-consumption stairwells, zero-flow aggregate slice
  (hex flag, never addresses)
* P4-060 Stormwater fee zones (zone table; subsidy-queue leg named
  missing)

HONESTY (AGENTS.md section 7.2): zone-table / tariff-table joins only;
NULL stays NULL with an Estonian reason. Per-parcel connection reality
is a MANUAL iseteenindus technical-conditions request (2 weeks), not an
open feed — so every dim returns None when its join slice is missing,
never a guess, never a calm 100 from absence. Scored reasons always
trace to a joined record; NULL reasons always say EI OLE and name the
missing input.

Openness verdict (2026-09-13, six polite requests total, custom UA,
short timeouts, no scraping, no auth attempts — bodies to /tmp only):
* https://tallinnavesi.ee/ -> HTTP 301 to www (nginx).
* https://www.tallinnavesi.ee/ -> HTTP 200 (nginx, text/html).
* Hinnakiri page -> HTTP 308 to canonical path, then HTTP 200
  (554 467 B JS-app page): water/sewer tariff PUBLISHED as page
  content — "Kehtiv alates 01.07.2026", Tallinn ja Saue linn:
  vesi 1,48 EUR/m3 KM-ga, kanal RG1 1,39 / RG2 2,78 EUR/m3
  (RG1 combined 2,87; RG2 combined 4,26), approved by
  Konkurentsiamet decision 26.05.2026 nr 9-3/2026-014. Tariff leg
  is OPEN (page table, transcribed into the snapshot layout below).
* Per-parcel connection reality: NO open feed — ÜVK/liitumise pages
  are content pages; reality comes from a manual iseteenindus
  technical-conditions request (same finding as #248/#332, which
  probed the liitumine page HTTP 200). Zone-table honest shape;
  missing stays NULL with the check named.
* Zero-flow aggregates per hex and stormwater-fee zone tables: NO
  published feed found (dated negative keeps the verdict) — the
  dims score ONLY joined snapshot slices and stay NULL otherwise.
See docs/p4_tvesi.md. Personal data is never fetched or stored.

Style mirrors services/scoring/dims_p4_taitur.py (#255/#336): pure
(joined-slice, listing) -> (Optional[int 0..100], Estonian reason),
absolute bands, hermetic fixture tests. Network lives only in
fetch_tvesi_snapshot (single polite GET, file cache, TTL); tests
never call it.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and group20a #212).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR because #343 defines coverage as
  extending the demoed ingestion ("no new plumbing expected") —
  P4-008/P4-046/P4-051/P4-060 each name Tallinna Vesi in their
  parameters4.md source lists, i.e. the feed P4-017 demos.
  Splitting would ship an ingestion with one consumer, then
  re-touch every signature (EHR #249/#333, taitur #255/#336
  precedent).
* P4-017 vs dims_p4_maa_subsurface.dim_water_sewer (#332): same
  buyer question, COMPLEMENTARY legs, not a duplicate. The
  subsurface dim reads geology-side ÜVK facts (kaitseala/puurkaev
  constraints from cached WFS polygons); this dim reads the
  utility's own zone table + tariff-validity leg. Bands match
  deliberately (same connection reality); the JOINED SOURCE named
  in each reason differs (tsoonitabel vs WFS-kiht). The central
  hook joins one source per parcel later — one joint change.
* Tariff bands calibrated 2026-09-13 against the live hinnakiri
  (RG1 combined 2,87 EUR/m3 KM-ga = today's Tallinn residential
  level): combined RG1 <= 3,50 -> 75 (Tallinna tase); <= 5,00 ->
  55 (RG2-tase); above -> 35. RG2 combined rides along as context,
  never as the residential score. Recalibrate on the next
  Konkurentsiamet decision (reopening checklist in docs).
* P4-008 scores the water/sewer leg ONLY and says the kaugküte
  leg (Utilitas/Adven + Konkurentsiamet piirhinnad) is not joined:
  the January-bill question is bigger than water, and a water-only
  75 must never read as a whole-bill calm.
* P4-046 scores the well+city-water redundancy slice ONLY; the
  fireplace, 2nd-exit, and drainage legs live in EHR/flood
  modules and are named missing, never zeroed.
* P4-051 thin cells (< 5 connections) stay NULL: a 1-of-2
  zero-flow "share" is noise and near-identifying — hex only,
  never addresses, per parameters4.md.
* 30 d TTL (2592000 s): tariff-change driven per parameters4.md
  P4-008 (re-pull on Konkurentsiamet decisions); the monthly poll
  converges over runs per AGENTS.md section 7.4.

Integration (deliberately NOT done here): feeding these dims with
the parcel's joined zone/tariff slices inside livability scoring
and rebalancing livability.WEIGHTS must be one joint change across
all parameter batches — existing tests pin set(WEIGHTS) exactly, so
per-batch WEIGHTS edits would break every sibling.
"""

import csv
import io
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated Tallinna Vesi snapshot pulls.
# ---------------------------------------------------------------------------

#: Tariff-change driven poll per parameters4.md P4-008 (re-pull on
#: Konkurentsiamet decisions; monthly poll converges over runs).
TVESI_TTL_S = 30 * 86400

#: Where the public slices live (verified 2026-09-13 — see module
#: docstring; hinnakiri page table, content pages otherwise, no
#: anonymous per-parcel connection feed).
TVESI_BASE_URL = "https://www.tallinnavesi.ee/"
TVESI_TARIFF_URL = ("https://www.tallinnavesi.ee/eraasiakas/veeteenused/"
                    "hinnakiri")

USER_AGENT = ("home-finder tvesi ingest (polite monthly pull, single GET, "
              "file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str, name: str) -> str:
    """Cache file for one named tvesi snapshot (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)
    return os.path.join(cache_dir, "tvesi-%s.csv" % safe)


def cache_is_fresh(path: str, ttl_s: int = TVESI_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_s seconds."""
    try:
        age_s = ((now if now is not None else time.time())
                 - os.path.getmtime(path))
    except OSError:
        return False
    return age_s < ttl_s


def fetch_tvesi_snapshot(name: str, url: str,
                         cache_dir: str = "/tmp/hf-cache",
                         ttl_s: int = TVESI_TTL_S) -> str:
    """Fetch one Tallinna Vesi snapshot politely (single GET, cached, TTL).

    Returns cached text when fresh; otherwise one GET with a polite
    User-Agent and a 30 s timeout. Transport errors RAISE (never cached
    as data, AGENTS.md section 7.2); HTTP errors raise too — an error
    body is never written to the cache. Treat HTTP 429 as a stop
    signal: it propagates, the stale cache is left untouched.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, name)
    if cache_is_fresh(path, ttl_s):
        with io.open(path, encoding="utf-8-sig") as f:
            return f.read()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = resp.read()
    text = body.decode("utf-8-sig")
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------------------
# Parsing: tvesi snapshot layouts (semicolon-separated, BOM-tolerant).
# Column names follow the documented snapshots; unknown columns are
# ignored, empty cells and absent columns read as None (never guessed).
# Tariff decimals accept the Estonian comma form ("1,48").
# ---------------------------------------------------------------------------

#: Canonical tariff keys produced by parse_tariffs (EUR/m3 KM-ga, the
#: page's headline unit; kehtib_alates/otsus trace the Konkurentsiamet
#: decision so a stale table is detectable).
TARIFF_FIELDS = (
    "piirkond", "vesi_eur_m3", "kanal_rg1_eur_m3", "kanal_rg2_eur_m3",
    "kehtib_alates", "otsus",
)

#: Canonical zone-table keys produced by parse_zones. vesi/kanal use
#: the closed token sets below; liitumiskohustus is the 5-figure-bill
#: flag (Nomme/Pirita/Merivalja liitumispiirkonnad).
ZONE_FIELDS = (
    "zone", "vesi", "kanal", "liitumiskohustus",
)

_VESI_TOKENS = ("central", "puurkaev", "salvkaev")
_KANAL_TOKENS = ("central", "omapuhasti")

#: Canonical zero-flow aggregate keys (hex/KOV only, never addresses).
ZEROFLOW_FIELDS = ("hex_id", "connections", "zero_flow")

#: Canonical stormwater-fee zone keys.
STORMWATER_FIELDS = ("zone", "sademeveetasu")


def _clean(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _norm(value: Optional[object]) -> str:
    return "" if value is None else str(value).strip().lower()


def _eur(value: Optional[object]) -> Optional[float]:
    """Estonian-format EUR/m3 (comma or point decimals) or None."""
    s = _clean(value)
    if s is None:
        return None
    try:
        v = float(s.replace(",", "."))
    except ValueError:
        return None
    return v if v >= 0 else None


def _bool_ee(value: Optional[object]) -> Optional[bool]:
    """Estonian boolean tokens (jah/ei, true/false, 1/0) or None."""
    s = _norm(value)
    if s in ("jah", "true", "1", "ja"):
        return True
    if s in ("ei", "false", "0"):
        return False
    return None


def _int(value: Optional[object]) -> Optional[int]:
    s = _clean(value)
    if s is None:
        return None
    try:
        v = int(s)
    except ValueError:
        return None
    return v if v >= 0 else None


def parse_tariffs(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse the transcribed hinnakiri table into tariff records.

    Rows without a piirkond are skipped (no join key). Rate cells
    that do not parse stay None (never guessed) — the P4-008 dim
    refuses to score a slice with a missing leg.
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        key = _clean(row.get("piirkond"))
        if not key:
            continue
        rec = {"piirkond": key}  # type: Dict[str, Optional[object]]
        for field in ("vesi_eur_m3", "kanal_rg1_eur_m3",
                      "kanal_rg2_eur_m3"):
            rec[field] = _eur(row.get(field))
        for field in ("kehtib_alates", "otsus"):
            rec[field] = _clean(row.get(field))
        records.append(rec)
    return records


def parse_zones(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse the ÜVK zone table into per-zone connection records.

    Unknown vesi/kanal tokens read as None (never guessed); unknown
    liitumiskohustus tokens read as None. Rows without a zone key
    are skipped (no join key — keeping them would fake coverage).
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        key = _clean(row.get("zone"))
        if not key:
            continue
        rec = {"zone": key}  # type: Dict[str, Optional[object]]
        vesi = _norm(row.get("vesi"))
        rec["vesi"] = vesi if vesi in _VESI_TOKENS else None
        kanal = _norm(row.get("kanal"))
        rec["kanal"] = kanal if kanal in _KANAL_TOKENS else None
        rec["liitumiskohustus"] = _bool_ee(row.get("liitumiskohustus"))
        records.append(rec)
    return records


def parse_zeroflow(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse aggregated zero-flow connections per hex (never addresses).

    Rows without a hex_id are skipped. Unparseable counts stay None —
    the P4-051 dim refuses thin/unknown cells instead of scoring them.
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        key = _clean(row.get("hex_id"))
        if not key:
            continue
        rec = {"hex_id": key}  # type: Dict[str, Optional[object]]
        rec["connections"] = _int(row.get("connections"))
        rec["zero_flow"] = _int(row.get("zero_flow"))
        records.append(rec)
    return records


def parse_stormwater(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse the stormwater-fee zone table (fee applies or not).

    Rows without a zone key are skipped; unparseable flags stay None.
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        key = _clean(row.get("zone"))
        if not key:
            continue
        rec = {"zone": key}  # type: Dict[str, Optional[object]]
        rec["sademeveetasu"] = _bool_ee(row.get("sademeveetasu"))
        records.append(rec)
    return records


def index_zones(
        records: List[Dict[str, Optional[object]]],
        key: str = "zone") -> Dict[str, Dict[str, Optional[object]]]:
    """Join index over a zone/keyed snapshot (last row wins on dupes)."""
    index = {}  # type: Dict[str, Dict[str, Optional[object]]]
    for rec in records:
        k = rec.get(key)
        if k:
            index[str(k)] = rec
    return index


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _parcel(parcel: Optional[dict]) -> dict:
    return parcel if isinstance(parcel, dict) else {}


def _missing_uvk(check: str = "Tallinna Vee iseteenindusest tehnilised "
                "tingimused või EHR-ist veevarustuse/kanalisatsiooni liik"
                ) -> Score:
    return None, ("Vee- ja kanalisatsiooniühenduse andmeid krundi kohta "
                  "EI OLE (hinnang puudub): ÜVK-liidestus puudub — "
                  "kontrolli %s, ära feigi" % check)


# ---------------------------------------------------------------------------
# P4-017 (demo): drinking-water quality + sewer reality from the
# Tallinna Vesi zone table. Per-parcel zone join.
#
# parcel keys: zone (str join key into zones), kvaliteet
#   ('hea'/'halb'/None — Terviseameti seire jalg).
# zones: zone -> {vesi, kanal, liitumiskohustus} from parse_zones.
# ---------------------------------------------------------------------------

def dim_water_sewer_zone(parcel: Optional[dict],
                         zones: Optional[dict]) -> Score:
    """P4-017: 5-figure-connection reading from the tvesi zone join.

    Central/central is calm; wells and on-site treatment pull the score
    down; a connection duty on an unconnected parcel caps it (the bill
    is coming). One missing leg stays NULL — half an ÜVK truth misleads.
    """
    parcel = _parcel(parcel)
    zone = parcel.get("zone")
    if not zone or not isinstance(zone, str):
        return _missing_uvk()
    if not isinstance(zones, dict) or zone not in zones:
        return None, ("Krundi tsooni '%s' ÜVK-tsoonitabelis EI OLE "
                      "(hinnang puudub): Tallinna Vesi tsooniliidestus "
                      "puudub — kontrolli iseteenindusest tehnilised "
                      "tingimused, ära feigi" % zone)
    rec = zones[zone] or {}
    vesi, kanal = rec.get("vesi"), rec.get("kanal")
    if vesi is None or kanal is None:
        missing = "vesi" if vesi is None else "kanal"
        return None, ("Tsooni '%s' ÜVK-tõde on poolik (%s-jalga EI OLE, "
                      "hinnang puudub): üks toru ei määra ühenduse hinda "
                      "— täienda tsooniliidestust, ära feigi"
                      % (zone, missing))
    if parcel.get("kvaliteet") not in ("hea", "halb", None):
        return None, ("Veekvaliteedi lipp on tundmatu väärtusega — "
                      "hinnangut EI OLE, ära feigi")
    duty = rec.get("liitumiskohustus")
    if duty is not None and not isinstance(duty, bool):
        return None, ("ÜVK-lipp 'liitumiskohustus' on tundmatu väärtusega "
                      "— hinnangut EI OLE, ära feigi")
    if vesi == "central" and kanal == "central":
        score, word = 85, "tsentraalne vesi + kanal (ühenduskulu puudub)"
    elif vesi == "central":
        score, word = 60, "tsentraalne vesi, omapuhasti (hoolduskulu)"
    elif kanal == "central":
        score, word = 55, "puurkaev/salvkaev + tsentraalne kanal (oma vee risk)"
    else:
        score, word = 45, "puurkaev/salvkaev + omapuhasti (oma vee risk)"
    caps = []
    if duty is True and not (vesi == "central" and kanal == "central"):
        score = min(score, 40)
        caps.append("liitumiskohustus (5-kohaline arve tulemas)")
    if parcel.get("kvaliteet") == "halb":
        score = min(score, 35)
        caps.append("seire: kvaliteet halb (Terviseamet)")
    note = ""
    if vesi in ("puurkaev", "salvkaev") and parcel.get("kvaliteet") is None:
        note = "; erakaevu kvaliteedi kohta ametlikke andmeid EI OLE"
    if caps:
        note = "; " + ", ".join(caps) + note
    return score, ("Vee-kanalisatsiooni hinnang %d/100 (%s, "
                   "Tallinna Vesi tsoonitabel%s)"
                   % (score, word, note))


# ---------------------------------------------------------------------------
# P4-008 (coverage): water/sewer tariff leg of the January-bill question.
# Per-address tariff-table join. The kaugkütte leg (Utilitas/Adven +
# Konkurentsiamet piirhinnad) is NOT joined and always named.
#
# slice keys: piirkond (str join key into tariffs).
# tariffs: piirkond -> {vesi_eur_m3, kanal_rg1_eur_m3, kanal_rg2_eur_m3,
#   kehtib_alates, otsus} from parse_tariffs (EUR/m3 KM-ga).
# ---------------------------------------------------------------------------

#: Residential calm band: today's Tallinn RG1 combined level is
#: 2,87 EUR/m3 KM-ga (live hinnakiri 2026-09-13); RG2 combined 4,26.
TARIFF_CALM_EUR_M3 = 3.50
TARIFF_MID_EUR_M3 = 5.00


def dim_water_tariff(slice: Optional[dict],  # noqa: A002
                     tariffs: Optional[dict]) -> Score:
    """P4-008: water/sewer tariff leg (75/55/35/NULL).

    Bands run on the RG1 combined rate (vesi + kanal RG1, EUR/m3
    KM-ga) — the residential reality. Every reason names the
    unjoined kaugkütte leg so a water-only calm never reads as a
    whole-bill calm.
    """
    joined = slice if isinstance(slice, dict) else {}
    area = joined.get("piirkond")
    if not area or not isinstance(area, str):
        return None, ("Vee tariifi piirkonnaliidestus puudub — "
                      "Tallinna Vesi hinnakirja tabelit EI OLE liidetud "
                      "(hinnang puudub): kontrolli hinnakirjast, ära feigi")
    if not isinstance(tariffs, dict) or area not in tariffs:
        return None, ("Piirkonda '%s' hinnakirja tabelis EI OLE (hinnang "
                      "puudub): tariifiliidestus puudub — kontrolli "
                      "Tallinna Vesi hinnakirjast, ära feigi" % area)
    rec = tariffs[area] or {}
    vesi, rg1 = rec.get("vesi_eur_m3"), rec.get("kanal_rg1_eur_m3")
    if vesi is None or rg1 is None:
        return None, ("Piirkonna '%s' tariifitõde on poolik (vesi- või "
                      "kanali-jalga EI OLE, hinnang puudub): täienda "
                      "hinnakirja-liidestust, ära feigi" % area)
    combined = vesi + rg1
    rg2 = rec.get("kanal_rg2_eur_m3")
    rg2_note = (", RG2-kombineeritud %.2f" % (vesi + rg2)
                if isinstance(rg2, (int, float)) else "")
    heat_note = ("; kaugkütte-jalga (Utilitas/Adven + piirhinnad) EI OLE "
                 "liidetud — jaanuarikuu arve tervikuna hinnang puudub")
    if combined <= TARIFF_CALM_EUR_M3:
        return 75, ("Vee+kanali RG1-kombineeritud %.2f EUR/m3 KM-ga%s "
                    "(Tallinna tase, registriandmed, mitte hinnang)%s"
                    % (combined, rg2_note, heat_note))
    if combined <= TARIFF_MID_EUR_M3:
        return 55, ("Vee+kanali RG1-kombineeritud %.2f EUR/m3 KM-ga%s "
                    "(RG2-tase, keskmine veekulu, mitte hinnang)%s"
                    % (combined, rg2_note, heat_note))
    return 35, ("Vee+kanali RG1-kombineeritud %.2f EUR/m3 KM-ga%s "
                "(kõrge veekulu, registriandmed, mitte hinnang)%s"
                % (combined, rg2_note, heat_note))


# ---------------------------------------------------------------------------
# P4-046 (coverage): dread-removal WATER slice — well+city redundancy.
# Per-listing redundancy dim. Fireplace, 2nd exit, and drainage legs
# live in EHR/flood modules and are always named missing.
#
# parcel keys: city_water (bool), well (bool).
# ---------------------------------------------------------------------------

def dim_water_redundancy(parcel: Optional[dict]) -> Score:
    """P4-046: mis hätta ei jäta — vee-varu jalg."""
    parcel = _parcel(parcel)
    city, well = parcel.get("city_water"), parcel.get("well")
    if city is None or well is None:
        return None, ("Vee-varu (linnavesi + kaev) andmeid EI OLE "
                      "(hinnang puudub): EHR-i kütte/vee-liiki või "
                      "Tallinna Vesi ÜVK-liidestust pole — kamina, "
                      "varuväljapääsu ja kuivenduse jalgu EI OLE "
                      "samuti liidetud, ära feigi")
    for key, val in (("city_water", city), ("well", well)):
        if not isinstance(val, bool):
            return None, ("Vee-lipp '%s' on tundmatu väärtusega — "
                          "hinnangut EI OLE, ära feigi" % key)
    rest = ("; kamina-, varuväljapääsu- ja kuivenduse-jalgu EI OLE "
            "liidetud (EHR/flood-moodulid)")
    if city and well:
        return 80, ("Linnavesi + kaev (registriandmed, mitte hinnang) — "
                    "vee-varu olemas, rike hätta ei jäta%s" % rest)
    if city:
        return 60, ("Ainult linnavesi, kaevu pole (registriandmed, mitte "
                    "hinnang) — üks toru, katkestus jätab hätta%s" % rest)
    if well:
        return 40, ("Ainult kaev, linnavett pole (registriandmed, mitte "
                    "hinnang) — oma vee risk, kuiv kaev jätab hätta%s"
                    % rest)
    return 25, ("Ei linnavett ega kaevu (registriandmed, mitte hinnang) — "
                "vesi jätab kindlalt hätta%s" % rest)


# ---------------------------------------------------------------------------
# P4-051 (coverage): zero-consumption stairwells from aggregated
# zero-flow connections per hex. Hex governance-risk flag — NEVER
# addresses (privacy-safe per parameters4.md).
#
# hex_slice keys: hex_id (str), connections (int), zero_flow (int).
# ---------------------------------------------------------------------------

#: Thin cells stay NULL (noise + near-identifying).
ZEROFLOW_MIN_CONNECTIONS = 5


def dim_zero_flow_hex(hex_slice: Optional[dict]) -> Score:
    """P4-051: dead-stairwell reading from the hex zero-flow aggregate."""
    if hex_slice is None or not isinstance(hex_slice, dict):
        return None, ("Null-vooluga liitumiste koondit heksi kohta EI OLE "
                      "(hinnang puudub): Tallinna Vesi koondi-liidestus "
                      "puudub — surnud trepikoja hinnangut ei anta, "
                      "ära feigi")
    connections = hex_slice.get("connections")
    zero_flow = hex_slice.get("zero_flow")
    hex_id = hex_slice.get("hex_id", "?")
    if not isinstance(connections, int) or not isinstance(zero_flow, int) \
            or connections <= 0 or zero_flow < 0 \
            or zero_flow > connections:
        return None, ("Heksi '%s' koond on poolik/tundmatu (ühenduste või "
                      "null-voolu arvu EI OLE, hinnang puudub): täienda "
                      "koondi-liidestust, ära feigi" % hex_id)
    if connections < ZEROFLOW_MIN_CONNECTIONS:
        return None, ("Heksi '%s' koond on liiga õhuke (%d ühendust, "
                      "hinnang puudub): väikese valimi osa on müra ja "
                      "tuvastatav — ära feigi" % (hex_id, connections))
    share = zero_flow / connections
    eli_note = ("; Elektrilevi null-tarbimise ristkontrolli-jalga EI OLE "
                "liidetud")
    if share >= 0.30:
        return 25, ("Heks '%s': null-vooluga %d/%d (osa %.0f%%, koond, "
                    "mitte hinnang) — surnud trepikoja risk, "
                    "remondifond kogumata%s"
                    % (hex_id, zero_flow, connections, share * 100,
                       eli_note))
    if share >= 0.15:
        return 45, ("Heks '%s': null-vooluga %d/%d (osa %.0f%%, koond, "
                    "mitte hinnang) — tühjenemise märk, KÜ aruannet "
                    "kontrolli%s"
                    % (hex_id, zero_flow, connections, share * 100,
                       eli_note))
    return 70, ("Heks '%s': null-vooluga %d/%d (osa %.0f%%, nõrk "
                "hea-signaal, ülempiir 70, mitte hinnang) — trepikoda "
                "elab%s" % (hex_id, zero_flow, connections, share * 100,
                            eli_note))


# ---------------------------------------------------------------------------
# P4-060 (coverage): stormwater-fee leg of the future-bill question.
# Zone table. The EIS renovation-subsidy queue leg is NOT joined and
# always named.
#
# parcel keys: zone (str join key into storm_zones).
# storm_zones: zone -> {sademeveetasu: bool} from parse_stormwater.
# ---------------------------------------------------------------------------

def dim_stormwater_fee(parcel: Optional[dict],
                       storm_zones: Optional[dict]) -> Score:
    """P4-060: sademeveetasu-tsoon (45/70/NULL)."""
    parcel = _parcel(parcel)
    zone = parcel.get("zone")
    if not zone or not isinstance(zone, str):
        return None, ("Sademeveetasu tsooni-liidestus puudub — Tallinna "
                      "Vesi sademevee-tabelit EI OLE liidetud (hinnang "
                      "puudub): kontrolli ÜVK-kaardilt, ära feigi")
    if not isinstance(storm_zones, dict) or zone not in storm_zones:
        return None, ("Tsooni '%s' sademevee-tabelis EI OLE (hinnang "
                      "puudub): tsooniliidestus puudub — kontrolli "
                      "ÜVK-kaardilt, ära feigi" % zone)
    fee = (storm_zones[zone] or {}).get("sademeveetasu")
    if not isinstance(fee, bool):
        return None, ("Tsooni '%s' sademeveetasu-lipp on tundmatu "
                      "väärtusega — hinnangut EI OLE, ära feigi" % zone)
    queue_note = ("; EIS renoveerimistoetuste järjekorra-jalga EI OLE "
                  "liidetud (P4-010 join)")
    if fee:
        return 45, ("Tsoon '%s': sademeveetasu kehtib (registriandmed, "
                    "mitte hinnang) — tulevane arve, vett mitteläbilaskev "
                    "pind loeb%s" % (zone, queue_note))
    return 70, ("Tsoon '%s': sademeveetasu ei kehti (nõrk hea-signaal, "
                "ülempiir 70, mitte hinnang) — tasu-jalg vaikne%s"
                % (zone, queue_note))


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_TVESI_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_TVESI_DIMS = (
    ("water_sewer_zone", "P4-017", dim_water_sewer_zone),
    ("water_tariff", "P4-008", dim_water_tariff),
    ("water_redundancy", "P4-046", dim_water_redundancy),
    ("zero_flow_hex", "P4-051", dim_zero_flow_hex),
    ("stormwater_fee", "P4-060", dim_stormwater_fee),
)


def score_p4_tvesi(parcel: Optional[dict] = None,
                   zones: Optional[dict] = None,
                   tariffs: Optional[dict] = None,
                   hex_slice: Optional[dict] = None,
                   storm_zones: Optional[dict] = None
                   ) -> Dict[str, Optional[int]]:
    """All five P4 tvesi dims for one listing (entry point for the future
    enrich/score hook; keys match P4_TVESI_DIMS). Missing slices stay
    None by design — zone/tariff-table joins, never a faked score."""
    return {
        "water_sewer_zone": dim_water_sewer_zone(parcel, zones)[0],
        "water_tariff": dim_water_tariff(
            {"piirkond": (_parcel(parcel).get("piirkond"))}, tariffs)[0],
        "water_redundancy": dim_water_redundancy(parcel)[0],
        "zero_flow_hex": dim_zero_flow_hex(hex_slice)[0],
        "stormwater_fee": dim_stormwater_fee(parcel, storm_zones)[0],
    }
