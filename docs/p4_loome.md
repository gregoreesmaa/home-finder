# P4 loome verdict note — Tallinna loomemajandus stats without a machine feed (P4-044)

> Dated-negative verdict for issue #322 (single-param demo, no
> coverage issue — the issue states 0 remaining params use this
> source, so the follow-up coverage issue is created after this
> demo).
> Checked 2026-09-13. The loome-stats slice is a documented no-map
> NULL dim (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_loome.py`, pinned by
> `services/scoring/tests/test_dims_p4_loome.py`.

## Verdict

**No verified pollable per-linnaosa creative-economy table — the
dim stays NULL with an Estonian reason.** Tallinn publishes human
policy/prose pages (Ettevõtlusamet loomemajandus page, uuringud /
statistika directory, city-level ettevõtlusstatistika prose) and
human search results — not a machine-readable per-linnaosa table.
The national portal is a JS app shell with no server-rendered loome
dataset, and the city's open-data API page only points at that
portal. There is no polite loome feed to cache, no TTL to state
beyond this one-off check (re-probe yearly, or sooner if the city
publishes a machine-readable per-linnaosa table), and no honest
grid taste-match join to paint without one — a single hand-read
policy page says nothing about the listing's herd.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

6 served requests total (single GETs, labelled one-off user-agent
`home-finder P4-loome openness probe (one-off, single GETs, no
scrape; contact via GitHub home-finder)`, 25 s timeout, no retries,
2 s pacing; headers + visible-text keyword scope read only; no form
driving, no subsite enumeration, no JS-app driving, no table-name
enumeration). Raw bodies: `/tmp/hf-loome-probe/` (one-off PR
record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=loomemajandus` → HTTP 200, 138369 bytes, ~9.0k visible chars, title "Otsi \| Tallinn" | 3x loomemajandus = policy/prose pages (loomemajandus page, uuringud/statistika directory); 0x csv/geojson/wfs/wms/masinloetav/andmestik/api | Search confirms prose pages only — no dataset pointer |
| `https://andmed.eesti.ee/dataset?q=loomemajandus` → HTTP 200, 75858 bytes, 12 visible chars, title "Teabevärav" | JS app shell, zero keyword hits | No trivially pollable national-portal loome dataset (same shell as #264/#277/#284/#290/#299) |
| `https://www.tallinn.ee/et/avaandmed` → HTTP 200, 1420 bytes, title "Avaandmed API" | "Universal API for Tallinn city open data" pointer page: datasets documented at avaandmed.eesti.ee (the JS shell above) | Real API surface, but no loome table name documented anywhere reachable — guessing names would be enumeration |
| `https://www.tallinn.ee/et/ettevotjale/loomemajandus-tuleviku-ettevotlus` → HTTP 200, 79025 bytes, ~5.4k visible chars, title "Loomemajandus – tuleviku ettevõtlus \| Tallinn" | Ettevõtlusamet policy/prose (8x loomemajandus, 2x loomeettevõt…); 0x linnaosa/csv/xlsx/pdf/geojson/wfs/andmestik/masinloetav/avaandmed/api; 0 file links | Policy page, not a statistics publication — no per-linnaosa cut |
| `https://www.tallinn.ee/et/ettevotjale/uuringud-statistika-turundusmaterjalid` → HTTP 200, 71152 bytes, ~3.9k visible chars | Human study/statistics directory (12x statistika, 8x uuring); 0x loomemajandus/linnaosa/any machine-readable keyword; 0 file links | Directory of human publications, no loome table |
| `https://www.tallinn.ee/et/ettevotlus/tallinna-ettevotlusstatistika` → HTTP 200, 83785 bytes, ~5.6k visible chars, title "Tallinna ettevõtlusstatistika \| Tallinn" | City-level business-stats prose (25x statistika, 1x asum); 0x loomemajandus/loome/linnaosa/csv/xlsx/pdf/andmestik/masinloetav/avaandmed/api; 0 file links | City-level stats prose with no loome slice and no district cut |

Judgment call: the check stopped at search/shell/pointer/policy
level on purpose — no uuringud-register driving, no Teabevärav
JS-app driving, no open-data-API table-name enumeration, no
Ettevõtlusamet subsite scraping (AGENTS.md §5; tervise #289
precedent). Driving query UIs publication-by-publication would be
scraping human pages, not polling a feed.

## Honest shape (NULL until a pollable feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-044 herd, loome-stats slice (demo) | `loome_linnaosa_stats` | per-linnaosa join → grid taste-match under the same contract as the ehis P4-044 slice (capped, neutral floor, maitsesobivus, never worth judgement); exact bands calibrate against the first real pull | kaalu loomekvartali-eelistust ostjaprofiilis + jalutuskäik Telliskivi / Paavli / Noblessneri kandis; scored cousins: REL2021 dims_p4_rel2021 (dim_herd_occupation_rel) + OSM dims_p4_osm (dim_herd) + EHIS dims_p4_ehis (dim_artschool_density) + tehingud dims_p4_maa_tehingud (dim_herd_gentrification_front); agreeing NULL: arireg dims_p4_arireg (dim_herd_arireg) |

Every scored-future reason must trace to a joined per-linnaosa
loome record; a single hand-read policy page must never score a
listing.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: #322 states the remaining
   0 params using this source need only a follow-up created after
   this demo — with a dated-negative demo there is no ingestion to
   extend, so one dim in one module is the whole honest scope
   (recre #312 carried two dims because its source family holds two
   distinct artifacts with different buyer checks; the loome source
   is one table).
2. Same-param split with five siblings (P4-024 pria/kaur/eelis/
   tervise/komun precedent): rel2021 owns the occupation-grid leg,
   osm the culture-density leg, ehis the art-school leg (#347),
   maa_tehingud the gentrification-front leg, arireg the
   employer-address NULL leg; loome owns only the city-stats-table
   leg (this issue). Different source artifacts, distinct dim keys,
   no double-scoring — each module names the others.
3. No shared-file edits (dims_p4_ehis.py, livability.py, WEIGHTS,
   layers, parameters4.md untouched): 3 new files only. Central
   hook (enrich join + WEIGHTS rebalance) stays one joint change
   across all batches.

## Reopening checklist (when a pollable feed appears)

1. Re-run the six probes above yearly (or sooner if the city
   publishes a machine-readable per-linnaosa loome table); paste
   fresh evidence.
2. If a server-rendered CSV/GeoJSON/WFS per-linnaosa loome table
   appears: build the polite cached ingestion (TTL from the
   publisher's stated cadence) and graduate the dim to the honest
   shape above — fixtures first, bands calibrated from a real
   Tallinn pull under the ehis taste-match contract.
3. If loome stats stay human-pages-only: keep the NULL —
   policy-page scraping stays out of the repo.
