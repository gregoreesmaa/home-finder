"""P4 Konkurentsiamet demo dim (issue #262, single param, no coverage issue).

Demo (#262): Konkurentsiameti kooskõlastatud soojuse piirhinnad
lõpptarbijale (P4-008 source (3)) — polite, cached, TTL-stated pulls
of the per-võrgupiirkond price-cap table plus an honest-shape
per-address table join end-to-end in Tallinn. Single param: P4-008
only. There is no follow-up coverage issue: this source feeds only
P4-008's source list, so one dim closes the demo.

Params (this agent only — sibling batches own disjoint sets):
* P4-008 Heating tariff zone + water/sewer tariff (demo, KA cap slice
  of the January-bill question — per-address join to the KA cap record)

HONESTY (AGENTS.md section 7.2): per-võrgupiirkond table join, capped
bands; NULL stays NULL with an Estonian reason. The KA file is a
per-ettevõte/võrgupiirkond zone table, NOT a per-address feed — the
address-to-zone mapping (which võrgupiirkond serves this address)
needs the operator's võrgupiirkonna kaart, which the KA file does not
carry. So the dim scores ONLY a joined cap record and returns None
when it is missing — never a guess, never a "cheap heat" 55 from
absence. Scored reasons always trace to the joined cap record
(company / network area / cap / decision); NULL reasons always say
EI OLE and name the missing input.

Openness verdict (2026-09-13, 4 polite requests total, custom UA,
short timeouts, paced >=5 s, bodies to /tmp/hf-p4-konkurents/, no
scraping, no auth attempts, redirects not spidered):
* HEAD https://www.konkurentsiamet.ee/ -> HTTP 200 (Cloudflare).
* GET https://www.konkurentsiamet.ee/ -> HTTP 200 (120 078 B,
  "Avaleht | Konkurentsiamet").
* GET .../elekter-gaas-soojus-ja-vesi/soojus/kooskolastatud-hinnad ->
  HTTP 200 (114 278 B, "Kooskõlastatud hinnad | Konkurentsiamet"):
  decision hub ("Kooskõlastatud soojuse piirhinna peab
  soojusettevõtja avalikustama oma võrgupiirkonnas ...",
  "Konkurentsiameti poolt kooskõlastatud soojuse piirhinnad ei
  sisalda käibemaksu") with downloadable tables, including
  "Kooskõlastatud soojuse piirhinnad lõpptarbijale" as
  .../2026-09/Koosk%C3%B5lastatud%20l%C3%B5pptarbijahinnad%20seisuga%2008.09.2026.xlsx
  (plus the tootmishinnad PDF and hinnataotlused PDF).
* GET the lõpptarbijahinnad XLSX -> HTTP 200 (43 371 B, valid
  Excel 2007+, sheet "Kehtiv"): header rows Ettevõte | otsuse nr |
  kuupäev | piirhind €/MWh (käibemaksuta) | uue otsuse nr | kuupäev
  | uus piirhind; company-group rows (e.g. "Adven Eesti AS:",
  "Utilitas Tallinn AS") plus zone rows (võrgupiirkond, otsus nr
  like 7-3/2024-090, kuupäev like 27.12.2024 or Excel serial,
  piirhind like 77.82). Tallinn demo row: Utilitas Tallinn AS /
  Tallinna võrgupiirkond / 77.82 €/MWh käibemaksuta / otsus
  7-3/2024-090 (27.12.2024), no pending uue-hinna columns.
Verdict: OPEN as a per-võrgupiirkond zone table (Tallinn present),
CLOSED as a per-address feed (no address-level mapping in the file).
The dim scores ONLY joined cap records transcribed into the snapshot
layout below. See docs/p4_konkurents.md.

Style mirrors services/scoring/dims_p4_heat.py (issue #261) and
services/scoring/dims_p4_tvesi.py (issues #263/#343): pure
(zone, listing) -> (Optional[int 0..100], Estonian reason), absolute
bands, hermetic fixture tests. Network lives only in
fetch_konkurents_xlsx (single polite GET, file cache, TTL); tests
never call it. Like the tvesi hinnakiri page table, the XLSX is
transcribed into the semicolon CSV snapshot layout parse_*
reads — the fetch proves the polite pull, the parser proves the
honest shape on fixtures.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and group20a #212).

Overlap note (READ sibling first per #262 — do NOT duplicate it):
dims_p4_heat.dim_heating_tariff (issue #261) already scores P4-008
from the OPERATOR slice (zone_key, operator, tariff_zone,
tariff_eur_mwh, tariff_status kehtiv/kooskõlastamisel, water_zone,
return_bonus; bands 60/45 for bill predictability, plus the P4-036
roof_bonus). This module scores the complementary KA DECISION slice
(zone_key, company, network_area, cap_eur_mwh käibemaksuta,
decision_no, decided, new_decision_no/new_cap_eur_mwh, vintage;
bands 55/40 for cap groundedness). Different dim key
(heat_price_cap vs heating_tariff), different cache prefix
(konkurents-*.xlsx vs heat-*.csv), different parse fields,
different bands. Like the tvesi water_tariff (P4-008 water/sewer
leg) and the elektrilevi tariff_zone (P4-008 NULL), each P4-008
slice names the legs it does NOT join.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single dim, single param, no coverage issue: the KA cap file feeds
  only P4-008 source (3), so there is no second param extending this
  ingestion (unlike heat #261/#342 or tvesi #263/#343).
* Bands are 55/40, never 0 and never 100: the KA cap alone never
  prices a January bill (the operator may charge BELOW the cap, and
  building consumption dominates — KÜ aruanne decides), and absence
  of a joined record is not proof of expensive heat either.
* 55 sits one band BELOW heat's 60 on purpose: heat's 60 joins the
  operator's applied tariff zone; the KA cap is a ceiling
  (käibemaksuta), i.e. strictly less predictive of the euros on the
  bill. Stated, not hidden.
* P4-008 here scores cap GROUNDEDNESS, not cheapness: ranking zones
  by €/MWh without consumption data would be fake precision. A
  kehtiv cap with a known number (55) beats a cap in motion or with
  a missing leg (40) because the buyer can budget against a ceiling.
* Pending uue-hinna columns (F-H in the XLSX) read as 40, not 55:
  a price change in flight means the ceiling the buyer budgets
  against is about to move.
* Decision-known/cap-missing and cap-known/decision-missing both
  read as 40 (weak, trace incomplete), never as NULL and never as
  55: the decision exists but the machine-readable trace is half —
  the buyer can still ask the operator/KA for the number.
* Joined-but-empty reads as NULL (not 40): a cap record carrying
  neither company/network area nor cap nor decision proves coverage
  of nothing (same precedent as heat's joined-but-empty).
* Comma-decimal caps ("77,82") parse to float; unparseable caps
  read as None (never guessed, never zero — zero would fake free
  heat). Negative caps read as None (a cap cannot be negative).
  Company/area/decision cells are open-ended stripped strings
  (company names are not a closed token set — restricting them
  would fake non-coverage).
* 30-day TTL (2592000 s): caps move on Konkurentsiamet decisions
  (the hub file carries a "seisuga 08.09.2026" vintage), so a
  monthly re-pull converges per AGENTS.md section 7.4 while a newer
  "seisuga" vintage triggers an out-of-band re-pull. Stated, not
  hidden.

Integration (deliberately NOT done here): feeding this dim with the
address's joined cap record inside livability scoring and
rebalancing livability.WEIGHTS must be one joint change across all
parameter batches — existing tests pin set(WEIGHTS) exactly, so
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
# Ingestion: polite, cached, TTL-stated Konkurentsiamet snapshot pulls.
# ---------------------------------------------------------------------------

#: Monthly pull per module docstring (caps move on KA decisions; a
#: newer "seisuga" vintage on the hub additionally triggers an
#: out-of-band re-pull).
KONKURENTS_TTL_S = 30 * 86400

#: Where the public slices live (verified 2026-09-13 — see module
#: docstring; decision hub plus downloadable zone tables, no
#: anonymous per-address feed).
KA_HUB_URL = ("https://www.konkurentsiamet.ee/"
              "elekter-gaas-soojus-ja-vesi/soojus/"
              "kooskolastatud-hinnad")
KA_LOPPTARBIJA_XLSX_URL = ("https://www.konkurentsiamet.ee/"
                           "sites/default/files/documents/2026-09/"
                           "Koosk%C3%B5lastatud%20l%C3%B5pptarbijahinnad"
                           "%20seisuga%2008.09.2026.xlsx")

USER_AGENT = ("home-finder konkurents ingest (polite monthly pull, "
              "single GET, file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str, name: str) -> str:
    """Cache file for one named KA snapshot (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)
    return os.path.join(cache_dir, "konkurents-%s.xlsx" % safe)


def cache_is_fresh(path: str, ttl_s: int = KONKURENTS_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_s seconds."""
    try:
        age_s = ((now if now is not None else time.time())
                 - os.path.getmtime(path))
    except OSError:
        return False
    return age_s < ttl_s


def fetch_konkurents_xlsx(name: str, url: str,
                          cache_dir: str = "/tmp/hf-cache",
                          ttl_s: int = KONKURENTS_TTL_S) -> bytes:
    """Fetch one KA price-cap XLSX politely (single GET, cached, TTL-stated).

    Returns cached bytes when fresh; otherwise one GET with a polite
    User-Agent and a 40 s timeout. Transport errors RAISE (never cached
    as data, AGENTS.md section 7.2); HTTP errors raise too — an error
    body is never written to the cache. Treat HTTP 429 as a stop
    signal: it propagates, the stale cache is left untouched.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, name)
    if cache_is_fresh(path, ttl_s):
        with io.open(path, "rb") as f:
            return f.read()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=40) as resp:  # noqa: S310
        body = resp.read()
    with io.open(path, "wb") as f:
        f.write(body)
    return body


# ---------------------------------------------------------------------------
# Parsing: transcribed KA cap snapshot layout (semicolon-separated,
# BOM-tolerant). Column names follow the documented snapshot (English
# keys transcribed from the XLSX Ettevõte/võrgupiirkond/piirhind/otsus
# columns); unknown columns are ignored, empty cells and absent
# columns read as None (never guessed). The transcription adds
# zone_key (join key slugged from the võrgupiirkond) plus vintage
# (hub "seisuga" date, e.g. 08.09.2026) so a stale table is
# detectable. No personal data in this layout by construction
# (per-võrgupiirkond caps, no addresses).
# ---------------------------------------------------------------------------

#: Canonical record keys produced by parse_konkurents_caps (all
#: Optional except the join key zone_key, which is always non-empty).
KONKURENTS_FIELDS = (
    "zone_key", "company", "network_area", "cap_eur_mwh",
    "decision_no", "decided", "new_decision_no", "new_cap_eur_mwh",
    "vintage",
)


def _clean(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _parse_cap(value: Optional[object]) -> Optional[float]:
    """Parse a käibemaksuta €/MWh cell (comma or dot decimals).

    Unparseable cells read as None (never guessed, never zero — zero
    would fake free heat); negative caps read as None (a cap cannot
    be negative).
    """
    s = _clean(value)
    if s is None:
        return None
    try:
        v = float(s.replace(",", "."))
    except ValueError:
        return None
    return v if v >= 0 else None


def parse_konkurents_caps(csv_text: str) -> List[Dict[str, Optional[object]]]:
    """Parse one transcribed KA cap snapshot into canonical cap records.

    Semicolon-separated, BOM-tolerant; empty cells and absent columns
    become None. Rows without a zone_key are skipped (no join key —
    keeping them would fake join coverage).
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []  # type: List[Dict[str, Optional[object]]]
    for row in reader:
        key = _clean(row.get("zone_key"))
        if not key:
            continue
        rec = {"zone_key": key}  # type: Dict[str, Optional[object]]
        rec["company"] = _clean(row.get("company"))
        rec["network_area"] = _clean(row.get("network_area"))
        rec["cap_eur_mwh"] = _parse_cap(row.get("cap_eur_mwh"))
        rec["decision_no"] = _clean(row.get("decision_no"))
        rec["decided"] = _clean(row.get("decided"))
        rec["new_decision_no"] = _clean(row.get("new_decision_no"))
        rec["new_cap_eur_mwh"] = _parse_cap(row.get("new_cap_eur_mwh"))
        rec["vintage"] = _clean(row.get("vintage"))
        records.append(rec)
    return records


def index_by_cap(
        records: List[Dict[str, Optional[object]]]
) -> Dict[str, Dict[str, Optional[object]]]:
    """Per-address join index (one cap record per key; first row wins)."""
    index = {}  # type: Dict[str, Dict[str, Optional[object]]]
    for rec in records:
        key = rec.get("zone_key")
        if key and str(key) not in index:
            index[str(key)] = rec
    return index


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _lst(listing: Optional[dict]) -> dict:
    return listing if isinstance(listing, dict) else {}


def _missing_cap() -> Score:
    return None, ("Selle aadressi Konkurentsiameti piirhinna-kirjet "
                  "hetktõmmises pole — võrgupiirkond ja kooskõlastatud "
                  "lagi on teadmata (EI OLE hinnangut): uuri operaatori "
                  "võrgupiirkonna kaardilt tsooni, küsi KÜ-lt jaanuariarve "
                  "näidis ja kontrolli Konkurentsiameti kooskõlastatud "
                  "hindu")


def _describe(zone: dict) -> str:
    company = zone.get("company") or "teadmata ettevõte"
    area = zone.get("network_area") or zone.get("zone_key")
    cap = zone.get("cap_eur_mwh")
    decision = zone.get("decision_no")
    if isinstance(cap, (int, float)):
        base = "%s, %s, %.2f €/MWh käibemaksuta" % (company, area, cap)
    else:
        base = "%s, %s, piirhind määramata" % (company, area)
    if decision is not None:
        decided = zone.get("decided")
        base += " (otsus %s%s)" % (
            decision, ", %s" % decided if decided else "")
    return base


# ---------------------------------------------------------------------------
# P4-008 (demo, KA cap slice): kooskõlastatud piirhind per võrgupiirkond.
# Per-address dim scoring cap GROUNDEDNESS (55/40/NULL) — never
# cheapness: the cap is a ceiling, and the operator may charge less.
# ---------------------------------------------------------------------------

def dim_heat_price_cap(zone: Optional[dict],
                       listing: Optional[dict] = None) -> Score:
    """P4-008: known KA cap makes January budgetable against a ceiling."""
    _ = _lst(listing)  # listing side unused — per-address cap join
    if not isinstance(zone, dict):
        return _missing_cap()
    company = zone.get("company")
    area = zone.get("network_area")
    cap = zone.get("cap_eur_mwh")
    decision = zone.get("decision_no")
    new_decision = zone.get("new_decision_no")
    new_cap = zone.get("new_cap_eur_mwh")
    if (company is None and area is None and cap is None
            and decision is None and new_decision is None
            and new_cap is None):
        # NOTE: zone_key alone is just the join key, never coverage —
        # a record with only zone_key proves nothing is joined.
        return None, ("Liidetud KA piirhinna-kirje on tühi (ettevõtet, "
                      "võrgupiirkonda, piirhinda ega otsust pole) — selle "
                      "aadressi kaugkütte lae kohta EI OLE hinnangut: "
                      "küsi KÜ-lt jaanuariarve näidis")
    if (isinstance(cap, (int, float)) and decision is not None
            and new_decision is None and new_cap is None):
        return (55, "Kehtiv Konkurentsiameti kooskõlastatud piirhind "
                    "(%s, registriandmed, mitte hinnang) — jaanuariarve "
                    "lagi on teada (ülempiir 55: operaator võib küsida "
                    "ka madalamat hinda ja tegelik kulu sõltub hoone "
                    "tarbimisest, vaata KÜ aruannet; vesi/kanalisatsioon "
                    "on liitmata)" % _describe(zone))
    if new_decision is not None or new_cap is not None:
        if isinstance(new_cap, (int, float)):
            new_bit = "uus %.2f €/MWh" % new_cap
        else:
            new_bit = "uus hind määramata"
        if new_decision is not None:
            new_bit += " (otsus %s)" % new_decision
        return (40, "Konkurentsiameti uus piirhind on muutmisel "
                    "(%s; %s, registriandmed, mitte hinnang) — nõrk "
                    "lagi, sest lagi liigub (ülempiir 40), jaanuariarve "
                    "selgub KÜ-lt" % (_describe(zone), new_bit))
    return (40, "Konkurentsiameti otsus on teada, aga lagi on poolik "
                "(%s, registriandmed, mitte hinnang) — nõrk signaal "
                "(ülempiir 40): küsi operaatorilt/Konkurentsiametist "
                "number ja KÜ-lt jaanuariarve näidis" % _describe(zone))


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_KONKURENTS_DIMS; pnums per
# parameters4.md).
# ---------------------------------------------------------------------------

P4_KONKURENTS_DIMS = (
    ("heat_price_cap", "P4-008", dim_heat_price_cap),
)


def score_p4_konkurents(zone: Optional[dict],
                        listing: Optional[dict] = None
                        ) -> Dict[str, Optional[int]]:
    """The P4 Konkurentsiamet dim for one address (entry point for the
    future enrich/score hook; keys match P4_KONKURENTS_DIMS). Missing
    slices stay None by design — per-address join, never a faked area
    score."""
    return {key: fn(zone, listing)[0] for key, _, fn in P4_KONKURENTS_DIMS}
