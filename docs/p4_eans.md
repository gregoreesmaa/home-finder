# P4 EANS: Tallinn noise-zone verdict note (issues #296 + #366)

Demo (#296) implements the EANS Tallinn noise-zone ingestion + P4-023
end-to-end; coverage (#366) wires P4-055 off the same source family.
One PR closes both because the #366 body states it extends the demo
ingestion with "no new plumbing expected" — the harbour/air calendar
reads the same cached snapshot family (Ämari-rattle corridors are the
same approach-corridor geography as the P4-023 zones; Sadam/Männiku
notices share the fetch + TTL + expiry shapes), each dim reading its
own POI kind. No second source is pulled.

## Openness verdict (2026-09-13, 10 tiny requests, custom UA, /tmp cache)

| Feed | Probe | Result |
|---|---|---|
| EANS public site (`eans.ee` == `www.eans.ee`) | single GET | **Dated negative**: HTTP 200, 569 681 B corporate site; visible-text sweep 0 for müra/noise/avaandmed/open data/API/kaart/tsoon, zero matching hrefs — no keyless zone feed |
| National-portal machine search | single GET each | **Dated negative**: new-style `/api/datasets?query=` → HTTP 400 "property query should not exist"; CKAN `/api/3/action/package_search` → HTTP 404 "Cannot GET" (corroborates kudocs #261 + EHR #249: no CKAN API) |
| Port of Tallinn (`ts.ee`) | single GET | **Dated negative as machine feed**: HTTP 200, 137 469 B; human schedule pages exist (`/saabuvad-liinireisid/`, `/laevad-sadamas/`) but sweep 0 for avaandmed/open data/API/GTFS/müra/noise |
| Kaitsevägi (`mil.ee`) | single GET | **Dated negative**: HTTP 200, 201 348 B; front-page sweep 0 for laskmine/laskmisteated/Männiku/teated/avaandmed/API — Männiku notices are human news, never a calendar feed |
| Transpordiamet noise topic (`/mura-ja-valisohk`) | single GET | **Confirmed lead, viewer only**: HTTP 200, 214 053 B; names the X-GIS mürakaart viewer, zero shp/geojson/WFS/download/avaandmed links |
| Maa-amet X-GIS mürakaart app | single GET | **Viewer only**: HTTP 200 but a 1 243 B JS bootstrap shell ("X-GIS 2.0 [myrakaart]", 21 visible chars, zero service/download links) — same shell precedent as lumekaart/veebikaart (#283) |

Raw probe files: `/tmp/hf-p4-eans/` (one-off PR record, not committed).
Pull contract: zones refresh quarterly (`ZONES_TTL_S = 90 d`, END 5-year
cycle / rare EANS procedure changes); harbour/air notices weekly
(`NOTICES_TTL_S = 7 d`, sailing/firing turnover). Cache hit within TTL
makes NO request; single GET, no retries — HTTP 429/errors are a stop
signal. Transport errors and short bodies are never cached as data.

## Honest shapes per param (checklist / bands, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-023 airport/military noise (EANS leg) | `airport_noise_eans` | ≤ 1000 m (join gate only) | label only, never gradient: lennumüra→35, õppus→50, sadam→60 (mirrors the trans END band on purpose) | outside mapped zones (unknown, not quiet); unknown label |
| P4-055 harbour/air timetables (notice leg) | `harbour_air_calendar` | ≤ 2000 m (propagation gate, never gradient) | flat 45 while a dated notice is in effect (udusignaal/jäämurre/ämari/männiku) | expired / future-dated / dateless entry; no join (unknown, never quiet) |

Measured zero vs missing join: notices are dated events, not exhaustive
calendars, and zones are mapped polygons — an empty buffer is unknown,
never "quiet" or "calm". Every scored reason says `hinnang` with
components; every NULL reason says `EI OLE` and names the missing input.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #366 defines coverage as extending the
   demo ingestion — nothing here needs a second source.
2. Per-source slices, not full params: P4-023 keeps the EHR
   insulation-requirement NULL (`dims_p4_ehr`), the KAUR Ämari-rattle
   leg (`dims_p4_kaur`) and the trans END band (`dims_p4_trans`); P4-055
   keeps the Elron ööaknad NULL (`dims_p4_elron`). Distinct dim keys so
   the central hook can weight slices independently.
3. Zone band mirrors trans on purpose (values encode exposure severity;
   the hook rebalances anyway); POI kind + reason keep slices distinct.
4. 2 km calendar gate: propagation gate for water-/air-carried sound
   (foghorns across the bay, Ämari corridors over North Tallinn) —
   flat score, never a gradient.
5. No Overpass fragment staged: positions arrive via the zone/notice
   join, not snapshot tags — stated, not omitted.
6. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   nomap.md, parameters4.md untouched): 3 new files only. Polygon join
   upstream + central hook (POI kinds + WEIGHTS rebalance) stay one
   joint change across all batches.

## First-full-pull / reopening checklist

1. Confirm a keyless zone polygon source (EANS procedure annex, END
   download, or X-GIS service URL if one is published); do point-in-
   polygon offline and emit `noisezone_eans` POIs (zone ∈ lennumüra /
   sadam / õppus).
2. Geocode Sadam/EANS/Männiku notice areas (ADS/Maa-amet step) into
   `schednuisance_eans` POIs with ISO start/end.
3. Recalibrate `NOISE_ZONE_SCORES` / `NUISANCE_ACTIVE_SCORE` and the
   2 km gate from real histograms; re-probe all six verdict rows and
   paste fresh evidence. Add the explicitly-flagged live integration
   test on that reopen PR (not a unit run).
