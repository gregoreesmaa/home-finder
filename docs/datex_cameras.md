# TarkTee DATEX road cameras — keyed harvester (issue #685)

> Code: `scripts/build/batch_datex_cameras.py`; tests:
> `services/scoring/tests/test_batch_datex_cameras.py` (hermetic; one
> explicitly-flagged keyed probe, skipped without `DATEX_API_KEY`,
> never runs in CI).

## §0 keyless-ArcGIS check FIRST (issue step zero) + ToS verdict

**Keyless-ArcGIS check (run 2026-09-19, before any other step):
NEGATIVE.** No public keyless Transpordiamet ArcGIS Server exists
(`https://arcgis.transpordiamet.ee/arcgis/rest/services` returns
empty) and no indexed public keyless camera service was found.
Profile §§6.8–6.10 gate BOTH camera publications
(PredefinedLocations + TrafficView) behind the API key. Verdict:
**dated-negative-compatible** — this keyed harvester ships; if a
keyless path later surfaces, the harvester is rescoped (locations via
the keyless path, keyed feed dropped).

**ToS verdict (shared with #681–#686): SHORT-TERM CACHE ONLY — no
committed sidecars, no stored tables.** Pasted from
`docs/datex_restrictions.md` §0 (the step-zero home): the DATEX
profile PDF (live text 2026-09-19) contains NO
storage/redistribution/licence clause; no separate TarkTee gateway
terms or open-data entry was locatable. The key is personal and
manually activated ("Keep your API-key secret!"); the data is live
operational state (historic unavailable, pictures refresh every
10 min). Built tables live on the harvest pole only
(`built/datex-cameras/table.json`, honest 503 until the first keyed
pull); raw bodies are /tmp-only in tests; fixtures are hand-written
minima; the key travels only as the `X-DATEX-API-KEY` header.

## Buyer question

"Kas selle piirkonna teedel on kaameraid / näen ise järele?" —
camera index per area (profile §6.8–§6.10): position + name + latest
picture URL. **Scope limit: URL-id only — image binaries are never
downloaded** (pinned by test: no `.jpg/.png` request can occur);
pictures refresh every 10 min, binaries would bloat the cache.

## Quota math (pinned in code)

2 feeds × 24 pulls/day = 48 → `QUOTA_MAX_CALLS = 50` per 24 h
window; TTL 1 h on the URL table; 429 = stop; transport errors never
cached. Feed slugs confirmed at the first keyed run via `--feeds`;
non-200 feeds skip honestly.

## Harvester

`batch_datex_cameras.py --pull/--build --cache-dir DIR
[--feeds cameraLocations,cameraImages] [--fixture file.xml]`.
Refuses without `DATEX_API_KEY` (exit 2, both paths tested); key
never printed/written (pinned). `--build` merges bodies by camera id
and prints `{"cameras", "located", "with_image"}`.

## Pole wiring (pole files, recorded here per AGENTS.md §9)

Wrapper `bin/run-datex-cameras.sh`:

```sh
#!/bin/sh
# Pole wrapper: TarkTee DATEX road cameras (hourly). Key from pole
# state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-cameras/table.json"
mkdir -p "$POLE/cache/datex-cameras" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_cameras.py" \
  --pull --build --cache-dir "$POLE/cache/datex-cameras" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
```

Cron (pole crontab): `52 * * * * $HOME/hf-pole/bin/run-datex-cameras.sh >>$HOME/hf-pole/logs/datex-cameras.log 2>&1`

Read API: `GET /v1/datex-cameras` (honest 503 until the first keyed
pull builds the table).

## §7 key placement

Export `DATEX_API_KEY` in the operator shell only (pole: `state/` +
wrapper). Never commit it, never put it in repo files, never paste
it in chat. Optional `DATEX_BASE_URL` override the same way.
