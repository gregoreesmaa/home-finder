# P4 CitySens verdict note — Tallinna smart-city pilot feeds (P4-031)

> Dated-negative verdict for issue #307 (single-param demo, no
> coverage issue — the issue states 0 remaining params use this
> source, so no follow-up coverage issue exists).
> Checked 2026-09-13. The single param is a documented no-map NULL
> dim (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_citysens.py`, pinned by
> `services/scoring/tests/test_dims_p4_citysens.py`.

## Verdict

**Press releases, no pollable feed — the dim stays NULL with an
Estonian reason.** Tallinna smart-city pilot coverage (Tehnopol
pre-test network, TallInnovation testbed programme) exists as news
prose and a competition site: neither pilot page carries a sensor
endpoint, a bulk download, or a single machine-readable link, and
the programme's old URL is dead (404). There is no polite pilot
bulk to cache, no TTL to state beyond this one-off check (re-probe
yearly, or sooner if a pilot feed URL appears), and no honest
backyard raster to paint without a pollable feed — one press
release says nothing about backyard frost pockets.

## Openness evidence (one polite round, 2026-09-13, no scraping)

9 requests total: 3 HEADs + 6 GETs, single pulls, labelled one-off
user-agent `home-finder-p4-citysens-probe/1.0`, paced sleeps between
hosts, `--max-time 20/25`, no retries; headers + visible-text
keyword sweeps only. Raw bodies: `/tmp/hf-citysens/` (one-off PR
record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `HEAD https://www.tehnopol.ee/` | HTTP 200, `content-type: text/html; charset=UTF-8`, `server: Apache / ZoneOS` | Pilot host reachable |
| `GET https://www.tehnopol.ee/` | HTTP 200, 251 432 bytes, title "Teadus ja ärilinnak tehnoloogiaettevõtetele" | Zero `csv/json/xml/xls` hrefs; zero sensor/andur/smart-city/pilot/testbed/avaandmed/open-data mentions (lone "api" hit is the `googleMapsApiKey` embed, not a data API) |
| `HEAD https://smarttallinn.ee/` | HTTP 301 → `https://www.tallinn.ee/eng/tallinnovations/` | Testbed brand moved off its own domain |
| `GET https://www.tallinn.ee/eng/tallinnovations/` | 301 → `/en/tallinnovation/` → 404 "Page not found \| Tallinn" (134 047-byte city 404 template) | Old programme URL dead — dated proof the trail is press pages, not a stable feed |
| `GET https://www.tallinn.ee/en/tallinnovation/` (canonical) | HTTP 200, 49 032 bytes, title "Tallinnovation \| Tallinn"; 1 678 chars visible text ("Smart City Solutions", "Testbeds", "Test in Tallinn", drone "pilots") | All NEWS prose; zero sensor/andur/open-data/avaandmed/csv/json/api tokens, zero machine hrefs — no endpoint, no bulk, no download |
| `GET https://data.sensor.community/airrohr/v1/filter/area=59.3,24.3,59.6,25.1` (one bounded DIY-leg context read) | HTTP 200, live records timestamped 2026-09-13 (Plantower/Nova Fitness particle + Dallas temperature sensors, Tallinn area) | P4-031 source (1), the DIY sensor.community leg, IS machine-open today — a different source slice with its own future demo; named in the NULL reason as the buyer check, never scored here |

Judgment call: the check stopped at homepages + one programme page
+ one bounded DIY read on purpose — no site search, no form posts,
no per-sensor enumeration, no account flows. Chasing press links
deeper would spider news to prove what the zero machine-link sweep
already proves.

## Honest shape (NULL until a pollable pilot feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-031 Backyard weather + DIY air, pilot slice (demo) | `pilot_microclimate` | coarse Tallinn pilot raster hinnang off polled pilot feeds (pilot-density bands, weak-good capped — coverage hints at context, never a guarantee; never 0/100 on this leg alone; press-release counts never score) | sensor.community map (DIY density, live 2026-09-13) + on-site shade/wind visit; scored cousins: Harku baseline dims_p4_ilm + LiDAR frost screen dims_p4_maa_lidar + EHR heating echo dims_p4_ehr + OSM shelter NULL dims_p4_osm |

Every scored-future reason must trace to a joined pilot-feed
record; a single press release must never score a backyard.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: #307 states the remaining
   0 params using this source need only a follow-up created after
   this demo — with a dated-negative demo there is no ingestion to
   extend, so one dim in one module is the whole honest scope.
2. Split-slice contract: the Harku city-baseline slice
   (dims_p4_ilm dim_backyard_weather, documented NULL), the LiDAR
   cold-air slice (dims_p4_maa_lidar dim_backyard_weather, DEM
   screen), the EHR heating-truth slice (dims_p4_ehr
   dim_backyard_weather, NULL + echo), the OSM shelter slice
   (dims_p4_osm dim_backyard_weather, NULL) and the KAUR station
   slice (dims_p4_kaur dim_mikrokliima_kaur) stay where they live
   and are named, never re-scored here. The sensor.community DIY
   slice (source (1)) is its own future demo. Sibling modules were
   read first; parameters4.md untouched.
3. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across
   all batches.

## Reopening checklist (when a pollable pilot feed appears)

- Pilot programme publishes an endpoint/bulk/CSV/JSON feed →
  re-open #307, point the fetch at it (polite, cached, TTL-stated),
  flip the dim to the capped raster shape above.
- sensor.community DIY-density demo lands first → the reason's
  buyer pointer stays valid; no change needed here.
- Programme pages gain machine links without a feed → dated note
  only, verdict stands (links must be pollable per-parcel data).

## DoD evidence (observed 2026-09-13, worktree `307-p4-citysens`)

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_citysens.py -q
......                                                                   [100%]
6 passed in 0.03s

$ python3 -m pytest services/scoring/tests/test_dims_p4_citysens.py services/scoring/tests/test_dims_p4_opencellid.py services/scoring/tests/test_dims_p4_ookla.py services/scoring/tests/test_dims_p4_ilm.py services/scoring/tests/test_dims_p4_osm.py services/scoring/tests/test_dims_p4_ehr.py services/scoring/tests/test_dims_p4_kaur.py services/scoring/tests/test_dims_p4_maa_lidar.py -q
........................................................................ [ 94%]
........                                                                 [100%]
151 passed, 1 skipped in 0.42s

$ python3 -m pytest services/scoring/tests -q
1958 passed, 4 skipped in 10.28s
```
