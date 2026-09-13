# P4 kvagi: Kaitsevägi training-area open data (issues #297 + #367)

Demo (#297) implements the Kaitsevägi (Brontos) training-area ingestion +
P4-023 end-to-end; coverage (#367) wires P4-033 and P4-055 off the same
source family. One PR closes both because the #367 body states it extends
the demo ingestion with "no new plumbing expected" — the seasonal calendar
and the Männiku weekend calendar read the same cached Brontos snapshots as
the P4-023 zone join, each dim reading its own filter. No second source is
pulled. Scorers live in `services/scoring/dims_p4_kvagi.py`, pinned by
`services/scoring/tests/test_dims_p4_kvagi.py`.

## Openness verdict (2026-09-13, 8 tiny requests, custom UA, /tmp cache)

**CONFIRMED OPEN**: machine-readable Brontos snapshots under CC 3.0 BY-SA.
Single GETs with `home-finder kvagi openness-check #297 (one-off, single
GETs, file cache for PR record; contact via GitHub home-finder)`, paced
≥ 5 s, no retries. Raw bodies: `/tmp/hf-kvagi-probe/` (one-off PR record,
not committed; synthetic fixtures in tests, never the live dump).

| Feed | Probe | Result |
|---|---|---|
| Kaitsevägi front (`mil.ee`) | single GET | **Storefront**: HTTP 200, 201 348 B; visible-text sweep 0 for laskmine/laskmisteated/Männiku/teated/avaandmed/API/csv/geojson/wfs/müra — links on to the area/exercise/news pages |
| Training areas (`/kaitsevagi/harjutusvaljad/`) | single GET | **Human guide**: HTTP 200, 1 151 541 B; Männiku x19, laskmine x31, müra x33, Tapa/Sirgala/Soodla named; 0 for machine formats — links to the safety page, the open-data page, PDF maps, one ArcGIS viewer (shell, not followed) |
| Exercises (`/kaitsevagi/oppused/`) | single GET | **Thin overview**: HTTP 200, 147 089 B, no dated calendar at page level; subpages are human pages (not followed) |
| News RSS (`/feed/`) | single GET | **Headlines only**: HTTP 200, 7 327 B, 10 items with pubDate, zero geo/category exercise metadata — never a calendar feed |
| Safety notice (`.../harjutusvaljad/teadmiseks/`) | single GET | **Human page**: HTTP 200, 129 957 B ("Teadmiseks kohalikule elanikule…"), 0 for machine formats — buyer-side reading |
| Open-data page (`.../valjaoppealade-avaandmed/`) | single GET | **CONFIRMED**: HTTP 200; declares machine-readable Brontos open data under CC 3.0 BY-SA — schedule rows appear ~1 week ahead, change live, running month deleted next month; files stated as 129.69 KB + 567.99 KB JSON |
| Schedule JSON (`training_ground_schedule.json`) | single GET | **CONFIRMED**: HTTP 200, 132 800 B; 68 area-month rows, 10 current-month (2026-09) rows with 475 dated exercises (Männiku 54 incl. Sat 2026-09-19 SHOOTING; Soodla 9; Sirgala 49; Keskpolügoon 144); ISO UTC slices, TACTICS/SHOOTING/BLASTING × LOW/AVERAGE/HIGH/VERY_HIGH/ABSENT |
| Map JSON (`training_ground_mapdata.json`) | single GET | **CONFIRMED**: HTTP 200, 581 619 B; 38 areas with EPSG:3857 polygons + coded training objects + area contact points; Männiku bbox-centroid inverts to ~59.34/24.73 (Nõmme edge — projection math checks out) |

Pull contract: schedule refresh daily max (`SCHEDULE_TTL_S = 1 d` — rows
appear ~1 week ahead and change live); mapdata quarterly
(`MAPDATA_TTL_S = 90 d` — polygons/contacts stable). Cache hit within TTL
makes NO request; single GET, no retries — HTTP 429/errors are a stop
signal. Transport errors and short bodies are never cached as data.

## Honest shapes per param (checklist / bands, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-023 exercise leg (demo) | `exercise_noise_zone` | ≤ 3 km audibility gate (membership, never gradient) | flat 50 while a dated, sound-carrying entry for a Tallinn-audible area is day-active (mirrors the EANS/trans õppus band) | no join; expired / future / dateless; ABSENT-silent or unknown noise; non-audible area (unknown or silent, never quiet) |
| P4-033 exercise weeks | `exercise_season_calendar` | ≤ 3 km gate | flat 45 while a dated entry is active; reason prints week dates (the "millal vali" answer) | same staleness/silence rule |
| P4-055 Männiku weekend pops | `manniku_weekend_calendar` | ≤ 3 km gate, Männiku + Sat/Sun overlap | flat 45 while a weekend-overlapping Männiku entry is active | weekday-only / stale / silent / non-Männiku entry |

Day grain: sub-day Brontos slices collapse to [start_day, end_day];
impact starts on the start day. ABSENT-noise entries (silent tactics
without blank ammo, per the published MÜRATASEMED legend) can never
score. Every scored reason says `hinnang` with components; every NULL
reason says `EI OLE` and names the missing input. Upstream (one joint
change): offline polygon step emits `exercisenoise_kvagi` POIs
`{area, start, end, noise, kind, lat, lon}` + livability kind splice +
WEIGHTS rebalance.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #367 defines coverage as extending the
   demo ingestion — nothing here needs a second source.
2. Per-source slices, not full params: P4-023 keeps the EANS
   approach-corridor leg (`dims_p4_eans`, branch `296-p4-eans`,
   unmerged at time of writing), the EHR insulation NULL, the KAUR
   rattle leg and the trans END band; P4-033 keeps the Sadam / cultural
   / bells / hunting / snow-dump legs for future source issues; P4-055
   keeps the Sadam + EANS legs (`dims_p4_eans`) and the Elron ööaknad
   NULL. Distinct dim keys + disjoint POI kind (`exercisenoise_kvagi`
   vs `schednuisance_eans`) so the hook weights slices independently.
   P4-023/P4-033 may fire together on one Männiku week (different buyer
   questions — insulation hit vs when-loud — same accepted overlap as
   the EANS zone+calendar pair).
3. Tallinn-audible set = Männiku + Soodla + Sirgala + Keskpolügoon:
   exactly the areas parameters4.md names (P4-023 source 3, P4-055
   source 3; Keskpolügoon = the Tapa central polygon). No
   distance-modelled audibility — far polygons simply never gate a
   Tallinn origin (never a gradient).
4. Uniform 3 km gate (heavy-weapons audibility; VERY_HIGH = artillery
   per the legend) + mirrored scores (50 = õppus band, 45 = calendar
   exposure): values encode exposure severity, hook rebalances anyway.
5. No shared-file edits (livability.py, WEIGHTS, layers, parameters4.md
   untouched): 3 new files only. CC BY-SA honoured by source links
   here; no dump committed (synthetic fixtures only).

## First-full-pull / reopening checklist

1. Seed the cache once (`fetch_cached` both URLs, daily cron), run the
   offline polygon step (EPSG:3857 → WGS84 anchors via
   `mercator_to_wgs84` + `parse_mapdata`) and emit
   `exercisenoise_kvagi` POIs for the audible set.
2. Re-verify the eight probe rows; if the JSON layout drifts, update
   the readers on fixtures first (unknown tokens stay NULL, never
   guessed).
3. Recalibrate the 3 km gate and the 50/45 bands from real histograms.
4. Add the explicitly-flagged live integration test on that reopen PR
   (not a unit run).
