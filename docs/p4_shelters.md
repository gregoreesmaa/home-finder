# P4 public-shelter proximity layer (issue #528)

Closes #528.

## 1. Verdict (2026-09-16): VIABLE — honest proximity dim, raster deferred

One polite probe round (UA `home-finder-idea-probe/1.0`, `--max-time 20/30`,
no retries, paced ≥ 3 s), cached to `/tmp/hf-526-529-probe` (one-off PR
record, not committed):

| # | URL | Result |
|---|-----|--------|
| 1 | `https://opendata.smit.ee/gis/varjumiskohad.csv` (HEAD) | **OPEN.** `HTTP/1.1 200`, `application/octet-stream`, 34 768 B |
| 2 | same (GET) | **303 shelter rows (67 Tallinn, 77 Harju).** `;`-separated UTF-8: id, nimi, aadress, lest_x (northing), lest_y (easting), L-EST97 metres. No WGS84 columns — projection via the labelled ~1 m inverse-LCC port (same constants as #527; axis order covered by that issue's 238-row dual-coordinate oracle, 6.1 cm worst-case, same day) |
| 3 | Coverage check (local) | **67 Tallinn shelters ≫ the issue's <5 token threshold** — a real proximity layer is viable, not a no-map. City-centre public buildings plus suburbs; staleness governed by the weekly snapshot date echoed in every reason |

Licence: **CC_BY_NC_4.0** per the national catalogue — attribute
Päästeamet, weekly TTL at most. Publisher caveat restated: brand-new
register (published 2026-07-29), data may shift between publications.
No 429 encountered.

## 2. What ships

`services/scoring/dims_p4_shelters.py` (new): `fetch_shelters_snapshot()`
(polite, cache-first, `SHELTERS_CACHE_TTL_S = 7 d`, default dir
`/tmp/hf-shelters-cache`) → `parse_shelters_csv()` (pure: L-EST97
plausibility gate + projection, coordinate-less rows skipped and
counted) → `dim_shelter_proximity()` (straight-line bands ≤500 m → 80,
≤1 km → 65, ≤2 km → 50, capped 80; beyond 2 km NULL, never "unsafe";
nearest shelter wins). Every reason carries the 72 h Government-order
caveat, the not-daily-use caveat, and the snapshot date. Non-public
shelters are not published and were never hunted. No routing claims.
Transport errors raise and never touch the cache; 429 stops the run.

No raster master in this PR (one probe round, no harvest): the dim is
the honest proximity-layer half; the raster follow-up is checklist
item 1 in §5. No web overlay file — fixture points are not a map.

## 3. Judgment calls for the reviewer

1. New files only (`dims_p4_shelters.py`,
   `tests/test_dims_p4_shelters.py`, `docs/p4_shelters.md`). No
   shared-file edits; no livability/WEIGHTS hook (joint-change rule).
2. Bands are the issue's proposal verbatim; the 80 cap is structural
   (SHELTER_CAP, pinned by test) — a shelter nearby is reassurance,
   never a safety guarantee.
3. Test fixtures are fully synthetic (invented lest values); real
   observed values appear only in §1 above, never as ingested data.
4. Beyond-2 km NULL reasons name the nearest shelter + distance so the
   buyer can judge, while stating the distance is not an unsafety score.

## 4. DoD evidence

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_shelters.py -q
.................s                                                       [100%]
17 passed, 1 skipped in 0.06s
```

Hermetic: suite makes zero network calls (live pull env-gated behind
`HF_LIVE_SHELTERS=1`). Full-suite output pasted in the PR body.

## 5. Reopening checklist

* Raster follow-up: weekly-cron harvest → walk-graph bands baked in,
  contract check (half/σ), city + rural screenshot, legend carrying
  the 72 h / not-daily-use / shifting-data caveats.
* Re-probe counts yearly (register churn as the new register fills).
* Group 14 OSM safety proxies (p13, p78, p315, p335, p467) untouched —
  distinct dim key (`shelter_proximity`), no double-scoring.
