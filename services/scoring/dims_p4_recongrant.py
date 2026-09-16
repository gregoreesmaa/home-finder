"""P4 renovation-grant dims (issue #538): EISA apartment-reconstruction
grants (korterelamute rekonstrueerimine) as a per-building join scorer.

Source (probed 2026-09-16, one polite GET each, labelled one-off
User-Agent, `--max-time 60`, raw file at /tmp/hf-probes/ -- one-off PR
record, never committed):
* Catalogue: https://andmed.eesti.ee/datasets/korterelamute-rekonstrueerimise-toetamine
  (publisher: Enterprise and Innovation Foundation EISA, SFOS
  structural-assistance register data, licence CC BY, updated
  2026-08-06).
* Direct file: https://andmed.eesti.ee/api/v2/datasets/858e5768-.../file
  -> HTTP 302 to a signed S3 URL
  (Korterelamute-rekonstrueerimise-toetamine.xlsx) -> HTTP 200,
  163 884 bytes, application/octet-stream, Excel 2007+.
* Workbook: 1 sheet ("Sheet 1"), 15 columns, 1313 data rows:
  Jrk nr | Programmperiood | Meede | Taotlusvoor | Aadress | Maakond |
  KOV | Projekti rahastamise kp | Projekti lopetamise kp |
  Projekti seisund | Ehitusregistrikood (trailing space in header!) |
  Projekti kogumaksumus | Toetus | Hoone pindala | Korterite arv.
* Coverage: Harju maakond 277 rows (21.1%); top counties Harju 277,
  Tartu 217, Laane-Viru 178. EHR-code fill: 650/1313 overall (49.5%),
  108/277 Harjumaa (39.0%) -- well above the issue's 20% token bar, so
  the EHR join path is real (108 Harjumaa rows >> 20 required) with the
  normalised-address fallback for the rest.
* Status values: Lopetatud 916, Rahastatud 396 (+1 blank row).
  Periods: 2014-2020 (632), 2021-2027 (567), 2020-2026 (113).
  Funding years 2015-2026 (peak 2021: 189, 2026: 154 -- ongoing round).
  Sample EHR codes: 116002151, 116063782, 121292342 (9-digit EHR shape).
* No depth/quality columns (no energy class before/after): grant !=
  quality -- the legend must say so (issue non-goal).

Params (this module only -- sibling batches own disjoint sets):
* P4-010 renovation-grant status, EISA SFOS leg: grant received
  (year + status) -> renovated-stock score. The kliimakava
  district-target leg stays in dims_p4_kliima, the EIS register leg in
  dims_p4_eis, the EHR mirror slice in dims_p4_ehr, the HOA buyer-side
  legs in Group 17 -- distinct dim keys, no double-score.

HONESTY (AGENTS.md section 7.2): no grant match stays NULL -- never
"unrenovated" (rounds are incomplete by publisher statement: some
rounds did not collect the EHR code). Reasons say "EI OLE" and point
at the KÜ-document check. Transport errors RAISE (never cached as
data); HTTP 429 propagates (stop signal).

Style mirrors services/scoring/dims_p4_emta.py (#256/#337): pure
(join record, index) -> (Optional[int 0..100], Estonian reason),
absolute status bands, hermetic fixture tests. Network lives only in
fetch_grants_xlsx (single polite GET, file cache, TTL); tests never
call it. The XLSX reader below is stdlib-only (zipfile + ElementTree)
because openpyxl is not in requirements.txt -- it reads the
publisher's exact layout (shared strings + plain numbers, first sheet).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Bands are status-based (Lopetatud 75 / Rahastatud 60 / other matched
  status 50 neutral), NOT grant-share-based: Toetus/kogumaksumus varies
  by round rules (508k/1068k vs 334k/828k in the probe), so a share
  cutoff would re-punish older rounds. Recency rides in the reason
  (funding year), not the score.
* EHR-code join outranks the address join (codes are exact; addresses
  vary in punctuation). An address-only hit scores the same band but
  the reason names the weaker join. KOV spellings keep the publisher's
  leading space trimmed (" Anija vald" observed) -- trim, never guess.
* The header "Ehitusregistrikood " carries a trailing space in the
  publisher file: the reader matches headers stripped + lowercased, so
  a fixed upstream header keeps working and a renamed one yields zero
  columns (dims stay NULL -- the honest failure mode).

Integration (deliberately NOT done here): feeding this dim with the
listing's EHR code / AKS address inside livability scoring and
rebalancing livability.WEIGHTS must be one joint change across all
parameter batches -- existing tests pin set(WEIGHTS) exactly, so
per-batch WEIGHTS edits would break every sibling.
"""

import os
import time
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated XLSX pull + stdlib reader.
# ---------------------------------------------------------------------------

#: Direct file URL (andmed.eesti.ee distribution -> signed S3 redirect).
GRANTS_FILE_URL = (
    "https://andmed.eesti.ee/api/v2/datasets/"
    "858e5768-6f22-4f85-911b-c8150b780ef9/distribution/"
    "f68abab5-9729-436c-ba00-8382c640254e/file"
)

#: IRREG feed (publisher) -> annual re-probe at most (issue constraint).
GRANTS_TTL_DAYS = 365

#: CC BY: attribute "EISA / andmed.eesti.ee" wherever scores surface.
GRANTS_ATTRIBUTION = "EISA (ettevotlus- ja innovatsioonifond), andmed.eesti.ee, CC BY"

USER_AGENT = ("home-finder EISA recongrant ingest (polite annual pulls, "
              "single GET, file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str) -> str:
    """Cache file for the publisher XLSX (flat dir, fixed name)."""
    return os.path.join(cache_dir, "eisa-recongrant.xlsx")


def cache_is_fresh(path: str, ttl_days: int = GRANTS_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_grants_xlsx(url: str = GRANTS_FILE_URL,
                      cache_dir: str = "/tmp/hf-cache",
                      ttl_days: int = GRANTS_TTL_DAYS) -> str:
    """Fetch the publisher XLSX politely (single GET, cached, TTL-stated).

    Returns the local path. Cached bytes are returned when fresh;
    otherwise one GET with a polite User-Agent (redirects followed to
    the signed S3 URL) and a 60 s timeout. Transport errors RAISE
    (never cached as data); HTTP errors raise too; HTTP 429
    propagates (stop signal, stale cache left untouched).
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir)
    if cache_is_fresh(path, ttl_days):
        return path
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        body = resp.read()
    with open(path, "wb") as f:
        f.write(body)
    return path


#: Publisher header (stripped + lowercased) -> record field.
HEADER_MAP = {
    "jrk nr": "seq",
    "programmperiood": "period",
    "meede": "measure",
    "taotlusvoor": "round",
    "aadress": "address",
    "maakond": "county",
    "kov": "kov",
    "projekti rahastamise kp": "funded",
    "projekti lõpetamise kp": "completed",
    "ehitusregistrikood": "ehr",
    "projekti kogumaksumus": "cost_eur",
    "toetus": "grant_eur",
    "hoone pindala": "area_m2",
    "korterite arv": "flats",
    "projekti seisund": "status",
}

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _cell_text(cell: ET.Element, shared: List[str]) -> str:
    """Text of one sheet <c> cell (shared string, inline, or literal)."""
    kind = cell.get("t")
    if kind == "s":
        v = cell.findtext("m:v", namespaces=_NS)
        if not v:
            return ""
        try:
            return shared[int(float(v))]
        except (ValueError, IndexError, TypeError):
            return ""
    if kind == "inlineStr":
        return "".join(cell.itertext()).strip()
    v = cell.findtext("m:v", namespaces=_NS)
    return (v or "").strip()


def parse_grants_xlsx(path: str) -> List[Dict[str, Optional[object]]]:
    """Parse the publisher XLSX into grant records (stdlib-only).

    Reads the first sheet; headers are matched stripped + lowercased
    (the publisher's "Ehitusregistrikood " trailing space included).
    Sparse-tolerant: unknown/missing cells read as None; rows without
    any mapped content are skipped. An unreadable archive RAISES
    (transport/parse errors are never data).
    """
    with zipfile.ZipFile(path) as z:
        try:
            shared_xml = z.read("xl/sharedStrings.xml")
        except KeyError:
            shared_xml = b""
        sheet_name = next(
            n for n in z.namelist()
            if n.startswith("xl/worksheets/sheet")
        )
        sheet_xml = z.read(sheet_name)
    shared: List[str] = []
    if shared_xml:
        for si in ET.fromstring(shared_xml).findall("m:si", _NS):
            shared.append("".join(si.itertext()))
    records: List[Dict[str, Optional[object]]] = []
    header: List[str] = []
    for row in ET.fromstring(sheet_xml).findall(".//m:row", _NS):
        cells = [_cell_text(c, shared) for c in row.findall("m:c", _NS)]
        if not any(c.strip() for c in cells):
            continue
        if not header:
            header = [HEADER_MAP.get(c.strip().lower(), "") for c in cells]
            continue
        rec: Dict[str, Optional[object]] = {}
        for key, val in zip(header, cells):
            if not key:
                continue
            rec[key] = val.strip() or None
        for numkey in ("cost_eur", "grant_eur", "area_m2", "flats"):
            raw = rec.get(numkey)
            if isinstance(raw, str):
                try:
                    rec[numkey] = float(raw.replace(" ", "").replace(",", "."))
                except ValueError:
                    rec[numkey] = None
        if any(v is not None for v in rec.values()):
            records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Join: EHR-code index with a normalised-address fallback.
# ---------------------------------------------------------------------------

def normalise_address(address: str) -> str:
    """Lowercase + whitespace collapse (no suffix games, no guessing)."""
    return " ".join(address.lower().split())


def build_grants_index(
        records: List[Dict[str, Optional[object]]]
) -> Dict[str, Dict[str, List[Dict[str, Optional[object]]]]]:
    """Index grant records by EHR code and by normalised address."""
    index: Dict[str, Dict[str, List[Dict[str, Optional[object]]]]] = {
        "ehr": {}, "address": {},
    }
    for rec in records:
        ehr = rec.get("ehr")
        if isinstance(ehr, str) and ehr.strip():
            index["ehr"].setdefault(ehr.strip(), []).append(rec)
        addr = rec.get("address")
        if isinstance(addr, str) and addr.strip():
            index["address"].setdefault(normalise_address(addr), []).append(rec)
    return index


def _band_for(status: Optional[object], year: Optional[object]) -> Score:
    """Status band: completed 75 / funded 60 / other matched 50."""
    when = " (rahastatud %s)" % year if year else ""
    if status == "Lõpetatud":
        return 75, ("Korterelamu rekonstrueeritud EISA toetusel%s -- "
                    "fassaad/soojus/ventilatsioon toetatud hoone, "
                    "toetus ei ole kvaliteedihinne" % when)
    if status == "Rahastatud":
        return 60, ("Korterelamu rekonstrueerimine EISA toetusel%s -- "
                    "toetus määratud, tööd pooleli või aruandluses, "
                    "küsi KÜ-lt seisu" % when)
    return 50, ("Korterelamu EISA toetuskirjes (seisund: %s%s) -- "
                "täpsusta KÜ-lt ja EISA registrist" % (status, when))


def dim_recongrant(
        ehr_code: Optional[str],
        address: Optional[str],
        index: Optional[Dict[str, Dict[str, List[Dict[str, Optional[object]]]]]],
) -> Score:
    """P4-010 EISA leg: NULL unless the building has a grant record.

    EHR-code hits outrank address hits. No match -> NULL (never
    "unrenovated"): rounds are incomplete by publisher statement, so
    absence is not evidence. Every NULL carries EI OLE + the KÜ check.
    """
    if index:
        if ehr_code and ehr_code.strip():
            hits = index["ehr"].get(ehr_code.strip())
            if hits:
                rec = sorted(
                    (h for h in hits),
                    key=lambda h: str(h.get("funded") or ""),
                    reverse=True,
                )[0]
                score, reason = _band_for(rec.get("status"), rec.get("funded"))
                return score, "EHR %s: %s" % (ehr_code.strip(), reason)
        if address and address.strip():
            hits = index["address"].get(normalise_address(address))
            if hits:
                rec = sorted(
                    (h for h in hits),
                    key=lambda h: str(h.get("funded") or ""),
                    reverse=True,
                )[0]
                score, reason = _band_for(rec.get("status"), rec.get("funded"))
                return score, ("%s (aadressivaste, nõrgem kui EHR-kood)"
                               % reason)
    return None, ("Renoveerimistoetuse kirjet pole (EI OLE EISA "
                  "korterelamute rekonstrueerimise kirjet selle hoone "
                  "kohta -- registri voorud on puudulikud, puudumine ei "
                  "tähenda renoveerimata hoonet): kontrolli KÜ "
                  "remondifondi/eelarvet ja küsi renoveerimisvõla seisu")


#: Registry for UI/API wiring on integration: param -> (title, fn).
P4_RECONGRANT_DIMS: Dict[str, Tuple[str, object]] = {
    "recongrant": ("Renoveerimistoetus (EISA)", dim_recongrant),
}


def score_p4_recongrant(
        ehr_code: Optional[str],
        address: Optional[str],
        index: Optional[Dict[str, Dict[str, List[Dict[str, Optional[object]]]]]],
) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All P4-recongrant dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in P4_RECONGRANT_DIMS.items():
        v, reason = fn(ehr_code, address, index)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
