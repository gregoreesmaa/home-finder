# P4 citynotices: tallinn.ee verdict note (issues #283 + #357)

Demo (#283) implements the tallinn.ee operational-notices ingestion +
P4-014 end-to-end; coverage (#357) wires P4-018 off the same source.
One PR closes both because the #357 body states it extends the demo
ingestion with "no new plumbing expected" — the snow dim reuses
`fetch_cached` plus the buffer/expiry shapes, reading its own POI
kind. No second source is pulled.

## Openness verdict (2026-09-13, 9 single GETs, custom UA, /tmp cache)

| Probe | Result |
|---|---|
| `https://www.tallinn.ee/` | 301 → `/et`; final HTTP 200 HTML 137 KB (Cloudflare + CMS) |
| `/et/teenused-ja-teave/transport-liiklus` | HTTP 200 HTML 124 KB; service overview, links `/et/lumi` + news listing |
| `/et/uudised?news_heading=7465` | **OPEN, keyless**: HTTP 200 HTML 146 KB, server-rendered weekly slugs (`eelinfo-14-20-september` … back to `13-19-juuli`) |
| `/et/uudis/eelinfo-14-20-september` | **OPEN, keyless**: HTTP 200 HTML 135 KB, dated weekday blocks ("Teisipäev, 15. september 9.00 …") |
| `/et/lumi` | **OPEN, keyless**: HTTP 200 HTML 57 KB, "Tallinna tänavate talihooldus 2025/2026" + `https://gis.tallinn.ee/lumekaart/` |
| `/avaandmed/` | **Dated negative**: HTTP 200 HTML 75 KB but a "Teabevärav" JS shell — no server-rendered datasets |
| `https://gis.tallinn.ee/veebikaart/` | **Dated negative**: HTTP 200 HTML ~5 KB ArcGIS Web AppBuilder shell (`jimu-core/init.js`) |
| `https://gis.tallinn.ee/lumekaart/` | **Dated negative**: HTTP 200 HTML ~5 KB app shell, 13 arcgis/rest markers in config — no keyless service URL confirmed without config-chasing (out of polite budget) |
| Prior art reused, not re-probed | `opendata.tallinn.ee` NXDOMAIN (TLT module); Tark Tee feeds key-gated (trans module) |

Raw probe files: `/tmp/hf-p4-citynotices/` (one-off PR record, not committed).
Pull contract: notice index refresh weekly (`NOTICES_TTL_S = 7 d`,
eelinfo cadence); snow page monthly (`SNOW_TTL_S = 30 d`, autumn
refresh per P4-018); cache hit within TTL makes NO request; single
GET, no retries — HTTP 429/errors are a stop signal. Transport errors
and short bodies are never cached as data.

HONESTY LIMIT (do not misquote): the observed eelinfo items are
district-elder **event agendas**, not closure notices — the readers
parse the dated-listing structure and never claim an agenda item is a
closure. Works/snow semantics arrive only via explicitly dated
entries. Geocode gap: notices name streets, never coordinates —
readers keep raw labels + ISO dates; ADS/Maa-amet geocoding to WGS84
is an explicit first-pull step. Fixtures carry WGS84 directly.

## Honest shapes per param (calendar dims with expiry, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-014 construction phase | `constr_phase` | ≤ 500 m | flat 45 while a dated entry is in effect (reason prints count, nearest, `kehtib kuni`) | no join / all expired (`aegunud`) / future-only (`algavad <date>`, no premium faked) / dateless |
| P4-018 snow notices | `snow_notices` | ≤ 500 m | flat 45 while a clearing-op notice is in effect | no join (unknown, never "trap") / expired (`hooaeg lõppenud`) / future-only / dateless |

No gradients anywhere: distance gates the join only. Every scored
reason says `hinnang` with components; every NULL reason says `EI OLE`
and names the missing input. `today` is an optional third scorer arg
(default `date.today()`) so expiry is hermetic in tests.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #357 defines coverage as extending the
   demo ingestion — nothing here needs a second source.
2. Per-source slices, not full params: P4-014 keeps the RB Rail /
   tram-timetable, EHR-corridor and Elron slices for their owners;
   P4-018 keeps the trans road-class band and the OSM + TLT NULLs.
   Distinct dim keys so the central hook can weight slices
   independently.
3. A snow-clearing notice scores as temporary exposure (45), not
   network membership: clearing ops restrict parking ("teisalda
   auto"), so the notice states nuisance, never coverage.
4. Future-dated entries stay NULL with their start date: scoring a
   plan as "premium later" would fake the premium half of the Buy Q.
5. No Overpass fragment staged: positions arrive via the geocoded
   notice join, not snapshot tags — stated, not omitted.
6. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   nomap.md, parameters4.md untouched): 3 new files only. Geocoding +
   central hook (POI kinds + WEIGHTS rebalance) stay one joint change
   across all batches.

## First-full-pull / reopening checklist

1. Weekly pull of the notice index into the cache dir; parse dated
   entries; geocode street labels via ADS/Maa-amet (count + report
   ungeocodable, never fake); drop dateless entries from POIs.
2. Re-probe lumekaart service config for a keyless feature layer;
   paste fresh evidence. Add the explicitly-flagged live integration
   test on that reopen PR (not a unit run).
3. Recalibrate the flat 45s from real notice histograms (works kinds,
   op durations) once rows exist.
