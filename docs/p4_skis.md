# Winter leisure: suusarajad groomed-track status (issue #692)

> Code: `scripts/build/batch_skis.py`; tests:
> `services/scoring/tests/test_batch_skis.py` (hermetic).
> Overlay: `apps/web/lib/layers_p4_skis.ts` + `.test.ts`
> (seasonal pins, honest off-season empty — DATEX SRTI pattern).

## Buyer question

"Kas lähedal on hooldatud suusarada?" — groomed cross-country
track status (Tallinn maintained tracks) as a seasonal leisure
layer for the winter-buyer segment.

## §6 Source verdict (STEP ZERO — 2026-09-19)

**Groomed-track status is HUMAN-ONLY — no machine feed exists.**
Polite one-off round, UA `home-finder-research/0.1`,
`--max-time` 25, paced, raw in `/tmp/hf_ski_pirita.html`
(one-off PR record, never committed).

| Check | Observed | Meaning |
|---|---|---|
| `GET piritaspordikeskus.ee/` → 302 to `tallinn.ee/et/piritaspordikeskus` → 200, 46 751 B human HTML | Page says verbatim: "2025/26 suusahooaeg on selleks korraks läbi. Kohtume järgmisel hooajal!" | Off-season confirmed LIVE 2026-09-19; status channel = the page + phone 600 8333 |
| Same page, link/endpoint scan | Zero JSON/API endpoints, zero GBFS/auto-discovery surface | Nothing to poll — a scraper would parse human prose, fragile and impolite |

Judgment call: no scraper around the human page (AGENTS.md §7.4 —
fragile prose parsing is not a feed). In season the operator reads
the page and drops a verified `status.json`; off-season the table
stays honestly empty (never carried over — stale groomed dots
would be fake snow).

## Harvester

`batch_skis.py --build --cache-dir DIR [--status status.json]`
(`--pull` honestly refuses, exit 2 — no machine feed). Only
groomed, coordinate-carrying KNOWN_TRACKS rows plot (Pirita
Velodroom, Nõmme-Harku, Harku, Hiiu — entry coordinates verified
at the first in-season drop, never hand-placed here). `--build`
prints `{"total", "season"}`; absent drop = `total: 0, season:
"off"`.

## Pole wiring (pole files, recorded here per AGENTS.md §9)

Wrapper `bin/run-skis.sh` (in-season only, Nov–Mar):

```sh
#!/bin/sh
# Pole wrapper: ski-track table from the operator-verified winter
# drop (human tallinn.ee page read, never scraped). Off-season the
# cron is disabled and the table stays honestly empty.
set -eu
POLE="$HOME/hf-pole"
OUT="$POLE/built/skis/table.json"
mkdir -p "$(dirname "$OUT")"
if [ -f "$POLE/state/skis-status.json" ]; then
  python3 "$POLE/harvesters/batch_skis.py" \
    --build --cache-dir "$POLE/cache/skis" \
    --status "$POLE/state/skis-status.json" > "$OUT.tmp"
  mv "$OUT.tmp" "$OUT"
fi
```

Cron (pole crontab, enabled Nov–Mar only):
`17 7 * * * $HOME/hf-pole/bin/run-skis.sh >>$HOME/hf-pole/logs/skis.log 2>&1`

Read API: `GET /v1/skis` (honest 503 until the first in-season
drop builds the table).

## Buyer-side check (off-season)

Hooaeg on läbi — vaata hooajal tallinn.ee Pirita Spordikeskuse
lehte (tel 600 8333) ja käi rada kohapeal läbi.
