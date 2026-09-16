# P4 asumedia reopen: polygon-join kernel + WFS verdict (issue #525)

Closes #525.

## 1. WFS verdict (2026-09-16): path works, asum grain absent

Two polite single GETs (UA `home-finder-p4-asum-probe/1.0`,
`--max-time 30`, paced ≥3 s, no retries), cached to
`/tmp/hf-525-probe`:

| # | URL | Result |
|---|-----|--------|
| 1 | `gsavalik.envir.ee/geoserver/wfs?service=WFS&version=2.0.0&request=GetCapabilities` | **OPEN, no key.** `HTTP/2 200`, 1 345 735 bytes, **1091 typenames**. EHAK grains present (`ehak:asustusyksuste_piirid`, `ehak:linnade_piirid`, `ehak:maakondade_piirid`, `ehak:omavalitsuste_piirid`, `knr:knr_haldusyksused`, `maaamet:ads_korteriomandid`, …) — **zero asum/linnaosa-grain layers** (case-insensitive grep over all 1091 names for `asum/haldus/ehak/asustus/linnaosa/jaotus/ads`). |
| 2 | `…GetFeature&typeNames=ehak:linnade_piirid&count=1&outputFormat=application/json` | **Polygon wire shape proven.** `HTTP/2 200`, 3 369 bytes: `FeatureCollection` → `MultiPolygon` rings in L-EST97 metres — the parser below reads exactly this shape. |

Consequence: the "Maa-amet haldusjaotus WFS" step of the reopen
checklist cannot supply the 84 Tallinna asum polygons — EHAK stops
at linn/asustusüksus grain. Checklist status after this PR:

| Reopen requirement | Status |
|---|---|
| 84 asumi polügoonid | **STILL MISSING** (dated 2026-09-16, 1091-name tally) |
| Kogunenud geokodeeritud snapshotid | **STILL MISSING** (adapter schema has no coords; fixtures only) |
| Päris-store'ilt kalibreeritud bändid | **DELIBERATELY UNCALIBRATED** (fixtures never calibrate production) |
| Polygon-join kernel (this PR) | **SHIPPED, fixture-tested** |

Commands run (evidence):

```bash
mkdir -p /tmp/hf-525-probe && cd /tmp/hf-525-probe
UA="home-finder-p4-asum-probe/1.0 (Estonia open-data openness check, single polite pull)"
curl -sS -A "$UA" --max-time 60 --max-filesize 1500000 -o caps.xml \
  "https://gsavalik.envir.ee/geoserver/wfs?service=WFS&version=2.0.0&request=GetCapabilities"
# HTTP 200, 1345735 bytes, 1091 <Name>, 0 asum-grain
sleep 3
curl -sS -A "$UA" --max-time 30 --max-filesize 200000 -o linn1.json \
  "https://gsavalik.envir.ee/geoserver/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=ehak%3Alinnade_piirid&count=1&outputFormat=application%2Fjson"
# HTTP 200, 3369 bytes, FeatureCollection/MultiPolygon
```

## 2. What ships

`services/scoring/dims_p4_asum_join.py`: `fetch_polygons_snapshot()`
(polite, cache-first, `ASUM_POLY_TTL_S = 30 d`; `typename=None`
refuses BEFORE any network — never guesses a layer)
→ `parse_polygons_geojson()` (pure: Polygon/MultiPolygon + holes,
fixture-tested against the observed wire shape)
→ `join_rows_to_polygons()` (pure: containment-only join, exact
`asum` key attached, first polygon wins, skipped rows COUNTED)
→ `group_by_asum()` / `describe_asum()` / `describe_joined_store()`
(same MIN_N=5 gate and reason shape as `dims_p4_own_asum.py` —
parity pinned three ways by test).

Production snapshot is EMPTY (no polygons vendored) → join yields
zero groups → `describe_joined_store` returns `{}` — honest-empty
by construction. No fake medians; thin asums stay NULL with their n
labeled. `dims_p4_own_asum.py`, `layers_asumedia.ts`, WEIGHTS, and
all group files untouched.

## 3. Judgment calls for the reviewer

1. New files only (3). The kernel feeds the #495 kernel; it does
   not reimplement its gate (parity, not a fork).
2. Boundary points count as inside; holes exclude; overlaps go to
   the first polygon — all documented in the module docstring.
3. The kernel is unit-agnostic (WGS84 degrees or L-EST metres —
   caller keeps rows and polygons in one frame); no projection
   math lives here (ohuseire #524 owns its own conversion).
4. Test fixtures are unit squares — real values only in §1 above.

## 4. DoD evidence

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_asum_join.py -q
13 passed in 0.04s
```

Hermetic: zero network calls in tests. Full-suite output in the PR body.

## 5. Reopening checklist (what finally flips this)

* 84 asumi polügoonid vendored or a named asum-grain typename →
  pass it to `fetch_polygons_snapshot(typename=…)`; the parse/join
  path is already tested.
* Geocoded snapshots accumulate (≥MIN_N joined rows per asum) →
  `describe_joined_store` fills; calibrate bands off that store.
* Joint WEIGHTS rebalancing (per-batch rebalancing stays one joint
  change).
