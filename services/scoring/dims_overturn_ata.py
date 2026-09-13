"""Overturn dim for p362 probate and estate sale delays (issue #233).

Param: p362 probate and estate sale delays (parameters3.md section
5.4, Group 4). Canonical scorer stays
dims_group04.dim_probate_delay (batch #204) -- this module does NOT
replace it and edits NO shared/group files. It adds the honest
per-listing/estate signal the G4 reasoning said would overturn the
verdict ("Ametlikud Teadaanded for p362", docs/nomap.md section 3
G4): a polite URI-query client over the free public AT feed plus
one scored-or-None dim over JOINED probate windows.

Relationship to services/scoring/dims_p4_ata.py (issues #254/#335,
READ to avoid overlap -- NOT edited, NOT imported): that module
owns the NEW-use AT ingestion (pankrot/taitemenetlus/arest/
developer slices, P4-020/P4-004/P4-021) with its own single-notice
fetch. This
module owns ONLY the p362 probate-notice slice: the notary-publisher
+ parimisteated-type + month/day-window LIST client (which
dims_p4_ata does not have), the probate list parser, and the p362
dim. Helpers are local copies (not imported from dims_p4_ata,
livability, or sibling batches): a future central hook may import
this module alongside them, and importing any of them here would
turn that into a cycle (same precedent as batch B3, PR #100,
group20a #212, and overturn #240).

OVERTURN EVIDENCE (2026-09-13, polite: 2 successful GETs with a
labelled one-off user-agent, paced >= 4 s apart, headers +
visible-text/element-name scope read only, bodies at /tmp/hf-ata233/
-- one-off PR record, NEVER committed; full log docs/overturn_ata.md):
* https://www.ametlikudteadaanded.ee/avalik/uriotsing -> HTTP 200
  (152469 bytes): documents the URI reuse layout
  /ee/{andmeandja}/{pealiik}/{alaliik}/{aasta}/{kuu}/{paev}/
  {teate_number}/{xml,rdf,txt}, trailing components droppable,
  "-" wildcard for publisher/type mid-URI (opens a matching NOTICE
  LIST), list download by appending "xml", and the cap "NB!
  Otsingus kuvatakse vaid 1000 esimest tulemust!". Privacy
  carve-out covers only individually-served and archived notices --
  probate-initiation notices are public.
* https://www.ametlikudteadaanded.ee/ee/-/parimisteated/
  parimismenetluse-algatamine/2026/9/xml -> HTTP 200, text/xml,
  2672862 bytes: 417 "Pärimismenetluse algatamise teade" notices,
  publishers 417/417 starting with "Notar" (per-notary andmeandja
  names, percent-encoded in notice URLs). Element census (names
  only): teadaanded/teadaanne, teate_number, url, liik (kood+nimi),
  andmeandja, avaldamise_kpv + arhiveerimise_kpv (currency on every
  notice), kinnitatud_sisu, sisendid rows named
  parandaja_surmakuupaev / parandaja_sunnikuupaev /
  toestamise_tahtpaev / toestamise_kuupaev / parandaja_endine_nimi /
  testamendi_info / muude -- NO address/kinnistu/katastritunnus
  field. The feed resolves per ESTATE (deceased), never per parcel:
  the listing->estate join needs the deceased identity, so the dim
  scores ONLY joined windows and stays NULL without one.
* September 1-13 already holds 417 initiation notices: a full month
  can approach the 1000-result cap, so the client queries month
  windows and splits to day windows when needs_split fires.
* One transient read timeout on the 2.6 MB month pull (retried once
  politely, then succeeded): large windows can time out, so
  fetch_probate_window keeps the 30 s timeout, RAISES on transport
  errors, and NEVER caches partial/error bodies as data.

HONESTY (AGENTS.md section 7.2): the AT registry is NOT in the
2026-09-12 snapshot, so the dim returns None whenever its joined
probate window is missing -- never a guess. "No notices found" is
weak-good CAPPED at 75 (never 100): absence from the queried
window/types is not proof of clear title, and the clean reason
says so. Scored reasons name the joined teadaanne (type + number +
dates -- traceable to a notice); reasons echo NEVER a person name
or code (puudutatud_isik / parandaja values stay in the runtime
record only). Unknown notice types and unknown currency stay NULL
with the type named. Paid facts stay NULL: the e-Kinnistusraamat
extract (ownership, encumbrances) is Tier 2 PAID and remains owned
by the dims_group04 NULL dims (untouched) -- this dim answers only
"is there an open parimismenetlus in the joined window?", and area
gradients stay invalid even then (per-estate signal, nomap.md G4).

Style mirrors services/scoring/dims_p4_ata.py (the closest scored
AT sibling): pure (probate, listing) -> (Optional[int 0..100],
Estonian reason), absolute bands, hermetic fixture tests. Network
lives only in fetch_probate_window (single polite GET, file cache,
TTL); tests never call it.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Window TTL is weekly (ATA_PROBATE_TTL_DAYS = 7), not daily like
  dims_p4_ata: a month window is ~2.6 MB, and probate delays evolve
  over weeks, not hours. Per-notice freshness comes from the
  arhiveerimise_kpv currency field, not re-pull frequency. Matches
  the polite daily-cron ceiling (AGENTS.md section 5) with margin.
* Weak-good cap is 75 (never 100): a clean AT window is weaker
  evidence than a joined registry record -- the query covers only
  known probate types/date windows, and e-Kinnistusraamat/notar
  are NOT joined. The clean reason names the unjoined check.
* Active initiation never scores 0: a notice can be stale,
  mis-joined (deceased-name collision), or superseded -- 20 is
  strong-bad, never "worthless". Same never-zero precedent as
  dims_p4_ata (15/20, not 0).
* Archived-only scores 60 (not clean 75): history is known, no
  active delay -- between clean and active, mirroring the sibling
  55/60 archived bands.
* Stems, not full words, for classification: AT liik names inflect
  (parimismenetluse/parimismenetlus) and URI slugs strip
  diacritics (parimisteated slug vs Pärimisteated display) -- full-word or
  ASCII-only matching would miss the forms the registry uses.
* Personal data (puudutatud_isik names/codes, parandaja dates) is
  parsed because the estate join needs it, but reasons echo ONLY
  notice type + number + dates -- never a person name or code.
* The "-" wildcard publisher is the DEFAULT query scope (per-notary
  slugs vary by proceeding); a concrete notary slug narrows it.
  Publisher names are echoed NOWHERE (not even notary names):
  the teate_number already traces to the notice.

Integration (deliberately NOT done here): feeding this dim with the
listing's joined probate window inside livability scoring and
rebalancing livability.WEIGHTS must be one joint change across all
parameter batches -- existing tests pin set(WEIGHTS) exactly, so
per-batch WEIGHTS edits would break every sibling. Updating the
GROUP04 verdict entry and docs/nomap.md stays with the final
docs-index PR. No shared/group files are edited here.
"""

import html
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Overturn probe date (2026-09-13) -- the day the two polite checks
#: above ran.
VERDICT_DATE = "2026-09-13"

#: Re-check the AT URI scheme + probate volume (cap pressure, schema
#: drift) no later than this date.
RECHECK_AFTER = "2027-03-13"

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated probate-window pulls.
# ---------------------------------------------------------------------------

#: Weekly bulk: month windows are megabytes; freshness comes from the
#: archive-date currency field, not re-pull frequency (see docstring).
ATA_PROBATE_TTL_DAYS = 7

#: Verified 2026-09-13 (anonymous GETs, see module docstring).
AT_BASE_URL = "https://www.ametlikudteadaanded.ee"

#: Documented cap: "Otsingus kuvatakse vaid 1000 esimest tulemust!"
PROBATE_RESULT_CAP = 1000

#: Probate notice group slug (pealiik), verified on /avalik/uriotsing.
PROBATE_GROUP = "parimisteated"

#: Initiation subtype slug (alaliik) -- the p362 delay signal.
PROBATE_SUBTYPE_INITIATION = "parimismenetluse-algatamine"

#: Other observed parimisteated subtype slugs (same group, for window
#: clients that need the full probate picture; NOT scored here).
PROBATE_SUBTYPE_HEIR_SUMMONS = "parijate-valjaselgitamise-yleskutsemen"
PROBATE_SUBTYPE_INITIATION_AND_SUMMONS = (
    "parimismenetluse-algat-ja-parijate-valjaselgitamise-yleskutsemen")

USER_AGENT = ("home-finder AT probate ingest (polite weekly pulls, "
              "single GET, file cache; contact via GitHub home-finder)")


def build_probate_list_url(publisher: str = "-",
                           group: str = PROBATE_GROUP,
                           subtype: str = PROBATE_SUBTYPE_INITIATION,
                           year: int = 2026, month: int = 9,
                           day: Optional[int] = None,
                           fmt: str = "xml") -> str:
    """One AT probate LIST URL per the documented /avalik/uriotsing layout.

    Publisher "-" is the documented wildcard (per-notary andmeandja
    names vary by proceeding; pass a registered notary slug to
    narrow). Day is None for month windows; pass a day to split a
    window that hit PROBATE_RESULT_CAP. Appending "xml" downloads
    the list results as XML (documented).
    """
    quoted = urllib.parse.quote(publisher, safe="-")
    parts = [AT_BASE_URL, "ee", quoted, group, subtype,
             str(year), str(month)]
    if day is not None:
        parts.append(str(day))
    parts.append(fmt)
    return "/".join(parts)


def build_probate_notice_url(publisher: str, group: str, subtype: str,
                             year: int, month: int, day: int,
                             number: int, fmt: str = "xml") -> str:
    """One AT single-notice URL (same documented layout, no wildcards)."""
    quoted = urllib.parse.quote(publisher, safe="-")
    return ("%s/ee/%s/%s/%s/%d/%d/%d/%d/%s"
            % (AT_BASE_URL, quoted, group, subtype,
               year, month, day, number, fmt))


def needs_split(count: int, limit: int = PROBATE_RESULT_CAP) -> bool:
    """True when a pulled window hit the result cap and must be split.

    Split month windows into day windows (build_probate_list_url with
    day set) and re-pull: a capped list silently drops notices, so a
    capped "clean" window is NOT evidence of anything.
    """
    return count >= limit


def _cache_path(cache_dir: str, url: str) -> str:
    """Cache file for one AT probate URL (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in url)
    return os.path.join(cache_dir, "ata-probate-%s.xml" % safe[-120:])


def cache_is_fresh(path: str, ttl_days: int = ATA_PROBATE_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_probate_window(url: str, cache_dir: str = "/tmp/hf-cache",
                         ttl_days: int = ATA_PROBATE_TTL_DAYS) -> str:
    """Fetch one AT probate list/notice XML politely (cached, TTL-stated).

    Returns cached text when fresh; otherwise one GET with a polite
    User-Agent and a 30 s timeout. Transport errors RAISE (never cached
    as data, AGENTS.md section 7.2); HTTP errors raise too -- an error
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
# Parsing: AT probate LIST XML (namespace-tolerant, sparse-tolerant).
# Field layout observed 2026-09-13 on a real 417-notice initiation
# window (element census in the module docstring): <teadaanded> of
# <teadaanne> with teate_number, url, liik/kood+nimi, andmeandja,
# avaldamise_kpv + arhiveerimise_kpv, kinnitatud_sisu, sisendid rows
# named parandaja_* / toestamise_* / testamendi_info / muude.
# Unknown elements are ignored; missing elements read as None (never
# guessed). Personal values (puudutatud_isik, parandaja dates) stay in
# the runtime record only -- reasons never echo them.
# ---------------------------------------------------------------------------

#: Canonical record keys produced by parse_probate_list (all Optional
#: except "archived", which parsing always sets via is_archived).
PROBATE_FIELDS = (
    "notice_id", "url", "liik_kood", "liik_nimi",
    "andmeandja", "avaldatud", "arhiveeritud", "archived",
    "parandaja", "sisu",
)

#: sisendid row names observed on initiation notices (schema facts;
#: values are estate-join keys, never echoed in reasons).
PARANDAJA_INPUTS = (
    "parandaja_surmakuupaev",
    "parandaja_sunnikuupaev",
    "parandaja_endine_nimi",
    "toestamise_tahtpaev",
    "toestamise_kuupaev",
    "testamendi_info",
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


def _parse_inputs(notice_elem: ET.Element) -> Optional[Dict[str, str]]:
    """Estate-join inputs from sisendid rows (values stay runtime-only)."""
    found: Dict[str, str] = {}
    for elem in notice_elem.iter():
        if _local(elem.tag) != "sisendirida":
            continue
        name = _child_text(elem, "nimi")
        value = _child_text(elem, "vaartus")
        if name in PARANDAJA_INPUTS and value:
            found[name] = value
    return found or None


def _parse_notice(elem: ET.Element,
                 today: Optional[date] = None) -> Dict[str, Optional[object]]:
    """Parse one <teadaanne> element into a canonical record."""
    rec = {field: None for field in PROBATE_FIELDS}  # type: Dict[str, Optional[object]]
    rec["notice_id"] = _child_text(elem, "teate_number") or _child_text(elem, "id")
    rec["url"] = _child_text(elem, "url")
    for child in elem:
        local = _local(child.tag)
        if local == "liik" and rec["liik_nimi"] is None:
            # First <liik> is the notice type; a nested one inside
            # <puudutatud_isik> describes the person, not the notice.
            rec["liik_kood"] = _child_text(child, "kood")
            rec["liik_nimi"] = _child_text(child, "nimi")
        elif local == "andmeandja":
            rec["andmeandja"] = _child_text(child, "nimi")
        elif local == "avaldamise_kpv":
            rec["avaldatud"] = (child.text or "").strip() or None
        elif local == "arhiveerimise_kpv":
            rec["arhiveeritud"] = (child.text or "").strip() or None
        elif local == "kinnitatud_sisu":
            rec["sisu"] = _strip_html("".join(child.itertext()))
    rec["parandaja"] = _parse_inputs(elem)
    rec["archived"] = is_archived(
        rec["arhiveeritud"] if isinstance(rec["arhiveeritud"], str) else None,
        today=today)
    return rec


def parse_probate_list(xml_text: str,
                       today: Optional[date] = None) -> List[Dict[str, Optional[object]]]:
    """Parse one AT probate LIST XML into canonical per-notice records.

    Accepts the <teadaanded> list envelope; a bare single-notice
    <teadaanne> document parses as a one-record list. Namespace- and
    sparse-tolerant (absent elements become None). "archived" is
    always set via is_archived (None when the archive date is
    missing/unparseable -- dims treat that as unknown currency,
    never as active).
    """
    root = ET.fromstring(xml_text.lstrip("﻿"))
    if _local(root.tag) == "teadaanne":
        return [_parse_notice(root, today=today)]
    return [_parse_notice(elem, today=today)
            for elem in root if _local(elem.tag) == "teadaanne"]


# ---------------------------------------------------------------------------
# Small input helpers (local copies -- no sibling imports, see docstring).
# ---------------------------------------------------------------------------

#: Probate-type stems on casefolded liik_nimi (inflected forms +
#: diacritic-stripped URI slugs both match; see docstring).
_PROBATE_STEMS = ("pärim", "parim", "pärand", "parand")


def _is_probate(notice: dict) -> bool:
    """True when the notice type reads as a probate (parim) matter."""
    value = notice.get("liik_nimi")
    text = "" if value is None else str(value).casefold()
    return any(stem in text for stem in _PROBATE_STEMS)


def is_notary_publisher(notice: dict) -> bool:
    """True when the andmeandja reads as a notary (casefolded prefix)."""
    value = notice.get("andmeandja")
    text = "" if value is None else str(value).casefold()
    return text.startswith("notar")


def _probate(probate: Optional[dict]) -> Optional[dict]:
    return probate if isinstance(probate, dict) else None


def _missing_window() -> Score:
    return None, ("Pärimisteadaannete kirje puudub -- teadaandeaknata "
                  "skoori EI OLE (hinnangut ei anta): kontrolli "
                  "ametlikudteadaanded.ee URI-otsingust (parimisteated) "
                  "ja notarilt menetluse seisu")


def _no_list() -> Score:
    return None, ("Pärimisteadaannete loend puudub (EI OLE hinnangut): "
                  "liidestus ei tagastanud teateid -- kontrolli notarilt")


def _notices(probate: dict) -> Optional[List[dict]]:
    raw = probate.get("notices")
    if not isinstance(raw, list):
        return None
    return [n for n in raw if isinstance(n, dict)]


def _is_active(notice: dict) -> Optional[bool]:
    """True = publication window open; False = archived; None = unknown."""
    flag = notice.get("archived")
    if not isinstance(flag, bool):
        return None
    return not flag


def _describe(notice: dict) -> str:
    liik = notice.get("liik_nimi")
    name = str(liik).strip() if liik else "nimetu teade"
    num = notice.get("notice_id")
    tail = " nr %s" % num if num else ""
    when = notice.get("avaldatud")
    head = " (avaldatud %s)" % when if when else ""
    return "%s%s%s" % (name, tail, head)


# ---------------------------------------------------------------------------
# p362 (overturn): probate-window dim -- open initiation is strong-bad
# (20), clean window is weak-good capped at 75, everything unjoined or
# unclassified stays NULL with a notary-check reason. Per-estate join,
# never an area gradient.
# ---------------------------------------------------------------------------

def dim_probate_delay_overturn(probate: Optional[dict],
                               listing: Optional[dict] = None) -> Score:
    """p362: open parimismenetlus in the joined window delays the deal."""
    _ = listing
    rec = _probate(probate)
    if rec is None:
        return _missing_window()
    notices = _notices(rec)
    if notices is None:
        return _no_list()
    if not notices:
        return (75, "Ametlikes Teadaannetes kehtivaid pärimismenetluse "
                    "teateid ei leitud (nõrk hea teadaandeakna põhjal, "
                    "mitte hinnang, ülempiir 75) -- EI OLE puhta tiitli "
                    "tõend: notar kinnitab seisu enne pakkumist")
    scoped = [n for n in notices if _is_probate(n)]
    if not scoped:
        return None, ("Aknas on ainult mitte-pärimisteateid (%d, EI OLE "
                      "hinnangut): pärimisviivituse kohta teadaandeaken "
                      "ei ütle -- küsi notarilt" % len(notices))
    active = [n for n in scoped if _is_active(n) is True]
    unknown = [n for n in scoped if _is_active(n) is None]
    archived = [n for n in scoped if _is_active(n) is False]
    # Non-probate notices in a mixed window are out of this dim's scope
    # (other AT slices -- arest, enampakkumine -- live in dims_p4_ata):
    # the probate-classified subset answers p362 on its own.
    for notice in active:
        role = " (avaldaja: notar" if is_notary_publisher(notice) else " ("
        return (20, "Kehtiv pärimismenetluse algatamise teade: %s%s, "
                    "Ametlike Teadaannete andmed, mitte hinnang) -- "
                    "kinnistu müük võib viibida, kuni menetlus lõpeb: "
                    "notar kinnitab seisu enne pakkumist"
                % (_describe(notice), role))
    for notice in unknown:
        return None, ("Teadaande kehtivus teadmata (%s, arhiivikuupäev "
                      "puudub) -- EI OLE hinnangut" % _describe(notice))
    return (60, "Ainult arhiveeritud pärimisteated (%d, Ametlike "
                "Teadaannete andmed, mitte hinnang) -- kehtivat "
                "menetlusviivitust pole, notar kinnitab kehtiva seisu"
            % len(archived))


OVERTURN_ATA_DIMS = (
    ("probate_delay_overturn", "p362", dim_probate_delay_overturn),
)


def score_overturn_ata(probate: Optional[dict],
                       listing: Optional[dict] = None) -> Dict[str, Optional[int]]:
    """The p362 overturn dim for one listing/estate (entry point for the
    weight-rebalance follow-up; keys match OVERTURN_ATA_DIMS)."""
    return {key: fn(probate, listing)[0] for key, _, fn in OVERTURN_ATA_DIMS}

