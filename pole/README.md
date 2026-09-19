# pole/ — harvest-Pi replica (issue #767)

This directory rebuilds the harvest pole (`~/hf-pole` on the always-on Pi,
`ssh gregor@192.168.50.178`) from repo sources plus operator-installed keys.
AGENTS.md §9 states the split; this directory is its executable record.

## Who holds what

| Lives here (repo, reviewed) | Lives on the Pi only |
|---|---|
| `api.py` — read API | `cache/` — rolling raw pulls (never pruned; gather-only) |
| `bin/` — 18 cron wrappers + guard/start | `built/` — latest sidecars served by the API |
| `crontab.txt` — exact cadence (18 lines) | `state/` — keys, tokens, static vintages (NEVER committed) |
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
crontab -l                            # verify 18 lines
sudo reboot                           # @reboot starts the API
curl 127.0.0.1:8001/health           # honest 503s until first pulls land
```

Keyed datasets refuse cleanly without keys (exit 2, nothing cached, nothing
faked): DATEX needs `state/datex.key`, TomTom `state/tomtom.key`, mobile
`state/opencellid.token`.

## Re-sync after repo changes (AGENTS.md §9)

```sh
scp repo/pole/api.py new-pole:hf-pole/api.py            # then restart API
scp repo/scripts/build/batch_<name>.py new-pole:hf-pole/harvesters/
scp repo/services/scoring/dims_<name>.py new-pole:hf-pole/dims/
scp repo/pole/bin/<name>.sh new-pole:hf-pole/bin/       # if wrapper changed
```

Or re-run `bootstrap.sh` (idempotent; keeps cache/built/state/logs).

## Adding a dataset

1. Merge the harvester + dims PRs first (repo rule).
2. Add `pole/bin/run-<name>.sh` here (Pi paths via `$HOME`/`$POLE` only).
3. Add its cron line to `pole/crontab.txt` + expose it in `pole/api.py`.
4. `python3 -m pytest pole/tests/ -q` — the drift test covers the new references.
5. Deploy per Re-sync above; smoke-run once; document cadence in the Pi README.

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
