# P4 sadam verdict note — Tallinna Sadam (P4-033 + 3 slices)

> Dated-negative verdict for issues #298 (demo) and #368 (coverage).
> Checked 2026-09-13. All four params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_sadam.py`, pinned by
> `services/scoring/tests/test_dims_p4_sadam.py`.

## Verdict

**No open machine feed — all four dims stay NULL with Estonian reasons.**
The cruise/ship timetable, the cruise-season pages, and the harbour
noise/odour notices live on human-readable ts.ee pages (filter-form
HTML tables, cruise marketing pages, the /uudised/ newsroom). There is
no public bulk feed to poll politely, so there is no ingestion to
cache, no TTL to state beyond this one-off check (re-probe each spring
before the cruise season), and no honest calendar band, zone join, or
sector to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

4 tiny requests total (four single GETs, 2 s pacing, `--max-time 25`,
labelled one-off user-agent `home-finder sadam openness-check (one-off,
few pages max, no scrape)`, headers + visible-text keyword scope read
only). Raw bodies: `/tmp/hf-p4-sadam/` (one-off PR record, not
committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.ts.ee/` → HTTP 200 (~137 KB, cloudflare) | Human storefront (~11.4k visible chars); sweep 0 for csv / geojson / wfs / api / masinloetav / andmestik / avaandmed; links /laevad-sadamas/, /kruiisid/, /uudised/ | Entry points confirmed, nothing machine-readable advertised |
| `https://www.ts.ee/laevad-sadamas/` → HTTP 200 (~158 KB) | Human ship timetable: server-rendered filter form ("Saabumise kuupäev alates/kuni", "Saabumise sadam", "Laeva nimi") + live rows (SPIRIT OF DISCOVERY, 13.09.2026, kai 27, Stockholm→Helsinki); page-source scope has no JSON/CSV/API endpoint (only a Maps key + theme ajax) | Timetable exists as filter-form HTML, never a pollable feed — no calendar band is painted from it |
| `https://www.ts.ee/kruiisid/` → HTTP 200 (~233 KB) | Human cruise page (26x "kruiisilaev", 105x "saabum", 27x "kai"); 0 for csv / geojson / wfs / api / masinloetav / andmestik | Season info is marketing HTML, not a cruise-day dataset |
| `https://andmed.eesti.ee/dataset?q=sadam` → HTTP 200 (~75 KB) | 12 visible characters ("Teabevärav" JS shell) | No trivially pollable national-portal sadam dataset (same shell as #264/#277/#284) |

Judgment call: the check stopped at storefront/page/shell level on
purpose — no filter-form replay, no newsroom crawling, no timetable
HTML scraping. Replaying the form would be exactly the human-page
harvesting this repo refuses (AGENTS.md §5).

## Honest shapes per param (all NULL until a feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-033 nuisance calendar (demo) | `sadam_cruise_calendar` | calendar dims with dates, never gradient (cruise days/yr off the schedule) | ts.ee/laevad-sadamas/ + /kruiisid/ timetables; Lauluväljak/Pirita + Kaitseväe calendars; hunting leg in dims_p4_kesk |
| P4-023 noise zones | `sadam_noise_notices` | zone join, never walk-gradient (harbour notice sector as zone label) | on-site listen at the Vanasadam/Pirita edge; flight/exercise zones in dims_p4_trans + dims_p4_kaur; insulation in dims_p4_ehr |
| P4-053 odour roses | `sadam_odour_sector` | sector + calendar, never circle buffer (harbour-odour cross-check) | downwind on-site walk; wind leg in dims_p4_ilm; sector days in dims_p4_kaur; emitters in dims_p4_eelis; complaints in dims_p4_komun |
| P4-055 timetable nuisances | `sadam_timetable` | calendar dims (foghorn/icebreaker season off the schedule) | fog/ice-season on-site listen; rail night-windows in dims_p4_elron; complaint validation in dims_p4_komun |

Never 0 and never 100 would apply once scored (absence is not proof of
calm or disaster); today every reason says `EI OLE` and points at the
concrete check above. Every scored-future reason must trace to a joined
record.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #368 defines coverage as extending the
   demoed ingestion — with a dated-negative demo there is no ingestion
   to extend, so all three coverage slices land in the same verdict
   module (komun #290+#363, TLT #277+#351, elektrilevi #264+#344,
   Elron #284+#358 precedent).
2. Pairing rationale: every param names Tallinna Sadam in its
   parameters4.md source list — P4-033 source (1) cruise schedule, P4-023
   source (4) ship/heli noise notices, P4-053 source (6) harbour-odour
   notices, P4-055 source (1) harbour schedule — so there is no weak
   link; each dim is the Sadam leg and names the cousin slices that own
   the other legs.
3. Complements, not duplicates: the P4-055 reason names the Elron
   night-maintenance NULL (dims_p4_elron) and the komun complaint
   validation (dims_p4_komun); P4-023 names the trans zone band, the
   KAUR rattle leg, and the EHR insulation NULL; P4-053 names the ilm
   rose, KAUR sector days, EELIS emitters, and komun complaints; P4-033
   names the kesk hunting leg. Distinct dim keys throughout.
4. The live timetable rows observed (SPIRIT OF DISCOVERY today) prove
   the harbour is active, not that it is open: activity is not a feed.
5. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all batches.

## Reopening checklist (when a pollable feed appears)

1. Re-run the four probes above each spring (cruise-season TTL:
   spring, before the May season); paste fresh evidence in the reopen
   PR.
2. If ts.ee (or andmed.eesti.ee) exposes a pollable schedule (CSV/JSON
   arrival-departure feed), transcribe one week of cruise days into the
   cache dir and run it through a `parse_sadam_schedule` + calendar
   join on fixtures first.
3. Graduate dims to bands ONLY from joined records (calendar per the
   table above; zone join for P4-023; sector + calendar for P4-053);
   keep NULL-with-Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
