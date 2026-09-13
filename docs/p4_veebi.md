# P4 veebi: Tallinna veebikaart + lighting verdict note (issues #304 + #373)

Demo (#304) implements the Tallinna veebikaart + lighting source
openness check + P4-035 end-to-end; coverage (#373) wires P4-029 +
P4-032 + P4-040 off the same verdict. One PR closes both because the
#373 body states it extends the demoed ingestion with "no new
plumbing expected" — and with a dated-negative verdict there is no
pipeline to extend, so all four dims land in one verdict module
(komun #290+#363, green #300+#369 precedent).

## Openness verdict: dated negative (2026-09-13, 6 polite requests, labelled UA)

Raw bodies: `/tmp/hf-veebi-probe/` (one-off PR record, not committed).
Single GETs, 25 s timeout, no retries, 3 s pacing; headers +
visible-text keyword scope only.

| URL | Result | Verdict |
|---|---|---|
| `https://kaart.tallinn.ee/` → 301 → `https://gis.tallinn.ee/veebikaart/` (GET 200, 5 023 B, 21 visible chars, JS app shell) | no WFS/WMS/GeoJSON/CSV endpoint at page level | DATED NEGATIVE for bulk layers (no service enumeration — refused) |
| `https://gis.tallinn.ee/` (GET 200, 703 B, IIS default page) | viewer entry only | DATED NEGATIVE for bulk polygons (same shell as green #300) |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=valgustus` (GET 200, ~147 KB, ~10.3k visible chars) | 4x valgustus = one human news page (Hirvepargi valgustuslahenduse eskiisprojekt); 0x csv/geojson/wfs/wms/masinloetav/andmestik/lamp | DATED NEGATIVE for the lamp inventory |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=veebikaart` (GET 200, ~145 KB, ~9.6k visible chars) | 8x veebikaart = human service pages (kaart + aerofoto + aadressiotsing + infokihid + reisiplaneerija in-app; Nõmme leisure map); 0x csv/geojson/wfs/wms/masinloetav/andmestik | DATED NEGATIVE for layer feeds |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=valgustatud%20teede` (GET 200, ~147 KB, ~9.8k visible chars) | 0x valgustatud/lamp/csv/geojson/wfs/wms | DATED NEGATIVE for the lit-street layer as a feed |
| `https://andmed.eesti.ee/dataset?q=valgustus` (GET 200, ~76 KB, 12 visible chars) | "Teabevärav" JS shell | DATED NEGATIVE (same shell as #264/#277/#284/#290/#300) |

Pull contract: nothing pollable, so no `fetch_*` helper (a fetcher
around human project pages would be brittle scraping dressed as
ingestion). TTL = one-off check; re-probe politely if the city
publishes a machine-readable inventory.

## Honest shapes per param (per-listing dim; NULL stays NULL)

| Param | Dim key | Scored shape | NULL when |
|---|---|---|---|
| P4-035 darkness, veebi legs (demo) | `december_darkness` | per-listing dim (lamp inventory/kaart × VIIRS × sun hours) | always (no inventory/kaart feed, no VIIRS input) |
| P4-029 ortho-history leg | `street_ortho_history` | per-listing dim with photo date (veebikaart orthophoto vintages per street) | always (history lives as in-app layer only) |
| P4-032 lit-street leg | `lit_street_usage` | hex usage hinnang, labelled usage-not-safety | always (layer name has no pollable page) |
| P4-040 arrival-lighting leg | `arrival_lighting` | per-listing dim with photo date (lit streets + lit windows, November 23:00) | always (no light layer, no window-density proxy) |

Every NULL reason says `hinnang` + `EI OLE` with the concrete buyer
check (detsembri 15:30 jalutuskäik, tänava-ülevaatus foto
kuupäevaga, õhtune 20–22 kasutusjalutus, novembri 23:00
saabumiskäik).

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #373 defines coverage as extending the
   demo ingestion — with a dated-negative verdict there is no
   pipeline, so one verdict module holds all four dims.
2. P4-035 is one dim (both veebi legs share one per-listing shape
   and one buyer check); P4-029/P4-032/P4-040 get one veebi leg each.
3. Slice boundary (no double-scoring): EHR owns the
   orientation/floor/window light model (capped), ilm owns the
   December sun-hours baseline (capped), lidar owns LoD2 courtyard
   shading, OSM owns the mapped lit proxy (which itself names the
   veebikaart/VIIRS gap); maa_aerial owns the Mapillary/CV street
   + enclosure/green arrival legs (one genuinely scores), OSM owns
   the sidewalk + evening-anchor + approach proxies, elron/TLT own
   the evening-ridership NULLs. This module owns ONLY the four
   veebikaart/lighting legs above, under distinct dim keys.
4. P4-032 keeps usage-not-safety, P4-040 keeps arrival-feel ≠ safety
   (PPA/Päästeamet explicitly NOT sources per parameters4.md).
5. No shared-file edits (WEIGHTS/Overpass rebalance stays one joint
   change); 3 new files only.

## Refresh checklist (city publishes a machine-readable feed)

1. Re-run the 6 polite probes above; confirm HTTP 200 + feed keywords.
2. Add a `fetch_veebi` pull + reviewed snapshot table in a new PR
   (human-reviewed facts, never a JS-app traffic scrape).
3. Score the four dims off the snapshot; keep NULL-with-reason for
   missing joins (unlit street != dark flat without the EHR leg).
