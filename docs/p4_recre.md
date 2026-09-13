# P4 recre verdict note — Tallinna recreation & allotments without a machine feed (P4-048)

> Dated-negative verdict for issue #312 (single-param demo, no
> coverage issue — the issue states 0 remaining params use this
> source, so no follow-up coverage issue exists).
> Checked 2026-09-13. Both params slices are documented no-map NULL
> dims (OTA PR #131 precedent); the scorers live in
> `services/scoring/dims_p4_recre.py`, pinned by
> `services/scoring/tests/test_dims_p4_recre.py`.

## Verdict

**No verified pollable recreation-facility table/timetable or
allotment-queue publication — both dims stay NULL with an Estonian
reason.** Tallinn publishes human directory pages (sport landing,
venue pages, pool timetable/ticket pages) and human search results —
not a machine-readable facility table. RMK's front page advertises
no bulk or visitor feed at landing level. The Lillepi search yields
a park maintenance plan (*Lillepi pargi hoolduskava*), not an
allotment queue, and the aiandusühistu search yields no queue table
at all. There is no polite facility/queue feed to cache, no TTL to
state beyond this one-off check (re-probe yearly, or sooner if the
city, RMK, or an aiandusühistu publishes a machine-readable
table), and no honest <15 min join or queue table to paint without
one — a single hand-read directory page says nothing about the
listing's daily joy.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

10 served requests total (single GETs, labelled one-off user-agent
`home-finder openness probe #312 (one-off, single GETs; contact via
GitHub home-finder)`, 25 s timeout, no retries, 2 s pacing; the two
RMK 301s followed once each to their canonical host; headers +
visible-text keyword scope read only; no form driving, no subsite
enumeration, no JS-app driving). Raw bodies:
`/tmp/hf-recre-probe/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.rmk.ee/` → HTTP 301 (empty body) to `https://rmk.ee/` | Canonical redirect, followed once | Working host confirmed on the canonical domain |
| `https://rmk.ee/` → HTTP 200, 118162 bytes, ~6.4k visible chars, title "Riigimetsa Majandamise Keskus (RMK)" | "rmk" 20x only; 0x csv/geojson/wfs/wms/masinloetav/andmestik/avaandmed/api | No bulk/visitor-feed pointer at landing level |
| `https://rmk.ee/kulastajale` → HTTP 404, 85616 bytes, title "Page not found » … (RMK)" | Stale URL guess, tried once | No visitor-info bulk at the guessed path |
| `https://www.tallinn.ee/et/sport` → HTTP 200, 61085 bytes, ~2.8k visible chars, title "Sport \| Tallinn" | Human directory ("Spordisaalid ja -hallid", "Ujulad ja veespordikeskused", "Linna spordibaasid", Kultuuri- ja Spordiamet contacts); ujula 2x + spordikeskus 2x = directory prose | Directory, not a dataset |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=ujula` → HTTP 200, 145941 bytes, server-rendered | 25x ujula + 2x tunniplaan + 7x pilet = human pool/timetable/ticket pages; 0x csv/geojson/wfs/masinloetav/andmestik/järjekord | Timetables exist as human pages — no machine table to poll |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=aiandusühistu` → HTTP 200, 143710 bytes, server-rendered | Only 1x aiandusühistu; 0x järjekord/csv/geojson/wfs | No association queue table published |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=Lillepi` → HTTP 200, 146307 bytes, server-rendered | 6x Lillepi = *Lillepi pargi hoolduskava* (park maintenance plan) + Pirita sport pages (19x pirita); 0x järjekord/csv/geojson/wfs | Lillepi hits are maintenance/sport content, not a queue |
| `https://andmed.eesti.ee/dataset?q=spordirajatis` → HTTP 200, 75497 bytes, 10 visible chars, title "Teabevärav" | JS app shell, zero keyword hits | No trivially pollable national-portal recreation dataset (same shell as #264/#277/#284/#290/#299) |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=spordikeskus` → HTTP 200, 145433 bytes, server-rendered | 25x spordikeskus = human venue pages (Pirita/Pae/Härma/Nõmme/Sõle/Tallinna Spordikeskus); 0x csv/geojson/wfs/masinloetav | Venue pages, not a facility feed |

Judgment call: the check stopped at landing/search/shell level on
purpose — no RMK subsite enumeration, no tallinn.ee venue-page
scraping, no Teabevärav JS-app driving, no allotment-association
queue scraping (AGENTS.md §5; tervise #289 precedent). Driving
query UIs venue-by-venue would be scraping human publications, not
polling a feed.

## Honest shapes (NULL until a pollable feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-048 recreation, facility slice (demo) | `recre_facility_15min` | <15 min facility-table join off operator-published timetables/tables (pool tunniplaan, venue lahtiolekuajad, RMK visitor info — never 0/100 on this leg alone; a timetable hints at access, never a guarantee) | 15-minuti prooviring kaardilt + tunniplaani/piletiinfo kontroll; scored cousins: kaugus dims_group11 (dim_rec_special) + ligipääs dims_p4_peatus / dims_p4_tlt |
| P4-048 recreation, queue slice (demo) | `recre_allotment_queue` | annual association-published queue table (Lillepi/Pelgu, queues = true demand) | küsi aiandusühistult järjekorra pikkust; agreeing NULLs: linna-register dims_p4_green (dim_allotment_queue) + OSM dims_p4_osm (dim_delights) |

Every scored-future reason must trace to a joined facility/queue
record; a single hand-read directory page must never score a
listing.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: #312 states the remaining
   0 params using this source need only a follow-up created after
   this demo — with a dated-negative demo there is no ingestion to
   extend, so two dims in one module are the whole honest scope.
2. Same-param split with dims_p4_green (P4-024 pria/kaur/eelis/
   tervise/komun precedent): green owns the kava-isochrone, bench-
   register, and city-register queue legs off the green-inventory
   source family (#300); recre owns the operator-timetable and
   association-publication legs off the recreation source family
   (this issue). Different source artifacts, distinct dim keys, no
   double-scoring — each module names the other.
3. Scored P4-048 legs stay where they live and are named, never
   re-scored: p101 snapshot proximity (dims_group11
   dim_rec_special), EHR breakfast-sun (dims_p4_ehr
   dim_small_delights), <15 min access halves (dims_p4_peatus
   dim_delights_access, dims_p4_tlt dim_tlt_delight_access).
4. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across
   all batches.

## Reopening checklist (when a pollable feed appears)

1. Re-run the ten probes above yearly (or sooner if the city, RMK,
   or an aiandusühistu publishes a machine-readable table); paste
   fresh evidence.
2. If a server-rendered CSV/GeoJSON/WFS facility table or queue
   table appears: build the polite cached ingestion (TTL from the
   publisher's stated cadence, else annual for queue tables) and
   graduate the matching dim to the honest shape above — fixtures
   first, recalibrated bands from a real Tallinn pull.
3. If timetables/queues stay human-pages-only: keep the NULLs —
   directory scraping stays out of the repo.
