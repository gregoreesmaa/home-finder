"""P4 EMTA (new uses) demo + coverage dims (issues #256, #337).

Demo (#256): EMTA ingestion for NEW uses beyond the #242 G16 scope —
maamaks rate/trend context (KOV fiscal forward), per-entity
maksuvõlg (võlapäring) checkpoint, automaks calculator + CO2-band
exposure — plus P4-019 end-to-end in Tallinn. Coverage (#337): the
remaining 2 params that consume the demoed ingestion (P4-004 debt
slice, P4-037 policy-exposure slice).

Params (this agent only — overturn #242 owns the parameters3 G16
tax-table params in dims_group16*.py, which this module does NOT
touch; no shared/group files are edited):
* P4-019 KOV fiscal health, EMTA slice: maamaks rate level + trend
  (demo, per-KOV table, annual)
* P4-004 Kinnistus süva, EMTA slice: maksuvõlg per entity +
  notary checkpoint (per-listing dim, weak-good capped)
* P4-037 Policy exposure: automaks + car-free exposure by commute
  dependence (per-listing exposure band)

HONESTY (AGENTS.md section 7.2): the EMTA bulk tables are NOT in
the snapshot, so every dim returns None when its joined EMTA row
is missing — never a guess. "No debt found" is weak-good
(CAPPED, never 100): the public võlapäring hides sub-100-euro
debts and estimated interest by its own documented rule, and
every clean reason says so. Scored reasons always name the joined
EMTA slice (traceable to a page/query the buyer can re-run);
unknown bands and unknown currency stay NULL with the slice
named. NULL stays NULL with an Estonian reason.

Openness verdict (2026-09-13, dated polite probes, cache
/tmp/hf-emta): MIXED / constrained-open — every buyer-facing page
is anonymously reachable, but NO bulk/open-data feed was
observed:
* https://www.emta.ee/ -> HTTP 200, 203803 bytes (public, no auth).
* .../eraklient/maksud-ja-tasumine/muud-maksud/maamaks ->
  HTTP 200, 267763 bytes — public land-tax guide: 2026 statutory
  bands (elamumaa 0,1-1%, maatulundusmaa 0,1-0,5%, muu 0,1-2%),
  KOV-set rates, koduomaniku soodustus (maamaksuseadus p11),
  yearly per-KOV rate PDFs referenced (2026/2025/...).
* https://avalik.emta.ee/mootorsoidukimaks -> HTTP 200, 2155
  bytes, JS SPA shell ("Laeme rakendust... JavaScript required")
  — public calculator app, anonymous GET fine, but content needs
  JS rendering: no server-side scrape, dims point the buyer at it.
* .../e-teenused-maksutarkus/registrid-paringud/avalikud-paringud
  -> HTTP 200, 164870 bytes — documents Võlapäring: public
  per-entity query by registrikood/isikukood showing only
  sissenõutavaid tähtpäevaks tasumata nõudeid; does NOT show
  estimated interest or debts under 100 euros.
* Two guessed deep URLs (/et/maksuvold, /et/mootorsoidukimaks)
  -> HTTP 404 (documented negative guesses, not real paths).
Verdict: OPEN for polite page pulls + per-deal user checks, NO
bulk join observed — so every dim scores ONLY joined rows and the
per-KOV PDF bulk join stays explicit future work (dims stay NULL
until it lands). See docs/p4_emta.md. NEVER commit real pulls —
fixtures in tests are synthetic (invented entities, rates, bands).

Style mirrors services/scoring/dims_p4_ata.py (issues #254/#335):
pure (emta, listing) -> (Optional[int 0..100], Estonian reason),
absolute bands, hermetic fixture tests. Network lives only in
fetch_emta_page (single polite GET, file cache, TTL); tests never
call it.

Helpers are local copies (not imported from livability, sibling
batches, or dims_group16): a future central hook may import this
module alongside them, and importing any of them here would turn
that into a cycle (same precedent as batch B3, PR #100, and
group20a #212). In particular nothing is shared with the #242
G16 tax-table pipeline — the new-use ingestion stands alone.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR because the coverage issue body
  states it "extends the demoed ingestion" — splitting would ship
  an ingestion with one consumer, then re-touch every dim
  signature (same precedent as the ATA #254+#335 PR).
* TTL is monthly (EMTA_TTL_DAYS = 30): KOV rate tables refresh
  yearly, but the info pages drift (links, bands, calculator) and
  debt guidance is per-deal — monthly re-pulls detect drift
  without hammering. Dims score only joined rows regardless.
* P4-019 caps at 70 (stricter than ATA's 75): the EMTA slice is
  rate level + trend only — võlakoormus/investments (the param's
  core) live in eelarve/Rahandusministeerium/Statamet rows this
  module never joins. Each scored reason names that gap.
* P4-019 scores the TREND (hike signal) modulated by LEVEL, not
  the level alone: a maxed-out-but-stable rate is predictable
  (55), a rising rate is the hike warning (45) at any level.
* P4-004 reuses ATA's 20/75 bands on purpose (same param, EMTA
  slice instead of AT slice): 20 active debt + notary pointer,
  75 clean capped with the sub-100-euro caveat the võlapäring
  page itself documents.
* P4-037 takes co2_band as a JOINED label (madal/keskmine/kõrge
  from the buyer's calculator run), never computed here: the
  calculator is a JS app with no scraped API, so encoding
  statutory CO2 cutoffs from memory would be fake precision.
  Unknown band stays NULL with the calculator named.
* Active-bad never scores 0 anywhere: a debt flag can be stale
  or mis-joined, a CO2 band is an estimate — strong-bad, never
  "worthless".
* The Tallinn gate (emta["tallinn"] is False -> NULL) keeps the
  demo scope honest: non-Tallinn joins are out of scope, not bad
  deals. A missing "tallinn" key defaults to relevant (older
  joins predate the flag; absence is not evidence either way).
* Võlapäring input is a registry code, never a name: reasons echo
  ONLY the debt flag + check date — never an isikukood.

Integration (deliberately NOT done here): feeding these dims with
the listing's joined EMTA record inside livability scoring and
rebalancing livability.WEIGHTS must be one joint change across
all parameter batches — existing tests pin set(WEIGHTS) exactly,
so per-batch WEIGHTS edits would break every sibling.
"""

import os
import re
import time
import urllib.request
from typing import Dict, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated EMTA info-page pulls.
# ---------------------------------------------------------------------------

#: Monthly bulk per the yearly-rate / per-deal-checkpoint mix (docstring).
EMTA_TTL_DAYS = 30

#: Verified 2026-09-13 (anonymous GETs, see module docstring).
EMTA_BASE_URL = "https://www.emta.ee"

#: Observed 2026-09-13 (anonymous GET, JS shell — needs rendering).
AUTOMAKS_CALCULATOR_URL = "https://avalik.emta.ee/mootorsoidukimaks"

MAAMAKS_PAGE_PATH = ("/eraklient/maksud-ja-tasumine/muud-maksud/"
                     "maamaks")

PARINGUD_PAGE_PATH = ("/eraklient/e-teenused-maksutarkus/"
                      "registrid-paringud/avalikud-paringud")

USER_AGENT = ("home-finder EMTA ingest (polite monthly pulls, single GET, "
              "file cache; contact via GitHub home-finder)")


def build_emta_url(path: str) -> str:
    """One EMTA info-page URL from a site-root path."""
    return "%s%s" % (EMTA_BASE_URL, path)


def _cache_path(cache_dir: str, url: str) -> str:
    """Cache file for one EMTA page URL (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in url)
    return os.path.join(cache_dir, "emta-%s.html" % safe[-120:])


def cache_is_fresh(path: str, ttl_days: int = EMTA_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_emta_page(url: str, cache_dir: str = "/tmp/hf-cache",
                    ttl_days: int = EMTA_TTL_DAYS) -> str:
    """Fetch one EMTA info page politely (single GET, cached, TTL-stated).

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
# Parsing: EMTA info-page facts (sparse-tolerant, fail-closed).
# Layout observed 2026-09-13 on the public maamaks guide + avalike
# paringute page (statutory bands with comma decimals, yearly KOV
# rate-PDF references, volaparing floor rule). Unknown elements read
# as None (never guessed) — a reworded page yields Nones and the
# dims stay NULL, which is the honest failure mode.
# ---------------------------------------------------------------------------

#: Canonical facts produced by parse_maamaks_page (all Optional).
EMTA_FACT_FIELDS = (
    "elamumaa_band",
    "maatulundusmaa_band",
    "muu_band",
    "rate_table_years",
    "volaparing_floor_eur",
    "volaparing_needs_code",
)


def _parse_band(html: str, keyword: str) -> Optional[Tuple[float, float]]:
    """Parse a 'X,Y-Z%' statutory band near a keyword (None if absent).

    Matches the page's own style: 'elamumaale ... 0,1-1%' with comma
    decimals and hyphen/en-dash ranges.
    """
    low = html.lower()
    idx = low.find(keyword.lower())
    if idx < 0:
        return None
    window = low[idx:idx + 400].replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*[-\u2013]\s*(\d+(?:\.\d+)?)\s*%",
                      window)
    if not match:
        return None
    try:
        return (float(match.group(1)), float(match.group(2)))
    except ValueError:
        return None


def parse_maamaks_page(html: str) -> Dict[str, Optional[object]]:
    """Extract the observed maamaks/volaparing facts from a page snapshot.

    Sparse-tolerant: every field is None when its marker is absent.
    The statutory bands mirror the 2026 ranges stated on the public
    guide (elamumaa 0,1–1%, maatulundusmaa 0,1–0,5%, muu 0,1–2%);
    rate_table_years lists the yearly KOV-table years the page
    references; volaparing_floor_eur is the documented 100-euro
    visibility floor (None when the rule text is absent).
    """
    facts = {field: None for field in EMTA_FACT_FIELDS}  # type: Dict[str, Optional[object]]
    facts["elamumaa_band"] = _parse_band(html, "elamumaale")
    facts["maatulundusmaa_band"] = _parse_band(html, "maatulundusmaale")
    facts["muu_band"] = _parse_band(html, "muu\u00a0sihtotstarbega")
    if facts["muu_band"] is None:
        facts["muu_band"] = _parse_band(html, "muu sihtotstarbega")
    years = sorted(set(re.findall(r"(20\d\d)\s*[|\u2013]?\s*pdf",
                                  html, flags=re.IGNORECASE)))
    facts["rate_table_years"] = years or None
    floor = re.search(r"alla\s+(\d+)\s*eurost\s+v", html, flags=re.IGNORECASE)
    if floor:
        try:
            facts["volaparing_floor_eur"] = int(floor.group(1))
        except ValueError:
            facts["volaparing_floor_eur"] = None
    if re.search(r"registrikood", html, flags=re.IGNORECASE):
        facts["volaparing_needs_code"] = True
    return facts


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _emta(emta: Optional[dict]) -> Optional[dict]:
    return emta if isinstance(emta, dict) else None


def _missing_emta() -> Score:
    return None, ("EMTA kirje puudub — maksuandmeteta skoori EI OLE "
                  "(hinnangut ei anta): KOV määr paistab EMTA maamaksu-"
                  "juhendist, võlg registrikoodi võlapäringust")


def _not_tallinn() -> Score:
    return None, ("EMTA kirje ei ole Tallinna-filtriga (EI OLE hinnangut): "
                  "demo ulatus on Tallinn — väljaspool linna skoori ei anta")


def _gate(emta: Optional[dict]) -> Tuple[Optional[dict], Optional[Score]]:
    """Shared join gates: missing record / Tallinn scope."""
    rec = _emta(emta)
    if rec is None:
        return None, _missing_emta()
    if rec.get("tallinn", True) is False:
        return None, _not_tallinn()
    return rec, None


def _num(value: object) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) else None


# ---------------------------------------------------------------------------
# P4-019 (demo): KOV fiscal health, EMTA slice — maamaks rate level +
# trend. Per-KOV table, annual. Capped at 70: võlakoormus/investments
# (the param's core) are eelarve/Rahandusministeerium/Statamet rows
# this module never joins.
# ---------------------------------------------------------------------------

_TRENDS = ("sama", "tõusnud", "langenud")


def dim_fiscal_health(emta: Optional[dict],
                      listing: Optional[dict] = None) -> Score:
    """P4-019: stable rate 70/55, rising 45; incomplete rows stay NULL."""
    rec, gated = _gate(emta)
    if gated is not None or rec is None:
        return gated  # type: ignore[return-value]
    rate = _num(rec.get("maamaksu_maar_pct"))
    if rate is None:
        return None, ("KOV maamaksumäär liidestuses puudub (EI OLE "
                      "hinnangut): määr paistab KOV määra-tabelist "
                      "(EMTA maamaksu-juhendi aastatabelid)")
    trend = rec.get("maamaksu_trend")
    if trend not in _TRENDS:
        return None, ("KOV maamaksu trend teadmata (EI OLE hinnangut): "
                      "üksik määr ilma ajaloota ei näita "
                      "maksutõusu riski — võrdle eelmise aasta määraga")
    kov = rec.get("kov") or "Tallinn"
    aasta = rec.get("maamaksu_aasta") or "jooksval aastal"
    if trend == "tõusnud":
        return (45, "KOV maamaks tõusuteel: %s määr %s%% %s (EMTA/KOV "
                    "andmed, mitte hinnang) — arvesta maksutõusu "
                    "riskiga; võlakoormus ja investeeringud "
                    "(eelarve/Rahandusministeerium/Statamet) "
                    "liidestamata" % (kov, rate, aasta))
    if rate >= 1.0:
        return (55, "KOV maamaks stabiilne, aga kõrge tase: %s määr %s%% "
                    "%s (EMTA/KOV andmed, mitte hinnang) — ettenähtav, "
                    "kuid kallis; võlakoormus (eelarve) liidestamata, "
                    "ülempiir 55" % (kov, rate, aasta))
    return (70, "KOV maamaks stabiilne: %s määr %s%% %s (EMTA/KOV andmed, "
                "mitte hinnang) — EI OLE maksevõime tõend: võlakoormus ja "
                "investeeringud (eelarve/Rahandusministeerium/Statamet) "
                "liidestamata, ülempiir 70" % (kov, rate, aasta))


# ---------------------------------------------------------------------------
# P4-004 (coverage): kinnistus süva, EMTA debt slice — maksuvõlg per
# entity (võlapäring) + notary checkpoint. Per-listing dim, weak-good
# cap 75 with the documented sub-100-euro caveat. RIK/notary stay the
# primary source; EMTA is one slice of it.
# ---------------------------------------------------------------------------

def _volaparing(rec: dict) -> Optional[dict]:
    raw = rec.get("volaparing")
    return raw if isinstance(raw, dict) else None


def dim_kinnistus_debt(emta: Optional[dict],
                       listing: Optional[dict] = None) -> Score:
    """P4-004: active debt is 20 + notary pointer; clean caps 75."""
    rec, gated = _gate(emta)
    if gated is not None or rec is None:
        return gated  # type: ignore[return-value]
    entity = rec.get("entity")
    if not entity or not str(entity).strip():
        return None, ("Müüja/omaniku registrikood liidestuses puudub "
                      "(EI OLE hinnangut): EMTA võlapäring käib "
                      "registrikoodi, mitte nime alusel")
    vp = _volaparing(rec)
    if vp is None:
        return None, ("EMTA võlapäring liidestuses puudub (EI OLE "
                      "hinnangut): kontrolli registrikoodi EMTA "
                      "võlapäringust enne pakkumist")
    debt = vp.get("debt")
    if debt is None:
        return None, ("Võlapäringu kehtivus teadmata (EI OLE hinnangut): "
                      "päringu aeg või ulatus liidestuses puudub")
    checked = vp.get("checked")
    tail = " (seis %s)" % checked if checked else ""
    if debt is True:
        return (20, "Kehtiv maksuvõlg%s (EMTA võlapäring, mitte hinnang) "
                    "— sulgemisrisk, notarikontroll (notar.ee) ja RIK "
                    "seis enne pakkumist" % tail)
    return (75, "Võlapäringus võlga ei leitud%s (nõrk hea, mitte hinnang) "
                "— EI OLE puhta tiitli tõend: päring ei näita alla "
                "100-eurost võlga ega arvestuslikku intressi; "
                "RIK/notar kontrollib sulgemise" % tail)


# ---------------------------------------------------------------------------
# P4-037 (coverage): policy exposure — automaks + car-free exposure by
# commute dependence. Per-listing exposure band. co2_band is a JOINED
# label from the buyer's calculator run (madal/keskmine/korge);
# never computed here (the calculator is a JS app with no scraped
# API — encoding cutoffs from memory would be fake precision).
# ---------------------------------------------------------------------------

_CO2_BANDS = ("madal", "keskmine", "kõrge")


def dim_policy_exposure(emta: Optional[dict],
                        listing: Optional[dict] = None) -> Score:
    """P4-037: car-free 70, car-bound 60/45/30; unknown band stays NULL."""
    rec, gated = _gate(emta)
    if gated is not None or rec is None:
        return gated  # type: ignore[return-value]
    dependent = rec.get("car_dependent")
    if dependent is None:
        return None, ("Pendelrände autoletoetuvus liidestuses puudub "
                      "(EI OLE hinnangut): hinda ühistranspordi "
                      "alternatiiv (TLT/Peatus.ee) ja arvuta automaks "
                      "EMTA kalkulaatoris (avalik.emta.ee)")
    if dependent is False:
        return (70, "Vähene poliitikarisk: aadress ei eelda autot "
                    "(ühistransport katab pendelrände, EMTA-loogika, "
                    "mitte hinnang) — EI OLE kaitse: ummikumaksu ja "
                    "autovaba-ala otsused liidestamata, ülempiir 70")
    band = rec.get("co2_band")
    if band not in _CO2_BANDS:
        return None, ("CO2-klass teadmata (EI OLE hinnangut): käivita "
                      "EMTA automaksu kalkulaator (avalik.emta.ee) "
                      "sõiduki andmetega ja liidesta tulemuse klass")
    if band == "madal":
        return (60, "Madal automaksu-mõjutus: autole toetuv, aga madal "
                    "CO2-klass (EMTA kalkulaatori loogika, mitte "
                    "hinnang) — täpse summa näitab avalik.emta.ee; "
                    "ummikumaks liidestamata")
    if band == "keskmine":
        return (45, "Keskmine automaksu-mõjutus: autole toetuv + "
                    "keskmine CO2-klass (EMTA kalkulaatori loogika, "
                    "mitte hinnang) — arvuta täpne summa "
                    "avalik.emta.ee kalkulaatoris")
    return (30, "Kõrge automaksu-mõjutus: autole toetuv + kõrge "
                "CO2-klass (EMTA kalkulaatori loogika, mitte hinnang) "
                "— kaalu autovaba alternatiivi; täpne summa "
                "avalik.emta.ee kalkulaatorist")


P4_EMTA_DIMS = (
    ("fiscal_health", "P4-019", dim_fiscal_health),
    ("kinnistus_debt", "P4-004", dim_kinnistus_debt),
    ("policy_exposure", "P4-037", dim_policy_exposure),
)


def score_p4_emta(emta: Optional[dict],
                  listing: Optional[dict] = None) -> Dict[str, Optional[int]]:
    """All three P4 EMTA dims for one listing (keys match P4_EMTA_DIMS)."""
    return {key: fn(emta, listing)[0] for key, _, fn in P4_EMTA_DIMS}
