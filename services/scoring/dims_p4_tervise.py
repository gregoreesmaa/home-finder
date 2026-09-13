"""P4 Terviseamet (new uses) dims (issues #289 demo + #362 coverage).

Params (this module only — demo + its coverage follow-up share one source):
* P4-017 Drinking-water quality + sewer reality, Terviseamet seire leg:
  joogivee kvaliteedi seire, Tallinn proovid (batch 2, demo in #289)
* P4-024 Country-health nuisances, Terviseamet legs: tick stats
  (puukentsefaliit/puukborrelioos) + bathing-water quality
  (Pirita/Stroomi/Kakumäe) (batch 2, coverage in #362)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#289): Terviseamet publishes no pollable machine-readable feed for
either slice. Polite evidence, 6 tiny requests total (six single GETs
with a labelled one-off user-agent, headers + visible-text keyword
scope read only, no scraping, no auth, no form driving), raw bodies
cached at /tmp/tervise-open/ (TTL: one-off check, kept for the PR
record, never committed):
* https://www.terviseamet.ee/ -> HTTP 200, ~155 KB (cloudflare).
  Visible text (~6.9k chars) sweeps 0 for avaandmed / open data /
  GTFS / arendaja / developer / API / X-tee / andmestik /
  masinloetav. The water pages below are linked as human guidance
  pages (/keskkonnatervis/vesi/joogivesi, .../suplusvesi,
  /nakkushaigused/puugihaigused, /nakkushaigused/statistika).
* .../keskkonnatervis/vesi/joogivesi -> HTTP 200, ~173 KB.
  Visible text (~16.0k chars) sweeps 0 for avaandmed / API / X-tee /
  andmestik / masinloetav / csv / xls / json. File links are human
  PDFs only (indicator descriptions, lab certificates) plus the site
  RSS. The page points at the "Joogivee kvaliteedi andmebaas" on
  vtiav.sm.ee (next bullet).
* .../keskkonnatervis/vesi/suplusvesi -> HTTP 200, ~188 KB.
  Visible text (~18.6k chars): seire x6, proov x9, and the one
  "nõuetele vastav" hit is prose. File links are human PDFs only
  (Suplusvee kvaliteediklassid 2025, Supluskohtade kvaliteediklassid
  2026. a hooajaks, microbiology indicators) plus the site RSS, and
  a link into the vtiav.sm.ee suplusvesi tab. No machine feed.
* https://vtiav.sm.ee/index.php/?active_tab_id=JV (vee
  terviseohutuse infosüsteem, "Avalikud andmed :: Terviseamet") ->
  HTTP 200, ~32 KB. A human query UI: POST filter form
  (frontpage/filter) with autocomplete fields, 971 kirjet over 49
  pages, per-veevärk üldhinnang (Vastav/Mittevastav) rows; tabs
  (Joogivesi/Suplusvesi/Ujulad/Avaandmed) load via tabRefresh AJAX
  (/ajax_urls/otsiTulemused...). The "Avaandmed" tab is a JS tab,
  not a bulk export — no CSV/JSON/API/export endpoint found.
  Driving the filter UI page-by-page would be scraping a human
  publication, not polling a feed — exactly the scraping this repo
  refuses (AGENTS.md section 5).
* .../nakkushaigused/statistika -> HTTP 200, ~221 KB. Visible text
  (~17.0k chars) sweeps 0 for csv / json / API / andmestik /
  masinloetav. Current stats are human PDFs (monthly
  NH_haigestumine_Eestis_maakondade kaupa, annual epid overviews);
  the single .xls on the page is a 2000-2006 archive table
  (kuude ja maakondade kaupa) — stale by construction and county
  grain, not a feed for current Tallinn tick risk.
* https://andmed.eesti.ee/dataset?q=terviseamet -> HTTP 200, ~75 KB
  JS "Teabevärav" shell with 12 visible characters and no
  server-rendered results — no trivially pollable national-portal
  Terviseamet dataset (same shell as the #264, #277 and #284
  checks).
So both dims return None for EVERY input including missing origin:
a per-parcel band painted from a one-off hand-check would be fake
precision (OTA PR #131 precedent). Reasons say "hinnang"
(estimate) and "EI OLE" and point at the concrete buyer-side check
(vtiav.sm.ee veevärk/suplusvesi lookup, Terviseameti
supluskohtade nimekiri + kvaliteediklassid, puugihaiguste leht,
kohapealne vaatlus) — never a faked area score.

Style mirrors services/scoring/livability.py and sibling batch
dims_p4_elron.py (#284/#358): every scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100], Estonian
reason). Network lives only in livability.fetch_pois; this module
adds no network calls, no Overpass fragment, and no tag mapping:
there is no honest snapshot tag to query for a health board's
unpublished monitoring vintage, so there is nothing for the live
path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#362) states it extends the demoed ingestion (#289): with
  the demo verdict dated-negative, there is no ingestion to extend,
  so the coverage slice lands in the same verdict module rather
  than a second file importing a pipeline that does not exist
  (same precedent as Elron #284+#358, TLT #277+#351, elektrilevi
  #264+#344, comapps #302+#371, RB #281+#355).
* Sibling legs stay scored where they live: the P4-017 Tallinna
  Vesi zone-table + tariff legs (dims_p4_tvesi dim_water_sewer_zone
  / dim_water_tariff, #263/#343) and the P4-017 geology-side ÜVK
  leg (dims_p4_maa_subsurface dim_water_sewer, #248/#332) are
  different sources' readings, not this verdict's Terviseamet
  seire leg — re-scoring those cousins here would claim the full
  param on a partial signal (same split-slice precedent as P4-020:
  ATA notices scored in dims_p4_ata, bureau scores NULL in
  dims_p4_creditinfo). Each reason names its scored cousins so the
  buyer knows which half is already machine-joined.
* County grain is not a listing signal: the tick PDFs are
  maakondade kaupa, so every Tallinn listing would share one Harju
  number — a per-parcel band from it would discriminate nothing
  and read as fake precision. Same for the 2000-2006 archive .xls
  (stale by construction on top of county grain).
* P4-024 covers ONLY the Terviseamet legs (tick stats +
  bathing-water quality): the õietolm (Keskkonnaagentuur), PRIA
  spray-drift, EELIS habitat-proxy and farm-odour slices belong to
  future source issues and are named in docs/p4_tervise.md as
  overturn paths, not scored here. The OSM/group07 allergen
  proxies (õietolm: p137 and kin) stay where they live.
* The openness check stopped at storefront/page level on purpose —
  no AJAX filter driving, no PDF parsing, no vtiav pagination
  walking.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-017/P4-024: documented no-map Terviseamet-feed NULLs (OTA PR #131
# precedent). Drinking-water monitoring per veevärk, tick stats per
# county, and bathing-water quality classes are human pages, query UIs
# or PDFs with no public bulk feed; each scorer reports the gap with
# a concrete buyer-side check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_water_quality_monitoring(origin: Optional[Tuple[float, float]],
                                 pois: Optional[List[dict]]) -> Score:
    """P4-017: NULL — Terviseamet seire leg needs the feed (no map)."""
    return None, ("Joogivee kvaliteedi seire-hinnang krundi veevärgi kohta "
                  "(EI OLE masinloetavat liidestust): Terviseameti vee "
                  "terviseohutuse infosüsteemi (vtiav.sm.ee) üldhinnangud "
                  "on inimloetav päringuliides, võrreldavat masin-vintsi "
                  "pole — kontrolli oma veevärgi üldhinnangut "
                  "(Vastav/Mittevastav) vtiav.sm.ee Joogivesi-otsingust "
                  "ning krundi ühenduse tõde Tallinna Vee iseteeninduse "
                  "tehnilistest tingimustest; tsooni-slice'id on juba "
                  "masinloetult liidetud dims_p4_tvesi-s "
                  "(dim_water_sewer_zone) ja dims_p4_maa_subsurface-s "
                  "(dim_water_sewer), ära feigi")


def dim_country_health_nuisances(origin: Optional[Tuple[float, float]],
                                 pois: Optional[List[dict]]) -> Score:
    """P4-024: NULL — tick stats + bathing water need the feed (no map)."""
    return None, ("Puugi- ja suplusvee-hinnang on maakonna/PDF-taseme "
                  "teadmine (EI OLE masinloetavat voogu): puugistatistika "
                  "elab maakondade-kaupa PDF-ides (iga Tallinna kuulutus "
                  "saaks sama Harju numbri — see ei eristaks krunte), "
                  "suplusvee kvaliteediklassid elavad hooaja-PDF-ides — "
                  "kontrolli Pirita/Stroomi/Kakumäe klassi Terviseameti "
                  "supluskohtade nimekirjast ja vtiav.sm.ee "
                  "suplusvesi-otsingust, puugiriski puugihaiguste lehelt "
                  "ning rohelise serva / pritsimisriba / farmilõhna "
                  "kohapealsel vaatlusel; õietolmu-, PRIA-, EELIS- ja "
                  "farmikaebuste-slice'id kuuluvad eraldi allikatele, "
                  "ära feigi")


P4_TERVISE_DIMS = (
    ("water_quality_monitoring", "P4-017", dim_water_quality_monitoring),
    ("country_health_nuisances", "P4-024", dim_country_health_nuisances),
)


def score_p4_tervise(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both P4 Terviseamet dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_TERVISE_DIMS). Every value
    is None by design — unpublished Terviseamet feed, never a faked
    area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_TERVISE_DIMS}
