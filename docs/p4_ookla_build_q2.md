# Build: Ookla 2026-Q2 fixed-tile shapefile path (issue #725)

> Scoped build from probe #693 (positive 2026-09-19 — see
> `docs/probe_ookla.md`, `services/scoring/probe_ookla.py`).
> Code: `ookla_shapefile_url()` + `fetch_ookla_shapefile()` in
> `services/scoring/dims_p4_ookla.py`; tests: hermetic additions in
> `services/scoring/tests/test_dims_p4_ookla.py` (fixtures only,
> never a download). The fixed/mobile band dims and the
> `ookla_fixed` / `ookla_mobile` map layers are unchanged and keep
> serving the Q1 extract.

## §1 Licence gate (LOAD-BEARING — resolved explicitly here)

The dataset licence is **CC BY-NC-SA 4.0 (non-commercial)**, confirmed
on the AWS registry page (probe #693). Repo policy (AGENTS.md §5):
public repo, no licence violations; the repo's own use is
non-commercial (same standing judgment as #268/#489: attributed
sample rows as test fixtures only, full attribution in
`docs/p4_ookla.md`).

**Verdict: the NC clause forbids committing the derived Tallinn
extract.** What ships is therefore the harvester path + docs as
**cache-only** (operator/pole pull — the TomTom/DATEX precedent),
with the verdict recorded here:

- `fetch_ookla_shapefile()` pulls the quarterly zip to cache
  (`/tmp/hf-ookla` default, `OOKLA_SNAPSHOT_PATH` override for
  operators) — the zip and the derived extract are never committed.
- Test fixtures stay minimal attributed sample rows (fair-shape reuse,
  unchanged).
- `OOKLA_LATEST_*` stays `2026-Q1` until the operator runs the Q2
  pull and drops the Q2 extract into the cache: bumping the served
  quarter without the extract would degrade the live layers to demo
  (pinned by `test_served_quarter_stays_q1_until_operator_pulls_q2`).
- Re-check the licence before any re-use that could count commercial;
  if NC ever conflicts with the repo's use, the harvester stays
  cache-only and the layers keep rendering the last verified extract.

## §2 Live verification (2026-09-19, polite, headers only)

UA `home-finder-research/0.1`, single HEAD, 429 = stop (none seen).
Zip body NOT downloaded (343 MB — out of budget by design):

| Check | Observed | Meaning |
|---|---|---|
| `HEAD .../shapefiles/performance/type=fixed/year=2026/quarter=2/2026-04-01_performance_fixed_tiles.zip` | **200**, `Content-Length: 342651784`, `Last-Modified: Wed, 19 Aug 2026`, `Accept-Ranges: bytes` | Q2 fixed path serves keyless, byte-identical size to probe #693 — the harvester target is live |

## §3 Operator extraction (Tallinn bbox, avg_d_mbps per tile)

On the pole/operator host (never CI):

```sh
python3 - <<'EOF'
from services.scoring.dims_p4_ookla import fetch_ookla_shapefile
zip_path = fetch_ookla_shapefile("fixed", 2026, 2, cache_dir="$HOME/hf-pole/cache/ookla")
print(zip_path)
EOF
# Unzip in cache, then reduce to the Tallinn bbox extract with the
# documented DuckDB-spatial step (lon 24.3-25.1 / lat 59.3-59.6,
# avg_d_kbps per tile, >= 5 tests guard in the scorer):
#   INSTALL spatial; LOAD spatial;
#   COPY (SELECT tile_x, tile_y, avg_d_kbps, avg_u_kbps, avg_lat_ms,
#                tests, devices, quadkey FROM st_read('fixed_tiles.shp')
#         WHERE tile_x BETWEEN 24.3 AND 25.1
#           AND tile_y BETWEEN 59.3 AND 59.6)
#        TO 'ookla-tallinn-2026Q2.json';
# Validate with coerce_tile()/summarize_ookla_tallinn(), drop the
# JSON next to the Q1 extract, then roll OOKLA_LATEST_* + OOKLA_QUARTER
# + OOKLA_SNAPSHOT_NAME to 2026-Q2 as one joint change with the extract.
```

Shapefile rows carry the same tile columns the parquet leg coerces
(`tile_x/tile_y/avg_d_kbps/.../tests/devices/quadkey`), so the
extract feeds `coerce_tile()` unchanged — no new schema, no new
dependency. Quarterly re-pull per `OOKLA_TTL_DAYS = 90`.

## Buyer-side check

Aadressi püsiühendust kontrolli TTJA netikaardilt; jooksvaid
katkestusi rikkekaardilt — kvartali ruut on hinnang, mitte leping.
