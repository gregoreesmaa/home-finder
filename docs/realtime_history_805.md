# Realtime feeds: aggregate over time vs window-only (issue #805)

> Decision date: 2026-09-20. Status: ToS re-check DONE (both blockers
> re-verified live); history lands ONLY where ToS allows. DATEX x6 +
> TomTom x2 stay SHORT-TERM-CACHE window tables (dated no-store
> decision, pinned by `pole/tests/test_realtime_history_805.py`);
> outage + delay already accumulate (precedents, untouched).

## §0 ToS re-check (2026-09-20, gates ALL of #805)

**DATEX (TarkTee profile PDF, re-fetched live 2026-09-20):**
HTTP 200, 838957 bytes, 9 pages — same document as the 2026-09-19
verdict. Full-text search of the fresh extract: 0 hits for
`redistribut*`, `licen*`, `permission`, `cache/caching`,
`retention`, `archive*`, `long-term`. §4.1 VERSIONING unchanged
("Only the current versions of elements are present in XML/JSON
message, historic data is not available"). §7 unchanged (personal
API key, "Keep your API-key secret!"). §6.6 `noRestriction` still
describes situation records, not a redistribution grant.
**Verdict STANDS: SHORT-TERM CACHE ONLY — no long-term history for
any DATEX feed.** Re-check again before any future long-term
storage; a published licence would lift this.

**TomTom (Portal Terms & Conditions, clause 11.4):**
Terms page verified live at
`https://docs.tomtom.com/legal/terms-and-conditions/` on 2026-09-20
(HTTP 200; direct curl from dev returns empty — page needs JS/CDN,
same limitation as 2026-09-19, so the operative clause text captured
live 2026-09-19 stands): "The caching or storing of any Results
shall be prohibited except that you may cache Results ... for longer
than the maximum age period indicated in such cache control
headers; ... Nothing under Clause 11.4 entitles any form of caching
for the purpose of scaling results to serve multiple clients or
users." Aggregating incident/shed history = storing Results beyond
max-age = prohibited under current terms.
**Verdict STANDS: SHORT-TERM CACHE ONLY — no long-term history for
any TomTom feed.**

## §1 Audit: every ~realtime dataset, convert or exempt

| Feed(s) | Pole dataset(s) | Pattern | Verdict (#805) |
|---|---|---|---|
| DATEX restrictions, SRTI, weather, counters, cameras, truckpark | `datex-restrictions/srti/weather/counters/cameras/truckpark` | window table replaced each pull (tmp+mv); TTL-capped cache | WINDOW-ONLY, no-store (ToS §0 above). No observation log — logging history would itself violate the verdict. Counts aggregates in the window table are the only rollup. |
| TomTom incidents (6-hourly), sheds (weekly) | `incidents`, `sheds` | same replace pattern | WINDOW-ONLY, no-store (ToS §0 above). Same reasoning. |
| Outage (Elektrilevi hetkeseis, 5-min) | `outage`, `outage-reliability` | append-only `cache/outage/observations.jsonl` (retention = forever) + 28-day reliability table | HISTORY — done (#780, #801). Untouched by #805; pinned intact by the new tests. |
| Delay (GPS sampler) | `delay` | gather-only cache, NEVER deleted (2026-09-19 operator decision); corridor table rebuilds from the growing cache | HISTORY — done. Untouched by #805. |
| fixit, medre, poi, mobile | `fixit`, `medre`, `poi`, `mobile` | snapshot rebuilds (daily/weekly/monthly), not realtime event streams | EXEMPT — not realtime; caches gather-only per the #801 prune decision. |
| viirs (annual), skis (seasonal) | `viirs`, `skis` | static/seasonal rebuilds | EXEMPT — not realtime. |

Geometry note (from the issue, confirmed): aggregating
`datex-restrictions` / `datex-srti` would yield counts/statistics
only — rows carry no coordinates by format, so history could never
produce map pins. The no-store verdict costs the map nothing it
could have plotted.

## §2 What #805 changes (window-only feeds)

No behavior change — the replace pattern is already failure-safe
(`set -eu`: a failed pull exits before `mv`, the trap removes the
tmp file, the previous table stays; pinned by test). #805:

1. Records the ToS re-check (§0) so the no-store decision is dated
   and reviewable instead of implicit.
2. Labels every no-store wrapper header (`pole/bin/run-datex-*.sh`,
   `pole/bin/run-tomtom-*.sh`) with the window-only verdict + pointer
   here, so a future "add history" edit confronts the ToS blocker.
3. Pins the invariants hermetically
   (`pole/tests/test_realtime_history_805.py`): short TTL/quota caps
   intact on all 8 harvesters; no observation-log path in any
   no-store wrapper/harvester; outage/delay history paths intact;
   failed wrapper runs leave the built table untouched.
4. Map contract unchanged and already compliant (#783): every
   live-descended layer names its window + vintage —
   `DATEX_WINDOW_ET` (per-feed `aken` strings),
   `INCIDENTS_WINDOW_ET` ("6 h aken"), `SHED_WINDOW_ET` ("7-päeva
   aken, nädalatõmme") + shed windowed status line; honest 503 until
   first build preserved (pole `api.py` untouched).

## §3 Disk growth

No-store feeds: bounded by design (one window table + one TTL-capped
cache each; growth ≈ 0). History feeds: outage observations grow
~1 record / 5 min forever (compact JSON, KB/day — negligible);
delay GPS ~24 MB/day per the prune-wrapper comment (~6 y headroom).
No new cron lines (crontab unchanged — there is nothing new to
schedule); re-sync per `pole/README.md` (wrappers + tests only, no
harvester/dims changes).
