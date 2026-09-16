"""P4 EMTA KOV-fiscal dims (issue #539): municipal tax-transfer
choropleth join (tulumaks + maamaks transferred to KOVs).

Source (probed 2026-09-16, one polite GET per endpoint, labelled
one-off User-Agent, `--max-time 25/60`, raw pages at /tmp/hf-probes/ --
one-off PR record, never committed):
* Old www.emta.ee stats paths 404 (site moved to emta.ee bare domain).
* andmed.eesti.ee dataset page renders the Teabevarav JS shell only
  (75 497 bytes, no server rows -- same shell as #264/#277/#284).
* New open-data page (HTTP 200, 296 288 bytes):
  https://emta.ee/eraklient/amet-uudised-ja-kontakt/uudised-pressiinfo-statistika/statistika-ja-avaandmed
  section "#kov-tulumaks-maamaks" (kohalikele omavalitsustele ule
  kantud tulumaks ja maamaks) with yearly files 2019-2026 in BOTH
  XLSX and CSV, e.g. 2026: tulumaks_2026.xlsx/.csv,
  maamaks_2026.xlsx/.csv on ncfailid.emta.ee share links.
* 2026 CSVs pulled once each (redirect followed, HTTP 200, 9 893 +
  17 837 bytes): `;`-delimited, BOM, Estonian thousands spaces;
  header rows: title / months Jan-Dec x (2026, 2025) / `Kood` row;
  78 numeric-KOV data rows each; ALL 16 Harjumaa KOVs present in both.
* Schema: EHAK `Kood` column + KOV name + monthly tulumaks/maamaks
  (EUR) + `Kokku` totals. No population column -- per-capita needs a
  rahvastik join this issue does not own (Statamet PX-Web cousin).

LICENCE (reviewer call, verified before ingesting per the issue's hard
gate): the catalogue states NONE, and the EMTA page carries no CC
machine tag either. What it does carry: the files are published by the
publisher itself under its "Maksu- ja Tolliameti avaandmed" section,
cross-linked from "Teabevarav / Eesti riigi avaandmete ametlik
portaal". That is a publisher-declared open-data publication, so this
module proceeds WITH attribution (`EMTA_ATTRIBUTION`) and WITHOUT
committing any pulled data (fixtures synthetic; harvest reads
maintainer-placed CSVs). If the reviewer reads the gate strictly
(machine-readable CC tag or nothing), flip to documented no-map: the
licence evidence above is pasted verbatim in docs/p4_emta_kov.md.

Params (this module only -- sibling batches own disjoint sets):
* P4-019 KOV fiscal health, transfer-composition leg: maamaks share of
  total KOV transfers (population-free burden proxy). The maamaks
  rate-level leg stays in dims_p4_emta, the budget/Statamet legs with
  their owners -- distinct dim keys, no double-score.

HONESTY (AGENTS.md section 7.2): unknown KOV -> NULL (never forced);
every reason says "hinnang" and states transfers != service quality.
Inside-Tallinn flatness (issue #521) is expected: Tallinn is one KOV
row -- stated, not fixed here.

Style mirrors services/scoring/dims_p4_emta.py (#256/#337): pure
(kov, table) -> (Optional[int 0..100], Estonian reason), absolute
bands, hermetic fixture tests. Network lives only in the harvest
(batch_emta_choropleth.py, maintainer-placed CSVs); tests never touch
it.

BANDS (locked 2026-09-16 from the measured Harjumaa-KOV distribution,
16 KOVs, 2025 full-year totals -- see docs/p4_emta_kov.md):
* maamaks_share_2025 = maamaks/(maamaks+tulumaks): p33 = 2.95%,
  p67 = 4.37% -> <=3.0 -> 70, <=4.4 -> 55, above -> 40.
  (Low share: Keila 1.50%, Raasiku 2.21%; high: Jõelähtme 9.72%,
  Maardu 9.44%, Viimsi 6.41%.)

Judgment calls (reviewable per AGENTS.md section 7.5):
* Share-of-transfers INSTEAD of per-capita: totals alone would rank
  Tallinn worst (33.9M maamaks) and Loksa best (81k) -- dishonest
  without the rahvastik join. The share is comparable across KOV sizes
  from the two files alone.
* The YoY maamaks trend (2026 Jan-Aug vs 2025 Jan-Aug) is COMPUTED by
  the batch but NOT scored: the 2025 land-revaluation reform makes one
  jump (Rae +83.9%, Raasiku +38.4%, Jõelähtme +36.6%) reform noise, not
  a persistent burden signal. Revisit with 2026-full + 2027.
* EHAK-code join first, normalised-name fallback second (MARU
  precedent); unmapped rows stay NULL, never forced (issue criterion).

Integration (deliberately NOT done here): KOV-code wiring from the
listing (EHAK lookup) inside livability scoring and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches -- existing tests pin set(WEIGHTS) exactly.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Attribution: publisher-declared open data (see licence note above).
EMTA_ATTRIBUTION = ("EMTA (Maksu- ja Tolliamet), avaandmed / "
                    "statistika-ja-avaandmed")

#: 2026 open-data page (verified 2026-09-16): yearly 2019-2026 files.
EMTA_KOV_SECTION_URL = (
    "https://emta.ee/eraklient/amet-uudised-ja-kontakt/"
    "uudised-pressiinfo-statistika/statistika-ja-avaandmed"
    "#kov-tulumaks-maamaks"
)

#: Monthly harvest at most (issue constraint).
EMTA_KOV_TTL_DAYS = 30

#: Band cutoffs locked 2026-09-16 (Harjumaa tertiles p33/p67).
SHARE_LO = 3.0
SHARE_HI = 4.4

#: 16 Harjumaa EHAK codes measured in the 2026 files (2026-09-16).
HARJUMAA_KOV_CODES = frozenset([
    "141", "198", "245", "296", "305", "338", "353", "424",
    "431", "446", "651", "653", "719", "725", "784", "890",
])


def normalise_kov(name: str) -> str:
    """Lowercase + whitespace collapse (MARU precedent, no fuzz)."""
    return " ".join(name.lower().split())


def kov_lookup_key(kov_code: Optional[str],
                   kov_name: Optional[str]) -> Optional[str]:
    """Join key: exact EHAK code wins, else the normalised name."""
    if kov_code and kov_code.strip():
        return "code:" + kov_code.strip()
    if kov_name and kov_name.strip():
        return "name:" + normalise_kov(kov_name)
    return None


def dim_maamaks_burden(
        kov_code: Optional[str],
        kov_name: Optional[str],
        table: Optional[Dict[str, Dict[str, float]]],
) -> Score:
    """P4-019 transfer leg: maamaks share of KOV transfers -> 70/55/40.

    `table` maps lookup keys (as built by kov_lookup_key) to
    {"maamaks_share_2025": pct, ...}. Unknown KOV -> NULL with the
    buyer-side check (p4_emta rate PDFs); never forced.
    """
    if table:
        for key in (kov_lookup_key(kov_code, None),
                    kov_lookup_key(None, kov_name)):
            if key is not None and key in table:
                share = None
                for field, val in table[key].items():
                    if field.startswith("maamaks_share_"):
                        share = val
                        break
                if share is None:
                    break
                label = kov_code or kov_name
                if share <= SHARE_LO:
                    return 70, ("Maamaksukoormuse hinnang KOV %s: madal "
                                "(maamaks %.2f%% KOV ulekannetest 2025, "
                                "EMTA avaandmed; ulekanded ei ole "
                                "teenusekvaliteedi moot)" % (label, share))
                if share <= SHARE_HI:
                    return 55, ("Maamaksukoormuse hinnang KOV %s: keskmine "
                                "(maamaks %.2f%% KOV ulekannetest 2025, "
                                "EMTA avaandmed; ulekanded ei ole "
                                "teenusekvaliteedi moot)" % (label, share))
                return 40, ("Maamaksukoormuse hinnang KOV %s: korge "
                            "(maamaks %.2f%% KOV ulekannetest 2025, "
                            "EMTA avaandmed; omanikud kannavad suhteliselt "
                            "rohkem maamaksu kaudu; ulekanded ei ole "
                            "teenusekvaliteedi moot)" % (label, share))
    return None, ("KOV maksubaarite hinnangut pole (EI OLE selle KOV "
                  "EMTA ulekanderida tabelis -- tundmatu KOV, rida "
                  "puudub voi jagamine on teadmata): kontrolli KOV "
                  "maamaksumaara 2026. aasta tabelist (p4_emta) ja KOV "
                  "eelarvet; Tallinna sees on uks KOV-rida (#521)")


#: Registry for UI/API wiring on integration: param -> (title, fn).
P4_EMTA_KOV_DIMS: Dict[str, Tuple[str, object]] = {
    "maamaks_burden": ("Maamaksukoormus (EMTA KOV ülekanded)",
                       dim_maamaks_burden),
}


def score_p4_emta_kov(
        kov_code: Optional[str],
        kov_name: Optional[str],
        table: Optional[Dict[str, Dict[str, float]]],
) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All P4-EMTA-KOV dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in P4_EMTA_KOV_DIMS.items():
        v, reason = fn(kov_code, kov_name, table)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
