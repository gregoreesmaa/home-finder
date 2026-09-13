"""Group 16 macro/finance per-listing dimensions, batch B (issue #206).

Params (this agent only — sibling batches own disjoint sets):
* p241 attractive-nuisance liability -> ALWAYS None (parcel legal fact)
* p243 flood-insurance premium caps -> ALWAYS None (insurer tariff fact)
* p249 transferable solar leases -> ALWAYS None (deal contract fact)
* p250 conservation tax credits -> ALWAYS None (Keskkonnaamet/EMTA registry)
* p318 unfunded municipal pension liability -> ALWAYS None (KOV books)
* p363 1031-exchange eligibility -> ALWAYS None (US concept, no EE equivalent)
* p366 tax abatement expirations -> ALWAYS None (deal contract fact)
* p370 flip/transfer tax -> ALWAYS None (deal cost fact)
* p421 appraisal gap risk -> ALWAYS None (deal valuation fact)
* p422 supplemental tax bills -> ALWAYS None (deal tax fact)
* p423 special assessment districts -> ALWAYS None (KOV levy registry)
* p424 PMI cancellation threshold -> ALWAYS None (US product, no EE equivalent)
* p425 energy-efficient mortgage -> ALWAYS None (US product, no EE equivalent)
* p426 capital gains exclusions -> ALWAYS None (US rule, no EE equivalent)
* p430 escrow buffer requirements -> ALWAYS None (loan contract fact)
* p444 summer tourist influx -> ALWAYS None (seasonal market-wide pulse)
* p481 street price ceiling -> ALWAYS None (deal comp fact, needs comps)
* p482 corporate ownership density -> ALWAYS None (registry aggregate)
* p483 shadow inventory -> ALWAYS None (market-wide estimate)
* p484 absorption rate -> ALWAYS None (market-wide series)
* p486 land-to-improvement ratio -> ALWAYS None (appraisal fact)
* p487 demographic transition -> ALWAYS None (market-wide slow series)

HONESTY (AGENTS.md section 7.2, OTA PR #131 precedent): the Maa-amet
tehingute andmebaas aggregates, Statistikaamet HH01/KK11 series, ECB
Euribor, EMTA/KOV tax registers and the kinnistusraamatu ownership
structure are NOT in the 2026-09-12 snapshot, and market-WIDE series
are one value for the whole market — painting a city-wide constant as
a gradient would be fake precision (a flat colour is not a map). Deal
facts (p241/p249/p363/p366/p370/p421/p422/p424/p425/p426/p430/p481/
p486) attach to the transaction or parcel, never to an area, and the
US-jurisdiction concepts (p363/p370/p424/p425/p426) have no Estonian
register at all. So every scorer returns None for EVERY input with an
Estonian reason that says "hinnang"/"EI OLE", names the missing
registry (or the deal/bank/notary check), and never presents a number.

Style mirrors sibling batch dims_group03b.py (#152): every scorer is
pure and offline-tested — (origin, pois) -> (None, Estonian reason).
Network lives only in livability.fetch_pois; this module adds no
network calls, no Overpass fragment and no tag mapping, because there
is no snapshot signal to query — a future central hook only needs
GROUP16B_DIMS + score_group16b below.

Integration (deliberately NOT done here): these dims are NULL-only, so
there is nothing to add to livability.OVERPASS_QUERY,
livability._POI_KIND or livability.WEIGHTS. Rebalancing WEIGHTS must
be one joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (always None, Estonian reason)


def dim_nuisance_liability(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p241: NULL — liability exposure is a parcel legal fact (do not fake)."""
    return None, ("Atraktiivse ohuallika vastutus on krundi-põhine õiguslik "
                  "hinnang — kaardikihti EI OLE: vajab notari/kindlustuse "
                  "kontrolli (EI OLE hinnangut, ära feigi)")


def dim_flood_insurance_caps(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p243: NULL — premium caps live in insurer tariff tables (do not fake)."""
    return None, ("Üleujutuskindlustuse limiitide registrit/tariifitabeleid "
                  "snapshots pole — vajab kindlustuspakkumise hinnangut (EI OLE "
                  "hinnangut, ära feigi)")


def dim_solar_lease_transfer(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p249: NULL — lease transferability is a deal contract fact (do not fake)."""
    return None, ("Päikesepargi rendilepingu ülekantavus on tehingu-põhine "
                  "lepingufakt — kaardisignaali EI OLE: vajab müügilepingu "
                  "kontrolli (EI OLE hinnangut, ära feigi)")


def dim_conservation_credits(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p250: NULL — conservation credits need the Keskkonnaamet/EMTA entry."""
    return None, ("Looduskaitse maksusoodustuste registrikannet "
                  "(Keskkonnaamet/EMTA) snapshots pole — vajab maksuameti "
                  "kontrolli (EI OLE hinnangut, ära feigi)")


def dim_pension_liability(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p318: NULL — KOV pension books are not in the snapshot (do not fake)."""
    return None, ("KOV rahastamata pensionikohustuste raamatupidamist "
                  "snapshots pole — vajab omavalitsuse eelarve hinnangut (EI OLE "
                  "hinnangut, ära feigi)")


def dim_exchange_eligibility(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p363: NULL — US 1031 exchange has no Estonian equivalent (do not fake)."""
    return None, ("1031-vahetus on USA maksukontseptsioon, millele Eesti "
                  "registrites vastet EI OLE — vajab maksunõustaja kontrolli "
                  "(EI OLE hinnangut, ära feigi)")


def dim_abatement_expiry(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p366: NULL — abatement expiry is a deal contract fact (do not fake)."""
    return None, ("Maksuvabastuse lõpptähtaeg on konkreetse tehingu "
                  "lepingufakt — kaardisignaali EI OLE: vajab notari/müüja "
                  "kontrolli (EI OLE hinnangut, ära feigi)")


def dim_transfer_fees(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p370: NULL — transfer fees are a deal cost fact (do not fake)."""
    return None, ("Võõrandamistasu/flip-maks on tehingu-põhine kulu — Eesti "
                  "registrites USA-tüüpi vastet EI OLE: vajab notaritariifi "
                  "kontrolli (EI OLE hinnangut, ära feigi)")


def dim_appraisal_gap(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p421: NULL — the gap exists only inside a concrete deal (do not fake)."""
    return None, ("Hindamisakti lõhe tekib alles konkreetses tehingus — "
                  "kaardisignaali EI OLE: vajab panga hindamisakti hinnangut "
                  "(EI OLE hinnangut, ära feigi)")


def dim_supplemental_tax(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p422: NULL — supplemental bills are a deal tax fact (do not fake)."""
    return None, ("Lisamaksuarvete (ümberhindlus) registrit snapshots pole — "
                  "konkreetse tehingu maksufakt vajab maksuameti kontrolli "
                  "(EI OLE hinnangut, ära feigi)")


def dim_assessment_district(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p423: NULL — KOV special-levy register is not in the snapshot."""
    return None, ("KOV eritasude/erihindamispiirkondade registrit snapshots "
                  "pole — vajab KOV-tabeli kontrolli (EI OLE hinnangut, "
                  "ära feigi)")


def dim_pmi_threshold(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p424: NULL — US PMI has no Estonian equivalent (do not fake)."""
    return None, ("PMI-lõpetamise lävi on USA laenutoote tingimus, millele "
                  "Eesti registrites vastet EI OLE — vajab pangatingimuste "
                  "kontrolli (EI OLE hinnangut, ära feigi)")


def dim_eem_loan(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p425: NULL — US EEM has no Estonian equivalent (do not fake)."""
    return None, ("Energiasäästlik hüpoteek (USA EEM) on USA laenutoode, "
                  "millele Eesti registrites vastet EI OLE — vajab panga "
                  "rohe-laenu kontrolli (EI OLE hinnangut, ära feigi)")


def dim_capital_gains(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p426: NULL — US exclusion has no Estonian equivalent (do not fake)."""
    return None, ("Kapitalikasumi vabastus (USA §121 loogika) on USA "
                  "maksureegel, millele Eesti tulumaksuseaduses samaväärset "
                  "EI OLE — vajab maksunõustaja kontrolli (EI OLE hinnangut, "
                  "ära feigi)")


def dim_escrow_buffer(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p430: NULL — escrow buffer is a loan-contract term (do not fake)."""
    return None, ("Deponeerimisreservi nõue on konkreetse laenulepingu "
                  "tingimus — kaardisignaali EI OLE: vajab pangatingimuste "
                  "kontrolli (EI OLE hinnangut, ära feigi)")


def dim_tourist_influx(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p444: NULL — seasonal market-wide pulse, never an area signal."""
    return None, ("Suvine turistide juurdevool on hooajaline turu-ülene "
                  "hinnang (Statistikaameti majutusstatistika), mitte "
                  "koha-signaal — kaardigradienti EI OLE (EI OLE "
                  "kvartali-hinnangut, ära feigi)")


def dim_price_ceiling(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p481: NULL — street ceiling needs closed comps for the listing."""
    return None, ("Tänava hinnalagi on Maa-ameti tehingute andmebaasi "
                  "võrdlushinnang konkreetse kuulutuse suhtes — asukoha- "
                  "gradienti EI OLE: lagi ilma tehinguteta oleks feik (EI OLE "
                  "hinnangut, ära feigi)")


def dim_corporate_density(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p482: NULL — ownership structure needs the land-register aggregate."""
    return None, ("Juriidiliste omanike osakaalu registriagregaati "
                  "(kinnistusraamat/tehingud) snapshots pole — turu-ülene "
                  "konstant gradiendina EI OLE (EI OLE hinnangut, ära feigi)")


def dim_shadow_inventory(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p483: NULL — shadow inventory is a market-wide estimate (do not fake)."""
    return None, ("Varjatud pakkumine on turu-ülene hinnang, mitte "
                  "koha-signaal — kaardigradienti EI OLE: ühte turu konstanti "
                  "ei lahutata kvartaliteks (EI OLE hinnangut, ära feigi)")


def dim_absorption_rate(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p484: NULL — absorption is a market-wide series, never an area signal."""
    return None, ("Neeldumiskiirus (Maa-amet/Statistikaameti tehingute "
                  "agregaat) on turu-ülene seeria, mitte koha-signaal — "
                  "kaardigradienti EI OLE (EI OLE kvartali-hinnangut, "
                  "ära feigi)")


def dim_land_improvement_ratio(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """p486: NULL — the ratio is an appraisal fact for the parcel."""
    return None, ("Maa-parenduste suhe selgub konkreetse hindamisakti/ "
                  "tehingu hinnangust — kaardisignaali EI OLE: vajab "
                  "hindamisakti kontrolli (EI OLE hinnangut, ära feigi)")


def dim_demographic_transition(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """p487: NULL — demographic drift is a slow market-wide series."""
    return None, ("Demograafiline üleminek (Statistikaameti "
                  "rahvastikustatistika) on aeglane turu-ülene seeria, mitte "
                  "koha-signaal — kaardigradienti EI OLE (EI OLE "
                  "kvartali-hinnangut, ära feigi)")


GROUP16B_DIMS = (
    ("nuisance_liability", "p241", dim_nuisance_liability),
    ("flood_insurance_caps", "p243", dim_flood_insurance_caps),
    ("solar_lease_transfer", "p249", dim_solar_lease_transfer),
    ("conservation_credits", "p250", dim_conservation_credits),
    ("pension_liability", "p318", dim_pension_liability),
    ("exchange_eligibility", "p363", dim_exchange_eligibility),
    ("abatement_expiry", "p366", dim_abatement_expiry),
    ("transfer_fees", "p370", dim_transfer_fees),
    ("appraisal_gap", "p421", dim_appraisal_gap),
    ("supplemental_tax", "p422", dim_supplemental_tax),
    ("assessment_district", "p423", dim_assessment_district),
    ("pmi_threshold", "p424", dim_pmi_threshold),
    ("eem_loan", "p425", dim_eem_loan),
    ("capital_gains", "p426", dim_capital_gains),
    ("escrow_buffer", "p430", dim_escrow_buffer),
    ("tourist_influx", "p444", dim_tourist_influx),
    ("price_ceiling", "p481", dim_price_ceiling),
    ("corporate_density", "p482", dim_corporate_density),
    ("shadow_inventory", "p483", dim_shadow_inventory),
    ("absorption_rate", "p484", dim_absorption_rate),
    ("land_improvement_ratio", "p486", dim_land_improvement_ratio),
    ("demographic_transition", "p487", dim_demographic_transition),
)


def score_group16b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All twenty-two Group 16 batch-B dims for one listing (entry point
    for the weight-rebalance follow-up; keys match GROUP16B_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP16B_DIMS}
