# TarkTee DATEX road restrictions — keyed verdict + short-lived-cache design (issue #681)

> Verdict date: 2026-09-19 (profile PDF fetched live, no key used).
> Code: `scripts/build/batch_datex_restrictions.py` (keyed pull +
> offline parse/build); tests:
> `services/scoring/tests/test_batch_datex_restrictions.py` (hermetic;
> one explicitly-flagged keyed probe, skipped without
> `DATEX_API_KEY`, never runs in CI).

## §0 ToS verdict (STEP ZERO — gates ALL DATEX work, #681–#686)

Source: `DATEX_II_Estonian_profile_Tark_Tee.pdf` (live text, fetched
2026-09-19 from `https://tarktee.ee/assets/datex/`,
9 pages, technical profile — **it contains no
storage/redistribution/licence clause**). No separate TarkTee data-gateway
terms, licence, or open-data entry was locatable on tarktee.ee,
transpordiamet.ee, or the national open-data portal (searched
2026-09-19). What the profile does say (§7 "ACCESSING FEEDS"):

> "To be able to access DATEX II feeds, a valid and active API-key is
> needed. The process to get this API-key, is as follows: 1. Register
> as user of Tark Tee data gateway. You will be sent an API-key.
> 2. Wait for an e-mail that your API-key is activated. 3. You can now
> access all Tark Tee DATEX II feeds by providing your API-key. Keep
> your API-key secret!"

Plus §4.1: "Only the current versions of elements are present in
XML/JSON message, historic data is not available."

**Verdict: SHORT-TERM CACHE ONLY — no committed sidecars, no stored
tables.** No clause affirmatively permits storage or redistribution;
the key is personal and manually activated ("Keep your API-key
secret!"); the data is live operational state by design (history
unavailable, camera images refresh every 10 min, weather every
10 min, counters every 15 min). So every DATEX harvester uses a
**short-lived-cache design** — a git-ignored operator cache dir,
TTL-capped per feed — and the repo holds code + fixtures only.
Built tables live on the harvest pole only
(`built/datex-*/table.json`, honest 503 until the first keyed pull).
The one DATEX-native openness signal (profile §6.6:
`ConfidentialityValueEnum noRestriction`, "Data is not restricted")
describes the situation records, not a redistribution grant, so it
does not lift the verdict. Re-check for a published licence before
any long-term storage.

> Re-check 2026-09-20 (issue #805): profile PDF re-fetched live
> (HTTP 200, 838957 bytes, 9 pages — same document). Full-text
> search of the fresh extract: zero hits for redistribut*,
> licen*, permission, cache/caching, retention, archive*,
> long-term; §4.1 ("historic data is not available") and §7
> ("Keep your API-key secret!") unchanged. Verdict STANDS:
> SHORT-TERM CACHE ONLY — all six DATEX feeds stay window-only,
> no observation logs (full audit:
> `docs/realtime_history_805.md`).

Design consequence (all six PRs state this): raw bodies are /tmp-only
in tests, fixtures are hand-written minima, and the key travels only
as the `X-DATEX-API-KEY` header, never in files or logs.

Judgment calls (for the reviewer): (1) feed slugs beyond
`restrictions` / `temporarySlipperyRoad` (the two verified live
2026-09-18 per the issues) are operator-confirmed at the first keyed
run — `--feed` / `--feeds` overrides exist for exactly this, and
non-200 feeds are skipped honestly, never faked; (2) the API base
defaults to `https://tarktee.transpordiamet.ee` (current host per the
feed-registry notes) with `DATEX_BASE_URL` override — direct checks
from a dev machine timed out on 2026-09-19, so the pole does the
pulling; (3) per-feed TTLs mirror the profile's own refresh notes
(weather/counters fast, restrictions daily, truck parking monthly).

## Buyer question

"Kas selle piirkonna teedel on praegu sulgemisi / teetöid /
ümbersõite?" — live road-restriction overlay per area (closures,
lane closures, roadworks, detours, weight/size limits) from the
restrictions SituationPublication.

## Quota math (pinned in code)

One GET per pull, daily cadence → `QUOTA_MAX_CALLS = 4` per 24 h
window (headroom for operator retries); 429 = stop; transport errors
never cached.

## Harvester

`batch_datex_restrictions.py --pull/--build --cache-dir DIR
[--feed restrictions] [--fixture file.xml]`. Refuses without
`DATEX_API_KEY` (exit 2, both paths tested); key never
printed/written (pinned by test). `--build` prints
`{"total", "by_record"}` to stdout; full rows stay in the operator
cache / pole built file.

## Pole wiring (deployed on the pole, recorded here per AGENTS.md §9)

Wrapper `bin/run-datex-restrictions.sh` (pole file, key from
`state/datex.key` — never in the repo):

```sh
#!/bin/sh
# Pole wrapper: TarkTee DATEX restrictions (daily). Key from pole
# state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-restrictions/table.json"
mkdir -p "$POLE/cache/datex-restrictions" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_restrictions.py" \
  --pull --build --cache-dir "$POLE/cache/datex-restrictions" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
```

Cron (pole crontab): `17 4 * * * $HOME/hf-pole/bin/run-datex-restrictions.sh >>$HOME/hf-pole/logs/datex-restrictions.log 2>&1`

Read API: `GET /v1/datex-restrictions` (honest 503 until the first
keyed pull builds the table); `harvesters/` + `dims/` re-sync copies
per AGENTS.md §9; pole README documents the line.

## §7 key placement

Export `DATEX_API_KEY` in the operator shell only (pole: `state/`
+ wrapper). Never commit it, never put it in repo files, never paste
it in chat. Optional `DATEX_BASE_URL` override the same way.
