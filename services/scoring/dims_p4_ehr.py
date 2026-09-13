"""P4 EHR / E-ehitus demo + coverage dims (issues #249 and #333).

Demo (#249): EHR / E-ehitus ingestion (P4-005) — polite, cached,
TTL-stated pulls of the EHR open-data CSV reports plus honest-shape
per-ehr_code join dims. Coverage (#333): the remaining 20 params that
consume the demoed ingestion, each wired to its EHR-record slice.

Params (this agent only — overturn #234 owns the parameters3 G2 EHR
bulk in dims_group02*.py, which this module does NOT touch):
* P4-005 ehitusluba/kasutusluba existence (demo, per-listing binary)
* P4-010 renovation-grant status + queue (per-building dim)
* P4-013 parking regime, EHR slice: parking-space count (per-listing)
* P4-016 engineering geology (always NULL — EGT/Maa-amet, not EHR)
* P4-021 developer/broker track record, EHR slice: builder history
* P4-023 airport + military noise zones (always NULL — zone join)
* P4-030 satellite change delta (NULL + EHR open-permit echo)
* P4-031 backyard weather + DIY air (NULL + EHR heating-type echo)
* P4-034 summer overheating risk (per-listing physics sim, capped)
* P4-035 December darkness (per-listing light model, capped)
* P4-036 roof income upside (per-building, upside-only floor 50)
* P4-041 glimpse economics / piilukas (capped view class, not vaade)
* P4-043 number-13 / name arbitrage (taste-match steal flag)
* P4-046 dread removal / redundancy (per-listing redundancy dims)
* P4-048 small delights, EHR slice: orientation breakfast-sun check
* P4-050 permit glut vs completions (NULL — quarterly area table)
* P4-052 turnover wave per building (NULL — tehingud readings)
* P4-056 enclosed-courtyard trap (always NULL — LiDAR, not EHR)
* P4-057 heat-pump hum corridors (weak hinnang from heating type)
* P4-058 falling-ice roofs + cliff retreat (per-parcel, dated)
* P4-059 wood-burning restriction zones (per-parcel rule join)

HONESTY (AGENTS.md section 7.2): the EHR registry is NOT in the
2026-09-12 snapshot (registries/ empty; same gap as dims_group02b),
so every dim returns None when its EHR slice is missing — never a
guess. Scored reasons always say "EHR" (traceable to a registry
record); estimated models (P4-034/035/041/048/057/058) always say
"hinnang" plus what was NOT measured; pure-join params
(P4-016/023/030/031/050/052/056) stay NULL with the primary source
named. NULL stays NULL with an Estonian reason.

Openness verdict (2026-09-13, dated probes, cache /tmp/hf-ehr):
* https://www.eehitus.ee/infoportal -> 301 ->
  https://eehitus.digitaalehitus.ee (HTTP 200, 695188 bytes) — the old
  infoportal URL now serves the digital-construction cluster site, no
  anonymous CSV endpoint found there.
* https://www.ehr.ee -> 301 -> https://livekluster.ehr.ee/ui/ehr/v1
  (HTTP 200, 3663-byte JS shell: "E-ehituse platvorm on Maa- ja
  Ruumiameti infosuesteem...") — live platform UI, login-gated, no
  anonymous bulk download probed (polite stop: one GET each).
* National portal moved avaandmed.eesti.ee -> andmed.eesti.ee
  (Teabevaerav SPA, HTTP 200, 75497 bytes); no CKAN-style
  /api/3/action (HTTP 404 "Cannot GET") — dataset search needs JS.
Dated negative keeps the verdict: no anonymous direct-download EHR
CSV URL verified 2026-09-13. The registry stays OPEN-but-gated
(email-gated infoportal reports, #234 precedent), so fetch_ehr_csv
below targets the documented report layout with a weekly TTL and the
dims score ONLY joined records. See docs/p4_ehr.md for the full note.

Style mirrors services/scoring/dims_group02b.py (issue #137): pure
(ehr, listing) -> (Optional[int 0..100], Estonian reason), absolute
bands, hermetic fixture tests. Network lives only in fetch_ehr_csv
(single polite GET, file cache, TTL); tests never call it.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and group20a #212).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR because the coverage issue body states
  it "extends the demoed ingestion" — splitting would ship an
  ingestion with one consumer, then re-touch every dim signature.
* P4-005 bands are 100/50/20, never 0: a standing flat is never
  scored zero on permits alone; explicit "no permits on record" is
  weak-bad (20), missing permit keys are NULL (old stock predates
  digital records — absence is not evidence).
* P4-021 caps at 80: EHR completion ratio is real signal but TTJA
  complaints are NOT joined, so a perfect ratio is weak-good, never
  "trusted seller".
* P4-034/035/041 read listing floor/orientation against EHR
  floors_total — the listing side comes from the portal adapters
  (Group 1), the building side from EHR; either side missing is NULL.
* P4-036 never scores below 50 (upside-only): a flat roof without
  feed-in paperwork is neutral, not bad.
* P4-043 scores ONLY the 13-flag (65, taste-match); every other
  number is NULL — street-prestige residuals need Maa-amet tehingud,
  not EHR.
* Join-only params echo the consumed EHR fact inside their NULL
  reason (P4-030 permits_open, P4-031 heating_type, P4-050 permit
  counts, P4-052 renovation permits) so fixture tests prove the
  wiring without faking a score.

Integration (deliberately NOT done here): feeding these dims with
the listing's EHR record inside livability scoring and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling.
"""

import csv
import io
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated EHR CSV-report pulls.
# ---------------------------------------------------------------------------

#: Weekly bulk per parameters4.md P4-005 ("TTL: weekly bulk").
EHR_TTL_DAYS = 7

#: Where the gated exports live (verified 2026-09-13 — see module
#: docstring; login/email-gated, no anonymous bulk URL).
EHR_UI_URL = "https://livekluster.ehr.ee/ui/ehr/v1"
EHR_INFO_URL = "https://eehitus.digitaalehitus.ee"

USER_AGENT = ("home-finder EHR ingest (polite weekly bulk, single GET, "
              "file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str, name: str) -> str:
    """Cache file for one named EHR report (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)
    return os.path.join(cache_dir, "ehr-%s.csv" % safe)


def cache_is_fresh(path: str, ttl_days: int = EHR_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_ehr_csv(name: str, url: str, cache_dir: str = "/tmp/hf-cache",
                  ttl_days: int = EHR_TTL_DAYS) -> str:
    """Fetch one EHR CSV report politely (single GET, cached, TTL-stated).

    Returns cached text when fresh; otherwise one GET with a polite
    User-Agent and a 30 s timeout. Transport errors RAISE (never cached
    as data, AGENTS.md section 7.2); HTTP errors raise too — an error
    body is never written to the cache. Treat HTTP 429 as a stop
    signal: it propagates, the stale cache is left untouched.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, name)
    if cache_is_fresh(path, ttl_days):
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
# Parsing: EHR CSV-report layout (semicolon-separated, BOM-tolerant).
# Column names follow the documented export; unknown columns are kept
# verbatim, missing columns read as None (never guessed).
# ---------------------------------------------------------------------------

#: Canonical record keys produced by parse_ehr_buildings (all Optional).
EHR_FIELDS = (
    "ehr_code", "address", "kov", "floors_total", "apartments",
    "build_year", "energy_class", "has_ehitusluba", "has_kasutusluba",
    "permits_open", "permits_finalized", "renovation_permits",
    "heating_type", "has_fireplace", "water_supply", "sewage",
    "roof_type", "developer", "builder", "renovation_grant_status",
    "grant_queue_pos", "parking_spaces", "cooling_type",
)

_INT_FIELDS = ("floors_total", "apartments", "build_year",
               "permits_open", "permits_finalized", "renovation_permits",
               "grant_queue_pos", "parking_spaces")

_BOOL_FIELDS = ("has_ehitusluba", "has_kasutusluba", "has_fireplace")

_TRUTHY = ("jah", "yes", "true", "1", "olemas")
_FALSY = ("ei", "no", "false", "0", "puudub")


def _to_int(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    s = str(raw).strip().replace(" ", "")
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _to_bool(raw: Optional[str]) -> Optional[bool]:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    if s in _TRUTHY:
        return True
    if s in _FALSY:
        return False
    return None


def parse_ehr_buildings(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse one EHR CSV report into canonical per-building records.

    Semicolon-separated, BOM-tolerant; empty cells and absent columns
    become None. Rows without an ehr_code are skipped (no join key —
    keeping them would fake join coverage).
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        code = (row.get("ehr_code") or "").strip()
        if not code:
            continue
        rec = {"ehr_code": code}  # type: Dict[str, Optional[object]]
        for field in EHR_FIELDS:
            if field == "ehr_code":
                continue
            raw = row.get(field)
            if field in _INT_FIELDS:
                rec[field] = _to_int(raw)
            elif field in _BOOL_FIELDS:
                rec[field] = _to_bool(raw)
            else:
                s = None if raw is None else str(raw).strip()
                rec[field] = s if s else None
        records.append(rec)
    return records


def index_by_ehr_code(
        records: List[Dict[str, Optional[object]]]
) -> Dict[str, Dict[str, Optional[object]]]:
    """Per-ehr_code join index (first row wins on duplicates)."""
    index = {}  # type: Dict[str, Dict[str, Optional[object]]]
    for rec in records:
        code = rec.get("ehr_code")
        if code and code not in index:
            index[code] = rec
    return index


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _rec(ehr: Optional[dict]) -> Optional[dict]:
    return ehr if isinstance(ehr, dict) else None


def _lst(listing: Optional[dict]) -> dict:
    return listing if isinstance(listing, dict) else {}


def _missing_ehr() -> Score:
    return None, ("EHR kirje puudub — ehitisregistri andmeteta skoori "
                  "EI OLE (hinnangut ei anta): kontrolli ehr_code järgi "
                  "livekluster.ehr.ee-st")


def _norm(value: Optional[object]) -> str:
    return "" if value is None else str(value).strip().lower()


# ---------------------------------------------------------------------------
# P4-005 (demo): ehitusluba/kasutusluba existence — per-listing binary.
# ---------------------------------------------------------------------------

def dim_permit_bankable(ehr: Optional[dict],
                        listing: Optional[dict] = None) -> Score:
    """P4-005: bankability from EHR permit existence (100/50/20/NULL)."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    kasutus = rec.get("has_kasutusluba")
    ehitus = rec.get("has_ehitusluba")
    if kasutus is True:
        return (100, "Kasutusluba olemas (EHR andmed, mitte hinnang) — "
                     "pankro")
    if ehitus is True:
        return (50, "Ehitusluba olemas, kasutusluba puudub (EHR andmed): "
                    "ehitis pooleli või lõpetamata — pank küsib täiendavalt, "
                    "mitte hinnang")
    if kasutus is None and ehitus is None:
        return None, ("EHR kirjes loa-infot pole (EI OLE hinnangut): vanem "
                      "hoone võib digiajastust varasem olla — kontrolli "
                      "menetlust livekluster.ehr.ee-st")
    return (20, "EHR kirjes pole ehitus- ega kasutusluba (nõrk signaal, "
                "mitte hinnang) — panga küsimus enne pakkumist")


# ---------------------------------------------------------------------------
# P4-010: KredEx/EIS renovation-grant status + queue (per-building dim).
# ---------------------------------------------------------------------------

_GRANT_BANDS = (
    (("eraldatud", "tehtud", "lõpetatud"), 85,
     "Renoveerimistoetus eraldatud/tehtud (EHR/EIS andmed, mitte hinnang)"),
    (("järjekorras", "ootel"), 60, None),
    (("taotletud", "menetluses"), 50, None),
    (("puudub", "ei", "tagasi lükatud"), 35,
     "Renoveerimistoetus puudub (EHR/EIS andmed): 5-kohaline ühistu-arve "
     "võimalik — KÜ fondi kontrolli, mitte hinnang"),
)


def dim_renovation_grant(ehr: Optional[dict],
                         listing: Optional[dict] = None) -> Score:
    """P4-010: grant status bands; queue position named when known."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    status = _norm(rec.get("renovation_grant_status"))
    if not status:
        return None, ("EIS renoveerimistoetuse järjekorra andmed puuduvad "
                      "(EI OLE hinnangut): KÜ-st ja EIS-ist kontrolli")
    for keys, score, fixed in _GRANT_BANDS:
        if status in keys:
            if fixed is not None:
                return score, fixed
            pos = rec.get("grant_queue_pos")
            tail = (" — järjekorrakoht %s" % pos
                    if isinstance(pos, int) else "")
            verb = ("järjekorras" if status in ("järjekorras", "ootel")
                    else "taotletud/menetluses")
            return (score, "Renoveerimistoetus %s%s (EHR/EIS andmed, mitte "
                           "hinnang) — raha teel, aga ooteajaga"
                    % (verb, tail))
    return None, ("Tundmatu renoveerimistoetuse staatus (%s) — EI OLE "
                  "hinnangut, kontrolli EIS-ist"
                  % str(rec.get("renovation_grant_status")).strip())


# ---------------------------------------------------------------------------
# P4-013: parking regime — EHR slice is the building's parking-space count.
# The tariff zone itself comes from Tallinna parkimiskorraldus (not EHR).
# ---------------------------------------------------------------------------

def dim_parking_ehr(ehr: Optional[dict],
                    listing: Optional[dict] = None) -> Score:
    """P4-013: EHR parking-space count; zone stays with the city source."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    spaces = rec.get("parking_spaces")
    if not isinstance(spaces, int):
        return None, ("EHR parkimiskohtade arv puudub (EI OLE hinnangut): "
                      "tasulise parkimise tsoon (Tallinna parkimiskorraldus) "
                      "määrab igapäeva — kontrolli eraldi")
    if spaces > 0:
        return (75, "EHR järgi hoones %d parkimiskoht(a) (andmed, mitte "
                    "hinnang) — tänavatasu tsoon määrab külalisparkimise"
                % spaces)
    return (30, "EHR järgi hoones parkimiskohti pole (nõrk signaal, mitte "
                "hinnang) — igapäevane parkimine sõltub tasulisest tsoonist")


# ---------------------------------------------------------------------------
# P4-016: engineering geology — EHR carries no soil data (always NULL).
# ---------------------------------------------------------------------------

def dim_geology(ehr: Optional[dict],
                listing: Optional[dict] = None) -> Score:
    """P4-016: NULL — turvas/karst/alvar needs EGT/Maa-amet, not EHR."""
    return None, ("Pinnaseinfo (turvas/karst/alvar, kandevõime) eeldab EGT "
                  "insenergeoloogiat / Maa-amet WFS-i — EHR kirjes seda pole "
                  "(EI OLE hinnangut)")


# ---------------------------------------------------------------------------
# P4-021: developer/broker track record — EHR slice: builder completion
# ratio. Capped at 80: TTJA complaints are NOT joined.
# ---------------------------------------------------------------------------

def dim_developer_record(ehr: Optional[dict],
                         listing: Optional[dict] = None) -> Score:
    """P4-021: EHR permit-completion ratio per builder (weak-good cap 80)."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    who = rec.get("builder") or rec.get("developer")
    if not who:
        return None, ("Ehitaja/arendaja EHR kirjes puudub (EI OLE "
                      "hinnangut): TTJA kaebusi ja portaalide dubleerimist "
                      "kontrolli eraldi")
    done = rec.get("permits_finalized")
    open_n = rec.get("permits_open")
    if not isinstance(done, int) or not isinstance(open_n, int):
        return None, ("Ehitaja %s loa-arvud EHR kirjes puuduvad (EI OLE "
                      "hinnangut)" % who)
    total = done + open_n
    if total <= 0:
        return None, ("Ehitaja %s lubade ajalugu EHR-is tühi (EI OLE "
                      "hinnangut)" % who)
    if open_n == 0:
        return (80, "Ehitaja %s lõpetanud %d/%d luba (EHR andmed, mitte "
                    "hinnang) — TTJA kaebuste kontroll eraldi, ülempiir 80"
                % (who, done, total))
    return (50, "Ehitaja %s: %d/%d luba lõpetatud, %d pooleli (EHR andmed, "
                "mitte hinnang) — usaldust ei hinnata"
            % (who, done, total, open_n))


# ---------------------------------------------------------------------------
# P4-023: airport + military noise — zone join, never EHR (always NULL).
# ---------------------------------------------------------------------------

def dim_noise_zone(ehr: Optional[dict],
                   listing: Optional[dict] = None) -> Score:
    """P4-023: NULL — noise zones need strategic maps/EANS, not EHR."""
    return None, ("Lennu-/harjutusmüra tsoon eeldab strateegilist mürakaarti "
                  "/ EANS tsoone — EHR kirje seda ei anna (EI OLE hinnangut)")


# ---------------------------------------------------------------------------
# P4-030: satellite change delta — join-only EHR echo (always NULL).
# ---------------------------------------------------------------------------

def dim_change_flag(ehr: Optional[dict],
                    listing: Optional[dict] = None) -> Score:
    """P4-030: NULL — change needs Sentinel-2/Maa-amet; EHR echo attached."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    open_n = rec.get("permits_open")
    echo = ("; EHR järgi hoones %d avatud luba (platsi-ristkontroll, mitte "
            "muutuslipp)" % open_n if isinstance(open_n, int) else "")
    return None, ("Rohe-/ehitusmuutus eeldab Sentinel-2 NDVI-deltat / "
                  "Maa-amet aerofotosid — ala-muutuslipp EI OLE (EI OLE "
                  "hinnangut)%s" % echo)


# ---------------------------------------------------------------------------
# P4-031: backyard weather + DIY air — join-only EHR echo (always NULL).
# ---------------------------------------------------------------------------

def dim_backyard_weather(ehr: Optional[dict],
                         listing: Optional[dict] = None) -> Score:
    """P4-031: NULL — frost/wind pockets need sensors; EHR echo attached."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    heat = rec.get("heating_type")
    echo = (" EHR kütte liik %s teada (küttetõe-ristkontroll)."
            % str(heat).strip() if heat else "")
    return None, ("Tasku-ilma (külmalohud, tuulekoridorid) hinnang eeldab "
                  "DIY-sensoreid (sensor.community) — EI OLE hinnangut.%s"
                  % echo)


# ---------------------------------------------------------------------------
# P4-034: summer overheating — capped per-listing physics sim.
# ---------------------------------------------------------------------------

_SOUTH_WEST = ("lõuna", "louna", "s", "south", "lääs", "laas", "w", "west",
               "edela", "kagu", "edel", "sw", "se")


def dim_overheating(ehr: Optional[dict],
                    listing: Optional[dict] = None) -> Score:
    """P4-034: top-floor + S/W + no cooling physics sim (capped)."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    lst = _lst(listing)
    floor = lst.get("floor")
    orient = _norm(lst.get("orientation"))
    if not isinstance(floor, int) or not orient:
        return None, ("Ülekuumenemise mudel eeldab kuulutuse korrust ja "
                      "orientatsiooni — puuduvad (EI OLE hinnangut)")
    cooling = _norm(rec.get("cooling_type"))
    cooled = bool(cooling) and cooling not in ("puudub", "ei", "no", "none")
    if cooled:
        return (80, "Jahutus/ventilatsioon kirjas (EHR/kuulutuse andmed, "
                    "mitte hinnang) — augusti-sauna risk maandatud")
    total = rec.get("floors_total")
    top = isinstance(total, int) and total > 0 and floor >= total
    south_west = orient in _SOUTH_WEST
    factors = (1 if top else 0) + (1 if south_west else 0)
    if factors == 2:
        return (30, "Ülemine korrus + lõuna/lääs + jahutus puudub (EHR korrus "
                    "/ kuulutuse orientatsioon): ülekuumenemise füüsikamudel "
                    "(hinnang), mitte mõõdetud temperatuur")
    if factors == 1:
        return (55, "Üks riskitegur (ülemine korrus või lõuna/lääs), jahutus "
                    "puudub: nõrk füüsikamudel (hinnang), mitte mõõdetud")
    return (70, "Alumine korrus + põhja/ida-poolne: ülekuumenemine "
                "ebatõenäoline (nõrk füüsikamudel, mitte mõõdetud)")


# ---------------------------------------------------------------------------
# P4-035: December darkness — capped per-listing light model.
# ---------------------------------------------------------------------------

_NORTH_EAST = ("põhi", "pohi", "n", "north", "kirre", "ida", "ida-", "e",
               "east", "ne")
_SOUTH = ("lõuna", "louna", "s", "south", "kagu", "edela", "se", "sw")


def dim_darkness(ehr: Optional[dict],
                 listing: Optional[dict] = None) -> Score:
    """P4-035: ground-floor + N/E vs upper + S light model (capped)."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    lst = _lst(listing)
    floor = lst.get("floor")
    orient = _norm(lst.get("orientation"))
    if not isinstance(floor, int) or not orient:
        return None, ("Detsembri-valguse mudel eeldab kuulutuse korrust ja "
                      "orientatsiooni — puuduvad (EI OLE hinnangut)")
    if orient in _NORTH_EAST and floor <= 1:
        return (35, "Põhja/ida + 0.–1. korrus: detsembrikoobas võimalik "
                    "(EHR korrus / kuulutuse orientatsioon — hinnang, mitte "
                    "mõõdetud valgustundide arv)")
    if orient in _SOUTH and floor >= 2:
        return (80, "Lõuna + ülemine korrus: detsembri-valgus parim võimalik "
                    "(hinnang, mitte mõõdetud luksid)")
    return (60, "Keskmine valgusolukord (korrus/orientatsioon — hinnang, "
                "mitte mõõdetud)")


# ---------------------------------------------------------------------------
# P4-036: roof income — per-building upside, floor 50 (never negative).
# ---------------------------------------------------------------------------

_FLAT_ROOFS = ("lame", "lamekatus", "flat")
_PITCHED_ROOFS = ("viil", "viilkatus", "kelp", "kelpkatus", "mansard",
                  "pult", "pultkatus", "pitched")


def dim_roof_income(ehr: Optional[dict],
                    listing: Optional[dict] = None) -> Score:
    """P4-036: solar/mast/ad upside from EHR roof type (floor 50)."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    roof = _norm(rec.get("roof_type"))
    if not roof:
        return None, ("EHR katuse tüüp puudub (EI OLE hinnangut): "
                      "päikese/masti-tulu eeldab katuseinfot + Eleringi "
                      "tingimusi")
    if roof in _FLAT_ROOFS:
        return (70, "Lamekatus (EHR andmed): päikese/masti-tulu võimalik — "
                    "ülespoole-potentsiaal (hinnang), mitte mõõdetud kWh")
    if roof in _PITCHED_ROOFS:
        return (55, "Viil/kelpkatus (EHR andmed): tulu sõltub kaldest ja "
                    "ilmakaarest — nõrk ülespoole-hinnang, mitte mõõdetud")
    return (50, "Katusetüüp %s (EHR andmed): tulupotentsiaal teadmata — "
                "neutraalne, mitte hinnang alla 50"
            % str(rec.get("roof_type")).strip())


# ---------------------------------------------------------------------------
# P4-041: glimpse economics (piilukas, not vaade) — capped view class.
# ---------------------------------------------------------------------------

def dim_glimpse(ehr: Optional[dict],
                listing: Optional[dict] = None) -> Score:
    """P4-041: upper-third floor glimpse class (cap 70, never vaade)."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    lst = _lst(listing)
    floor = lst.get("floor")
    total = rec.get("floors_total")
    if not isinstance(floor, int) or not isinstance(total, int) or total < 3:
        return None, ("Piilukas-klass eeldab EHR korruste arvu (≥3) ja "
                      "kuulutuse korrust — puuduvad (EI OLE hinnangut)")
    if floor * 3 >= total * 2:
        return (70, "Ülemine kolmandik (EHR korrus %d/%d): mere/vanalinna "
                    "piilukas võimalik — vaateklass (hinnang), mitte mõõdetud "
                    "vaade" % (floor, total))
    return None, ("Alumistel korrustel (EHR korrus %d/%d) piilukas "
                  "ebatõenäoline — vaadet mõõdetud pole (EI OLE hinnangut)"
                  % (floor, total))


# ---------------------------------------------------------------------------
# P4-043: number-13 / name arbitrage — taste-match steal flag only.
# ---------------------------------------------------------------------------

def dim_number_thirteen(ehr: Optional[dict],
                        listing: Optional[dict] = None) -> Score:
    """P4-043: floor/house 13 flag (65); everything else NULL."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    lst = _lst(listing)
    floor = lst.get("floor")
    house = "" if lst.get("house_number") is None else str(
        lst.get("house_number"))
    hit = (isinstance(floor, int) and floor == 13) or "13" in house
    if not hit:
        return None, ("Numbri-13 arbitraaži pole (EI OLE hinnangut): "
                      "tänava-prestiizi jäägid eeldavad Maa-amet tehinguid, "
                      "mitte EHR-i")
    total = rec.get("floors_total")
    tail = ""
    if isinstance(total, int) and total < 13:
        tail = " — EHR järgi hoones %d korrust, numbrit kontrolli" % total
    return (65, "13. korrus/maja-number: numbriallahindlus maitsesobivale "
                "ostjale (EHR korruse-ristkontroll, mitte väärtushinnang)%s"
            % tail)


# ---------------------------------------------------------------------------
# P4-046: dread removal — heating + fireplace redundancy dims.
# ---------------------------------------------------------------------------

_MODERN_HEAT = ("kaugküte", "kaugkute", "elekter", "elektriküte",
                "soojuspump", "õhksoojuspump", "maasoojuspump", "gaas")
_STOVE_HEAT = ("ahi", "pliit", "kamin", "tahke", "tahkeküte", "puit",
               "pellet", "katel")


def dim_dread_redundancy(ehr: Optional[dict],
                         listing: Optional[dict] = None) -> Score:
    """P4-046: heat-source redundancy (fireplace + modern heat best)."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    heat = _norm(rec.get("heating_type"))
    if not heat:
        return None, ("EHR kütte liik puudub (EI OLE hinnangut): "
                      "dubleeritust ei saa hinnata")
    fireplace = rec.get("has_fireplace") is True
    modern = heat in _MODERN_HEAT
    stove = heat in _STOVE_HEAT
    water = rec.get("water_supply")
    water_tail = ("; vesi: %s" % str(water).strip() if water else "")
    if fireplace and (modern or stove):
        if modern:
            return (85, "Kamin/ahi + kaugküte/moodne küte (EHR andmed, mitte "
                        "hinnang): soojuse dubleeritus — hätta jäämine "
                        "välistatud%s" % water_tail)
        return (75, "Kamin/ahi + tahkeküte (EHR andmed, mitte hinnang): "
                    "puit varuks, elektrita soe%s" % water_tail)
    if modern:
        return (65, "Moodne küte (%s, EHR andmed), kaminat pole: töökindel, "
                    "aga ühe allikaga%s"
                % (str(rec.get("heating_type")).strip(), water_tail))
    return (55, "Ainult tahkeküte (%s, EHR andmed): soe, aga ühe allika "
                "vaev — varupliit kontrolli%s"
            % (str(rec.get("heating_type")).strip(), water_tail))


# ---------------------------------------------------------------------------
# P4-048: small delights — EHR slice is the orientation breakfast-sun check.
# ---------------------------------------------------------------------------

_EAST = ("ida", "e", "east", "kagu", "kirde", "se", "ne")


def dim_small_delights(ehr: Optional[dict],
                       listing: Optional[dict] = None) -> Score:
    """P4-048: east breakfast-sun check; queues stay a separate table."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    orient = _norm(_lst(listing).get("orientation"))
    if not orient:
        return None, ("Hommikupäike eeldab kuulutuse orientatsiooni — "
                      "puudub (EI OLE hinnangut); aiamaa-järjekorrad on "
                      "eraldi aastatabel")
    if orient in _EAST:
        return (70, "Idapoolne orientatsioon: hommikupäike võimalik "
                    "(orientatsioon — hinnang, mitte mõõdetud); "
                    "ujula/jäähall <15 min ja aiamaa-järjekorrad eraldi")
    return None, ("Mitte-idapoolne orientatsioon: hommikupäikest pole "
                  "(EI OLE hinnangut); pink-vaated ja järjekorrad eraldi")


# ---------------------------------------------------------------------------
# P4-050: permit glut vs completions — NULL (quarterly area table).
# ---------------------------------------------------------------------------

def dim_permit_glut(ehr: Optional[dict],
                    listing: Optional[dict] = None) -> Score:
    """P4-050: NULL — glut needs a quarterly micro-area table."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    open_n = rec.get("permits_open")
    done = rec.get("permits_finalized")
    if isinstance(open_n, int) and isinstance(done, int):
        echo = (" Hoone enda %d avatud / %d lõpetatud luba (EHR andmed)."
                % (open_n, done))
    else:
        echo = ""
    return None, ("Loa-uputus vs valmimine eeldab kvartaalset asumitabelit "
                  "(EHR load vs kasutusload asumiti) — ala-hinnangut EI OLE "
                  "(EI OLE hinnangut).%s" % echo)


# ---------------------------------------------------------------------------
# P4-052: turnover wave — NULL (tehingud readings, both in reason).
# ---------------------------------------------------------------------------

def dim_turnover_wave(ehr: Optional[dict],
                      listing: Optional[dict] = None) -> Score:
    """P4-052: NULL — wave needs tehingud; EHR echo names the storm-in aid."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    reno = rec.get("renovation_permits")
    echo = (" EHR renoveerimisload %d (sissetormi-lugemi ristkontroll)."
            % reno if isinstance(reno, int) else "")
    return None, ("Käibe-laine eeldab Maa-amet tehinguid hoone kohta: "
                  "probleem vs gentrifikatsioon — mõlemad lugemid, EI OLE "
                  "hinnangut.%s" % echo)


# ---------------------------------------------------------------------------
# P4-056: enclosed-courtyard trap — LiDAR morphology, never EHR (NULL).
# ---------------------------------------------------------------------------

def dim_courtyard_trap(ehr: Optional[dict],
                       listing: Optional[dict] = None) -> Score:
    """P4-056: NULL — enclosure index needs LiDAR/LoD2, not EHR."""
    return None, ("Suletud hoovi mikrokliima (külm + heitgaasid + kuumus) "
                  "eeldab LiDAR sulgindeksit — EHR kirjes seda pole "
                  "(EI OLE hinnangut)")


# ---------------------------------------------------------------------------
# P4-057: heat-pump hum corridors — weak hinnang from heating type only.
# ---------------------------------------------------------------------------

def dim_heatpump_hum(ehr: Optional[dict],
                     listing: Optional[dict] = None) -> Score:
    """P4-057: own heat-pump type is a weak hum hint (55); else NULL."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    heat = _norm(rec.get("heating_type"))
    if not heat:
        return None, ("EHR kütte liik puudub (EI OLE hinnangut): "
                      "pumbamüraallikat ei saa hinnata")
    if "soojuspump" in heat:
        return (55, "Soojuspump (%s, EHR andmed): väliseadme sumin võimalik "
                    "— naabrite seadmed teadmata (nõrk hinnang, mitte "
                    "mõõdetud müratase)"
                % str(rec.get("heating_type")).strip())
    return None, ("Oma pumbamüraallikas puudub (%s, EHR andmed) — naabrite "
                  "oma teadmata (EI OLE hinnangut)"
                  % str(rec.get("heating_type")).strip())


# ---------------------------------------------------------------------------
# P4-058: falling-ice roofs + cliff retreat — per-parcel dims with dates.
# ---------------------------------------------------------------------------

def dim_falling_ice(ehr: Optional[dict],
                    listing: Optional[dict] = None) -> Score:
    """P4-058: pitched roofs are a weak ice-fall hint; cliffs need Maa-amet."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    roof = _norm(rec.get("roof_type"))
    if not roof:
        return None, ("EHR katuse tüüp puudub (EI OLE hinnangut): "
                      "jääpurika-riski ei saa hinnata; kaldaastangu "
                      "(Kakumäe/Pirita) eeldab Maa-amet rannajoont")
    if roof in _PITCHED_ROOFS:
        return (45, "Viil/kelpkatus (EHR andmed): talvine jääpurika-risk "
                    "kõnniteel — talihoolduse kohustus (nõrk hinnang, mitte "
                    "mõõdetud kukkumiste arv, kehtib lumeajal)")
    if roof in _FLAT_ROOFS:
        return (75, "Lamekatus (EHR andmed): jääpurika-risk väike (nõrk "
                    "hinnang)")
    return None, ("Tundmatu katusetüüp (%s) — EI OLE hinnangut"
                  % str(rec.get("roof_type")).strip())


# ---------------------------------------------------------------------------
# P4-059: wood-burning restriction zones — per-parcel rule join.
# ---------------------------------------------------------------------------

def dim_woodburn_zone(ehr: Optional[dict],
                      listing: Optional[dict] = None) -> Score:
    """P4-059: stove assets face the restriction table; clean heat is 80."""
    rec = _rec(ehr)
    if rec is None:
        return _missing_ehr()
    heat = _norm(rec.get("heating_type"))
    if not heat:
        return None, ("EHR kütte liik puudub (EI OLE hinnangut): "
                      "tahkekütte-piirangut ei saa kontrollida")
    if heat in _MODERN_HEAT and "soojuspump" not in heat:
        modern_label = str(rec.get("heating_type")).strip()
        if heat in ("kaugküte", "kaugkute", "elekter", "elektriküte",
                    "gaas"):
            return (80, "%s (EHR andmed): tahkekütte-piirang ei strandita — "
                        "kontrollitud reeglitabeli vastu, mitte hinnang"
                    % modern_label)
    if heat in _STOVE_HEAT or "kamin" in heat:
        return (40, "Tahkeküte (%s, EHR andmed): Tallinna piiranguala "
                    "kontrolli — ahi võib varana jääda (reeglitabeli-rist, "
                    "mitte hinnang)"
                % str(rec.get("heating_type")).strip())
    if "soojuspump" in heat:
        return (80, "%s (EHR andmed): tahkekütte-piirang ei strandita — "
                    "kontrollitud reeglitabeli vastu, mitte hinnang"
                % str(rec.get("heating_type")).strip())
    return None, ("Tundmatu kütte liik (%s) — EI OLE hinnangut"
                  % str(rec.get("heating_type")).strip())


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_EHR_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_EHR_DIMS = (
    ("permit_bankable", "P4-005", dim_permit_bankable),
    ("renovation_grant", "P4-010", dim_renovation_grant),
    ("parking_ehr", "P4-013", dim_parking_ehr),
    ("geology", "P4-016", dim_geology),
    ("developer_record", "P4-021", dim_developer_record),
    ("noise_zone", "P4-023", dim_noise_zone),
    ("change_flag", "P4-030", dim_change_flag),
    ("backyard_weather", "P4-031", dim_backyard_weather),
    ("overheating", "P4-034", dim_overheating),
    ("darkness", "P4-035", dim_darkness),
    ("roof_income", "P4-036", dim_roof_income),
    ("glimpse", "P4-041", dim_glimpse),
    ("number_thirteen", "P4-043", dim_number_thirteen),
    ("dread_redundancy", "P4-046", dim_dread_redundancy),
    ("small_delights", "P4-048", dim_small_delights),
    ("permit_glut", "P4-050", dim_permit_glut),
    ("turnover_wave", "P4-052", dim_turnover_wave),
    ("courtyard_trap", "P4-056", dim_courtyard_trap),
    ("heatpump_hum", "P4-057", dim_heatpump_hum),
    ("falling_ice", "P4-058", dim_falling_ice),
    ("woodburn_zone", "P4-059", dim_woodburn_zone),
)


def score_p4_ehr(ehr: Optional[dict],
                 listing: Optional[dict] = None
                 ) -> Dict[str, Optional[int]]:
    """All 21 P4 EHR dims for one listing (entry point for the future
    enrich/score hook; keys match P4_EHR_DIMS). Missing slices stay None
    by design — per-ehr_code join, never a faked area score."""
    return {key: fn(ehr, listing)[0] for key, _, fn in P4_EHR_DIMS}

