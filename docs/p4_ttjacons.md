# P4 TTJA consumer-complaints verdict note — seller track record (P4-021 slice)

> Dated-negative verdict for issue #295 (demo, single-param).
> Checked 2026-09-13. The one param is a documented register-only NULL
> dim (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_ttjacons.py`, pinned by
> `services/scoring/tests/test_dims_p4_ttjacons.py`.

## Verdict

**No open feed — the single dim stays NULL with an Estonian
reason.** TTJA consumer-complaint decisions on sellers
(developers/brokers) live in the interactive JVIS
otsusteregister, and the must-nimekiri blacklist is a name-only
HTML table with no export. There is no public per-entity feed
to poll politely, so there is no ingestion to cache, no TTL to
state beyond this one-off check, and no honest per-entity band
to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

6 tiny requests total (single GETs, labelled one-off user-agent
`home-finder openness-check (one-off, no scrape)`, paced ≥ 3 s,
headers + visible-text keyword scope read only, no form
submissions, no XHR probing). Raw bodies:
`/tmp/hf-ttjacons/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://ttja.ee/` → 200, 177990 B, "Eraklient \| TTJA" | Visible text: must nimekiri 3x, kaebus 1x; avaandmed / open data / masinloetav / X-tee / X-Road / andmestik / arendaja / developer / api all 0 | Agency portal, not a data portal: no open-data page, no developer portal, no X-tee service advertised |
| `https://ttja.ee/komisjoni-otsused` ("Komisjoni otsused") → 200, 187004 B | Info page pointing decisions at JVIS; avaandmed / masinloetav / X-tee / andmestik all 0 | Human-facing guidance, no machine feed advertised |
| `https://jvis.ttja.ee/.../tarbijavaidluskomisjoni-otsused/avalik` → 200, 18122 B, "Tarbijavaidluste komisjoni otsuste register \| JVIS" | 18 KB Axios/WeBase JS app shell with a search form (1 form, 3 server-rendered rows); decisions load through app-internal requests | Decisions are interactive-register-only; driving app internals would be scraping (refused, X-GIS precedent #266) |
| `https://jvis.ttja.ee/.../tarbijavaidluskomisjoni-otsused/mustnimekiri` → 200, 193078 B, "Mustas nimekirjas olevad ettevõtted \| JVIS" | Server-rendered HTML table, 144 company rows (Kaupleja = name only, no registry code; Otsuse nr; Nimekirjas alates date); real-estate filters "Kinnisasi - ostmine" and "Kinnisasi - remont/ehitus" exist; no csv / xlsx / json / api / avaandmed export | Listed max 12 months until the trader complies; polling it means scraping HTML tables, and a name-only join without registry codes is fuzzy matching, not a per-entity join |
| `https://andmed.eesti.ee/dataset?q=ttja` → 200 JS "Teabevärav" shell | Zero server-rendered tarbijakaitse / kaebus / komisjon hits | No trivially pollable national-portal dataset |

Judgment call: the check stopped at storefront/app-shell level on
purpose — no endpoint enumeration, no JVIS search-form
submission, no XHR probing, no HTML-table scraping. Deeper
probing is exactly the scraping this repo refuses (AGENTS.md §5).

## Sibling slices (owned elsewhere, untouched)

- **P4-021 EHR ehitaja-history slice:** its own demo, not this source.
- **P4-021 own cross-portal broker-stats slice:** its own demo, not this source.
- **P4-021 e-Äriregister company-facts slice:** its own demo, not this source.
- **P4-021 Ametlikud Teadaanded developer-notice slice:**
  `dims_p4_ata.dim_developer_track` (#254/#335).
- **P4-021 Maa-amet tehingud resale-performance slice:** its own demo, not this source.

This source feeds only P4-021, so there is no follow-up coverage
issue (single-param, like #262).

## What stays open (overturn path, not wired here)

TTJA (or JVIS / andmed.eesti.ee) publishes a machine
per-entity complaint feed — ideally with registry codes — →
re-open #295, build the polite cached ingestion (quarterly TTL
per parameters4.md P4-021), and graduate
`seller_complaint_record` to a per-entity join. Until then
the buyer-side check is: manual JVIS must-nimekiri +
otsusteregister lookup by company name.
