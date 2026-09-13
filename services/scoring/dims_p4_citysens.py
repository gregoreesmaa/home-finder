"""P4 CitySens smart-city pilot dims (issue #307, single-param demo, no coverage issue).

Demo (#307): Tallinna smart-city pilot sensor data (parameters4.md
P4-031 source (2), "where open, e.g. Tehnopol pre-test network")
end-to-end in Tallinn — openness verification plus the honest-shape
P4-031 leg. Single param: P4-031 Backyard weather + DIY air, the
pilot-data slice. Honest shape when a feed lands: coarse hinnang,
never per-backyard precision.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #307): pilot press releases are not pollable data — the pilot
pages carry news prose but no machine feed. Polite evidence, 9
requests total (3 HEADs + 6 GETs, single pulls with a labelled
one-off user-agent, paced sleeps between hosts, short timeouts, no
retries, no scraping beyond headers + visible-text keyword sweeps),
raw bodies cached at /tmp/hf-citysens/ (one-off PR record, TTL:
one-off check, never committed):
* HEAD https://www.tehnopol.ee/ -> HTTP 200, text/html (Apache/ZoneOS).
* GET https://www.tehnopol.ee/ -> HTTP 200, 251 432 bytes, title
  "Teadus ja arilinnak tehnoloogiaettevotetele" — ZERO
  csv/json/xml/xls hrefs and ZERO sensor/andur/smart-city/pilot/
  testbed/avaandmed/open-data mentions (the lone "api" hit is the
  googleMapsApiKey embed, not a data API).
* HEAD https://smarttallinn.ee/ -> 301 to
  https://www.tallinn.ee/eng/tallinnovations/ (the city's
  TallInnovation testbed programme moved off its own domain).
* GET .../eng/tallinnovations/ -> 301 -> /en/tallinnovation/ ->
  404 "Page not found | Tallinn" (134 047-byte city 404 template):
  the old programme URL is dead — dated proof the pilot trail is
  press pages, not a stable feed.
* GET https://www.tallinn.ee/en/tallinnovation/ (canonical, after
  one redirect) -> HTTP 200, 49 032 bytes, title "Tallinnovation |
  Tallinn". Visible text (1 678 chars) mentions "Smart City
  Solutions", "Testbeds", "Test in Tallinn", drone "pilots" — all
  NEWS prose. ZERO sensor/andur/open-data/avaandmed/csv/json/api
  tokens and ZERO machine hrefs: no endpoint, no bulk, no download.
* GET https://data.sensor.community/airrohr/v1/filter/area=
  59.3,24.3,59.6,25.1 (one bounded DIY-leg context read) ->
  HTTP 200 with LIVE records timestamped 2026-09-13 (Plantower/
  Nova Fitness particle + Dallas temperature sensors around
  Tallinn). The DIY sensor.community leg (P4-031 source (1)) IS
  machine-open today — but it is a DIFFERENT source slice with its
  own future demo, so this module names its map as the buyer-side
  check and never re-scores it here.
So the single dim returns None for EVERY input including missing
origin: a pilot-microclimate raster painted without a pollable
pilot feed (or from one press release) would be fake precision
(OTA PR #131 precedent). Reasons say "hinnang" (estimate) and
"EI OLE" and point at the concrete buyer-side checks
(sensor.community map + on-site shade/wind visit) — never a faked
per-backyard score.

SIBLING OVERLAP (read first, not edited): the other P4-031 slices
stay where they live and are named here, never re-scored — the
Harku city-baseline slice (dims_p4_ilm dim_backyard_weather,
documented NULL carrying the baseline context), the LiDAR
cold-air-drainage slice (dims_p4_maa_lidar dim_backyard_weather,
DEM frost-pocket screen), the EHR heating-truth slice
(dims_p4_ehr dim_backyard_weather, NULL + heating-type echo), the
OSM shelter slice (dims_p4_osm dim_backyard_weather, NULL — bus
shelters are not balcony facts), and the KAUR met/wind station
slice (dims_p4_kaur dim_mikrokliima_kaur, Harku-only/count bands).
This module owns ONLY the smart-city pilot leg (Tehnopol/
Tallinnovation programme feeds), which has no pollable endpoint —
hence NULL.

Style mirrors services/scoring/dims_p4_opencellid.py (#269, the
closest dated-negative single-param precedent: documented NULL,
dated 401/404 evidence in the reason, sibling pointers, no network
calls, no Overpass fragment, no tag mapping — there is no honest
snapshot tag to query for pilot-sensor density, so there is nothing
for the live path to fetch).

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: #307 states the remaining
  0 params using this source need only a follow-up created after
  this demo — with a dated-negative demo there is no ingestion to
  extend, so there is nothing to split out. One dim, one module,
  three new files, no shared-file edits.
* No ingestion to cache and no TTL to state beyond this one-off
  check (opencellid #269 / rik #252 precedent): re-probe yearly,
  or sooner if a pilot programme publishes a pollable feed (then
  re-open #307). A newly opened pilot endpoint flips the verdict
  without re-probing deeper than the programme page + one
  anonymous feed read.
* sensor.community was read ONCE as dated context, not ingested:
  its live 2026-09-13 records prove the DIY slice (source (1))
  stays the honest sensor leg for P4-031, so the NULL reason
  points buyers at its map. Scoring pilot NULLs off DIY rows
  would claim the wrong source — the split stays clean.
* Honest future shape (stated, not scored): coarse Tallinn pilot
  raster hinnang off polled pilot feeds (pilot-density bands,
  weak-good capped — pilot coverage hints at context, never a
  guarantee; never 100 on this leg alone, never 0 on this leg
  alone). Press-release counts must never score a backyard.
  Today every reason says EI OLE and names the sensor map +
  on-site check.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-031: documented no-map smart-city pilot NULL (OTA PR #131
# precedent). Tallinna pilot-sensor data (Tehnopol pre-test network /
# TallInnovation programme feeds) has no pollable machine endpoint —
# the programme pages are press releases, so the scorer reports the
# gap with the concrete buyer-side checks instead of a faked number.
# ---------------------------------------------------------------------------

def dim_pilot_microclimate(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-031: NULL — pilootandurite voog pole küsitav (press, mitte feed)."""
    return None, ("Tehnopol/Tallinnovation pilootandurite (targa linna "
                  "mikrokliima jäme raster-hinnang, nõrk-hea laega "
                  "tulevikukuju) avatud masinvoogu EI OLE — tegu on "
                  "pressiteadete ja konkursiuudistega, mitte küsitava "
                  "andmeliidesega: Tehnopol avaleht (251 kB, 2026-09-13) "
                  "ilma masinlingi ja andurimaineta, Tallinnovation vana "
                  "URL 404, programmilehel sensor/andur/avaandmed/CSV/JSON/"
                  "API EI OLE — puhverdatavat pilootvoogu pole, ära feigi. "
                  "Hoovi külmakotid ja tuulekoridorid selguvad DIY-andurite "
                  "tihedusest (sensor.community kaart, elus loetav "
                  "2026-09-13, oma tulevane demo) ja kohapealsest varju/"
                  "tuule vaatlusest — baasjalad: Harku linnabaas "
                  "dims_p4_ilm (dim_backyard_weather), DEM-külmanõg "
                  "dims_p4_maa_lidar (dim_backyard_weather), kütte-liik "
                  "dims_p4_ehr (dim_backyard_weather), varjualuse-null "
                  "dims_p4_osm (dim_backyard_weather)")


P4_CITYSENS_DIMS = (
    ("pilot_microclimate", "P4-031", dim_pilot_microclimate),
)


def score_p4_citysens(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 CitySens dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_CITYSENS_DIMS). The
    value is None by design — press releases are not a pollable
    pilot feed, never a faked per-backyard score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_CITYSENS_DIMS}
