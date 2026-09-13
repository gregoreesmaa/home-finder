# P4 haridus verdict note — Tallinna Haridusamet feed (P4-011 + 2 slices)

> Dated-negative verdict for issues #270 (demo) and #346 (coverage).
> Checked 2026-09-13. All three params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_haridus.py`, pinned by
> `services/scoring/tests/test_dims_p4_haridus.py`.

## Verdict

**No open feed — all three dims stay NULL with Estonian reasons.**
Kindergarten queue stats per linnaosa/asum, school open/close plans,
catchment changes per asum, and GP nimistu open/closed per linnaosa
live in CMS content pages, a JS app shell, a per-institution
directory, or an authenticated register. There is no public bulk
feed to poll politely, so there is no ingestion to cache, no TTL to
state beyond this one-off check, and no honest per-linnaosa band to
paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

13 tiny requests total (HEADs + single GETs, labelled one-off
user-agent `home-finder openness-check (one-off, no scrape)`,
headers + visible-text keyword scope read only). Raw bodies:
`/tmp/hf-haridus-open/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.tallinn.ee/et/haridus` → 200 CMS page (95 223 B) | haridusamet 6x, lasteaia 8x as content nav; avaandmed / andmestik / csv / json / api / x-tee all 0 | Content portal, not a data feed |
| Queue application page (`/et/haridus/lasteaiakoha-taotlemine`, linked from landing) | Per-child e-service page | Queue is a per-child transaction, never a per-linnaosa stats table |
| `https://haridussilm.ee/` → 200, 41 chars server-rendered ("Haridusandmete portaal") | JS app shell, no server-rendered stats | No bulk endpoint advertised at storefront level |
| `https://andmed.eesti.ee/dataset?q=haridusamet` → 200 JS "Teabevärav" shell (12 chars visible) | No server-rendered results | No trivially pollable national-portal dataset (same finding as #400) |
| `https://teatmik.haridus.ee/lasteaiad/` → 200 (HTM directory, linked from tallinn.ee) | Per-institution directory | Institution list ≠ queue-stats table; joining it needs per-page scraping, which the repo refuses |
| Tervisekassa GP-list directory path (guessed) → 404 "Lehekülge ei leitud" | No bulk per-linnaosa open/closed table found | Check stops here — no URL-guess enumeration |
| `https://enda.ehis.ee/` → 200 | Authenticated EHIS register | No anonymous bulk pull; no auth attempted |

Judgment call: the check stopped at storefront/directory level on
purpose — no e-service session flows, no directory scraping, no
account creation, no app-shell internals. Deeper probing is exactly
the scraping this repo refuses (AGENTS.md §5).

## What stays open (overturn paths, not wired here)

- **P4-011 queue half:** a Haridusamet per-linnaosa queue-stats
  table (or a machine endpoint behind the taotlemine e-service)
  would graduate `kindergarten_queue_gp` to a per-linnaosa join.
  The HTM teatmik directory alone never qualifies — institutions
  are not queues.
- **P4-011 GP half:** a Tervisekassa bulk open/closed table per
  linnaosa would graduate the same dim's second leg. The
  per-GP searchable directory never qualifies without scraping.
- **P4-025 liquidity cousins:** REL2021 age/migration/vacancy
  grids, KV DOM medians, and tehingute arv stay the buyer-side
  checks; each graduates under its own demo (Statamet,
  own-store, Maa-amet tehingud), not here.
- **P4-052 turnover cousins:** Maa-amet tehingute käive per
  building and KÜ remondifondi dünaamika stay the buyer-side
  checks; the catchment reading graduates only if Haridusamet
  publishes machine-readable teeninduspiirkondade changes.
- **Full overturn:** Haridusamet (or andmed.eesti.ee) publishes a
  machine feed for any slice → re-open #270, build the polite
  cached ingestion (quarterly TTL per parameters4.md P4-011),
  and graduate that dim to a per-linnaosa join.

## Why demo + coverage share one PR

The coverage body (#346) states it extends the demo ingestion
(#270). With the demo verdict dated-negative there is no
ingestion to extend, so the two coverage slices (P4-025 school
plans, P4-052 catchment changes — parameters4.md sources (5) in
both name the Haridusamet feed P4-011 demos) land in the same
verdict module instead of a second file importing a pipeline that
does not exist. One module, one test file, one verdict note — no
edits to shared files.
