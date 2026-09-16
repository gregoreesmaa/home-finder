# P4 wildfire-recurrence avoidance layer (issue #529)

Closes #529.

## 1. Verdict (2026-09-16): VIABLE — measured recency dim, raster deferred

One polite probe round (UA `home-finder-idea-probe/1.0`, `--max-time 20/30`,
no retries, paced ≥ 3 s), cached to `/tmp/hf-526-529-probe` (one-off PR
record, not committed):

| # | URL | Result |
|---|-----|--------|
| 1 | `https://opendata.smit.ee/paa/csv/metsa_ja_maastikutulekahjud_jooksev_aasta.csv` (HEAD) | **OPEN.** `HTTP/1.1 200`, `application/octet-stream`, 191 911 B |
| 2 | same (GET) | **652 rows 2026-YTD (173 Harju: 58 Tallinn, 14 Saue, 13 Lääne-Harju, 13 Harku, 13 Jõelähtme, 12 Maardu …).** TAB-separated, 25 columns: sundmuse_number, sundmuse_kuupaev_dt (ISO), tulekahju_liik (all `Metsa-ja maastikutulekahju`), mis_poles (Maastik 515 / Mets 70 / both 66 / blank 1), **wgs_latitude/wgs_longitude (WGS84 directly — zero blanks in 652 rows)**, maakond, kov. No L-EST97 question at all (#522 precedent not needed — coordinates are WGS84 by column name and Tallinn-plausible) |
| 3 | Archive guess (HEAD) | **404, dated gap kept.** `…/metsa_ja_maastikutulekahjud_2014_2025.csv` does not exist under that name (single HEAD, no hunting per polite rules). The 2014–2025 / 2014–2021 archives named in the issue need Teabevärav-catalogue URL resolution — adapter follow-up (§5). The dim is history-shape ready regardless (caller-supplied multi-year rows) |

Licence: **CC_BY_NC_ND_4.0** per the national catalogue — attribute
Päästeamet, respect NC/ND, daily TTL at most. Statistics caveat stated
in code + reasons: the dataset feeds national fire statistics but is
NOT the Environment Agency's official statistics (do not conflate).
No 429 encountered.

## 2. What ships

`services/scoring/dims_p4_wildfire.py` (new): `fetch_wildfire_snapshot()`
(polite, cache-first, `WILDFIRE_CACHE_TTL_S = 1 d` — publisher updates
daily, default dir `/tmp/hf-wildfire-cache`) → `parse_metsa_tsv()`
(pure: TAB, BOM-tolerant, coordinate-less or undated rows skipped and
counted) → `dim_wildfire_recency()` (recency kernel off the caller date
`as_of` — no wall-clock in the scorer: near(≤500 m)+recent(≤5 y) → 35,
near+old → 55, far(≤2 km)+recent → 55, far+old → 65; nearest incident
decides; beyond 2 km or undated snapshot is NULL, never "safe").
Reasons name the nearest incident year + fuel + KOV, the buyer check
(kindlustus, Päästeameti tuleohukaart), and the statistics caveat.
No per-address "fire risk score" beyond the honest kernel. Transport
errors raise and never touch the cache; 429 stops the run.

No raster master in this PR (one probe round, archive URLs unresolved):
the dim is the honest measured layer half; the raster follow-up is
checklist item 1 in §5. No web overlay file — fixture incidents are
not a map.

## 3. Judgment calls for the reviewer

1. New files only (`dims_p4_wildfire.py`,
   `tests/test_dims_p4_wildfire.py`, `docs/p4_wildfire.md`). No
   shared-file edits; no livability/WEIGHTS hook (joint-change rule).
2. Mets vs Maastik fuel does not split bands (same smoke question);
   the fuel label travels in the reason for the buyer to judge.
3. Undated incidents read as unusable (skipped), never as fresh — a
   recency kernel cannot score what it cannot date.
4. Test fixtures are fully synthetic (invented rows); real observed
   values appear only in §1 above, never as ingested data.

## 4. DoD evidence

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_wildfire.py -q
................s                                                        [100%]
16 passed, 1 skipped in 0.06s
```

Hermetic: suite makes zero network calls (live pull env-gated behind
`HF_LIVE_WILDFIRE=1`). Full-suite output pasted in the PR body.

## 5. Reopening checklist

* Adapter follow-up: resolve the 2014–2025 / 2014–2021 archive CSV URLs
  via the Teabevärav catalogue entry (single polite round), extend the
  fetcher to current-year + archives, re-probe Harjumaa 2014–2026 yearly
  distribution to justify the 5-year window on a histogram.
* Raster follow-up: daily-cron harvest → density/recency kernel master,
  contract check (half/σ), Nõmme/Merivälja screenshot.
* EELIS protection zones (#517) stay complementary, not merged —
  distinct dim key (`wildfire_recency`), no double-scoring.
