# pole/ — harvest-Pi replica (issue #767)

This directory rebuilds the harvest pole (`~/hf-pole` on the always-on Pi,
`ssh gregor@192.168.50.178`) from repo sources plus operator-installed keys.
AGENTS.md §9 states the split; this directory is its executable record.

## Who holds what

| Lives here (repo, reviewed) | Lives on the Pi only |
|---|---|
| `api.py` — read API | `cache/` — rolling raw pulls (never pruned; gather-only) |
| `bin/` — 17 cron wrappers + guard/start/sync + exit recorder | `built/` — latest sidecars served by the API |
| `crontab.txt` — exact cadence (20 lines) | `state/` — keys, tokens, static vintages (NEVER committed) |
| `requirements.txt` — API venv pin | `logs/` — per-job logs (trimmed >10 MB) |
| `bootstrap.sh` — new-Pi setup | `venv/` — built by bootstrap |
| `tests/` — API + replica drift tests | |

`harvesters/` and `dims/` are intentionally NOT duplicated here: bootstrap
copies them from `scripts/build/batch_*.py` and `services/scoring/dims_*.py`
(explicit manifest in `bootstrap.sh`), and `tests/test_replica.py` fails if a
wrapper references a module the repo does not have.

## Fresh-Pi setup

```sh
git clone <repo> ~/home-finder        # or scp an export
./home-finder/pole/bootstrap.sh       # materializes ~/hf-pole, installs cron
# keys BY HAND (never committed, never in chat):
scp old-pole:hf-pole/state/datex.key old-pole:hf-pole/state/tomtom.key \
    old-pole:hf-pole/state/opencellid.token old-pole:hf-pole/state/*.zip \
    ~/hf-pole/state/
crontab -l                            # verify 20 lines
sudo reboot                           # @reboot starts the API
curl 127.0.0.1:8001/health           # honest 503s until first pulls land
```

Keyed datasets refuse cleanly without keys (exit 2, nothing cached, nothing
faked): DATEX needs `state/datex.key`, TomTom `state/tomtom.key`, mobile
`state/opencellid.token`.

## Auto-sync with green-main (issue #806)

No operator re-sync: `bin/pole-sync.sh` runs hourly (`:17`, crontab line
20) and lands the latest green-`main` by itself — worst-case lag ~1 h.

- Target: the `pole-release` tag when it exists on origin, else
  `origin/main` (same rule the Mac watcher uses for its staleness
  check, so both sides agree on what "behind" means).
- Code only: harvesters + dims (per `pole/manifest.sh`, shared with
  `bootstrap.sh`), `api.py`, `bin/*.sh`, crontab. Never touches
  `cache/`/`built/`/`state/` keys/`logs/` (only sync bookkeeping:
  `state/deployed-sha.txt`, `state/deployed-at.txt`,
  `state/sync-status.json`, code backups under `state/code-backup/`).
- Safe deploy: previous code tarballed to `state/code-backup/` (newest 3
  kept, restorable by hand); venv rebuilt only when
  `pole/requirements.txt` changed; API restarted on change (deploy
  restarts go through sync — `guard-restarts.jsonl` stays crash-only).
- Deployed identity: `GET /health` returns `deployed_sha` + `deployed_at`
  (nulls on a fresh pole / in the repo checkout — never faked).
- Prove/force it by hand: `~/hf-pole/bin/pole-sync.sh --check` (exit 0 in
  sync, 1 behind), `--dry-run` (plan, changes nothing).

Manual re-sync (recovery only — sync is automatic otherwise): re-run
`bootstrap.sh` (idempotent; keeps cache/built/state/logs).

## Failure surfacing: Mac-side watcher (issue #806)

`scripts/pole_watch.py` polls the pole through the existing tunnel
(`POLE_BASE_URL`) every 15 min (Mac cron below) and files one GitHub
issue per failure class (label `pole-watch`), updating instead of
duplicating, auto-closing on recovery:

| Class | Signal |
|---|---|
| `sync-behind` | `deployed_sha` != green-`main` for >2 h |
| `sync-failing` | last `pole-sync.sh` run exited nonzero |
| `wrapper-<job>` | wrapper's last recorded exit nonzero (via `wrap-run.sh`) |
| `stale-<dataset>` | table older than its serve TTL (`X-Pole-Built-At` vs `DATASET_TTL_S` in `api.py`) |
| `guard-restarts` | unexpected API death (deploy restarts excluded) |
| `never-built-<ds>` / `regression-<ds>` | honest 503 past the 7-day first-build grace / ready→503 flip |

Noise control: state classes need 2 consecutive failing polls (~30 min
debounce) so one 429/transient never files; max 5 new issues per run;
transport errors (tunnel/pole down) are never issues and never data
(exit 2, file nothing). Evidence in each issue: SHAs, exit codes,
ages/TTLs from `GET /v1/errors` plus the exact ssh log-tail command.

Auth: the operator's existing `gh auth login` — no new token anywhere,
nothing to install on the Pi (watcher placement is deliberately
Mac-side; token install step: none).

```sh
# Mac cron (every 15 min). Without HF_POLE_WATCH=1 the watcher only
# reports (dry-run) — live filing is explicitly-flagged, like the
# presence sweep. State lives in ~/.hf-pole-watch/ (never committed).
*/15 * * * * HF_POLE_WATCH=1 POLE_BASE_URL=http://127.0.0.1:18001 \
  python3 ~/home-finder/scripts/pole_watch.py >>/tmp/pole-watch.log 2>&1
```

Machine-readable evidence endpoint: `GET /v1/errors` (guard restarts,
per-wrapper last exits, last sync result, per-dataset age vs TTL).
Every cron wrapper runs through `bin/wrap-run.sh <job>` (crontab);
hand runs (e.g. seasonal `run-skis.sh`) should use it too:
`wrap-run.sh skis bin/run-skis.sh`.

Mirror note: the Pi `~/hf-pole/README.md` documents the same cadence;
after merging, re-sync it with this file's Auto-sync + watcher sections
(it is Pi-local, not in the repo).

## Adding a dataset

1. Merge the harvester + dims PRs first (repo rule).
2. Add `pole/bin/run-<name>.sh` here (Pi paths via `$HOME`/`$POLE` only).
3. Add its cron line to `pole/crontab.txt` (routed through
   `wrap-run.sh <name>` so exits surface in `/v1/errors`) + expose it in
   `pole/api.py` (+ a `DATASET_TTL_S` entry, `None` only when the dataset
   has no cron). Add harvester/dims names to `pole/manifest.sh`.
4. `python3 -m pytest pole/tests/ -q` — the drift test covers the new references.
5. Deploy per Re-sync above; smoke-run once; document cadence in the Pi README.

## History policy (issue #805)

Realtime feeds accumulate history ONLY where ToS allows
(full audit: `docs/realtime_history_805.md`):

- **History**: `outage` (append-only
  `cache/outage/observations.jsonl`, retention = forever, plus the
  28-day `outage-reliability` rollup) and `delay` (gather-only cache,
  never deleted). Disk growth: outage ≈ KB/day; delay ≈ 24 MB/day
  (see `bin/run-prune.sh` for headroom math).
- **Window-only, no-store** (ToS re-check 2026-09-20): all six
  `datex-*` tables (DATEX SHORT-TERM CACHE ONLY — profile §4.1, no
  storage/redistribution clause) and `incidents` + `sheds` (TomTom
  clause 11.4). Wrappers replace the window table each pull
  (atomic tmp+mv; failures keep the previous table) and must never
  grow an observation log — pinned by
  `pole/tests/test_realtime_history_805.py`.
- **Exempt** (not realtime): fixit/medre/poi/mobile snapshot
  rebuilds, viirs annual, skis seasonal.

No new cron lines for #805 (nothing new to schedule); re-sync after
repo changes per the section above (wrappers + tests only — no
harvester/dims changes).

## Seasonal datasets (no cron)

`skis` is the seasonal exception: `pole/api.py` already exposes
`skis/table.json` and `pole/bin/run-skis.sh` builds it, but there is
deliberately NO cron line (off-season the cron does not run at all —
docs/p4_skis.md). In season the operator drops a verified
`state/skis-status.json` and runs `bin/run-skis.sh` by hand; absent
drop = honest off-season empty. GBFS has no wrapper at all by the
2026-09-19 verdict (no verified keyless feed — docs/p4_gbfs.md);
add one only after a live re-verification.

## Consuming the data

Direct LAN HTTP to the Pi is upstream-filtered (port 22 only). The Mac holds
an ssh tunnel `127.0.0.1:18001 -> pole:8001` (LaunchAgent
`ee.homefinder.pole-tunnel`, KeepAlive); consumers use `http://127.0.0.1:18001`
(`POLE_BASE_URL`). Endpoints: `GET /v1/<dataset>`, `/health`, `/v1/datasets`
— freshness via `X-Pole-Built-At`, honest 503s, never faked data.

Containerized consumers (`docker compose` web, issue #776) cannot use the
loopback URL — inside a container `127.0.0.1` is the container itself — so
`docker-compose.yml` sets
`POLE_BASE_URL=http://host.docker.internal:18001` (verified 200 from compose
web 2026-09-19 against the loopback-bound tunnel, plus `extra_hosts` for
Linux docker). Native dev keeps the `127.0.0.1` default in
`apps/web/lib/server/livecache.ts`.
