# P4 GTFS stop overlay: peatus/Elron/TLT stops as points (issue #483)

Group A layer issue. AC: stops as a POINT overlay only (no frequency
kernel, no walk raster); evening-ridership NULLs stay NULL with EI OLE
reasons.

## Feed honesty (verified 2026-09-13 against real files)

The issue body's "feeds verified open" overstates — checked per
AGENTS.md §7.1, the honest shape is mixed:

| Leg | Verdict | Evidence |
|---|---|---|
| TLT city (buss/tramm/troll) | OPEN as a snapshot vintage | `gtfs/tallinn-gtfs-2026-09-11.zip` in the 2026-09-12 snapshot (agency Tallinn / transport.tallinn.ee): 1120 stops, 80 routes (69 bus + 6 tram + 5 troll), 20 081 trips, 483 986 stop_times. Positions, modes and scheduled departures measured from it |
| Peatus.ee national GTFS | CLOSED live (dated negative) | `https://peatus.ee/gtfs/gtfs.zip` 302s to a "Rakendus on suletud" page (see `dims_p4_peatus.py`). Regional stops outside the city vintage are NOT plotted |
| Elron rail | NO machine feed (dated negative) | Direction PDFs + human news only (see `dims_p4_elron.py`). 112 stations/halts ride the overlay as MAPPED-ONLY OSM points (railway=station/stop), no frequencies |
| Evening RIDERSHIP (P4-032) | Unpublished everywhere | GTFS static has scheduled departures, never occupancy. Overlay shows schedules; `dim_elron_evening_ridership` + `dim_tlt_evening_ridership` stay None + EI OLE (pinned by `test_dims_p4_gtfsstops.py`) |

Cross-checks that raise confidence: Wednesday deps/stop re-measures
median 138 / p10 42 / max 974 — exactly the group-12 anchor quoted in
`dims_p4_peatus.py` (same vintage, independent reader). Mode split:
buss 941 / tramm 81 / troll 8 / mitu 89 / modeless 1 (Sinilille
00902-2: in stops.txt, zero trips in the vintage — plotted without `t`,
unknown service, never 0).

## What ships

* `services/scoring/dims_p4_gtfsstops.py` — pure offline derivation
  (single source; no network calls by source-inspection test).
* `scripts/build/batch_gtfs_stops.py` — offline builder writing
  `osm/derived-gtfsstops.json` (1232 bare LayerPoint dicts: GTFS
  {lon,lat,t} + Elron {lon,lat,tags}).
* `apps/web/lib/layers_gtfsstops.ts` — layer `gtfsstops` (p15, shared
  with transit per the fiber/mobile p51 precedent): trips spec
  {half 1500, modeBonus 10, minModes 2} (transit parity — half reads
  Balti jaam 57 / Raekoja 70 / Õismäe 42 / Viimsi 6 / rural unknown).
  NO walk raster / metro master built (overlay-only): absent files
  degrade to the Euclidean fallback splat, labeled "euclidiline varu".
  Markers stride-sampled (every stop equal), sized by scheduled
  Wednesday departures, Elron stations at weight 1 (unknown, never 0).
* Difference vs the transit layer: measured-only point set (no
  default-100 fills), so beyond-vintage reads honestly unknown instead
  of mid-ramp; GTFS points are classless by honesty (no invented OSM
  tags), so the mode kicker fires only via Elron rail tags.

## Judgment calls (for the reviewer)

1. New layer id instead of enriching transit: the transit heat bakes
   default-100 fills county-wide ("unknown, not bad" design) — mixing a
   measured-only set into it would corrupt p15's contract. Separate id,
   shared paramId, documented.
2. Half 1500 copied from transit, not recalibrated: same vintage, same
   scheduled-departures semantics; the builder printout re-verifies the
   ramp on the new point set (above) instead of hiding the reuse.
3. OSM `railway=stop` counted as Elron halts (94) alongside `station`
   (18): spot-checked against Ülemiste/Maardu coordinates; tram_stop /
   platform / technical_station excluded (GTFS leg owns trams/buses).
4. Evening/Saturday window counts are computed by the builder and
   printed for the record but NOT shipped on the wire (LayerPoint has
   no such fields; scorers read their own GTFS windows at score time).

## Reopening checklist (when feeds change)

* peatus.ee serves a zip again → extend the GTFS leg beyond the city
  vintage (see `docs/p4_peatus.md` checklist), recalibrate half.
* Elron publishes a machine timetable → join frequencies, add `t` to
  rail points, drop "mapped-only" from title/source/legend.
* Real occupancy/ridership appears → NEW param work; never backfill
  ridership from departures (a schedule is not a passenger count).
