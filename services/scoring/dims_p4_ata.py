"""P4 Ametlikud Teadaanded (new uses) demo + coverage dims (issues #254, #335).

Demo (#254): Ametlikud Teadaanded ingestion for NEW uses beyond the
#233 probate scope — pankrotiteated, täitemenetlus/kohtutäitur, vara
arest/keelumärge, developer notices (Tallinn filter) — plus P4-020
end-to-end in Tallinn. Coverage (#335): the remaining 2 params that
consume the demoed ingestion (P4-004 restriction slice, P4-021
developer-notice slice).

Params (this agent only — overturn #233 owns the parameters3 p362
probate URI client in dims_group04*.py, which this module does NOT
touch; no shared/group files are edited):
* P4-020 Enforcement: pankrot/täitemenetlus on property (demo,
  per-entity dim, weak-good capped)
* P4-004 Kinnistus süva, AT slice: keelumärge/arest summary + notary
  checkpoint (per-listing dim, weak-good capped)
* P4-021 Developer/broker track record, AT slice: developer notices
  (per-entity dim, weak-good capped)

HONESTY (AGENTS.md section 7.2): the AT registry is NOT in the
2026-09-12 snapshot, so every dim returns None when its joined AT
record is missing — never a guess. "No notices found" is weak-good
(CAPPED, never 100): absence from the queried window/types is not
proof of clear title, and every clean reason says so. Scored reasons
always name the joined teadaanne (traceable to a notice); unknown
notice types and unknown currency stay NULL with the type named.
NULL stays NULL with an Estonian reason.

Openness verdict (2026-09-13, dated polite probes, cache /tmp/hf-ata):
* https://www.ametlikudteadaanded.ee/ -> HTTP 200, 92326 bytes.
* https://www.ametlikudteadaanded.ee/avalik/uriotsing -> HTTP 200,
  152108 bytes — documents the URI reuse scheme
  /ee/{andmeandja}/{pealiik}/{alaliik}/{aasta}/{kuu}/{paev}/
  {teate_number}/{xml,rdf}, publisher/type/date filters, HTML/XML/
  XML-RDF formats (1000-result cap per #233).
* The page's own documented XML example
  .../eesti-advokatuur/.../2019/06/13/1483034/xml -> HTTP 200
  (text/xml, 4171 bytes), real teadaanne schema observed
  (teate_number, liik/kood+nimi, andmeandja, puudutatud_isik,
  avaldamise/arhiveerimise_kpv, kinnitatud_sisu, sisendid).
Verdict: OPEN, anonymous pulls verified. fetch_notice_xml below
targets that URI layout with a daily TTL; the dims score ONLY joined
records. See docs/p4_ata.md for the full note. NEVER commit real
pulls — fixtures in tests are synthetic (invented entities).

Style mirrors services/scoring/dims_p4_ehr.py (issues #249/#333):
pure (ata, listing) -> (Optional[int 0..100], Estonian reason),
absolute bands, hermetic fixture tests. Network lives only in
fetch_notice_xml (single polite GET, file cache, TTL); tests never
call it.

Helpers are local copies (not imported from livability, sibling
batches, or dims_group04): a future central hook may import this
module alongside them, and importing any of them here would turn
that into a cycle (same precedent as batch B3, PR #100, and
group20a #212). In particular nothing is shared with the #233
probate client — the new-use ingestion stands alone.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR because the coverage issue body states
  it "extends the demoed ingestion" — splitting would ship an
  ingestion with one consumer, then re-touch every dim signature
  (same precedent as the EHR #249+#333 PR).
* TTL is daily (ATA_TTL_DAYS = 1), not weekly like EHR: enforcement
  notices are time-sensitive (a fresh arest freezes a deal today),
  and the 1000-result cap forces date-windowed re-pulls anyway.
  Matches the polite daily-cron convention (AGENTS.md section 5).
* Weak-good cap is 75 for all three (never 100): a clean AT window
  is weaker evidence than a joined registry record — the query
  covers only known notice types/date windows, and RIK/notary/TTJA
  are NOT joined. Each clean reason names the unjoined check.
* P4-021 appears twice on purpose with disjoint slices: dims_p4_ehr
  scores the EHR builder-completion slice (cap 80); this module
  scores the AT developer-notice slice (cap 75). Neither claims the
  full param; TTJA complaints stay unjoined in both.
* Active enforcement never scores 0: a notice can be stale,
  mis-joined, or superseded — 15/20 is strong-bad, never "worthless".
* The Tallinn gate (ata["tallinn"] is False -> NULL) keeps the demo
  scope honest: non-Tallinn joins are out of scope, not bad deals.
  A missing "tallinn" key defaults to relevant (older joins predate
  the flag; absence is not evidence either way).
* Personal data (puudutatud_isik names/codes) is parsed because the
  join needs it, but reasons echo ONLY notice type + dates — never
  a person name or code.

Integration (deliberately NOT done here): feeding these dims with
the listing's joined AT record inside livability scoring and
rebalancing livability.WEIGHTS must be one joint change across all
parameter batches — existing tests pin set(WEIGHTS) exactly, so
per-batch WEIGHTS edits would break every sibling.
"""

import html
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated AT URI-scheme XML pulls.
# ---------------------------------------------------------------------------

#: Daily bulk per the time-sensitive enforcement window (see docstring).
ATA_TTL_DAYS = 1

#: Verified 2026-09-13 (anonymous GETs, see module docstring).
AT_BASE_URL = "https://www.ametlikudteadaanded.ee"

USER_AGENT = ("home-finder AT ingest (polite daily pulls, single GET, "
              "file cache; contact via GitHub home-finder)")


def build_notice_url(publisher: str, group: str, subtype: str, year: int,
                     month: int, day: int, number: int,
                     fmt: str = "xml") -> str:
    """One AT URI-scheme URL per the documented /avalik/uriotsing layout."""
    return ("%s/ee/%s/%s/%s/%d/%d/%d/%d/%s"
            % (AT_BASE_URL, publisher, group, subtype,
               year, month, day, number, fmt))


def _cache_path(cache_dir: str, url: str) -> str:
    """Cache file for one AT notice URL (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in url)
    return os.path.join(cache_dir, "ata-%s.xml" % safe[-120:])


def cache_is_fresh(path: str, ttl_days: int = ATA_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_notice_xml(url: str, cache_dir: str = "/tmp/hf-cache",
                     ttl_days: int = ATA_TTL_DAYS) -> str:
    """Fetch one AT notice XML politely (single GET, cached, TTL-stated).

    Returns cached text when fresh; otherwise one GET with a polite
    User-Agent and a 30 s timeout. Transport errors RAISE (never cached
    as data, AGENTS.md section 7.2); HTTP errors raise too — an error
    body is never written to the cache. Treat HTTP 429 as a stop
    signal: it propagates, the stale cache is left untouched.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, url)
    if cache_is_fresh(path, ttl_days):
        with open(path, encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = resp.read()
    text = body.decode("utf-8")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------------------
# Parsing: AT teadaanne XML (namespace-tolerant, sparse-tolerant).
# Field layout observed 2026-09-13 on the site's own documented XML
# example (teate_number, liik/kood+nimi, mall, andmeandja,
# puudutatud_isik, avaldamise/arhiveerimise_kpv, kinnitatud_sisu,
# sisendid/sisendirida). Unknown elements are ignored; missing
# elements read as None (never guessed).
# ---------------------------------------------------------------------------

#: Canonical record keys produced by parse_notice_xml (all Optional
#: except "archived", which ingest always sets via is_archived).
ATA_FIELDS = (
    "notice_id", "url", "liik_kood", "liik_nimi", "mall_nimi",
    "andmeandja", "puudutatud_nimi", "puudutatud_kood", "avaldatud",
    "arhiveeritud", "archived", "sisu",
)


def _local(tag: str) -> str:
    return tag.split("}")[-1].split(":")[-1]


def _child_text(elem: ET.Element, name: str) -> Optional[str]:
    for child in elem:
        if _local(child.tag) == name:
            text = "".join(child.itertext()).strip()
            return text if text else None
    return None


def _strip_html(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    unescaped = html.unescape(raw)
    stripped = re.sub(r"<[^>]+>", " ", unescaped)
    collapsed = re.sub(r"\s+", " ", stripped).strip()
    return collapsed if collapsed else None


def parse_kpv(raw: Optional[str]) -> Optional[date]:
    """Parse an AT dd.mm.yyyy date; unparseable/missing -> None."""
    if not raw:
        return None
    parts = raw.strip().split(".")
    if len(parts) != 3:
        return None
    try:
        day, month, year = (int(p) for p in parts)
        return date(year, month, day)
    except ValueError:
        return None


def is_archived(arhiveeritud: Optional[str],
                today: Optional[date] = None) -> Optional[bool]:
    """Currency of a notice from its arhiveerimise_kpv (None = unknown)."""
    day = parse_kpv(arhiveeritud)
    if day is None:
        return None
    return day < (today if today is not None else date.today())


def parse_notice_xml(xml_text: str,
                     today: Optional[date] = None) -> Dict[str, Optional[object]]:
    """Parse one AT teadaanne XML into a canonical per-notice record.

    Namespace-tolerant (matches by local tag name); sparse-tolerant
    (absent elements become None). "archived" is always set via
    is_archived (None when the archive date is missing/unparseable —
    dims treat that as unknown currency, never as active).
    """
    root = ET.fromstring(xml_text.lstrip("﻿"))
    rec = {field: None for field in ATA_FIELDS}  # type: Dict[str, Optional[object]]
    rec["notice_id"] = _child_text(root, "teate_number") or _child_text(root, "id")
    rec["url"] = _child_text(root, "url")
    for child in root:
        local = _local(child.tag)
        if local == "liik" and rec["liik_nimi"] is None:
            # First <liik> is the notice type; a nested one inside
            # <puudutatud_isik> describes the person, not the notice.
            rec["liik_kood"] = _child_text(child, "kood")
            rec["liik_nimi"] = _child_text(child, "nimi")
        elif local == "mall":
            rec["mall_nimi"] = _child_text(child, "nimi")
        elif local == "andmeandja":
            rec["andmeandja"] = _child_text(child, "nimi")
        elif local == "puudutatud_isik":
            perenimi = _child_text(child, "nimi")
            eesnimi = _child_text(child, "eesnimi")
            if perenimi and eesnimi:
                rec["puudutatud_nimi"] = "%s %s" % (eesnimi, perenimi)
            else:
                rec["puudutatud_nimi"] = perenimi or eesnimi
            rec["puudutatud_kood"] = _child_text(child, "kood")
        elif local == "avaldamise_kpv":
            rec["avaldatud"] = (child.text or "").strip() or None
        elif local == "arhiveerimise_kpv":
            rec["arhiveeritud"] = (child.text or "").strip() or None
        elif local == "kinnitatud_sisu":
            rec["sisu"] = _strip_html("".join(child.itertext()))
    rec["archived"] = is_archived(
        rec["arhiveeritud"] if isinstance(rec["arhiveeritud"], str) else None,
        today=today)
    return rec


def mentions_tallinn(notice: Optional[dict]) -> bool:
    """Tallinn-filter helper: does the joined notice mention Tallinn?"""
    if not isinstance(notice, dict):
        return False
    for key in ("sisu", "andmeandja", "puudutatud_nimi"):
        value = notice.get(key)
        if isinstance(value, str) and "tallinn" in value.lower():
            return True
    return False


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _ata(ata: Optional[dict]) -> Optional[dict]:
    return ata if isinstance(ata, dict) else None


def _missing_ata() -> Score:
    return None, ("Ametlike Teadaannete kirje puudub — teadaannete "
                  "andmeteta skoori EI OLE (hinnangut ei anta): kontrolli "
                  "ametlikudteadaanded.ee URI-otsingust")


def _not_tallinn() -> Score:
    return None, ("Teadaanne ei ole Tallinna-filteriga (EI OLE hinnangut): "
                  "demo ulatus on Tallinn — väljaspool linna skoori ei anta")


def _notices(ata: dict) -> Optional[List[dict]]:
    raw = ata.get("notices")
    if not isinstance(raw, list):
        return None
    return [n for n in raw if isinstance(n, dict)]


def _liik(notice: dict) -> str:
    value = notice.get("liik_nimi")
    return "" if value is None else str(value).strip().lower()


_PANKROT = ("pankrot",)
_TAIT = ("täitemenetlus", "täitur", "kohtutäitur")
_AREST = ("arest", "keelumärk")
_AUCTION = ("enampakkumi",)


def _classify(notice: dict) -> str:
    """Notice kind from liik_nimi keyword STEMS ("unknown" never guessed).

    Stems, not full words: AT liik names inflect (enampakkumise,
    keelumärke, täitemenetluse), so full-word matching would miss the
    genitive forms the registry actually uses."""
    liik = _liik(notice)
    if any(k in liik for k in _PANKROT):
        return "pankrot"
    if any(k in liik for k in _TAIT):
        return "tait"
    if any(k in liik for k in _AREST):
        return "arest"
    if any(k in liik for k in _AUCTION):
        return "auction"
    return "unknown"


def _is_active(notice: dict) -> Optional[bool]:
    """True = published window open; False = archived; None = unknown."""
    flag = notice.get("archived")
    if not isinstance(flag, bool):
        return None
    return not flag


def _describe(notice: dict) -> str:
    liik = notice.get("liik_nimi")
    name = str(liik).strip() if liik else "nimetu teade"
    num = notice.get("notice_id")
    tail = " nr %s" % num if num else ""
    return "%s%s" % (name, tail)


def _gate(ata: Optional[dict]) -> Tuple[Optional[dict], Optional[Score]]:
    """Shared join gates: missing record / Tallinn scope / notice list."""
    rec = _ata(ata)
    if rec is None:
        return None, _missing_ata()
    if rec.get("tallinn", True) is False:
        return None, _not_tallinn()
    notices = _notices(rec)
    if notices is None:
        return None, (None, "Ametlike Teadaannete loend puudub (EI OLE "
                            "hinnangut): liidestus ei tagastanud teateid")
    return rec, None


def _split(notices: List[dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    """Split joined notices into (active, archived, unknown-currency)."""
    active, archived, unknown = [], [], []
    for notice in notices:
        flag = _is_active(notice)
        if flag is True:
            active.append(notice)
        elif flag is False:
            archived.append(notice)
        else:
            unknown.append(notice)
    return active, archived, unknown


# ---------------------------------------------------------------------------
# P4-020 (demo): enforcement layer — pankrot/täitemenetlus on the
# property/developer. Per-entity dim, weak-good capped at 75.
# ---------------------------------------------------------------------------

def dim_enforcement(ata: Optional[dict],
                    listing: Optional[dict] = None) -> Score:
    """P4-020: active enforcement is strong-bad (15); clean caps at 75."""
    rec, gated = _gate(ata)
    if gated is not None or rec is None:
        return gated  # type: ignore[return-value]
    notices = _notices(rec)
    assert notices is not None
    if not notices:
        return (75, "Ametlikes Teadaannetes kehtivaid täite-/pankroti-/"
                    "arestiteateid ei leitud (nõrk hea teadaandeakna "
                    "põhjal, mitte hinnang) — EI OLE puhta tiitli tõend: "
                    "RIK/notar kontrollib sulgemise")
    active, archived, unknown = _split(notices)
    for notice in active:
        if _classify(notice) in ("pankrot", "tait", "arest"):
            return (15, "Kehtiv täitemenetlus: %s (Ametlike Teadaannete "
                        "andmed, mitte hinnang) — tehing võib olla "
                        "külmutatud, notar/kohtutäitur kinnitab"
                    % _describe(notice))
    for notice in active:
        if _classify(notice) == "auction":
            return (45, "Kehtiv enampakkumisteade: %s (Ametlike "
                        "Teadaannete andmed, mitte hinnang) — sundmüügi "
                        "kontekst, hinda ettevaatlikult"
                    % _describe(notice))
    for notice in active:
        if _classify(notice) == "unknown":
            return None, ("Tundmatu kehtiv teateliik (%s) — EI OLE "
                          "hinnangut, loe teadaanne ametlikest "
                          "teadaannetest" % _describe(notice))
    for notice in unknown:
        return None, ("Teadaande kehtivus teadmata (%s, arhiivikuupäev "
                      "puudub) — EI OLE hinnangut" % _describe(notice))
    return (55, "Ainult arhiveeritud täite-/arestiteated (%d, Ametlike "
                "Teadaannete andmed, mitte hinnang) — ajalugu teada, "
                "kehtivat piirangut pole" % len(archived))


# ---------------------------------------------------------------------------
# P4-004 (coverage): kinnistus süva, AT restriction slice — keelumärge/
# arest summary + notary checkpoint. Per-listing dim, weak-good cap 75.
# RIK/notary stay the primary source; AT is one slice of it.
# ---------------------------------------------------------------------------

def dim_kinnistus_checkpoint(ata: Optional[dict],
                             listing: Optional[dict] = None) -> Score:
    """P4-004: active restriction is 20 + notary pointer; clean caps 75."""
    rec, gated = _gate(ata)
    if gated is not None or rec is None:
        return gated  # type: ignore[return-value]
    notices = _notices(rec)
    assert notices is not None
    if not notices:
        return (75, "Ametlikes Teadaannetes kehtivaid keelumärke/areste "
                    "ei leitud (nõrk hea teadaandeakna põhjal, mitte "
                    "hinnang) — EI OLE puhta tiitli tõend: notarikontroll "
                    "(notar.ee) jääb enne pakkumist")
    active, archived, unknown = _split(notices)
    for notice in active:
        if _classify(notice) in ("arest", "pankrot", "tait"):
            return (20, "Kehtiv piirang: %s (Ametlike Teadaannete andmed, "
                        "mitte hinnang) — sulgemiskõlblikkus selgub "
                        "notarikontrollist (notar.ee) enne pakkumist"
                    % _describe(notice))
    for notice in active:
        if _classify(notice) == "auction":
            return (50, "Kehtiv enampakkumisteade: %s (Ametlike "
                        "Teadaannete andmed, mitte hinnang) — "
                        "notarikontroll (notar.ee) enne pakkumist"
                    % _describe(notice))
    for notice in active:
        if _classify(notice) == "unknown":
            return None, ("Tundmatu kehtiv teateliik (%s) — EI OLE "
                          "hinnangut; notarikontroll (notar.ee) "
                          "selgitab" % _describe(notice))
    for notice in unknown:
        return None, ("Teadaande kehtivus teadmata (%s, arhiivikuupäev "
                      "puudub) — EI OLE hinnangut" % _describe(notice))
    return (60, "Ainult arhiveeritud piiranguteated (%d, Ametlike "
                "Teadaannete andmed, mitte hinnang) — notarikontroll "
                "(notar.ee) kinnitab kehtiva seisu" % len(archived))


# ---------------------------------------------------------------------------
# P4-021 (coverage): developer/broker track record, AT developer-notice
# slice. Per-entity dim, weak-good cap 75 (TTJA/EHR NOT joined — the
# EHR builder-history slice lives in dims_p4_ehr, cap 80).
# ---------------------------------------------------------------------------

def dim_developer_track(ata: Optional[dict],
                        listing: Optional[dict] = None) -> Score:
    """P4-021: developer pankrot is 20; clean caps at 75 (no TTJA)."""
    rec, gated = _gate(ata)
    if gated is not None or rec is None:
        return gated  # type: ignore[return-value]
    entity = rec.get("entity")
    if not entity or not str(entity).strip():
        return None, ("Arendaja/müüja nimi liidestuses puudub (EI OLE "
                      "hinnangut): TTJA kaebusi ja EHR ajalugu kontrolli "
                      "eraldi")
    who = str(entity).strip()
    notices = _notices(rec)
    assert notices is not None
    if not notices:
        return (75, "Arendaja %s kohta kehtivaid teadaandeid ei leitud "
                    "(nõrk hea teadaandeakna põhjal, mitte hinnang) — "
                    "EI OLE usaldusväärsuse tõend: TTJA kaebuste ja EHR "
                    "ehitusloo kontroll eraldi, ülempiir 75" % who)
    active, archived, unknown = _split(notices)
    for notice in active:
        if _classify(notice) in ("pankrot", "tait"):
            return (20, "Arendaja %s: kehtiv menetlus %s (Ametlike "
                        "Teadaannete andmed, mitte hinnang) — TTJA "
                        "kaebuste kontroll eraldi" % (who, _describe(notice)))
    for notice in active:
        if _classify(notice) in ("arest", "auction"):
            return (45, "Arendaja %s: kehtiv varateade %s (Ametlike "
                        "Teadaannete andmed, mitte hinnang) — usaldust "
                        "ei hinnata" % (who, _describe(notice)))
    for notice in active:
        if _classify(notice) == "unknown":
            return None, ("Tundmatu kehtiv teateliik arendaja %s kohta "
                          "(%s) — EI OLE hinnangut" % (who, _describe(notice)))
    for notice in unknown:
        return None, ("Teadaande kehtivus teadmata (%s, arhiivikuupäev "
                      "puudub) — EI OLE hinnangut" % _describe(notice))
    return (60, "Arendaja %s kohta ainult arhiveeritud teated (%d, "
                "Ametlike Teadaannete andmed, mitte hinnang) — TTJA "
                "kaebuste kontroll eraldi" % (who, len(archived)))


P4_ATA_DIMS = (
    ("enforcement", "P4-020", dim_enforcement),
    ("kinnistus_checkpoint", "P4-004", dim_kinnistus_checkpoint),
    ("developer_track", "P4-021", dim_developer_track),
)


def score_p4_ata(ata: Optional[dict],
                 listing: Optional[dict] = None) -> Dict[str, Optional[int]]:
    """All three P4 ATA dims for one listing (keys match P4_ATA_DIMS)."""
    return {key: fn(ata, listing)[0] for key, _, fn in P4_ATA_DIMS}
