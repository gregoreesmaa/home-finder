# P4 senscom verdict note — sensor.community DIY air, Tallinn (P4-031 slice)

> POSITIVE verdict for issue #306 (single param, no coverage issue —
> sensor.community DIY outdoor locations serve only P4-031; the
> follow-up coverage issue has 0 params).
> Checked 2026-09-13. The dim scores a capped coarse-density hinnang
> from the Tallinn extract; scorers live in
> `services/scoring/dims_p4_senscom.py`, pinned by
> `services/scoring/tests/test_dims_p4_senscom.py`.

## Verdict

**Machine-open — the dim SCORES from the Tallinn extract (cap 80).**
The `static/v2/data.json` live feed answers without a key (CORS
`*`, CC0 landing), and one full pull proves Tallinn coverage
live: 1 outdoor DIY location in the Tallinn bbox right now
(loc 23610, 59.38/24.642, SDS011 + DS18B20), 3 outdoor EE
locations total. Live DIY outdoor locations ARE a local backyard
signal (unlike the single Harku station), so the honest shape is
a coarse density hinnang with a sensor-count reason — never a
calibrated measurement, never a heating-truth score.

## Openness evidence (polite round, 2026-09-13, one bulk pull)

6 requests total, labelled one-off user-agent
`home-finder-p4-senscom-probe/1.0`, paced ≥3 s, `--max-time 20`
(short timeouts). Raw bodies: `/tmp/hf-senscom/` (one-off PR
record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `HEAD .../static/v2/data.json` | HTTP/2 200, `content-type: application/json`, `content-length: 8610582`, `last-modified: Sun, 13 Sep 2026 15:15:29 GMT`, `accept-ranges: bytes`, `access-control-allow-origin: *` | Machine-open, no key (headers only) |
| Bounded range-read bytes 0-8191 of the same feed | HTTP 206, JSON array of observation records: `location{latitude, longitude, country, indoor}`, `sensor{sensor_type{name}}`, `sensordatavalues[]`, `timestamp` (first records PPD42NS + DHT22 in DE) | Record shape proven without a bulk pull |
| `HEAD https://archive.sensor.community/` | HTTP/2 200, `content-type: text/html;charset=UTF-8` | Daily per-sensor CSV archive reachable (history anchor) |
| `GET https://sensor.community/` | HTTP 200, 45-byte JS stub (`window.location.href = "/en"`) | Landing is a JS redirect, not content |
| `GET https://sensor.community/en/` | HTTP 200, 29 791 bytes, links `creativecommons.org/publicdomain/zero/1.0` (CC0), "open data, civic tech network" | CC0 dedication, no login wall |
| One full `GET` of the live feed | HTTP 200, 8 609 312 bytes in 9.8 s; 17 866 records, `timestamp` window 15:11:06 → 15:16:15 UTC (~5-minute rolling); EE: 5 records at 3 distinct OUTDOOR locations | Tallinn coverage PROVEN live (single pull, cached) |

EE inventory observed live (outdoor, all `indoor: 0`):

| location id | lat / lon | boards |
|---|---|---|
| 23610 (Tallinn bbox) | 59.38 / 24.642 | SDS011, DS18B20 |
| 46248 (Viljandi) | 58.364 / 25.582 | BME280, SDS011 |
| 86012 (Rapla) | 58.992 / 24.83 | PMS5003 |

Commands run (evidence):

```bash
mkdir -p /tmp/hf-senscom && cd /tmp/hf-senscom
UA="home-finder-p4-senscom-probe/1.0 (Estonia open-data openness check, single polite pull)"
curl -sS -A "$UA" --max-time 20 -I "https://data.sensor.community/static/v2/data.json"
# HTTP/2 200, content-length: 8610582, accept-ranges: bytes, CORS *
curl -sS -A "$UA" --max-time 20 --range 0-8191 -o sample_prefix.json \
  "https://data.sensor.community/static/v2/data.json"
# HTTP 206, 8192 bytes, JSON observation records
curl -sS -A "$UA" --max-time 20 -I "https://archive.sensor.community/"
# HTTP/2 200
curl -sS -A "$UA" --max-time 20 --max-filesize 204800 -o landing_en.html \
  "https://sensor.community/en/"
# HTTP 200, 29791 bytes, CC0 link
sleep 3
curl -sS -A "$UA" --max-time 120 -o data.json \
  "https://data.sensor.community/static/v2/data.json"
# HTTP 200, 8609312 bytes, 9.8 s -> local tally: 17866 records,
# 5 EE records / 3 outdoor locations / 1 in Tallinn bbox
```

Judgment call: the demo pulled the 8.6 MB feed whole ONCE (it is
the documented consumption path and fits a polite single GET;
the 175–349 MB ookla precedent that forced range-reads does not
apply at this size). The scheduled ingest pulls it at most once
per day per `SENSCOM_TTL_S`, never per listing.

## Ingestion (polite pulls + cache + TTL)

- `fetch_senscom_dump(cache_dir, ttl_s)` — cache-first single GET
  (`/tmp/hf-senscom/`, `SENSCOM_TTL_S = 86400`). Transport/HTTP
  errors RAISE, never cached; HTTP 429 propagates as a stop
  signal. Returns `(raw_text, provenance)`.
- `parse_senscom_dump(text)` (pure) — JSON array → deduped
  OUTDOOR locations (`{id, lat, lon, types}`); indoor, flagless,
  coordless and junk rows skipped; `ValueError` on garbage.
- `tallinn_extract(records, fetched)` (pure) — bbox filter
  (lon 24.3–25.1 / lat 59.3–59.6) → snapshot
  `{fetched, bbox, sensors, n_sensors}` → saved to
  `sensor-community-tallinn.json` by the operator step:

```bash
# daily pull (no key) + Tallinn bbox extract -> small JSON
cd /tmp/hf-senscom
curl -A "home-finder-p4-senscom/1.0 (Estonia open-data daily adapter; polite single-pull, cache-first)" \
  -o sensor-community-data.json https://data.sensor.community/static/v2/data.json
python3 -c "
import json, sys
sys.path.insert(0, 'services/scoring')
from dims_p4_senscom import parse_senscom_dump, tallinn_extract
raw = open('/tmp/hf-senscom/sensor-community-data.json').read()
snap = tallinn_extract(parse_senscom_dump(raw))
json.dump(snap, open('/tmp/hf-senscom/sensor-community-tallinn.json', 'w'))
print(snap['fetched'], snap['n_sensors'])
"
```

- `load_senscom_snapshot(cache_dir)` — cached extract or `None`
  (missing/corrupt is never data).

## Honest shape (bands, NULL stays NULL)

| Nearby outdoor locations ≤500 m | Score | Reason carries |
|---|---|---|
| 1 | 60 | sensor count, radius, snapshot date, sibling pointers |
| 2–3 | 70 | same |
| 4+ | 80 (cap) | same |

NULL (Estonian reason, `hinnang` + `EI OLE` + buyer-side check)
when: no origin, no snapshot, empty extract, or 0 locations in
radius. Scored reasons say `hinnang` and never `EI OLE`
(machine-checked invariant), never `mõõdetud`/`garanteeritud`,
never 0/100.

## Sibling-leg split (no double-scoring)

| Param slice | Owner (untouched, named in reasons) |
|---|---|
| Harku city baseline | `dims_p4_ilm.dim_backyard_weather` (NULL pointing at sensor density) |
| EHR heating truth | `dims_p4_ehr.dim_backyard_weather` (kütte-liik echo) |
| LiDAR DEM frost screen | `dims_p4_maa_lidar.dim_backyard_weather` (cold-air drainage) |
| KAUR met/wind density | `dims_p4_kaur.dim_mikrokliima_kaur` (reference stations) |
| OSM shelter tags | documented NULL (bus stops ≠ balcony facts) |

The dim key carries the `_senscom` suffix
(`backyard_air_senscom`) so a future central hook can import
this module alongside the sibling legs without collisions.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage pairing (AGENTS.md §3 one
   issue per PR): the source serves only P4-031, so there is no
   coverage issue to pair — unlike demo+coverage batches, this
   PR closes #306 alone.
2. 500 m radius (tighter than KAUR's 2 km on purpose):
   reference stations interpolate, balconies do not — a DIY
   sensor 2 km away says nothing about the backyard.
3. Fail-closed indoor filter: only an explicit outdoor marker
   (`indoor` 0/False) counts; indoor boards measure living
   rooms and unknown flags are ignored, never scored as
   absence.
4. One location id = one witness (three boards on one balcony
   are one balcony); cap 80 (uncalibrated DIY + no heating
   truth — a watched block is not a measured balcony).
5. TTL 24 h vs the feed's ~5-minute refresh: density moves on
   installation timescales; the snapshot date travels in the
   extract and is echoed in every scored reason.
6. Test fixtures are fully synthetic (clearly labelled) — real
   observed values appear only in §1 above, never as ingested
   data.

## DoD evidence (observed 2026-09-13, worktree `306-p4-senscom`)

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_senscom.py -q
...........                                                     [100%]
11 passed in 0.06s

$ python3 -m pytest services/scoring/tests/test_dims_p4_senscom.py \
    services/scoring/tests/test_dims_p4_ilm.py \
    services/scoring/tests/test_dims_p4_ookla.py \
    services/scoring/tests/test_dims_p4_kaur.py \
    services/scoring/tests/test_dims_p4_osm.py -q
100 passed, 1 skipped in 0.33s

$ python3 -m pytest services/scoring/tests -q
1968 passed, 4 skipped in 12.17s
```

No shared-file edits: 3 new files only
(`services/scoring/dims_p4_senscom.py`,
`services/scoring/tests/test_dims_p4_senscom.py`,
`docs/p4_senscom.md`). Sibling P4-031 legs (`dims_p4_ilm.py`,
`dims_p4_ehr.py`, `dims_p4_maa_lidar.py`, `dims_p4_kaur.py`,
`dims_p4_osm.py`) and all group files untouched.
