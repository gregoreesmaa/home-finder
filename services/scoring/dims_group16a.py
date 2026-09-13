"""Group 16 macro/finance per-listing dimensions, batch A (issue #205).

Params (this agent only — sibling batches own disjoint sets):
* p2 property taxes -> dim_property_taxes (EMTA/KOV land-tax table)
* p6 mortgage interest rates -> dim_mortgage_rates (ECB Euribor + Eesti Pank MFI)
* p7 homeowners insurance -> dim_home_insurance (insurer quote, per building)
* p8 closing costs -> dim_closing_costs (notary/fees, per deal)
* p9 down payment requirements -> dim_down_payment (bank policy + buyer)
* p41 historical appreciation -> dim_historical_appreciation (Maa-amet tehingud / HH01)
* p43 resale appeal -> dim_resale_appeal (multi-registry comp judgment)
* p70 home insurability -> dim_home_insurability (insurer risk decision)
* p73 special tax assessment -> dim_special_tax_assessment (KOV table)
* p77 municipal fiscal health -> dim_municipal_fiscal_health (KOV budget / EMTA arrears)
* p143 assumable mortgages -> dim_assumable_mortgages (loan contract term)
* p147 contractor availability -> dim_contractor_availability (market, not a registry)
* p148 relocation incentives -> dim_relocation_incentives (KOV/employer programmes)
* p149 market liquidity -> dim_market_liquidity (Maa-amet volumes / KK11)
* p151 tax reassessment rules -> dim_tax_reassessment (law + KOV application)
* p153 seller concessions -> dim_seller_concessions (negotiation outcome)
* p155 mortgage portability -> dim_mortgage_portability (bank contract term)
* p156 first-time buyer programs -> dim_first_time_buyer (KredEx/state, national)
* p157 rent-back feasibility -> dim_rent_back (deal-structure agreement)
* p159 opportunity zones -> dim_opportunity_zones (zone/planning register)
* p160 title insurance costs -> dim_title_insurance (notary + kinnistusraamat)
* p185 net-metering laws -> dim_net_metering (law + Elering terms, national)

HONESTY (AGENTS.md section 7.2): the Maa-amet tehingud medians,
Statistikaamet HH01/KK11 aggregates, EMTA land-tax tables and KOV
budgets are quarterly/annual REGISTRY tables that are NOT in the
2026-09-12 OSM snapshot, and the ECB 6M Euribor / Eesti Pank MFI /
KredEx / net-metering inputs are NATIONAL series or rules — identical
in Tallinn and rural Harjumaa. Every scorer therefore returns None
with a buyer-check reason naming the missing registry. Reasons say
"hinnang" (estimate) and "EI OLE" (there is none) — never measured
rates, taxes, deal terms, or resolved programme eligibility. The
national series (p6/p156/p185) are NEVER presented as area signals:
a county-wide gradient of a single national number would be fake
precision (OTA PR #131 precedent).

Style mirrors sibling batch dims_group03b.py (#152): every scorer is
pure and offline-tested — (origin, pois) -> (None, Estonian reason).
Network lives only in livability.fetch_pois; this module adds no
network calls and no Overpass fragment — there is no OSM tag that can
honestly proxy a mortgage rate, a tax table, or a deal term, so there
is deliberately NO GROUP16A_OVERPASS_FRAGMENT, NO GROUP16A_POI_KIND
and NO kinds_from_tags (a fragment here would only invite faking one).

Helpers are intentionally absent (not even local haversine copies):
with zero distance-scored dims there is nothing for them to serve,
and importing them from livability or sibling batches would turn a
future central hook into a cycle (same precedent as batch B3, PR
#100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* ALL 22 dims return None for EVERY input including missing origin:
  inventing a gradient from zero snapshot signal would be fake
  precision. The reasons point at the registry/bank/KOV check the
  buyer must do instead.
* KOV-set rates (p2/p73) DO vary by municipality, but the EMTA/KOV
  table is not in-snapshot — so even they stay NULL rather than get
  a KOV-coloured invented map.
* p143 notes the Estonian reality (fixed-rate loans generally do not
  transfer); p160 notes title insurance as a US product is virtually
  absent in Estonia (kinnistusraamat + notary carry the function).

Integration (deliberately NOT done here): consuming these dims in a
weight rebalance must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


def dim_property_taxes(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p2: NULL — EMTA/KOV land-tax table is not in the snapshot."""
    return None, ("Maamaksu määrad (EMTA/KOV tabel) snapshots pole — vajab KOV "
                  "maamaksu tabeli kontrolli (EI OLE hinnangut, ära feigi)")


def dim_mortgage_rates(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p6: NULL — Euribor/MFI is a national series, never an area signal."""
    return None, ("6M Euribor (ECB) + Eesti Pank MFI on üleriigiline seeria, mis "
                  "Tallinnas ja maal ei erine — vajab panga pakkumust (EI OLE "
                  "kohahinnangut, ära feigi)")


def dim_home_insurance(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p7: NULL — insurance price is a per-building quote."""
    return None, ("Kodukindlustuse hind on hoone-põhine pakkumus, tariife snapshots "
                  "pole — vajab võrdluspakkumust (EI OLE hinnangut, ära feigi)")


def dim_closing_costs(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p8: NULL — closing costs are per-deal arithmetic, not a place fact."""
    return None, ("Notari- ja tehingukulud sõltuvad tehinguhinnast ja -vormist — "
                  "vajab notarikulu kalkulaatorit (EI OLE hinnangut snapshots, "
                  "ära feigi)")


def dim_down_payment(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p9: NULL — down payment is bank policy + buyer profile."""
    return None, ("Sissemakse nõue on panga poliitika + ostja profiil — vajab "
                  "pangatingimuste kontrolli (EI OLE hinnangut snapshots, ära feigi)")


def dim_historical_appreciation(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """p41: NULL — price history lives in registry tables, not the snapshot."""
    return None, ("Hinnajalugu (Maa-amet tehingud / Statistikaamet HH01) on kvartali "
                  "registritabel, mida snapshots pole — vajab registri väljavõtet "
                  "(EI OLE hinnangut, ära feigi)")


def dim_resale_appeal(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p43: NULL — resale appeal is a multi-registry comp judgment."""
    return None, ("Edasimüügi atraktiivsus on mitme registri koondotsus — vajab "
                  "maakleri võrdlustehingute (comp) kontrolli (EI OLE ühte "
                  "hinnangut snapshots, ära feigi)")


def dim_home_insurability(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p70: NULL — insurability is the insurer's per-building decision."""
    return None, ("Kindlustatavus on seltsi riskiotsus hoone kohta — vajab "
                  "kindlustusseltsi eelkinnitust (EI OLE hinnangut snapshots, "
                  "ära feigi)")


def dim_special_tax_assessment(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """p73: NULL — special assessments live in the KOV table."""
    return None, ("Erimaksustamine (KOV eriotsused/tasud) on registritabel, mida "
                  "snapshots pole — vajab KOV-maksuinfo kontrolli (EI OLE "
                  "hinnangut, ära feigi)")


def dim_municipal_fiscal_health(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """p77: NULL — OSM geometry does not measure a municipal budget."""
    return None, ("KOV fiskaaltervis (eelarve/maksuvõlad, EMTA avaandmed) on aastane "
                  "registrifakt — vajab KOV majandusaasta aruande kontrolli (EI OLE "
                  "hinnangut snapshots, ära feigi)")


def dim_assumable_mortgages(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p143: NULL — assumability is a clause in one specific loan contract."""
    return None, ("Laenu ülevõetavus on konkreetse lepingu tingimus (Eesti "
                  "fikseeritud laenud üldjuhul üle ei lähe) — vajab müüja panga "
                  "kinnitust (EI OLE hinnangut snapshots, ära feigi)")


def dim_contractor_availability(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """p147: NULL — crew availability is a market moment, not a registry fact."""
    return None, ("Ehitajate saadavus on turu hetkeseis (Äriregister loetleb firmasid, "
                  "mitte vabu brigaade) — vajab hinnapäringuid (EI OLE hinnangut "
                  "snapshots, ära feigi)")


def dim_relocation_incentives(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """p148: NULL — no central mappable table of relocation programmes."""
    return None, ("Kolimistoetused (KOV/tööandja programmid) on programmipõhised, "
                  "ühtset kaardistatavat tabelit pole — vajab KOV-toetuste kontrolli "
                  "(EI OLE hinnangut snapshots, ära feigi)")


def dim_market_liquidity(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p149: NULL — turnover speed lives in registry aggregates."""
    return None, ("Turulikviidsus (Maa-amet tehingute arv / KK11) on kvartali "
                  "registriagregaat, mida snapshots pole — vajab registri väljavõtet "
                  "(EI OLE hinnangut, ära feigi)")


def dim_tax_reassessment(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p151: NULL — reassessment rules are law text, not geometry."""
    return None, ("Maamaksu ümberhindluse reeglid (seadus + KOV rakendus) on õigusfakt "
                  "— vajab EMTA/KOV-info kontrolli (EI OLE hinnangut snapshots, "
                  "ära feigi)")


def dim_seller_concessions(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p153: NULL — concessions are born in negotiation, not on a map."""
    return None, ("Müüja järeleandmised sünnivad läbirääkimisel — vajab "
                  "pakkumisstrateegia kontrolli (EI OLE hinnangut snapshots, "
                  "ära feigi)")


def dim_mortgage_portability(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p155: NULL — portability is one bank's contract term."""
    return None, ("Laenu portatiivsus on konkreetse panga lepingutingimus — vajab "
                  "laenulepingu kontrolli (EI OLE hinnangut snapshots, ära feigi)")


def dim_first_time_buyer(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p156: NULL — KredEx/state rules are national, not an area signal."""
    return None, ("Esmakordse ostja programmid (KredEx/riik) on üleriigilised reeglid, "
                  "mis kaardipunktist ei sõltu — vajab programmi tingimuste kontrolli "
                  "(EI OLE kohahinnangut, ära feigi)")


def dim_rent_back(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p157: NULL — rent-back is a buyer/seller agreement."""
    return None, ("Tagasiüüri võimalus on müüja/ostja kokkulepe — vajab "
                  "tehingustruktuuri kontrolli (EI OLE hinnangut snapshots, "
                  "ära feigi)")


def dim_opportunity_zones(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p159: NULL — no zone register in-snapshot to colour a map from."""
    return None, ("Soodustsoonid on registri-/planeeringufakt (KOV planeeringuala on "
                  "krundi-põhine) — vajab planeeringuinfo kontrolli (EI OLE hinnangut "
                  "snapshots, ära feigi)")


def dim_title_insurance(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p160: NULL — per-deal closing cost; the US product barely exists in EE."""
    return None, ("Omandikindlustus/kinnistuskulud (notar + kinnistusraamat) on "
                  "tehingu-fakt — vajab notari/kinnistusraamatu kulukalkulaatorit "
                  "(EI OLE hinnangut snapshots, ära feigi)")


def dim_net_metering(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p185: NULL — grid rules are national, never an area signal."""
    return None, ("Netoarvestus (seadus + Eleringi/võrguettevõtja tingimused) on "
                  "üleriigiline reegel, tariif kaardil liikudes ei muutu — vajab "
                  "võrguettevõtja tingimuste kontrolli (EI OLE kohahinnangut, "
                  "ära feigi)")


GROUP16A_DIMS = (
    ("property_taxes", "p2", dim_property_taxes),
    ("mortgage_rates", "p6", dim_mortgage_rates),
    ("home_insurance", "p7", dim_home_insurance),
    ("closing_costs", "p8", dim_closing_costs),
    ("down_payment", "p9", dim_down_payment),
    ("historical_appreciation", "p41", dim_historical_appreciation),
    ("resale_appeal", "p43", dim_resale_appeal),
    ("home_insurability", "p70", dim_home_insurability),
    ("special_tax_assessment", "p73", dim_special_tax_assessment),
    ("municipal_fiscal_health", "p77", dim_municipal_fiscal_health),
    ("assumable_mortgages", "p143", dim_assumable_mortgages),
    ("contractor_availability", "p147", dim_contractor_availability),
    ("relocation_incentives", "p148", dim_relocation_incentives),
    ("market_liquidity", "p149", dim_market_liquidity),
    ("tax_reassessment", "p151", dim_tax_reassessment),
    ("seller_concessions", "p153", dim_seller_concessions),
    ("mortgage_portability", "p155", dim_mortgage_portability),
    ("first_time_buyer", "p156", dim_first_time_buyer),
    ("rent_back", "p157", dim_rent_back),
    ("opportunity_zones", "p159", dim_opportunity_zones),
    ("title_insurance", "p160", dim_title_insurance),
    ("net_metering", "p185", dim_net_metering),
)


def score_group16a(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All 22 Group 16 batch-A dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP16A_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP16A_DIMS}
