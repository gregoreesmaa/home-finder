# P4 EHIS / HaridusSilm verdict note (issues #271 demo + #347 coverage)

Date: 2026-09-13. Scope: P4-011 (demo) plus the 1 coverage param in
#347 (P4-044), both consuming one EHIS / HaridusSilm per-linnaosa
snapshot table (`services/scoring/dims_p4_ehis.py`). Sibling legs
(Haridusamet queue #270, Tervisekassa perearst, REL2021 occupation
grid, OSM culture, arireg employers, tehingud front) are separate
pipelines — untouched.

## Openness verdict: OPEN-partial (dated negative on capacity bulk)

Five polite requests total (custom UA, short timeouts, no scraping,
no auth attempts; bodies to /tmp/hf-ehis only):

```
GET https://www.haridussilm.ee/            -> 301 to haridussilm.ee; HTTP 200 (41 186 B)
GET https://ehis.ee/                       -> https://www.ehis.ee/; HTTP 200 (7 815 B)
GET https://enda.ehis.ee/avalik/           -> HTTP 200 (436 B)
GET https://haridusportaal.edu.ee/kool/kaart -> HTTP 200 (66 834 B)
HEAD .../gituja.../koolide_kontaktid.xls   -> HTTP 200 (application/octet-stream)
```

haridussilm.ee ("Haridusandmete portaal") is a JS SPA shell — title
only, no server-rendered data, no bulk href. enda.ehis.ee/avalik
(the public view) is a 436-byte "Loading..." shell; no anonymous
bulk endpoint probed (polite stop). The Koolide kaart school map is
a JS SPA shell (66 KB, title only) — needs JS, no bulk href. The
EENet file-store extracts (koolide_kontaktid.xls, oppekavad.xlsx)
ARE anonymously fetchable, but they carry contacts/curricula, NOT
per-linnaosa capacity — so no per-linnaosa capacity bulk is
verified (dated negative keeps this verdict).

Consequence, kept honestly in code:

- `fetch_ehis_table` takes an explicit snapshot-pipeline URL with
  `EHIS_TTL_DAYS = 90` (quarterly per parameters4.md P4-011),
  single polite GET, file cache; transport/HTTP errors RAISE and
  are never cached as data; HTTP 429 propagates (stop signal). No
  default bulk URL is wired — inventing one would be fake precision.
- Both dims score ONLY joined rows; with no linnaosa match both
  return NULL with an Estonian reason. No anonymous bulk = no
  backfill = NULLs until a snapshot row is joined.

## Honest shapes per param (bands, NULL stays NULL)

| Param | Dim key | Joined slice | Scored shape | NULL when |
|---|---|---|---|---|
| P4-011 capacity (demo) | `school_pressure` | pupils / pupil_places per linnaosa | <85% → 75; <95% → 60; ≤105% → 45; above → 30 (never 0/100) | row missing / half leg / places ≤ 0 |
| P4-044 herd (coverage) | `artschool_density` | art_music_schools per linnaosa | 0 → 50 (neutral); 1–2 → 60; ≥3 → 70 (taste-match cap) | row missing / slice missing |

Every scored reason says `HaridusSilm/EHIS registriandmed` with the
joined numbers; every NULL reason says `EI OLE` and points at the
concrete check (koolikaart, Haridusamet, Tervisekassa,
ostjaprofiil). Queue length, when the row carries it, is echoed as
a Haridusamet number — scored nowhere here.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #347 defines coverage as extending the
   demoed ingestion ("no new plumbing expected") — P4-044 source (3)
   is the art/music slice of the same per-linnaosa table P4-011
   demos (EHR #249/#333, tvesi #263/#343 precedent).
2. P4-011 vs #270 (Tallinna Haridusamet demo, same param): same
   buyer question, COMPLEMENTARY legs, not a duplicate. This dim
   reads the EHIS capacity leg (utilization); #270 reads the queue
   leg. Bands match deliberately; the JOINED SOURCE named in each
   reason differs. The central hook joins one source per linnaosa
   later — one joint change.
3. P4-044 vs sibling legs (arireg NULL leg, tehingud front, OSM
   culture taste-match): this dim is the art/music-density
   cross-check leg only, capped 50–70, floor deliberate — zero art
   schools is neutral for a taste-match, never bad.
4. No shared-file edits (livability.py, WEIGHTS, parameters4.md
   untouched): 3 new files only. Central hook (enrich join +
   WEIGHTS rebalance) stays one joint change across all batches.

## Reopening checklist (when a capacity bulk appears)

1. Re-run the probes above; paste fresh evidence in the reopen PR.
2. Transcribe one per-linnaosa table into the cache dir; run it
   through `parse_linnaosa_table` + `index_by_linnaosa` on fixtures
   first.
3. Recalibrate the 75/60/45/30 bands against the new school year
   (note õppeaasta in the snapshot).
4. Add the explicitly-flagged live integration test (not a unit run).
