# P4 ilm verdict: Ilmateenistus Tallinn-Harku (P4-031 demo + 4-param coverage)

Closes #308 (demo) and #374 (coverage) — paired in one PR because the
coverage body states it extends the demo ingestion; no new plumbing was
needed beyond the demo's `baseline` argument (said here as required).

## 1. Openness verdict (2026-09-13, KEEP — dated negative counts)

Two polite single pulls (UA `home-finder-p4-ilm-probe/1.0`, `--max-time 20`),
cached to `/tmp/hf-ilm-cache`, no retries:

| # | URL | Result |
|---|-----|--------|
| 1 | `https://www.ilmateenistus.ee/ilma_andmed/xml/observations.php` | **OPEN, machine-readable, no key.** `HTTP/2 200`, `content-type: text/xml; charset=UTF-8`, 125 283 bytes. Root `timestamp="1789305511"` (2026-09-13). `Tallinn-Harku` block present: `wmocode 26038`, `latitude 59.398122222355134`, `longitude 24.602891666624284`, fields `phenomenon, visibility, precipitations, airpressure (1012.9), relativehumidity (82.5), airtemperature (16), winddirection (259), windspeed (3.7), windspeedmax, sunshineduration (0), globalradiation (184)`. Server says `cache-control: public, max-age=60` (obs refresh ~hourly). |
| 2 | `https://www.ilmateenistus.ee/kliima/kliimanormid/` | **OPEN as human HTML tables only.** `HTTP/2 200`, 286 608 bytes. `Tallinn-Harku` monthly rows present (incl. `Päikesepaiste kestus` / sunshine duration). **No machine-readable download**: zero `csv/xls/json/xml` links in the page — cross-check reference only, never ingested. |
| 3 | Machine wind-rose feed | **NOT located in the two pulls above (dated negative, kept).** No extra hunting per polite-automation rules. Consequence: the rose is derived from the archived observations' `winddirection` series (pull #1 proves that series machine-open), not from a rose endpoint. |

Commands run (evidence):

```bash
mkdir -p /tmp/hf-ilm-cache && cd /tmp/hf-ilm-cache
UA="home-finder-p4-ilm-probe/1.0 (Estonia open-data openness check, single polite pull)"
curl -sS -A "$UA" --max-time 20 -D obs.headers -o observations.xml \
  "https://www.ilmateenistus.ee/ilma_andmed/xml/observations.php"
# HTTP/2 200, 125283 bytes, grep Tallinn-Harku -> hit (wmocode 26038 block)
curl -sS -A "$UA" --max-time 20 -D norm.headers -o kliimanormid.html \
  "https://www.ilmateenistus.ee/kliima/kliimanormid/"
# HTTP/2 200, 286608 bytes, Harku rows + "Päikesepaiste kestus", no data downloads
```

## 2. Ingestion contract (what the demo implements end-to-end)

`services/scoring/dims_p4_ilm.py`: `fetch_harku_observation()` (polite,
cache-first, `ILM_CACHE_TTL_S = 24 h` — obs refresh hourly but a climate
baseline moves slowly, so at most one live pull/day) →
`parse_harku_observation()` (pure, fixture-tested) → daily archiver
accumulates records → `aggregate_baseline()` (pure: monthly buckets,
16-sector rose, calm share, CDD18) → the five dims. Transport errors
raise and never touch the cache; HTTP 429 stops the run. Cache file:
`<cache-dir>/ilmateenistus-observations.xml` (default dir `/tmp/hf-ilm-cache`).

## 3. Per-param honest shapes (never a gradient — one station)

| Param | Shape | No-baseline / missing-input behaviour |
|-------|-------|----------------------------------------|
| P4-031 backyard weather + DIY air | Documented NULL (demo proves ingestion → reason cites the Harku city baseline + sensor count) | NULL, reason points at `sensor.community` density + on-site shade/wind check |
| P4-034 summer overheating | July-mean city baseline band, capped (floor 20 — S/W top-floor sim needs EHR facts) | NULL naming the missing July archive + listing-fact check |
| P4-035 December darkness | December sun-hours city baseline band, capped (cap 80 — lamps need the inventory) | NULL naming the missing December archive + lamp/shade check |
| P4-053 odour roses | 16-sector dim off the Harku rose, meteorological wind-FROM convention, saturation at 20% share; nearest caller-supplied `odour_emitter` selects the sector (never a circle buffer) | NULL (no origin / no emitter inventory / no rose / sector absent from rose) |
| P4-056 enclosed courtyard | Documented NULL (reason carries Harku calm-share ventilation context) | NULL pointing at the missing LiDAR enclosure index |

All NULL reasons say `hinnang` + `EI OLE` and name the buyer-side check.
No Overpass fragment / tag mapping: Ilmateenistus data is not OSM data,
and the emitter inventory is caller-supplied until a future adapter owns
it — inventing either would be dishonest plumbing. No WEIGHTS / livability
/ layers / docs changes (joint rebalancing stays a joint change).

## 4. Judgment calls for the reviewer

1. Demo+coverage in ONE PR (AGENTS.md §3 says one issue per PR): the
   coverage issue body explicitly states it extends the demo ingestion,
   so splitting would review the same ingestion twice. Both issues close
   here; a fresh reviewer still merges.
2. Scorers take `(origin, pois, baseline=None)` — the optional third
   argument is the coverage-anticipated new plumbing: calendar dims need
   the ingested baseline the snapshot never carries, and stuffing climate
   normals into OSM POIs would abuse the POI channel.
3. Band edges (P4-034 July `<16/18/20/22 °C`, P4-035 December
   `<10/20/35/50 h`, odour saturation `0.20`, calm `<0.5 m/s`, CDD base
   `18 °C`) are coarse baseline judgments, documented in the module
   docstring — challengeable, dull by design.
4. Missing July/December returns NULL rather than substituting another
   month; a missing rose sector returns NULL rather than interpolating.
   Never-a-gradient applies to time too.
5. Test normals are synthetic fixtures (clearly labelled) — real observed
   values appear only in §1 above, never as ingested data.

## 5. DoD evidence (observed 2026-09-13, worktree `308-p4-ilm`)

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_ilm.py -q
...................s                                                     [100%]
19 passed, 1 skipped in 0.07s

$ python3 -m pytest services/scoring/tests -q
782 passed, 2 skipped in 8.02s
```

- Hermetic: default suite makes zero network calls; the single live pull
  runs only with `HF_LIVE_ILM=1` (env-gated, skipped otherwise — the
  1 skip above).
- New files only: `services/scoring/dims_p4_ilm.py`,
  `services/scoring/tests/test_dims_p4_ilm.py`, `docs/p4_ilm.md`.
  No edits to shared files (`livability.py`, WEIGHTS, layers,
  `docs/layers.md`, `docs/nomap.md`, `parameters4.md` — untouched).
