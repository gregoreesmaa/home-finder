# P4 civic verdict note — civic participation signals without a precinct join (P4-039)

> Mixed verdict for issue #320 (single-param demo, no
> coverage issue — the issue states 0 remaining params use this
> source, so no follow-up coverage issue exists).
> Checked 2026-09-13. Static election-result numbers verified
> (CC BY 4.0 XML ZIPs, ringkond granularity, no jaoskond rows,
> no boundary feed), kaasav eelarve + Teeme Ära human-pages
> only — all three slices are documented no-map NULL dims (OTA
> PR #131 precedent); the scorers live in
> `services/scoring/dims_p4_civic.py`, pinned by
> `services/scoring/tests/test_dims_p4_civic.py`.

## Verdict

**No honest precinct/hex choropleth exists — all three dims stay
NULL with an Estonian reason.** The Valimiskomisjon publishes
machine-readable result numbers, but one granularity level too
coarse (8 valimisringkonda R1–R8, no jaoskond rows — verified in
the KOV2021 Tallinn file) and with no precinct-boundary feed to
join them to a listing (0 boundary/geo hits at landing/open-data
level; jaoskond mentions are voting-procedure nav prose).
Painting a per-listing turnout gradient from a stale (2021)
coarse snapshot without boundaries would be hand-mapped fake
precision — and a linnaosa-turnout gradient risks exactly the
ethnic/wealth proxy P4-039 forbids. Kaasav eelarve lives as
human vote pages (2026 vote 8.–28. September), Teeme Ära as a
campaign front page (signup CTA) — neither publishes a
participation table. There is therefore no polite living feed to
cache and no TTL beyond the one-off check below (re-probe per
election cycle / yearly, or sooner if a jaoskond-boundary feed
appears); the one licensed static ZIP stays `/tmp` PR-record
evidence, never committed, never parsed at runtime.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

10 served requests total (nine single GETs + one licensed
static-file download, labelled one-off user-agent `home-finder
openness probe #320 (one-off, single GETs; contact via GitHub
home-finder)`, 25 s timeout, no retries, 2 s pacing; the
avaandmed page is one follow of the site's own advertised
open-data nav pointer, not enumeration; headers + visible-text
keyword scope read only; no form driving, no archive-UI driving,
no JS-app driving, no registration scraping). Raw bodies:
`/tmp/hf-civic-probe/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://valimised.ee/` → HTTP 301 (162 B) to `https://www.valimised.ee/` | Canonical redirect, documented once | Working host confirmed on the www domain |
| `https://www.valimised.ee/` → HTTP 200, 79381 bytes, ~4.8k visible chars, title "\| Valimised Eestis" | Result-archive nav per election (RKV/KOVV/EP/VPV/RH/RKJV üldstatistika), "Statistika ja analüüs" + "Valimiste avaandmed" nav; 1x "api" is a substring artifact inside "etapid", 8x "statistika" is archive nav | Human election site with an advertised open-data page (followed once, next row) — no feed at landing level |
| `https://www.valimised.ee/et/valimiste-arhiiv/valimiste-avaandmed` → HTTP 200, 88695 bytes, ~5.7k visible chars, title "Valimiste avaandmed \| Valimised Eestis" | "Avaandmed on tervikuna allalaaditavad masinloetavas XML-formaadis, tasuta … (CC BY 4.0) … pärast valimistulemuste väljakuulutamist … ei uuene reaalajas." 7 static per-election ZIPs (KOV2013–2021, RK2015/2019, EP2014/2019; newer data behind the unfollowed "alates 2023" hub). 0x geomeetria/wfs/geojson/shp/gml/koordinaat; "piir" 1x = "ligipääsupiiranguteta", "kaart" 2x = "Sisukaart", "jaoskonna" 4x = voting-procedure nav | POSITIVE-PARTIAL: licensed static numbers exist; NEGATIVE for the precinct join: no boundary feed advertised |
| `…/2022-02/KOV2021_election_result_data.zip` → HTTP 200, 2814943 bytes (one licensed CC-BY download) | Per-municipality DETAILED_RESULT XMLs (Tallinn = PARISH_0784, ~4.0 MB, generated 2021-10-22) + PARTICIPATION_INFO + EHAK classifier + Estonian usage PDF. Tallinn participation rows: EIGHT valimisringkond rows (R1–R8, districtNumber 1–8) — no jaoskond rows; PARTICIPATION_INFO is county-level (Harju maakond) time series | Numbers verified one level coarser than the param's honest shape — kept as `/tmp` evidence, not ingested (nothing to join them with) |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=valimisaktiivsus` → HTTP 200, 136412 bytes, server-rendered, ~8.6k visible chars | 3x "valimisaktiivsus" = youth-turnout grant-call news (ministry fund, not a table); 2x "avaandmed" + 4x "statistika" = footer/nav chrome | No turnout table at city-search level |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=kaasav%20eelarve` → HTTP 200, 146259 bytes, server-rendered, ~9.7k visible chars | 13x "kaasav" = human service/vote content ("Kaasav eelarve 2026", "Koos loodud linn 2026" vote 8.–28. September 2026) + nav; 0x csv/geojson/wfs/masinloetav/andmestik | Vote pages, not a participation table per linnaosa |
| `https://www.teemeara.ee/` → HTTP 200, 42430 bytes, ~2.7k visible chars, title "Esileht – Teeme Ära" | "talgupäev" 8x = event news + "PANE TALGUD KIRJA" signup CTA; 0x feed keywords | Campaign front page, not a participation register per asum |
| `https://andmed.eesti.ee/dataset?q=<valimised / kaasav eelarve / teeme ära>` → HTTP 200 each, ~75 KB, 10 visible chars, title "Teabevärav" | JS app shell, zero keyword hits on all three queries | No trivially pollable national-portal civic dataset (same shell as #264/#277/#284/#290/#299) |

Judgment call: the check stopped at landing/search/shell + one
advertised open-data page + one licensed static file on purpose
— no per-election archive-UI driving, no per-jaoskond result
scraping, no Teabevärav JS-app driving, no
talgute-registration scraping (AGENTS.md §5; tervise #289
precedent). Driving result UIs precinct-by-precinct would be
scraping human publications, not polling a feed.

## Honest shapes (NULL until a precinct join appears)

| Param | Dim key | Honest shape when feeds land | Buyer-side check meanwhile |
|---|---|---|---|
| P4-039 civic capital, turnout slice (demo) | `civic_turnout` | precinct/hex turnout choropleth off jaoskond-level numbers + jaoskond-boundary feed (taste-match only, never ethnic/wealth proxy; ringkond-level statics alone never score a listing) | valimiste avaandmete leht + ühisvara kohapealne jalutuskäik; agreeing NULLs: dims_p4_osm (dim_civic) + dims_p4_arireg (dim_commons_echo) + dims_p4_libs (dim_civic_use_visits) |
| P4-039 civic capital, participatory-budget slice (demo) | `civic_participatory_budget` | per-linnaosa participation-table join off a pollable kaasava eelarve feed | osale hääletusel (Kaasav eelarve 2026, 8.–28. September 2026) + küsi linnaosakogult osalusarve; agreeing NULLs: dims_p4_osm + dims_p4_libs |
| P4-039 civic capital, cleanup-campaign slice (demo) | `civic_cleanup_action` | per-asum participation-register join off a pollable Teeme Ära feed | pane talgud kirja (PANE TALGUD KIRJA) + küsi asumiseltsilt osalust; agreeing NULLs: dims_p4_osm + dims_p4_libs |

Every scored-future reason must trace to a joined
precinct/participation record; a single hand-read results page
must never score a listing, and no linnaosa-turnout gradient may
stand in for taste (proxy guard).

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: #320 states the
   remaining 0 params using this source need only a follow-up
   created after this demo — with no ingestion pipeline (no
   pollable living feed) there is nothing to split out, so
   three dims in one module are the whole honest scope.
2. The verified static XML ZIPs are deliberately NOT ingested:
   ringkond-only granularity (R1–R8, no jaoskond rows),
   vintages topping out at 2021 on the static page (newer data
   behind the unfollowed post-2023 hub + archive UIs), no
   precinct-boundary feed — plus the proxy guard. Pulling
   numbers we cannot honestly join would be fake precision
   (OTA PR #131 precedent).
3. Same-param split with dims_p4_osm / dims_p4_arireg /
   dims_p4_libs (P4-024 pria/kaur/eelis/tervise/komun
   precedent): osm owns the freshness NULL (dim_civic), arireg
   owns the fond-echo NULL (dim_commons_echo), libs owns the
   visits NULL (dim_civic_use_visits); civic owns the turnout +
   budget + cleanup legs off this issue's DATA SOURCES.
   Different artifacts, distinct dim keys, no double-scoring —
   each module names the others.
4. No shared-file edits (livability.py, WEIGHTS, layers,
   layers.md, parameters4.md untouched): 3 new files only.
   Central hook (enrich join + WEIGHTS rebalance) stays one
   joint change across all batches.

## Reopening checklist (when a precinct join appears)

1. Re-run the ten probes above per election cycle (KOV/RK/EP;
   kaasav eelarve + talgupäev yearly) or sooner if the
   Valimiskomisjon publishes a jaoskond-boundary feed; paste
   fresh evidence.
2. If jaoskond-level numbers + precinct boundaries both appear:
   build the polite cached ingestion (static per-vintage TTL —
   "ei uuene reaalajas", re-pull only on newly proclaimed
   results) and graduate `civic_turnout` to the precinct/hex
   join — fixtures first, taste-match guard kept, proxy check
   reviewed.
3. If participation tables appear (kaasav eelarve / Teeme Ära
   per-linnaosa/asum feeds): graduate the matching dim the
   same way. Until then the NULLs stand — human-page scraping
   stays out of the repo.
