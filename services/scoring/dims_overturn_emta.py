"""Overturn re-check for G16 EMTA/KOV tax-table params (issue #242).

Scope: the G16 tax-table set p2 / p73 / p151 / p422 / p423
(parameters3.md section 5.16, Group 16). The canonical scorers stay
dims_group16a.dim_property_taxes / dim_special_tax_assessment /
dim_tax_reassessment (#205) and
dims_group16b.dim_supplemental_tax / dim_assessment_district (#206)
-- READ first, untouched here, as is dims_p4_emta.py (#256/#337:
the P4-019 fiscal-health trend slice, P4-004 debt slice and P4-037
policy-exposure slice -- new USES of EMTA ingestion, a different
question family from these parameters3 G16 rate-table params;
NOT edited, NOT imported).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps every
verdict: the per-KOV tables are yearly human-readable PDFs behind
Nextcloud share links, with no machine-readable bulk feed, so all
five dims stay NULL). Polite evidence, 2 GETs + 1 HEAD + 1 failed
API probe total (labelled one-off user-agent, paced >= 4 s apart,
headers + visible-text/link-scope read only, no scraping, no auth;
HTTP 404 is a stop signal, not a retry dare), raw bodies cached at
/tmp/hf-emta242/ (one-off PR record, never committed):
* https://www.emta.ee/eraklient/maksud-ja-tasumine/muud-maksud/maamaks
  -> HTTP 200, 268124 bytes: the public land-tax guide. States the
  2026 statutory bands (elamumaa + maatulundusmaa ouemaa 0,1-1%,
  maatulundusmaa 0,1-0,5%, muu sihtotstarve 0,1-2%), KOV-set rates,
  koduomaniku soodustus as ISIKUPOHINE (MaaMS s. 11) and
  vabastused as MAAPOHISED (MaaMS s. 4) -- per-person / per-parcel
  facts, never area signals. Links the yearly per-KOV tables
  2022-2026 as Nextcloud-share PDFs (8 ncfailid.emta.ee hrefs,
  labelled "pdf"); the ONLY machine-readable href on the whole
  page is the site RSS feed (no data).
* 2026 share HEAD -> HTTP 200, text/html (Nextcloud landing wrapper,
  not a direct file): the table needs interaction/PDF parsing, not
  a GET-and-join.
* https://avaandmed.eesti.ee/api/3/action/package_search?q=maamaks
  -> HTTP 404: no CKAN-style bulk API at the standard path.
Full log: docs/overturn_emta.md.

So every scorer below returns None for EVERY input including
missing origin: colouring KOVs from a hand-transcribed PDF would
be invented data, and a gradient of the national statutory bands
would be one flat colour (OTA PR #131 precedent). Reasons say
"hinnang" (estimate) and "EI OLE" and point at the concrete
buyer-side check -- never a faked rate.

Honest shapes when a machine-readable per-KOV table ships (join,
never a gradient -- KOV-set rates vary by municipality but a
walk-graph gradient of a municipal decree is still fake
precision, nomap.md section 3 G16): RATE_JOINABLE params (p2 only)
graduate to per-KOV lookups fed ONLY by lookup_kov_rate on a
cached table; RATE_NEVER params (p73/p151/p422/p423) stay NULL
permanently -- their questions need a different record (KOV
määrus text, MaaMS law text, the deal's own tax bill) that no
rate table holds. The parse/index/lookup helpers below are the
pinned join path: pure, hermetic, fixture-tested, waiting for a
table.

Style mirrors services/scoring/dims_overturn_muinas.py (#237, the
closest sibling: same dated-negative NULL shape): every scorer is
pure and offline-tested -- (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest
snapshot tag for a KOV tax decree, so there is nothing for the
live path to fetch.

Helpers are local copies (not imported from livability, sibling
batches, dims_p4_emta, or dims_group16*): a future central hook
may import this module alongside them, and importing any of them
here would turn that into a cycle (same precedent as batch B3,
PR #100, group20a #212, and overturn #233). In particular
nothing is shared with the #256/#337 P4 EMTA pipeline -- the
G16 rate-table join stands alone.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Dated negative, not a stub farm: the five dims duplicate the
  group16a/16b None-stubs' questions on purpose -- the stubs say
  "no honest signal", these dims say "the named table was probed
  on this date and is PDF-only with no bulk feed, re-probe by
  RECHECK_AFTER". Same verdict, dated evidence.
* p2 alone is RATE_JOINABLE: it is the only param whose question
  a per-KOV table answers (which rate applies in this KOV this
  year). p73 stays NEVER even though KOV eriotsused exist --
  they are per-KOV decree texts in Riigi Teataja with no central
  table, and harvesting RT act texts is the scraping this repo
  refuses (AGENTS.md section 5).
* p422 stays NEVER (not joinable): Estonia has no supplemental-bill
  instrument -- a reassessment lands on the next year's regular
  bill, so the "bill" is the deal's own tax notice, never a
  table row. p151 stays NEVER: reassessment RULES are MaaMS law
  text, identical county-wide. p423 stays NEVER: no KOV levy
  register exists centrally.
* Band validation is year-gated: rows stamped STATUTORY_YEAR are
  rejected when outside the observed statutory bands (a dirty
  table can never fake a rate); rows from other years skip the
  band check because bands move yearly and only 2026 was
  observed -- unverifiable is unjoinable-adjacent, never coerced.
* KOV match is exact on the normalised name + year: a rate from
  the wrong KOV or the wrong year is a different decree, never
  a fallback. First wins on duplicates (stable, reviewable).
* No shared-file edits (dims_group16*.py, dims_p4_emta.py,
  livability.py, WEIGHTS, layers, nomap.md untouched): 3 new
  files only. The final docs-index PR updates nomap.md.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-issue WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, Iterable, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Verdict date (2026-09-13) -- the day the polite probes above ran.
VERDICT_DATE = "2026-09-13"

#: Re-probe the EMTA guide + yearly-table links no later than this
#: date (annual KOV-table cadence with margin; matches #233/#240).
RECHECK_AFTER = "2027-03-13"

#: The public EMTA land-tax guide (stable page; yearly per-KOV
#: tables are linked off it -- Nextcloud-share PDFs as of
#: VERDICT_DATE).
EMTA_MAAMAKS_GUIDE_PATH = (
    "/eraklient/maksud-ja-tasumine/muud-maksud/maamaks")
EMTA_BASE_URL = "https://www.emta.ee"

#: Yearly per-KOV table editions linked off the guide on
#: VERDICT_DATE (all labelled "pdf", Nextcloud shares).
KOV_TABLE_YEARS = ("2022", "2023", "2024", "2025", "2026")

#: Observed 2026 statutory bands, percent (guide visible text,
#: VERDICT_DATE). Year-gated: only rows stamped STATUTORY_YEAR
#: are validated against these.
STATUTORY_YEAR = 2026
ELAMUMAA_BAND = (0.1, 1.0)
MAATULUNDUSMAA_BAND = (0.1, 0.5)
MUU_BAND = (0.1, 2.0)

#: The one param a per-KOV table CAN answer once joined (which
#: rate applies in this KOV this year -- still never a gradient:
#: a municipal decree is not a field).
RATE_JOINABLE = ("p2",)

#: Params whose question no rate table can answer (wrong record
#: type by construction -- stay NULL permanently, see docstring).
RATE_NEVER = ("p73", "p151", "p422", "p423")


def build_guide_url() -> str:
    """The stable EMTA maamaks guide URL (tables linked off it)."""
    return "%s%s" % (EMTA_BASE_URL, EMTA_MAAMAKS_GUIDE_PATH)


# ---------------------------------------------------------------------------
# Per-KOV rate-table join (pure, hermetic, fixture-tested). Today the
# index is always empty (no machine-readable table: PDF-only shares
# above); the helpers pin the contract the reopen PR feeds with a
# cached table.
# ---------------------------------------------------------------------------

def _norm_kov(kov: object) -> Optional[str]:
    if not isinstance(kov, str) or not kov.strip():
        return None
    return " ".join(kov.strip().casefold().split())


def _in_band(value: object, band: Tuple[float, float]) -> bool:
    return isinstance(value, (int, float)) and band[0] <= value <= band[1]


def parse_kov_row(row: object) -> Optional[dict]:
    """Normalize one raw per-KOV rate-table row to a joinable record.

    Fixture shape (synthetic, see module docstring): {"kov": str,
    "year": int, "elamumaa_pct": float, "maatulundusmaa_pct": float,
    "muu_pct": float}. Returns None for anything unjoinable --
    missing/blank KOV, non-int year, non-numeric rates, or a
    STATUTORY_YEAR row outside the observed statutory bands -- so
    a dirty table can never fake a rate.
    """
    if not isinstance(row, dict):
        return None
    kov = _norm_kov(row.get("kov"))
    if kov is None:
        return None
    year = row.get("year")
    if not isinstance(year, int):
        return None
    rates = {}
    for key in ("elamumaa_pct", "maatulundusmaa_pct", "muu_pct"):
        value = row.get(key)
        if not isinstance(value, (int, float)):
            return None
        rates[key] = float(value)
    if year == STATUTORY_YEAR:
        if not _in_band(rates["elamumaa_pct"], ELAMUMAA_BAND):
            return None
        if not _in_band(rates["maatulundusmaa_pct"],
                        MAATULUNDUSMAA_BAND):
            return None
        if not _in_band(rates["muu_pct"], MUU_BAND):
            return None
    return {"kov": kov, "year": year, **rates}


def build_kov_index(rows: Iterable[dict]) -> Dict[Tuple[str, int], dict]:
    """Index parsed KOV rate records by (kov, year) (first wins).

    Unparseable rows are skipped, never coerced: a table gap stays
    a gap (NULL with KOV-table reason downstream), not a guess.
    """
    index: Dict[Tuple[str, int], dict] = {}
    for row in rows or []:
        parsed = parse_kov_row(row)
        if parsed is not None:
            key = (parsed["kov"], parsed["year"])
            if key not in index:
                index[key] = parsed
    return index


def lookup_kov_rate(kov: object, year: object,
                    index: Optional[Dict[Tuple[str, int], dict]]
                    ) -> Optional[dict]:
    """Exact-match rate lookup for one KOV + year.

    Returns the joined record, or None where unresolvable (unknown
    KOV, non-int year, empty table): NULL-with-KOV-table-reason
    downstream, never a neighbouring KOV's decree or another
    year's rate.
    """
    name = _norm_kov(kov)
    if name is None or not isinstance(year, int):
        return None
    if not index:
        return None
    return index.get((name, year))


# ---------------------------------------------------------------------------
# p2/p73/p151/p422/p423: documented no-table tax NULLs (OTA PR #131
# precedent). Each scorer reports the gap with the concrete
# buyer-side check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_property_taxes_overturn(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """p2: NULL -- per-KOV rates are PDF-only (no bulk join)."""
    _ = (origin, pois)
    return None, ("Maamaksumäära (KOV-tabel) hinnangut EI OLE võimalik "
                  "anda -- KOV-määrade masinloetav koondtabel puudub "
                  "(EMTA juhend lehel on 2022-2026 tabelid ainult "
                  "Nextcloud-pdf-id, hulgiliidest EI OLE, kontrollitud "
                  "2026-09-13): küsi KOV maamaksumäärade tabelist "
                  "käesolevaks aastaks ja arvesta koduomaniku "
                  "soodustusega (isikupõhine, MaaMS § 11), ära feigi "
                  "naaber-KOV määra (puuduv väärtus katkestab tehingu "
                  "skoori)")


def dim_special_tax_overturn(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p73: NULL -- KOV eriotsused have no central table (never)."""
    _ = (origin, pois)
    return None, ("Erimaksustamise (KOV eriotsused/tasud) hinnangut EI OLE "
                  "võimalik anda -- eriotsused on KOV määruste tekstid "
                  "(Riigi Teataja), millele koondtabelit EI OLE "
                  "(kontrollitud 2026-09-13): küsi KOV maksuinfost, kas "
                  "kinnistule rakendub eriotsus, ära feigi -- määruse "
                  "kaevandamine hajutatud aktidest ei ole aus liides")


def dim_tax_reassessment_overturn(origin: Optional[Tuple[float, float]],
                                  pois: Optional[List[dict]]) -> Score:
    """p151: NULL -- reassessment rules are law text (never)."""
    _ = (origin, pois)
    return None, ("Maamaksu ümberhindluse reeglite hinnangut EI OLE "
                  "võimalik kaardist anda -- reeglid on maamaksuseaduse "
                  "tekst, mis kehtib maakonnas ühtemoodi "
                  "(kontrollitud 2026-09-13): loe EMTA juhendi "
                  "ümberhindluse jaotist ja KOV rakendusinfot, ära feigi "
                  "-- üleriigiline reegel ei ole kohahinnang")


def dim_supplemental_tax_overturn(origin: Optional[Tuple[float, float]],
                                  pois: Optional[List[dict]]) -> Score:
    """p422: NULL -- no supplemental-bill instrument (never)."""
    _ = (origin, pois)
    return None, ("Lisamaksuarve (ümberhindlus) hinnangut EI OLE võimalik "
                  "anda -- Eestis eraldi lisamaksuarve instrumenti EI OLE: "
                  "ümberhindlus jõuab järgmise aasta tavalisele arvele "
                  "(kontrollitud 2026-09-13): küsi müüjalt/notarilt "
                  "kinnistu viimast maksuteadet (e-MTA), ära feigi -- "
                  "arve on tehingu-, mitte koha-fakt")


def dim_assessment_district_overturn(
        origin: Optional[Tuple[float, float]],
        pois: Optional[List[dict]]) -> Score:
    """p423: NULL -- no KOV levy register exists (never)."""
    _ = (origin, pois)
    return None, ("Erimaksupiirkonna (levy) hinnangut EI OLE võimalik anda "
                  "-- KOV eritasude keskregistrit EI OLE "
                  "(kontrollitud 2026-09-13): küsi KOV-st, kas aadress "
                  "jääb eritasupiirkonda, ära feigi -- registrita "
                  "gradient oleks väljamõeldis")


#: Registry for the central weight-rebalance follow-up: (dims key, param id, fn).
EMTA_OVERTURN_DIMS = (
    ("property_taxes_overturn", "p2", dim_property_taxes_overturn),
    ("special_tax_overturn", "p73", dim_special_tax_overturn),
    ("tax_reassessment_overturn", "p151", dim_tax_reassessment_overturn),
    ("supplemental_tax_overturn", "p422", dim_supplemental_tax_overturn),
    ("assessment_district_overturn", "p423",
     dim_assessment_district_overturn),
)


def score_overturn_emta(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]
                        ) -> Dict[str, Optional[int]]:
    """The five G16 EMTA/KOV overturn-check dims for one listing (entry
    point for the weight-rebalance follow-up; keys match
    EMTA_OVERTURN_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in EMTA_OVERTURN_DIMS}
