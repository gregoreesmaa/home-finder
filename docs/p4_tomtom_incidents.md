# P4 TomTom daily incident overlay — freshness-dated (issue #672)

> Code: `services/scoring/dims_tomtom_incidents.py` (keyed pull +
> scorer leg); harvester: `scripts/build/batch_tomtom_incidents.py`;
> tests: `services/scoring/tests/test_batch_tomtom_incidents.py` (+
> hermetic `test_dims_tomtom_incidents.py`; one explicitly-flagged
> keyed probe, skipped without `TOMTOM_API_KEY`, never runs in CI).

## §0 ToS verdict (STEP ZERO from #669 — applies verbatim)

TomTom Portal Terms & Conditions, clause 11.4 (live text 2026-09-19,
`https://docs.tomtom.com/legal/terms-and-conditions/`):

> "The caching or storing of any Results shall be prohibited except
> that you may cache Results delivered by the Licensed Products
> provided that: ... such Results must not be cached in clients for
> longer than the maximum age period indicated in such cache control
> headers; ... Nothing under Clause 11.4 entitles any form of caching
> for the purpose of scaling results to serve multiple clients or
> users."

**Verdict: SHORT-TERM CACHE ONLY — no committed sidecars, no stored
tables.** Full verdict in `docs/p4_tomtom_matrix.md` §0. This
harvester keeps a 6 h operator cache and honors response max-age in
code — incidents are the most perishable of the seven datasets, so
the TTL is the shortest.

> Re-check 2026-09-20 (issue #805): terms page verified live at the
> same URL (HTTP 200; direct dev-machine fetch returns empty —
> page needs JS/CDN, same limitation as 2026-09-19 — so the
> operative clause-11.4 text captured live 2026-09-19 stands, with
> no evidenced storage-permitting amendment). Verdict STANDS:
> SHORT-TERM CACHE ONLY — incidents stay window-only, no
> observation log (full audit: `docs/realtime_history_805.md`).

## Buyer question

"Kas mu marsruudil on täna ummik, sulgus või teetööd" — one Tallinn
bbox poll (`timeValidityFilter=present`), daily. Freshness-dated
overlay in the teeolud family.

## Quota math (pinned in code)

**1–2 txn/day** (one bbox poll + one spare). `INCIDENTS_MAX_CALLS =
2` per 6 h window; 429 = stop.

## Expiry (documented, load-bearing)

- Every snapshot carries `fetched_at`; `is_fresh` decides against
  the 6 h TTL. Older = STALE.
- The scorer returns NULL on stale ("aegunud ... värsket mõõtmikut
  oodatakse") — never presented as live when old.
- The overlay contract: render the freshness timestamp, not just the
  geometry; stale geometry must hide behind the timestamp.

## Harvester

`batch_tomtom_incidents.py --pull/--build --cache-dir DIR [--bbox
...]`. Refuses without `TOMTOM_API_KEY` (exit 2, both paths tested);
key never printed/written (pinned by test). `--build` prints counts
(by magnitude) + `fresh` flag.

## Honest shapes (scorer dim)

| Leg | Dim key | Scored shape | NULL when |
|---|---|---|---|
| Teeolud | `teeolud` | incidents ≤1 km: 0→75, 1–2→60, 3+→40; reason carries magnitude label | no keyed pull; snapshot stale (aegunud, never live) |

## §7 key placement

Export `TOMTOM_API_KEY` in the operator shell only. Never commit it,
never put it in repo files, never paste it in chat. No WEIGHTS splice
here (joint follow-up). 5 new files, zero shared-file edits.

Refresh runs on the pole (`pole/bin/run-tomtom-incidents.sh`, every
6 h at :17, key from pole `state/tomtom.key`; the harvester
self-skips while the 6 h cache is fresh and quota-caps at 2 pulls /
6 h). The wrapper writes the servable table
(`built/tomtom-incidents/table.json`, `--build` stdout contract
#776), exposed as pole dataset `incidents` and read pole-first by
the `[layer]` route (local cache fallback, 6 h TTL both legs, 200
names `source: pole|cache`) — #782.
