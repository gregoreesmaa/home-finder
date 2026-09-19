# Probe: lasteaia queue lengths (#690) — verdict 2026-09-19

**Verdict:** dated negative. No keyless machine-readable kindergarten queue lengths; queue positions are per-child data behind authenticated self-service (personal data stays out by design).

**Method (polite, /tmp only):** single GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf690_*`, never committed.
- `GET www.tallinn.ee/et/lasteaed` → 301 → `/et/haridus/lasteaed` → 200, 85 KB. Zero `järjekord` mentions; links point at `info.haridus.ee`, `teatmik.haridus.ee/lasteaiad/`, `harno.ee`.
- `GET teatmik.haridus.ee/lasteaiad/` → 200, 39 KB JS-driven listing (`KindergartensController.doShowKindergartensPage`): has a `vacantSpots` filter but no static per-kindergarten queue data; backing API endpoint lives in JS bundles (beyond polite budget).
- `GET teatmik.haridus.ee/lasteaiad/vacant-spots` → 301 → same JS listing (no static table).
- `taotlus.tallinn.ee/` → DNS did not resolve on this network (curl exit 6, single-network evidence — needs review-time second-network confirmation; likely a wrong hostname guess).

**What would overturn:** a documented keyless aggregate (e.g. per-lasteaed free-place counts as CSV/API, not per-child queues) appearing on Harno/teatmik or the open-data portal. Then file a scoped build issue and reference this probe.
