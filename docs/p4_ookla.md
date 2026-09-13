# P4 Ookla verdict note — Speedtest Open Data Tallinn tiles (P4-009 fallback)

> POSITIVE verdict for issue #268 (single param, no coverage issue —
> Ookla fixed/mobile tiles serve only P4-009; the follow-up coverage
> issue has 0 params).
> Checked 2026-09-13. Both layers score as capped coarse-raster
> hinnang; scorers live in `services/scoring/dims_p4_ookla.py`, pinned
> by `services/scoring/tests/test_dims_p4_ookla.py`.

## Verdict

**Machine-open — both dims SCORE from the Tallinn extract (cap 85).**
The Q1-2026 fixed/mobile parquets are reachable without a key, and
bounded range-reads prove Tallinn coverage live: 1914 fixed tiles
(23 465 tests) + 1706 mobile tiles (9 084 tests) in the Tallinn
bbox, dense Kesklinn tiles carrying 36–151 tests each. Per-tile
download averages ARE a local signal (unlike Elering's national
series), so the honest shape is a coarse z16-raster hinnang —
never a per-address measurement, never a power-cut score.

## Openness evidence (polite round, 2026-09-13, no bulk pull)

9 requests total, labelled one-off user-agent
`home-finder openness-check (one-off, no scrape)`. Raw bodies:
`/tmp/hf-ookla/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `HEAD https://www.ookla.com/ookla-for-good/open-data` | HTTP 200, `content-length: 119826` | Landing reachable |
| `GET` same (120 KB) visible-text sweep | "Global Fixed Broadband and Mobile Network Maps" + "Download this data"; fixed 4x, mobile 5x, quarter 1x | Both layers + quarterly cadence advertised |
| `GET https://raw.githubusercontent.com/teamookla/ookla-open-data/master/README.md` | HTTP 200, 14893 bytes: z16 tiles (~610.8 m at equator), Q1 2019 → Q1 2026, Shapefile + Parquet (WKT, EPSG:4326), GPS-quality samples averaged per tile, `--no-sign-request` S3 layout `s3://ookla-open-data/{shapefiles,parquet}/performance/type={fixed,mobile}/year=YYYY/quarter=Q/`, centroid-filter tutorial | Full machine layout documented, no key |
| README licence section | `CC BY-NC-SA 4.0` + suggested attribution string (below) | Open with attribution; non-commercial fits this repo; test fixtures reuse 8 attributed sample rows only |
| `HEAD .../parquet/performance/type=fixed/year=2026/quarter=1/2026-01-01_performance_fixed_tiles.parquet` | HTTP 200, `Content-Length: 348853499`, `Last-Modified: Mon, 13 Apr 2026` | Machine-open, no key (headers only, body never pulled) |
| `HEAD .../type=mobile/.../2026-01-01_performance_mobile_tiles.parquet` | HTTP 200, `Content-Length: 175330099`, `Last-Modified: Mon, 13 Apr 2026` | Machine-open, no key (headers only) |
| Bounded DuckDB range-read, fixed Q1-2026, Tallinn bbox lon 24.3–25.1 / lat 59.3–59.6 | 1914 tiles, 23 465 tests, 8 536 devices; download p25/med/p75 = 92 624 / 154 425 / 220 187 kbps; median upload 117 012 kbps; median latency 5 ms | Tallinn fixed coverage PROVEN live (column chunks only, file never downloaded whole) |
| Bounded DuckDB range-read, mobile Q1-2026, same bbox | 1706 tiles, 9 084 tests, 4 906 devices; download p25/med/p75 = 94 047 / 220 138 / 381 664 kbps; median upload 26 276 kbps; median latency 15 ms | Tallinn mobile coverage PROVEN live |
| Kesklinn samples (fixed) | e.g. (24.7549, 59.4381): 176 088 down / 170 230 up kbps, 151 tests, 44 devices, quadkey `1201202310211212` | Dense urban tiles — band signal, not anecdote |

Judgment call: the demo stopped at HEADs + analytical range-reads
on purpose — the 349/175 MB globals were never pulled whole.
Bulk converges over runs (AGENTS.md §7.4): the scheduled ingest
pulls one file per layer per quarter, not the demo.

## Ingestion (polite pulls + cache + TTL)

- `fetch_ookla_parquet(service, year, quarter)` — cache-first
  single GET per layer per quarter (`/tmp/hf-ookla/`,
  `OOKLA_TTL_DAYS = 90`). Transport/HTTP errors RAISE, never
  cached; HTTP 429 propagates as a stop signal.
- Tallinn extract (operator step, documented here so the file
  pull stays reviewable — needs no new dependency in the
  module, which stays stdlib-only):

```bash
# quarterly pull (no key) + Tallinn bbox extract -> small JSON
cd /tmp/hf-ookla
for T in fixed mobile; do
  curl -A "home-finder ookla ingest (quarterly pull)" -o ookla-$T-2026Q1.parquet \
    https://ookla-open-data.s3.amazonaws.com/parquet/performance/type=$T/year=2026/quarter=1/2026-01-01_performance_${T}_tiles.parquet
done
python3 -c "
import duckdb
con = duckdb.connect()
for t in ('fixed', 'mobile'):
    con.execute(f\"COPY (SELECT tile_x, tile_y, avg_d_kbps, avg_u_kbps, avg_lat_ms, tests, devices, quadkey FROM 'ookla-{t}-2026Q1.parquet' WHERE tile_x BETWEEN 24.3 AND 25.1 AND tile_y BETWEEN 59.3 AND 59.6) TO 'ookla-tallinn-2026Q1-{t}.json'\")
"
```

- TTL: **90 days (quarterly re-pull)**. parameters4.md P4-009 says
  "monthly", but the source releases quarterly — a monthly GET
  would re-fetch identical bytes. Compliant middle ground: a
  monthly HEAD freshness check against the S3 object (headers
  only), quarterly GET on a new release. `ookla_url()` builds
  any quarter, so a new release needs no code change.
- `load_ookla_snapshot` / `summarize_ookla_tallinn` turn the
  extract into the snapshot the dims consume (bad rows
  skipped, missing speeds stay None never 0).

## Honest-shape table (Tallinn extract in / capped bands out)

| Param | Ookla slice consumed | Shape | When missing |
|---|---|---|---|
| P4-009 fixed (`ookla_fixed`) | fixed-layer tile avg download near address | 35 / 55 / 75 / capped 85 band off nearest qualifying tile ≤ 1 km (≥ 5 tests) | NULL → TTJA netikaart + rikkekaart |
| P4-009 mobile (`ookla_mobile`) | mobile-layer tile avg download near address | same band edges (experienced download kbps), capped 85 | NULL → TTJA netikaart + rikkekaart |

Band edges (30 / 100 / 300 Mbit/s): EU broadband tiers (30 =
fast-broadband line, 100 = ultrafast) checked against live
Tallinn Q1-2026 quartiles (fixed p25/med/p75 = 93/154/220) —
most of Tallinn lands at 75, weak spots at 55/35, the top tail
at capped 85. Scored reasons name tile distance, quarter,
Mbit/s, test/device counts, and the missing pieces
(per-address measurement, feeder SAIDI); "EI OLE" appears
only in NULL reasons (pinned by tests, dims_p4_osm precedent).

## What stays open (overturn paths, not wired here)

- **Power half of P4-009:** Ookla measures throughput, not
  outages — Elektrilevi SAIDI stays unpublished
  (`dims_p4_elektrilevi` NULL verdict #264). Reasons point at
  the rikkekaart live map; scoring throughput as reliability
  would claim the full param on a partial signal.
- **Sibling broadband slices:** Elering national series (NULL,
  #265), TTJA netikaart address check (#266), operator maps
  (#267), OpenCellID masts (#230 masters) — untouched, each
  its own demo.
- **Full overturn:** Ookla removes Tallinn/Estonia tiles
  (their 2026-04-16 changelog reserves region cuts) → the
  extract comes back empty and the dims fall to the
  empty-layer NULL naming the cut; re-open #268. Licence
  change away from CC BY-NC-SA → dated-negative re-check.

## Map layer (issue #489, 2026-09-13)

Two `/layers` overlays (`ookla_fixed`, `ookla_mobile`) visualize the
P4-009 slice both dims score: tile centroids from the Tallinn extract
served by `apps/web/lib/server/ookla.ts`, colored by the scorer's own
nearest-tile band kernel (`tileband` spec in
`apps/web/lib/layers_p4_ookla.ts` — byte parity with `_band_d` /
`OOKLA_RADIUS_M` / `OOKLA_MIN_TESTS`, pinned by
`apps/web/lib/layers_p4_ookla.test.ts`). No raster master by
documented decision (`OOKLA_NO_RASTER`): the points-splat tileband
kernel IS the field; the window route serves 500 and the client falls
back to the splat (senscom/GTFS precedent). paramIds stays `[]` with
`paramLabel: "P4-009"` (parameters3 p9 is an inspection-group fact and
must never gain a map — senscom P4-031 precedent).

Re-verification for this layer (same day, 2 HEADs + 2 bounded
range-reads, labelled one-off user-agent `home-finder openness-check
(one-off, no scrape)`): HEAD fixed Q1-2026 parquet → HTTP 200,
`Content-Length: 348853499`, `Last-Modified: Mon, 13 Apr 2026`;
HEAD mobile → HTTP 200, `Content-Length: 175330099`, same date
(both unchanged from the table above); 2 bounded DuckDB range-reads
(column chunks only, files never pulled whole) with the scorer's own
guards (tests ≥ 5, avg_d present) → fixed 971 qualifying tiles /
21 598 tests (median 164 537 kbps), mobile 555 / 6 856 tests (median
261 748 kbps). Verdict stays POSITIVE — no dated-negative, no
synthetic fill.

## Attribution (CC BY-NC-SA 4.0, kept for any surfacing)

Speedtest® by Ookla® Global Fixed and Mobile Network
Performance Maps was accessed on 13 September 2026 from AWS.
Based on home-finder's analysis of Speedtest® by Ookla®
Global Fixed and Mobile Network Performance Maps for 2026-Q1.
Ookla trademarks used under license and reprinted with
permission.
