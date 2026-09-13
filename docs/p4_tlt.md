# P4 TLT verdict note — Tallinna Transport / TLT feed (P4-061 + 8 slices)

> Dated-negative verdict for issues #277 (demo) and #351 (coverage).
> Checked 2026-09-13. All nine params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_tlt.py`, pinned by
> `services/scoring/tests/test_dims_p4_tlt.py`.

## Verdict

**No open machine feed — all nine dims stay NULL with Estonian reasons.**
TLT timetables, liinimuudatuste teated, winter timetables, the night
network, stop-level ridership and commute-time planning live on the
WordPress corporate site (human-readable news), the interactive
transport.tallinn.ee timetables/trip-planner app, or nowhere at all.
There is no public bulk feed to poll politely, so there is no
ingestion to cache, no TTL to state beyond this one-off check, and
no honest per-stop band or calendar to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

6 tiny requests total (redirect checks + three single GETs, labelled
one-off user-agent `home-finder openness-check (one-off, no scrape)`,
headers + visible-text keyword scope read only). Raw bodies:
`/tmp/tlt-open/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.tlt.ee/` → 301 to `https://tlt.ee/` (HTTP 200, ~60 KB) | WordPress corporate site (news, piletiinfo, teenused); visible-text sweep 0 for avaandmed / open data / GTFS / arendaja / developer / API / X-tee / andmestik / masinloetav (sõiduplaan 1x as a passenger link) | No open-data page, no developer portal, no machine feed advertised |
| `tlt.ee/teadeteajalugu/` link surface | Human-readable notices (e.g. "1. septembrist minnakse üle sügis-talvistele sõiduplaanidele", Tallinna maraton traffic changes) | Liinimuudatused exist as news HTML, never a comparable machine vintage — the P4-061 cut fraction cannot be measured |
| `https://transport.tallinn.ee/` (HTTP 200, ~150 KB); `https://soiduplaan.tallinn.ee/` → 301 to it | Interactive timetables / trip-planner app (Routes and Schedules, Trip planner, Map); visible-text sweep 0 for every open-data keyword | Interactive planner, not a pollable per-address/stop join |
| `https://andmed.eesti.ee/dataset?q=tallinna+linnatransport+GTFS` (HTTP 200, ~75 KB) | JS "Teabevärav" shell, 12 visible characters, no server-rendered results | No trivially pollable national-portal TLT dataset (same shell as the #264 check) |
| `https://opendata.tallinn.ee/` | DNS NXDOMAIN | No Tallinn open-data portal exists to poll |
| Kooliteed / winter bus ops / öötransport / ridership / commute times | Published nowhere machine-readable | Nothing to poll for the P4-012/P4-018/P4-027/P4-032/P4-037 slices |

Judgment call: the check stopped at storefront/app-shell level on
purpose — no endpoint enumeration, no planner session flows, no
map-app internals scraping. Deeper probing is exactly the scraping
this repo refuses (AGENTS.md §5).

## What stays open (overturn paths, not wired here)

- **P4-061 bus-cut half:** tlt.ee teadeteajalugu stays the
  human-readable buyer check; the Peatus GTFS prev-vs-cur diff
  (dims_p4_peatus dim_bus_cut) stays the scored machine cousin for
  the same param. A TLT machine vintage would graduate only the TLT
  leg here.
- **P4-012 school half:** kohapealne ristmiku vaatlus + OSM
  zebra/speed-bump inventory (dims_p4_osm dim_blackspots) stay the
  checks; a Kooliteed machine map would graduate the TLT leg.
- **P4-018 winter half:** tlt.ee sügis-talvised teated + Tallinna
  talihoolduse tasemed stay the checks.
- **P4-027 night half:** transport.tallinn.ee trip planner + Wolt/Bolt
  night coverage stay the checks.
- **P4-032 ridership half:** kohapealne õhtune vaatlus stays the
  check — and even an open count must stay a usage-not-safety proxy
  (PPA/Päästeamet explicitly NOT a source).
- **P4-037 commute half:** trip-planner pendel + EMTA automaksu
  kalkulaator stay the checks; the Peatus Wednesday-offset leg
  (dims_p4_peatus dim_policy_exposure) stays the scored cousin.
- **P4-045/P4-048/P4-049 access halves:** evening / <15 min / Sat
  19:00 trip-planner probes stay the checks; the Peatus evening /
  walk / Saturday legs stay the scored cousins.
- **Full overturn:** TLT (or andmed.eesti.ee) publishes a machine
  timetable/change feed for any slice → re-open #277, build the
  polite cached ingestion (daily TTL per parameters3.md §5.12
  cadence), and graduate that dim to a per-stop band / calendar.
- **Stop positions (not a verdict change):** TLT-city stops ride the
  `gtfsstops` point overlay (#483) from the snapshot GTFS vintage
  `gtfs/tallinn-gtfs-2026-09-11.zip` (scheduled departures as marker
  size; evening ridership still NULL above).

## Why demo + coverage share one PR

The coverage body (#351) states it extends the demoed ingestion
(#277). With the demo verdict dated-negative there is no ingestion
to extend, so the eight coverage slices (P4-012, P4-018, P4-027,
P4-032, P4-037, P4-045, P4-048, P4-049) land in the same verdict
module instead of a second file importing a pipeline that does not
exist. One module, one test file, one verdict note — no edits to
shared files (same precedent as elektrilevi #264+#344).
