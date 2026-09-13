"""Overturn for G4 p361/p369 with free e-Ariregister bulk data (issue #232).

Params (parameters3.md section 5.4, Group 4): p361 trust/LLC
transferability (dim_trust_llc_transfer) and p369 co-op board
approval (dim_coop_approval). Both resolve per listing from the
seller/owner ENTITY, never from area data - honest output is
per-listing scorer dims, never a raster. The canonical Group 4
NULL dims in dims_group04.py are NOT touched here (no shared/group
files edited; the final docs-index PR updates docs/nomap.md).

HUNT (2026-09-13, polite: 6 doc/storefront GETs + 4 HEADs + 2
static-file GETs, labelled one-off UA, paced >= 4 s, headers +
visible-text scope only; raw bodies at /tmp/arireg-bulk/, never
committed). Full log: docs/overturn_arireg.md. Result: the issue
body's claim holds - free bulk downloads exist OUTSIDE the
contract-gated XML query API, at
https://avaandmed.ariregister.rik.ee/et/avaandmete-allalaadimine
(prerequisite is licence-terms acceptance, not a RIK contract):
12 datasets, most refreshed daily, public rows only for statuses
registrisse kantud / likvideerimisel / pankrotis. Verified live:

* Lihtandmed CSV zip (18 511 171 B, Last-Modified Sun 13 Sep 2026):
  377 730 entity rows; real header
  nimi;ariregistri_kood;ettevotja_oiguslik_vorm;...;ettevotja_staatus;
  ... - status R 368 331 / L 8 725 / N 673; Osaühing 292 839,
  Korteriühistu 25 648, FIE 24 647, MTÜ 22 997, Usaldusühing 3 666,
  AS 2 038.
* Osanikud JSON zip (33 854 442 B, same-day stamp), 763 MB
  uncompressed, 377 730 company objects: per-company
  {"ariregistri_kood", "nimi", "osanikud": [...],
  "osapandid_tingimuslikud_voorandamised": [...]} with shareholder
  rows carrying isiku_tyyp (F 345 203 / J 44 999), isiku_roll
  (OSAN + O, both labelled "Osanik"), osaluse_omandiliik
  (L=Ainuomand 382 270 / Y=Ühisomand 7 894 / K=Kaasomand 36 /
  KY=Kaasomandiosa ühisomandis 2), osaluse_protsent. Shareholder
  counts: 0: 84 910 / 1: 237 527 / 2: 41 264 / 3: 8 521 / 4+: ~5k.
  Non-empty pledge/conditional arrays: 124 companies.
* Hard removals (dated, stay NULL permanently): personal ID codes
  gone since 01.11.2024 (isikukood_registrikood null, only
  isikukood_hash remains); beneficial-owner open data ENDED
  10.07.2026 (Rahandusministeerium notice); trust administrations
  (usaldushaldus) have a contract-API query only, NO download
  file; AS shareholder books live at the securities centre, not
  in bulk; articles TEXTS (põhikiri) are paid file documents
  (downloads carry only the articles LIST in üldandmed, a 230 MB
  file whose body was deliberately not pulled).

WHAT FLIPPED vs STAYED NULL (2026-09-13 verdict, pinned by tests):

* p361 SCORED-or-None from free bulk: status block (L->20,
  N->10, never 0 - stale-record precedent), then for Osaühing the
  shareholder-shape bands (1->75 / 2->65 / 3-4->55 / 5+->45, caps:
  joint/co-ownership haircut -10, corporate-owner layer -5, floor
  25; pledge/conditional presence caps at 40), FIE flat 70. Every
  scored reason says "hinnang" with components and the notary
  remainder (beneficial owners unpublished, register lag).
* p361 NULL where the free bulk cannot answer: AS (shareholder
  book at the CSD), partnerships (partners live in the free
  kaardile-kantud-isikud file, not ingested this round -
  recheck hook), KÜ/MTÜ/SA/filiaal/public bodies (no OÜ-share
  logic), OÜ with zero shareholder rows (register lag - absence
  is unknown, never good), unresolvable entity (no registry
  code). Trust-administration (usaldushaldus) facet stays NULL:
  contract-query only, no free file.
* p369 ALWAYS NULL with a KÜ echo: the downloads identify every
  KÜ (25 648) by code/status/address but the approval RULE lives
  in the KÜ põhikirja TEXT (paid file). The dim echoes the
  joined KÜ identity (P4-010 echo precedent) and points at the
  concrete check (written board confirmation). Paid extracts stay
  NULL permanently.

Ingestion (stdlib only, offline-first):
* fetch_arireg_bulk_snapshot(cache_dir): polite pull, max 1
  download / 7 d per file per cache dir (ARIREG_TTL_S; files
  refresh daily, weekly pull matches the G4 weekly rhythm).
  Fresh-cache files are NOT refetched (bulk work converges over
  runs). One GET per stale file with ARIREG_UA, 60 s timeout;
  the body is stored only on HTTP 200 with zip content, else
  None (transport errors are never data). No retries - HTTP 429
  is a stop signal (AGENTS.md 7.4). Downloading requires
  accepting the RIK licence terms (see docs/overturn_arireg.md).
* parse_lihtandmed_csv / parse_osanikud_json: pure offline
  readers over the cached files (real header/keys above;
  fixtures match them). The 763 MB holders file is read through
  iter_osanikud_companies, a memory-flat incremental scanner -
  never a whole-file json.load. Malformed rows are skipped,
  never faked; a missing/unparseable file parses to None
  (unknown), never to an empty index. Scorers and tests never
  touch the network.
* Coverage honesty: the dumps carry ONLY R/L/N statuses, so a
  missing join key is unresolvable (deleted entities are absent
  by construction) - always NULL, never clean.

Style mirrors services/scoring/dims_p4_arireg.py (issues
#257/#338): pure (entity, listing) -> (Optional[int 0..100],
Estonian reason), absolute first-cut bands (MUST be recalibrated
from a joined listing sample on reopen - see docs), hermetic
fixture tests. Network lives only in fetch_arireg_bulk_snapshot.

Helpers are local copies (not imported from livability, sibling
batches, dims_group04, or dims_p4_arireg): a future central hook
may import this module alongside them, and importing any of them
here would turn that into a cycle (same precedent as batch B3,
PR #100, and group20a #212). In particular nothing is shared
with the P4 arireg module - the G4 entity join stands alone.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-shareholder OÜ caps at 75, never higher: the
  shareholder list can lag and beneficial owners are
  unpublished since 10.07.2026 - a "clean" bulk row is narrower
  evidence than a notary extract (P4-020 cap-70 precedent).
* Status blocks override shape: a bankrupt single-owner OÜ
  scores 10 (frozen transfer), not 75 - the block is the
  binding constraint.
* Role code "O" counts as a party row: the live dump labels all
  23 075 of them "Osanik", identical to OSAN - excluding them
  would undercount parties on unexplained grounds.
* Kommertspandid (free 0.95 MB file, HEAD-verified) are NOT
  consumed: pledges answer encumbrance (p144/p248 territory),
  not party shape - named here so the boundary is reviewable.
* p369 echoes instead of scoring on purpose: scoring the KÜ's
  existence again would double-answer p361's status block while
  the actual question (does THIS KÜ's põhikiri require consent?)
  stays unread - the EHR P4-030/031/050/052 echo precedent.
* No address->KÜ join in this PR although lihtandmed carries
  normalised addresses: matching a listing to its building's KÜ
  is a second join with its own false-match risk - recheck hook
  in docs/overturn_arireg.md, not half-built here.

Integration (deliberately NOT done here): feeding these dims
with the listing's seller registry code inside livability
scoring and rebalancing livability.WEIGHTS must be one joint
change across all parameter batches - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break
every sibling. No shared files touched: 3 new files only.
"""

import csv
import json
import os
import time
import urllib.request
from typing import Dict, Iterator, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Open-data download environment (free bulk; licence-terms
#: acceptance, NOT a RIK contract - verified 2026-09-13).
ARIREG_DOWNLOAD_BASE = "https://avaandmed.ariregister.rik.ee"

#: The two static files this overturn ingests (HEAD-verified
#: 2026-09-13, refreshed same-day: daily rhythm confirmed live).
ARIREG_LIHTANDMED_PATH = (
    "/sites/default/files/avaandmed/"
    "ettevotja_rekvisiidid__lihtandmed.csv.zip"
)
ARIREG_OSANIKUD_PATH = (
    "/sites/default/files/avaandmed/"
    "ettevotja_rekvisiidid__osanikud.json.zip"
)

#: Max one download per 7 d per file per cache dir (files refresh
#: daily; weekly pull matches the G4 weekly rhythm). Stated TTL.
ARIREG_TTL_S = 7 * 24 * 3600

#: Snapshot filenames inside the cache dir.
LIHTANDMED_FILENAME = "arireg-lihtandmed.csv.zip"
OSANIKUD_FILENAME = "arireg-osanikud.json.zip"

#: Identifying user agent for the polite pull (published static
#: files, single GET per stale file, no scrape).
ARIREG_UA = "home-finder arireg-bulk ingest (max 1 req/7d/file, no scrape)"

#: Verdict / re-check dates (overturn protocol, docs/nomap.md section 2).
VERDICT_DATE = "2026-09-13"
RECHECK_AFTER = "2027-03-13"

#: Registry statuses carried by the dumps (deleted entities are
#: absent by construction - a missing join is unresolvable).
STATUS_REGISTERED = "R"  # Registrisse kantud
STATUS_LIQUIDATION = "L"  # Likvideerimisel
STATUS_BANKRUPT = "N"  # Pankrotis

#: Legal forms (ettevotja_oiguslik_vorm) the dims branch on.
FORM_OU = "Osa\xfching"
FORM_AS = "Aktsiaselts"
FORM_KU = "Korteri\xfchistu"
FORM_FIE = "F\xfc\u00fcsilisest isikust ettev\xf5tja"
FORM_PARTNERSHIPS = ("T\xe4is\xfching", "Usaldus\xfching")

#: Shareholder-shape bands for a registered OYU: party count ->
#: score (first-cut, recalibrate from a joined listing sample).
SH_BANDS = [(1, 75), (2, 65), (4, 55), (float("inf"), 45)]

#: Joint/co-ownership haircut (Y/Yhisomand, K/Kaasomand,
#: KY/Kaasomandiosa yhisomandis on the row).
JOINT_HAIRCUT = 10
JOINT_CODES = ("Y", "K", "KY")

#: Layered-ownership haircut (a J-type corporate shareholder -
#: its own owners need the unpublished beneficial-owner data).
CORP_HAIRCUT = 5

#: Shape floor (stale/mis-joined rows exist - never 0).
SHAPE_FLOOR = 25

#: Pledge/conditional-disposal presence caps the shape score.
PLEDGE_CAP = 40

#: Flat scores.
FIE_SCORE = 70
STATUS_LIQUIDATION_SCORE = 20
STATUS_BANKRUPT_SCORE = 10


def fetch_arireg_bulk_snapshot(cache_dir: str,
                               ttl_s: int = ARIREG_TTL_S,
                               base_url: str = ARIREG_DOWNLOAD_BASE,
                               ) -> Optional[Dict[str, str]]:
    """Polite bulk pull with a stated TTL. Returns {key: path} or None.

    Fresh-cache files (mtime within ttl_s) are NOT refetched -
    bulk work converges over runs instead of hammering through in
    one. Each STALE file costs exactly one GET with ARIREG_UA and
    a 60 s timeout; the body is stored only on HTTP 200 with zip
    content, else that file stays missing and nothing is cached
    (transport errors are never data). No retries - HTTP 429 and
    errors are a stop signal. Returns None when neither file is
    available (unknown), else the paths of the files present
    (partial snapshot is honest: scorers join what is there).
    Downloading the files requires accepting the RIK licence
    terms (see docs/overturn_arireg.md). Scorers never call this;
    tests cover the cache-hit path with a stubbed opener, never
    the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    wanted = (("lihtandmed", LIHTANDMED_FILENAME, ARIREG_LIHTANDMED_PATH),
              ("osanikud", OSANIKUD_FILENAME, ARIREG_OSANIKUD_PATH))
    out: Dict[str, str] = {}
    for key, filename, url_path in wanted:
        dest = os.path.join(cache_dir, filename)
        try:
            fresh = (os.path.exists(dest)
                     and time.time() - os.path.getmtime(dest) < ttl_s)
        except OSError:
            return None
        if fresh:
            out[key] = dest
            continue
        try:
            req = urllib.request.Request(base_url + url_path,
                                         headers={"User-Agent": ARIREG_UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                status = getattr(resp, "status", 200)
                ctype = resp.headers.get("Content-Type", "")
                if status != 200 or "zip" not in ctype:
                    continue
                body = resp.read()
            if len(body) < 4 or body[:4] != b"PK\x03\x04":
                continue
            with open(dest, "wb") as fh:
                fh.write(body)
            out[key] = dest
        except Exception:
            continue  # stale file stays missing; never cached as data
    return out or None


# ---------------------------------------------------------------------------
# Offline readers over the cached files (pure; fixtures match schema).
# ---------------------------------------------------------------------------

#: Lihtandmed CSV columns consumed here (real header 2026-09-13;
#: ';'-separated, UTF-8 BOM). Address/EHAK columns ride along for
#: the future address->KÜ join (recheck hook, not scored here).
LIHTANDMED_FIELDS = (
    "nimi", "ariregistri_kood", "ettevotja_oiguslik_vorm",
    "ettevotja_oigusliku_vormi_alaliik", "kmkr_nr",
    "ettevotja_staatus", "ettevotja_staatus_tekstina",
    "ettevotja_esmakande_kpv", "ettevotja_aadress",
    "asukoht_ettevotja_aadressis", "asukoha_ehak_kood",
    "asukoha_ehak_tekstina", "indeks_ettevotja_aadressis",
    "ads_adr_id", "ads_ads_oid",
    "ads_normaliseeritud_taisaadress", "teabesysteemi_link",
)


def parse_lihtandmed_csv(path: str) -> Optional[dict]:
    """Read a cached Lihtandmed CSV zip member. Offline, stdlib.

    Returns {"companies": [...]} with malformed rows skipped, or
    None when the file is missing/unparseable (unknown, never an
    empty index - scorers must not read "no file" as "clean").
    """
    import zipfile
    try:
        with zipfile.ZipFile(path) as zf:
            member = zf.namelist()[0]
            with zf.open(member) as fh:
                raw = fh.read()
    except (OSError, ValueError, IndexError, KeyError,
            zipfile.BadZipFile):
        return None
    try:
        text = raw.decode("utf-8-sig")
    except (ValueError, UnicodeDecodeError):
        return None
    lines = text.splitlines()
    if not lines:
        return None
    try:
        reader = csv.DictReader(lines, delimiter=";")
    except csv.Error:
        return None
    companies = []
    for row in reader:
        try:
            code = (row.get("ariregistri_kood") or "").strip()
        except AttributeError:
            continue
        if not code or not code.isdigit():
            continue  # no join key - keeping it fakes join coverage
        companies.append({
            "registry_code": code,
            "name": (row.get("nimi") or "").strip() or None,
            "legal_form": (
                row.get("ettevotja_oiguslik_vorm") or "").strip() or None,
            "form_subtype": (
                row.get("ettevotja_oigusliku_vormi_alaliik")
                or "").strip() or None,
            "status": (row.get("ettevotja_staatus") or "").strip() or None,
            "status_text": (
                row.get("ettevotja_staatus_tekstina") or "").strip() or None,
            "first_entry": (
                row.get("ettevotja_esmakande_kpv") or "").strip() or None,
            "address": (
                row.get("ads_normaliseeritud_taisaadress")
                or row.get("ettevotja_aadress") or "").strip() or None,
            "ehak": (row.get("asukoha_ehak_kood") or "").strip() or None,
        })
    return {"companies": companies}


def iter_osanikud_companies(fh) -> Iterator[str]:
    """Yield raw per-company JSON objects from a TEXT Osanikud stream.

    Memory-flat incremental scanner over the 763 MB holders file:
    tracks brace depth outside strings (with backslash-escape
    handling) and yields each top-level array element (depth 1 -
    the file is one JSON array of company objects) as a JSON
    string for json.loads. Callers must pass a text stream (so
    multi-byte characters split across read chunks still decode;
    parse_osanikud_json wraps with TextIOWrapper). Feeding in
    arbitrary chunks is supported (tests pin split-chunk parity).
    """
    depth = 0
    in_string = False
    escape = False
    started = False
    buf: List[str] = []
    while True:
        chunk = fh.read(1 << 20)
        if not chunk:
            break
        for ch in chunk:
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                if started:
                    buf.append(ch)
                continue
            if ch == '"':
                in_string = True
                if started:
                    buf.append(ch)
                continue
            if ch == "{":
                depth += 1
                if depth == 1:
                    started = True
                    buf = ["{"]
                elif started:
                    buf.append(ch)
                continue
            if ch == "}":
                if started:
                    buf.append(ch)
                if depth == 1 and started:
                    started = False
                    yield "".join(buf)
                    buf = []
                depth -= 1
                continue
            if started:
                buf.append(ch)


def parse_osanikud_json(path: str, limit: Optional[int] = None) -> Optional[dict]:
    """Read a cached Osanikud JSON zip member. Offline, stdlib.

    Returns {"holders": [...]} with malformed company objects
    skipped, or None when the file is missing/unparseable.
    `limit` caps parsed companies (sampling/tests only).
    """
    import io
    import zipfile
    try:
        zf = zipfile.ZipFile(path)
    except (OSError, ValueError, zipfile.BadZipFile):
        return None
    try:
        member = zf.namelist()[0]
        with zf.open(member) as raw_fh:
            # Text wrapper: incremental UTF-8 decoding keeps
            # multi-byte characters intact across read chunks.
            fh = io.TextIOWrapper(raw_fh, encoding="utf-8")
            holders = []
            try:
                for raw in iter_osanikud_companies(fh):
                    if limit is not None and len(holders) >= limit:
                        break
                    try:
                        obj = json.loads(raw)
                    except ValueError:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    code = obj.get("ariregistri_kood")
                    code = str(code).strip() if code is not None else ""
                    if not code or not code.isdigit():
                        continue
                    shareholders = []
                    rows = obj.get("osanikud")
                    if isinstance(rows, list):
                        for row in rows:
                            if not isinstance(row, dict):
                                continue
                            pct = row.get("osaluse_protsent")
                            try:
                                pct_f = (None if pct is None
                                         else float(str(pct).replace(",", ".")))
                            except (TypeError, ValueError):
                                pct_f = None
                            shareholders.append({
                                "type": row.get("isiku_tyyp") or None,
                                "role": row.get("isiku_roll") or None,
                                "ownership": (
                                    row.get("osaluse_omandiliik") or None),
                                "percent": pct_f,
                            })
                    pledges = obj.get(
                        "osapandid_tingimuslikud_voorandamised")
                    holders.append({
                        "registry_code": code,
                        "name": obj.get("nimi") or None,
                        "shareholders": shareholders,
                        "pledges_present": bool(
                            isinstance(pledges, list) and len(pledges) > 0),
                    })
            except (OSError, ValueError, zipfile.BadZipFile):
                return None
    finally:
        try:
            zf.close()
        except Exception:
            pass
    return {"holders": holders}


def index_by_registry_code(
        records: List[Dict[str, Optional[object]]]
) -> Dict[str, Dict[str, Optional[object]]]:
    """Per-registry_code join index (first row wins on duplicates)."""
    index: Dict[str, Dict[str, Optional[object]]] = {}
    for rec in records:
        code = rec.get("registry_code")
        if code and code not in index:
            index[code] = rec
    return index


# ---------------------------------------------------------------------------
# Small input helpers (local copies - no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _provenance(entity: dict) -> str:
    code = entity.get("registry_code") or "teadmata"
    name = entity.get("name") or "nimetu"
    return "%s (%s, e-Äriregister avaandmed)" % (name, code)


def _missing_entity() -> Score:
    return None, ("Müüja üksuse registrikood teadmata - omandistruktuuri "
                  "hinnangut EI OLE: küsi müüjalt registrikood ja kontrolli "
                  "ettevõtja staatust/osanikke ariregister.rik.ee-st, "
                  "osaühingu puhul kinnitab notari õigusaudit")


def _band_sh(count: int) -> int:
    """First score whose threshold covers the party count."""
    for limit, pts in SH_BANDS:
        if count <= limit:
            return pts
    return SH_BANDS[-1][1]


# ---------------------------------------------------------------------------
# p361: trust/LLC transferability - scored-or-None from free bulk.
# ---------------------------------------------------------------------------

def dim_trust_llc_transfer(entity: Optional[dict],
                           listing: Optional[dict] = None) -> Score:
    """p361: seller-entity transfer friction (high = simple transfer).

    Status blocks override shape; a registered OÜ scores its
    shareholder-shape bands with joint/corporate haircuts and the
    pledge cap; FIE scores flat. Everything needing paid
    registers (AS book, trust administration, beneficial owners,
    articles texts) or missing data stays NULL with the concrete
    check reason. Never a raster: per-listing entity join only.
    """
    _ = listing
    if not isinstance(entity, dict) or not entity.get("registry_code"):
        return _missing_entity()
    status = entity.get("status")
    form = entity.get("legal_form")
    prov = _provenance(entity)
    if status == STATUS_BANKRUPT:
        return STATUS_BANKRUPT_SCORE, (
            "Omandaja on pankrotis (hinnang): vara käsutamine on "
            "peatatud - tehingut ei saa tavakorras lõpule viia (%s); "
            "kontrolli pankrotihaldurilt/notarilt" % prov)
    if status == STATUS_LIQUIDATION:
        return STATUS_LIQUIDATION_SCORE, (
            "Omandaja on likvideerimisel (hinnang): tehing vajab "
            "likvideerija nõusolekut ja lisakontrolli (%s); "
            "kontrolli likvideerijalt/notarilt" % prov)
    if status != STATUS_REGISTERED:
        return None, ("Omandaja staatus teadmata (EI OLE hinnangut): %s - "
                      "staatust ariregister.rik.ee-st ei leitud, kontrolli "
                      "registrikoodi ja notari õigusauditit" % prov)
    if form == FORM_OU:
        return _score_ou_shape(entity, prov)
    if form == FORM_FIE:
        return FIE_SCORE, ("FIE omandistruktuur (hinnang, ülempiir 70): "
                           "isik = ettevõtja, osanike-vaidluse riski ei ole "
                           "(%s); isikliku ja ettevõtlusvara piiri ning "
                           "võlakohustused kinnitab notari õigusaudit" % prov)
    if form == FORM_AS:
        return None, ("Aktsiaseltsi aktsiaraamatut avaandmetes EI OLE "
                      "(hinnangut ei anta): %s - aktsionäride struktuur "
                      "selgub väärtpaberikeskuse registrist/notari "
                      "õigusauditist" % prov)
    if form in FORM_PARTNERSHIPS:
        return None, ("Osanike/partnerite koosseisu avaandmete faili "
                      "selles voos EI OLE liidetud (hinnangut ei anta): "
                      "%s - partnerid on kirjas kaardile kantud isikute "
                      "failis (tasuta, liidab kordus-tõmme), seni kontrolli "
                      "notarilt" % prov)
    if form == FORM_KU:
        return None, ("Korteriühistu ei ole osaühingu-müüja (EI OLE p361 "
                      "hinnangut): %s - ühistu heakskiidu küsimuse vastab "
                      "p369 dimm (põhikirja nõusolekuklausel)" % prov)
    if form is None:
        return None, ("Omandaja õiguslik vorm teadmata (EI OLE hinnangut): "
                      "%s - kontrolli vormi ariregister.rik.ee-st" % prov)
    return None, ("Õiguslik vorm %s: osaühingu-osanike loogika ei kehti "
                  "(EI OLE hinnangut): %s - ülekantavuse kinnitab notari "
                  "õigusaudit koos põhikirjaga" % (form, prov))


def _score_ou_shape(entity: dict, prov: str) -> Score:
    """Shareholder-shape bands for a registered OÜ."""
    if not entity.get("holders_joined"):
        return None, ("Osaühingu osanike ridu selles tõmbes EI OLE "
                      "(hinnangut ei anta): %s - osanike fail võib hilineda, "
                      "puudumine ei ole puhtus; kontrolli osanike registrist "
                      "notari õigusauditiga" % prov)
    parties = entity.get("shareholders") or []
    if not parties:
        return None, ("Osaühingu osanike read puuduvad (EI OLE hinnangut): "
                      "%s - registri viivis, puudumine ei ole puhtus; "
                      "kontrolli notari õigusauditiga" % prov)
    count = len(parties)
    score = _band_sh(count)
    bits = ["osanikke %d" % count]
    if any((p.get("ownership") or "") in JOINT_CODES for p in parties):
        score = max(score - JOINT_HAIRCUT, SHAPE_FLOOR)
        bits.append("ühis/kaasomand")
    if any(p.get("type") == "J" for p in parties):
        score = max(score - CORP_HAIRCUT, SHAPE_FLOOR)
        bits.append("juriidilisest isikust osanik")
    if entity.get("pledges_present"):
        score = min(score, PLEDGE_CAP)
        bits.append("osapant/tingimuslik võõrandamine")
    return score, ("OÜ omandistruktuur (hinnang, ülempiir 75: %s) - %s; "
                   "tegelikud kasusaajad on alates 10.07.2026 suletud "
                   "andmed ja register võib hilineda, struktuuri kinnitab "
                   "notari õigusaudit" % (", ".join(bits), prov))


# ---------------------------------------------------------------------------
# p369: co-op board approval - always NULL with a KÜ echo.
# ---------------------------------------------------------------------------

def dim_coop_approval(entity: Optional[dict],
                      listing: Optional[dict] = None) -> Score:
    """p369: KÜ board-approval need (always NULL - articles text is paid).

    The free bulk identifies every KÜ by code/status/address but the
    approval RULE lives in the KÜ põhikirja text (paid file
    document). The dim echoes the joined KÜ identity so fixture
    tests prove the wiring without faking a verdict, and points at
    the concrete check (written board confirmation).
    """
    _ = listing
    if not isinstance(entity, dict) or not entity.get("registry_code"):
        return None, ("Maja korteriühistu teadmata (EI OLE hinnangut): küsi "
                      "müüjalt KÜ registrikood ja kontrolli ühistu olemasolu "
                      "ariregister.rik.ee-st; heakskiidu vajadus selgub "
                      "ainult KÜ põhikirja nõusolekuklauslist - küsi "
                      "ühistult kirjalikku kinnitust")
    prov = _provenance(entity)
    status = entity.get("status")
    if entity.get("legal_form") != FORM_KU:
        return None, ("Müüja üksus ei ole korteriühistu (EI OLE p369 "
                      "hinnangut): %s - maja KÜ (avaandmetes 25 648) leia "
                      "aadressi järgi ariregister.rik.ee-st; heakskiidu "
                      "küsimuse vastab KÜ põhikiri, küsi ühistult kirjalikku "
                      "kinnitust" % prov)
    if status == STATUS_BANKRUPT:
        return None, ("KÜ on pankrotis - juhatuse heakskiidu küsimusele "
                      "hinnangut EI OLE: %s; halduri ja notari õigusaudit "
                      "enne broneerimislepingut" % prov)
    if status == STATUS_LIQUIDATION:
        return None, ("KÜ on likvideerimisel - juhatuse heakskiidu "
                      "küsimusele hinnangut EI OLE: %s; likvideerija ja "
                      "notari õigusaudit enne broneerimislepingut" % prov)
    return None, ("KÜ %s on registris - heakskiidu vajadusele hinnangut "
                  "EI OLE: põhikirja tekst on tasuline toimikudokument, "
                  "nõusolekuklausli sisu teab ainult ühistu; küsi "
                  "ühistult/müüjalt kirjalikku heakskiidu-kinnitust" % prov)


OVERTURN_ARIREG_DIMS = (
    ("trust_llc_transfer", "p361", dim_trust_llc_transfer),
    ("coop_approval", "p369", dim_coop_approval),
)


def score_overturn_arireg(entity: Optional[dict],
                          listing: Optional[dict] = None
                          ) -> Dict[str, Optional[int]]:
    """The p361/p369 overturn dims for one listing's joined entity
    (entry point for the weight-rebalance follow-up; keys match
    OVERTURN_ARIREG_DIMS)."""
    return {key: fn(entity, listing)[0] for key, _, fn in OVERTURN_ARIREG_DIMS}


def join_entity(basic: Optional[dict],
                holders: Optional[dict]) -> Optional[dict]:
    """Join one entity's Lihtandmed row with its Osanikud rows.

    Either side may be None (partial snapshot is honest); the
    result carries what is there. Returns None only when there is
    no basic row at all (no join key, nothing to score).
    """
    if not isinstance(basic, dict):
        return None
    entity = dict(basic)
    entity["shareholders"] = (
        list(holders.get("shareholders", []))
        if isinstance(holders, dict) else [])
    entity["pledges_present"] = (
        bool(holders.get("pledges_present", False))
        if isinstance(holders, dict) else False)
    entity["holders_joined"] = isinstance(holders, dict)
    return entity
