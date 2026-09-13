# P4 Elron verdict note — Elron timetable/notice feed (P4-014 + 3 slices)

> Dated-negative verdict for issues #284 (demo) and #358 (coverage).
> Checked 2026-09-13. All four params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_elron.py`, pinned by
> `services/scoring/tests/test_dims_p4_elron.py`.

## Verdict

**No open machine feed — all four dims stay NULL with Estonian reasons.**
Elron timetables live as per-direction PDFs, schedule changes and
railway repairs as human-readable news HTML. There is no public bulk
feed (no GTFS, no API, no RSS, no open-data page) to poll politely,
so there is no ingestion to cache, no TTL to state beyond this
one-off check, and no honest per-station band or calendar to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

5 tiny requests total (four single GETs, labelled one-off user-agent
`home-finder openness-check (one-off, no scrape; issues #284/#358)`,
headers + visible-text keyword scope read only). Raw bodies:
`/tmp/elron-open/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://elron.ee/` (HTTP 200, ~93 KB) | Visible text ~2.5k chars; sweep 0 for avaandmed / open data / GTFS / arendaja / developer / API / X-tee / andmestik / masinloetav | No open-data page, no developer portal, no machine feed advertised |
| `https://elron.ee/soiduinfo/soiduplaanid` (HTTP 200, ~82 KB) | Timetables are per-direction PDFs (`/sites/default/files/2026-08/…pdf`: lääne-, edela-, ida-/lõuna-, Tallinn–Riia/Vilnius); visible text ~2.1k chars, sweep 0 for GTFS / avaandmed / API / masinloetav / rss | Direction timetables exist as human PDFs, never a comparable machine vintage — the P4-014 calendar cannot be measured |
| `https://elron.ee/soiduinfo/teated` (HTTP 200, ~100 KB) | "Rongiliikluse teated" are dated human news entries (e.g. "13.09.2026 10:27 Reis…"); visible text ~3.8k chars, sweep 0 for GTFS / avaandmed / masinloetav / rss / API | Schedule changes exist as news HTML — the P4-061 fringe-station cut fraction cannot be measured |
| `/soiduinfo/soiduplaanid` link surface | "Telli teated" (human subscription) + `/raudteeremondid` (human repair page) | Maintenance windows exist as human pages — the P4-055 ööaknad calendar cannot be joined |
| `https://andmed.eesti.ee/dataset?q=elron` (HTTP 200, ~75 KB) | JS "Teabevärav" shell, 12 visible characters, no server-rendered results | No trivially pollable national-portal Elron dataset (same shell as the #264/#277 checks) |
| Peatus.ee GTFS | Closed per the #314 check (2026-09-13, "Rakendus on suletud"), not re-probed | The national GTFS door Elron departures would ride stays shut |

Judgment call: the check stopped at storefront/page level on
purpose — no PDF parsing, no subscription-flow driving, no timetable
internals scraping. Parsing direction PDFs would be scraping human
publications, not polling a feed — exactly what this repo refuses
(AGENTS.md §5).

## What stays open (overturn paths, not wired here)

- **P4-014 construction half:** elron.ee direction PDFs + teated stay
  the human-readable buyer checks; the Rail Baltica slices
  (dims_p4_rb dim_ehitusfaas_rb / dim_koridor_reserv_rb, #410) stay
  the scored cousins for the same param. An Elron machine timetable
  vintage would graduate only the Elron leg here.
- **P4-032 ridership half:** kohapealne õhtune vaatlus stays the
  check — and even an open count must stay a usage-not-safety proxy
  (PPA/Päästeamet explicitly NOT a source). The TLT leg stays NULL
  in dims_p4_tlt; the OSM leisure-density proxy stays in
  dims_p4_osm.
- **P4-055 rail-noise half:** elron.ee/raudteeremondid + teated stay
  the checks. The harbour/air slices (Sadam laevagraafik, EANS
  lennuinfo, Männiku laskmisteated) belong to future source issues.
- **P4-061 fringe half:** elron.ee teated stay the human-readable
  buyer check; the Peatus GTFS prev-vs-cur diff (dims_p4_peatus
  dim_bus_cut) stays the scored machine cousin for the same param.
  An Elron machine vintage would graduate only the Elron leg.
- **Full overturn:** Elron (or andmed.eesti.ee / Peatus.ee) publishes
  a machine timetable/change feed for any slice → re-open #284,
  build the polite cached ingestion (daily TTL per parameters3.md
  §5.12 cadence), and graduate that dim to a per-station band /
  calendar.

## Why demo + coverage share one PR

The coverage body (#358) states it extends the demoed ingestion
(#284). With the demo verdict dated-negative there is no ingestion
to extend, so the three coverage slices (P4-032, P4-055, P4-061)
land in the same verdict module instead of a second file importing
a pipeline that does not exist. One module, one test file, one
verdict note — no edits to shared files (same precedent as TLT
#277+#351 and RB #281+#355).
